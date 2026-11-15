---
title: Plan — Account-Password-Derived Survey Unlocking
category: development
priority: 5
status: proposal
---

# Plan: Account-Password-Derived Survey Unlocking

**Status:** Proposal — awaiting sign-off. This document analyses replacing the
publish-time passphrase (with BIP39 recovery-phrase backup) for password-account
users with a key derived from their existing account credentials, while keeping
the current workflow available as a fallback.

## 1. Summary and Recommendation

**Feasible: yes**, with one honest caveat that must be accepted up front.

The proposal is essentially "extend the OIDC auto-unlock pattern (already in
production) to password-account users". The OIDC path already derives a wrapping
key from a stable identity and auto-unlocks surveys at login; this plan mirrors
that for password users using `password + per-user salt + platform pepper`.

The caveat: **a key derived from the account password can never be robust to a
"forgot password" reset on its own.** If the user resets via an email link, the
old password is gone and nothing derived from it can unwrap the key. Robustness
to reset therefore requires *some* recovery path — either a one-time recovery
phrase entry after reset (preserves zero-knowledge) or a platform-side escrow
(trust downgrade). Section 5 sets out the options; the recommendation is a
hybrid that keeps zero-knowledge by default and reuses the existing
`RecoveryRequest` platform-recovery workflow as the last resort.

**Recommendation:** proceed with the Account Key design in Section 4, with
Option C (recovery-phrase-at-reset) as the default reset path and Option B
(auto-recovery key in Vault) as an opt-in, clearly-documented self-host choice.

## 2. Current State (verified against code)

- Every survey has an X25519 submission keypair; responses are encrypted with
  the public key at submission. The private key is wrapped in up to four ways:
  - `encrypted_kek_password` — scrypt-derived from a **publish-time passphrase**
    (min 12 chars, chosen in `survey_encryption_setup`, independent of the
    account password)
  - `encrypted_kek_recovery` — BIP39 12-word phrase, shown once
  - `encrypted_kek_oidc` — derived from `provider:subject` + per-user salt
    (`derive_key_from_oidc_identity` in `surveys/utils.py`, `core/auth.py`)
  - `encrypted_kek_org` — organisation master key
- Unlock (`survey_unlock`) supports passphrase, recovery phrase, OIDC
  auto-unlock, and a legacy raw-key path. Session storage uses the
  forward-secrecy pattern (`encrypt_sensitive` under the session key, 30-minute
  timeout, re-derivation per request).
- Platform escrow already exists: `UserSurveyKEKEscrow` (per user+survey, in
  Vault) under the platform master key (`PlatformKeyVersion` vault component XOR
  custodian component), unlocked via `RecoveryRequest` (dual admin approval +
  time delay + audit trail).
- Password lifecycle uses stock `django.contrib.auth` views:
  - `accounts/password_change/` → `_PasswordChangeWithKeyRevocation` (revokes
    API keys; the **old password is available in the form**)
  - `accounts/password_reset/` → `BrandedPasswordResetView` (email flow; the
    **old password is NOT available**)
- Auth backends: `CustomOIDCAuthenticationBackend`, `ModelBackend`,
  `axes.backends.AxesStandaloneBackend`. The plaintext password is available at
  login inside `ModelBackend.authenticate()` and at signup in `core/views.signup`.
- Password policy: `MinimumLengthValidator` (12) + `CommonPasswordValidator` +
  similarity checks. Axes lockout (5 attempts / 1 hour) protects login.
- AuditLog already has `PASSWORD_CHANGED`, `PASSWORD_RESET`, `EMAIL_CHANGED`,
  `KEY_RECOVERY` actions.

**Scope note:** this concerns the *survey owner* (publisher) unlocking
responses. Respondents — including on public surveys — never provide key
material; that property is unchanged.

## 3. Goals and Non-Goals

**Goals**

1. Password-account users no longer choose/remember a separate passphrase to
   unlock survey responses.
2. Unlocking works automatically when signed in (parity with OIDC users).
3. Survives password *change* without data loss and without support involvement.
4. Survives password *reset* (forgot password) via a defined, auditable path.
5. Existing passphrase/recovery-phrase/OIDC/org wrapping continues to work
   (backward compatible, per-survey and per-user legacy support).

**Non-Goals**

- Changing the submission encryption (X25519 + AES-256-GCM payload) — untouched.
- Changing respondent-facing flows — untouched.
- Removing the passphrase workflow — retained as an opt-in backup and for
  legacy surveys.

## 4. Proposed Design: Account Key (AK)

### 4.1 Key hierarchy

```
Account password (user knows)
        │
        ▼  scrypt(n=2^15, r=8, p=1)          ← raised from 2^14
password wrap key = scrypt(password,
                    per-user salt (32B, random),
                    platform pepper (Vault-held, versioned))
        │
        ▼  AES-256-GCM wrap
Wrapped Account Key (AK)  ── stored on UserProfile (DB)
        │                      + escrowed in Vault (Section 5)
        ▼  AK is a random 32-byte key, generated once per user
        │
        ▼  AES-256-GCM wrap (per survey)
Survey.encrypted_kek_account  ── wraps the survey private key / KEK
        │
        ▼
Responses decrypt as today (unlock → private key → load_complete_response)
```

### 4.2 KDF inputs — what to use and what to avoid

- **Password:** captured at login / signup / password change (see 4.4). Never
  logged, never persisted (project logging rules apply).
- **Per-user salt:** random 32 bytes on `UserProfile`, generated once. Prevents
  cross-user precomputation.
- **Platform pepper ("platform salt"):** a server-side secret held in Vault
  (or env for self-hosters without Vault), versioned like `PlatformKeyVersion`
  so it can rotate. Protects against a DB-only breach: an attacker with the
  database but not Vault cannot even attempt offline guessing of the wrapped AK.
  Do **not** use a static global salt committed to config — that adds nothing.
- **Email: do not include it in the KDF.** Three reasons:
  1. It is public/guessable — it adds no entropy against an offline attacker.
  2. It is mutable (`EMAIL_CHANGED` audit action exists); binding keys to email
     turns every email change into a re-keying migration hazard.
  3. Identity binding adds nothing server-side: the server already knows who
     the user is when it derives the key. If identity binding is wanted for
     audit clarity, use the immutable user UUID as *associated data* (AAD) in
     the AES-GCM wrap instead of KDF input — it binds the blob to the account
     without creating a migration hazard.

### 4.3 New model fields

```python
# UserProfile (core)
account_key_salt = models.BinaryField(null=True)          # 32B random
wrapped_account_key = models.BinaryField(null=True)       # salt|nonce|ct (AES-GCM under password wrap key)
account_key_wrap_version = models.CharField()             # pepper version + KDF params id, e.g. "v1-scrypt-2^15"
account_key_created_at = models.DateTimeField(null=True)

# Survey (surveys)
encrypted_kek_account = models.BinaryField(null=True)     # survey private key / KEK wrapped under AK
```

A distinct `encrypted_kek_account` field (rather than overloading
`encrypted_kek_password`) avoids ambiguity between "wrapped with the legacy
publish-time passphrase" and "wrapped with the account password" — legacy rows
must keep unlocking with their original passphrase.

### 4.4 Capturing the password and unlocking

- **Login:** add `KeyDerivingModelBackend(ModelBackend)` ahead of `ModelBackend`
  in `AUTHENTICATION_BACKENDS`. Its `authenticate()` calls `super()`, and on
  success derives the password wrap key, unwraps the AK (or creates one on
  first login), and stores the AK in the session using the existing
  forward-secrecy pattern:

  ```python
  encrypted = encrypt_sensitive(session_key.encode(), {"account_key": base64_ak})
  request.session["unlock_credentials"] = base64.b64encode(encrypted).decode()
  request.session["unlock_method"] = "account"
  request.session["unlock_verified_at"] = ...
  ```

  The 30-minute timeout and per-request re-read in
  `get_survey_key_from_session` gain an `"account"` branch that returns
  `_submission_key_for_survey(survey, unwrap_account_wrapped_key(survey, ak))`.
  Note: with an AK, the *AK* (not the password) is what the session holds, so
  per-request scrypt re-derivation is no longer needed — a small performance win.

- **Signup (`core.views.signup`):** after `form.save()`, generate the AK and
  wrap it with the signup password before `login()`.
- **Unlock UX:** surveys with `encrypted_kek_account` and an AK in the session
  auto-unlock (mirroring `can_user_unlock_automatically` for OIDC). The unlock
  page keeps passphrase / recovery-phrase options for legacy wraps and as
  explicit-intent fallback.
- **Never log the password or the AK.** Audit only events
  (`account_key_created`, `account_unlock`, method metadata).

### 4.5 Publish flow change

In `survey_encryption_setup`, for password users (non-SSO, non-org or org
without master key), the default path becomes:

1. `setup_submission_keypair()` as today.
2. Wrap the private key under the session AK → `encrypted_kek_account`.
3. Still generate and wrap a BIP39 recovery phrase → `encrypted_kek_recovery`
   (retained: it is the reset path in Section 5 and the last-resort backup).
4. **No passphrase prompt.** The passphrase branch remains available as an
   explicit opt-in ("add an extra passphrase") for users who want a second
   independent secret, and remains mandatory for legacy rows.

`has_any_encryption()` must include `encrypted_kek_account` so the setup
redirect logic treats account-wrapped surveys as encrypted.

## 5. Password Lifecycle — the crux

### 5.1 Password change (old password known) — straightforward

`_PasswordChangeWithKeyRevocation.form_valid` already receives the old
password via `PasswordChangeForm`. Extend it:

1. Derive old wrap key from old password → unwrap AK.
2. Derive new wrap key from new password → re-wrap AK → save
   `wrapped_account_key` (and bump `account_key_wrap_version` if the pepper
   version changed).
3. Survey rows are untouched — only the AK wrapping changes. This is the key
   usability win over the current passphrase scheme, where a password change
   has no effect and the passphrase must be remembered forever.
4. Audit `PASSWORD_CHANGED` (existing) + `account_key_rewrapped`.

Failure mode: if unwrapping fails (e.g. AK created before this feature),
fall back to prompting for the recovery phrase once to re-establish the AK.

### 5.2 Password reset (old password forgotten) — requires a decision

Nothing derived from the *new* password can open the old wrap. Options:

**Option A — Recovery phrase at reset (recommended default, zero-knowledge)**
After the email-verified reset completes, the next login detects
`wrapped_account_key` cannot be unwrapped and shows a one-time
"re-establish your encryption key" step: the user enters their recovery
phrase (or a legacy passphrase for old surveys) once; the AK is unwrapped
via `encrypted_kek_recovery` and re-wrapped under the new password.
- ✅ Zero-knowledge preserved; no new platform trust.
- ✅ Reuses existing wrap fields and unlock logic.
- ⚠️ Friction only on reset — the user still needs the recovery phrase they
  were shown at first publish. If they lost *both* password and phrase, the
  existing `RecoveryRequest` workflow (dual approval + custodian unseal)
  is the last resort — already built.

**Option B — Auto-recovery key in Vault (opt-in, trust downgrade)**
Escrow the AK in Vault encrypted under a dedicated *auto-recovery* key that
does **not** require the custodian component. The reset flow recovers the AK
server-side and re-wraps it under the new password automatically.
- ✅ Fully self-service reset, zero friction.
- ⚠️ The platform can silently decrypt account keys (and thus responses).
  This materially changes the security story for a medical platform and must
  be documented in `docs/data-governance.md` and the privacy notice.
- Implementation: env-gated (`ENCRYPTION_AUTO_RECOVERY=1`), separate Vault
  path namespace, AuditLog `KEY_RECOVERY` on every automated use, and a
  per-user counter surfaced on the profile page.

**Option C — Custodian-gated automated recovery (strictest)**
Escrow the AK under the existing platform master key (vault XOR custodian).
Reset generates a `RecoveryRequest`-style flow; admins unseal with custodian
shares; AK is re-wrapped.
- ✅ Same trust level as today's emergency recovery.
- ⚠️ Not self-service; hours of delay. Poor UX for a forgotten password.

**Recommendation:** Option A as the default; Option B available behind an
explicit flag for self-hosters who prefer convenience; Option C is what
already exists for catastrophic loss. If product decides reset friction is
unacceptable for the target audience, revisit Option B with DPO sign-off.

### 5.3 Email change

No cryptographic impact (email is not in the KDF). Audit only.

### 5.4 Account deletion / `hard_delete`

`Survey.hard_delete` already overwrites all `encrypted_kek_*` fields; add
`encrypted_kek_account` to the overwrite list and to `update_fields`. Also
clear `wrapped_account_key`/`account_key_salt` on the profile and delete any
Vault escrow rows for the user.

## 6. Security Tradeoffs vs the Current Passphrase Model

Be explicit with stakeholders: this is a UX-for-security trade, the same one
already accepted for OIDC auto-unlock.

| Threat | Today (passphrase) | Proposed (account password) | Mitigation |
|---|---|---|---|
| DB breach + offline crack of wrap blob | scrypt over passphrase | scrypt over account password + user salt + **Vault pepper** | Pepper blocks DB-only attack; password policy (min 12, common-password list) already enforced; consider raising scrypt to 2^15 |
| Phished / stolen password | Passphrase is a second secret; data stays safe | Stolen password = data access on next login | 2FA at login (if enabled platform-wide), Axes lockout, IP rate limiting, email notification on new-device login |
| Session hijack | Passphrase re-entry after 30 min | AK in session, same 30-min window | Identical exposure to the OIDC auto-unlock path already in production |
| Malicious insider / compromised server | Server sees passphrase only transiently | Server sees password at every login and *could* derive the AK | Fundamental to any server-side password-derived scheme (and already true of OIDC auto-unlock); mitigated by audit logging, Option A reset path, and custodian-gated escrow |
| Forgotten passphrase | Data loss risk (phrase backup exists) | No passphrase to forget | Core motivation for the change |
| Forgotten password + lost phrase | RecoveryRequest workflow | Same workflow (Option A), or auto-recovery (Option B) | Unchanged / documented |

Additional hardening to include regardless of option:

- Enforce `MinimumLengthValidator` (12) and `CommonPasswordValidator` on every
  path that (re)wraps the AK — including password reset.
- Rate-limit the reset-time re-establishment step (it is effectively an
  offline-guess oracle for the recovery phrase).
- Add `unlock_method="account"` handling to `get_survey_key_from_session` with
  the same slug validation and timeout as other methods.

## 7. Implementation Plan

### Phase 0 — Decisions (blocking)

1. Confirm reset strategy: Option A default / Option B flag (Section 5.2).
2. Confirm whether the passphrase prompt is removed from the default publish
   flow or offered as an opt-in "extra passphrase" (recommended: opt-in).
3. DPO/compliance review of the trust-model table in Section 6.

### Phase 1 — Crypto primitives (`checktick_app/surveys/utils.py`)

1. `derive_password_wrap_key(password, user_salt, pepper) -> bytes` — scrypt
   (n=2^15, r=8, p=1, 32B), salt+pepper as KDF salt/pepper inputs.
2. `wrap_account_key(ak, password, user_salt, pepper) -> bytes` and
   `unwrap_account_key(blob, password, user_salt, pepper) -> bytes` —
   AES-256-GCM, blob format `salt(16)|nonce(12)|ct` mirroring
   `encrypt_kek_with_passphrase`; bind `user.id` as AAD.
3. `wrap_survey_key_with_account_key(survey_key, ak) -> bytes` /
   `unwrap_survey_key_with_account_key(blob, ak) -> bytes`.
4. Pepper accessor with versioning: read active pepper version from Vault (or
   `settings.ENCRYPTION_PEPPER` fallback), return `(version, pepper)`.
5. Unit tests: round-trip, wrong password, wrong pepper version, AAD binding,
   blob-format vectors.

### Phase 2 — Models and migration

1. Migration: `UserProfile.account_key_salt`, `wrapped_account_key`,
   `account_key_wrap_version`, `account_key_created_at`;
   `Survey.encrypted_kek_account`.
2. `UserProfile` helpers: `ensure_account_key(password) -> ak`,
   `unwrap_account_key(password) -> ak | None`,
   `rewrap_account_key(old_pw, new_pw) -> bool`.
3. `Survey.set_account_encryption(kek_or_private_key, ak)` and
   `unlock_with_account_key(ak)` mirroring `set_oidc_encryption` /
   `unlock_with_oidc`.
4. Update `has_any_encryption()`, `hard_delete()` overwrite list.
5. Migration tests incl. memoryview handling (PostgreSQL BinaryField).

### Phase 3 — Auth integration

1. `KeyDerivingModelBackend` in `checktick_app/core/auth.py`; register ahead of
   `ModelBackend` in `settings.AUTHENTICATION_BACKENDS`. Must remain
   Axes-compatible (Axes wraps authenticate separately) and must not break
   `client.login()` in tests (backend falls back cleanly when the user has no
   AK yet).
2. Signup: create + wrap AK in `core.views.signup`.
3. Session plumbing: `"account"` branch in `get_survey_key_from_session`
   (`surveys/views.py`), including `_submission_key_for_survey` dispatch for
   keypair vs legacy-KEK surveys.
4. Auto-unlock: extend `can_user_unlock_automatically` and the responses/export
   views' auto-unlock path (mirror the OIDC branch) with an AuditLog
   `KEY_ACCESS` event, `method: "account"`.

### Phase 4 — Publish flow

1. `survey_encryption_setup`: default password-user path wraps the new
   keypair under the session AK (+ recovery phrase as today); passphrase
   becomes opt-in. Keep the SSO and org branches untouched.
2. `survey_create` (builder-time creation path): same treatment.
3. Templates: `encryption_setup.html` (remove/condition passphrase fields),
   `encryption_display.html` (show recovery phrase; drop "remember this
   passphrase" copy), unlock page copy.
4. `has_any_encryption` gating so first-publish redirect is skipped when the
   survey is account-wrapped.

### Phase 5 — Password lifecycle hooks

1. `_PasswordChangeWithKeyRevocation`: rewrap AK (Section 5.1); on unwrap
   failure, redirect to a "re-establish encryption key" view.
2. New `ReestablishAccountKeyView` (Option A): post-reset, accepts recovery
   phrase or legacy passphrase, unwraps the survey key / AK, re-wraps AK under
   the new password. Rate-limited; audit-logged.
3. Password reset completion view: flag the profile
   (`account_key_needs_reestablishment = True`) so the next login routes to
   step 2 before any data access.
4. If Option B is enabled: Vault escrow of the AK at creation
   (`escrow_user_survey_kek`-style, new path namespace), automated recovery in
   the reset flow, `KEY_RECOVERY` audit on each use.

### Phase 6 — Docs, lint, rollout

1. Update `docs/encryption-technical-reference.md` (new wrap path + trust
   model), `docs/publishing-surveys.md` (publish flow), and the user-facing
   publish guide.
2. `docs/data-governance.md`: reset/recovery story.
3. `s/lint`; `s/test --no-a11y`; targeted suites:
   `checktick_app/surveys/tests/test_survey_dual_encryption.py`,
   `test_oidc_encryption.py` (regression), new
   `test_account_key_encryption.py`, `test_password_reset_flow.py` extensions.
4. Rollout: feature-flag (`ACCOUNT_KEY_UNLOCK=1`) → internal → all users.
   Legacy surveys keep passphrase/recovery unlock; no data migration needed.
   Optional progressive re-wrap: when a user unlocks a legacy survey with its
   passphrase, also add an AK-wrapped copy (`encrypted_kek_account`) so future
   unlocks are automatic.

## 8. Migration and Back-Compatibility

- No existing wrapped blobs change. `encrypted_kek_password` keeps its meaning
  (publish-time passphrase) forever.
- Unlock precedence per survey: session AK → account wrap → OIDC → passphrase →
  recovery phrase → legacy key.
- Surveys created before the feature behave exactly as today.
- The recovery phrase remains generated at first publish in all cases (it is
  the Option A reset path), so the "shown once" UX stays but the *passphrase*
  memory burden disappears.

## 9. Open Questions

1. Is 2FA available/mandatory for password accounts? With password-derived
   keys, 2FA becomes the main defence against phished passwords unlocking
   data — if it is not already enforced for owners of encrypted surveys,
   consider making it so.
2. Should org-member password users also get AK wrapping, or keep org-master-key
   wrapping only? (Recommend: AK wrapping in addition to org wrap — it is
   additive.)
3. Pepper storage for self-hosters without Vault: env var (documented) vs
   derived from `SECRET_KEY` (discouraged — rotation impossible). Recommend env
   var with a documented "not set = no pepper" degraded mode.
4. Scrypt parameter bump (2^14 → 2^15) applies to new wraps only; confirm the
   ~100ms derivation cost at login is acceptable (it replaces a per-request
   scrypt today, so net cost is likely lower).
