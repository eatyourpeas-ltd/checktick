---
title: Security Upgrade — Encrypt All Survey Responses at Rest
category: security
priority: 1
status: in-progress
---

# Security Upgrade: Encrypt All Survey Responses at Rest

> **Implementation status (2026-08-31):** Phases 1–3 and the Option B key
> architecture are implemented on branch `planning-docs`:
> model fields + Option C predicate (0054), grandfathering of pre-existing
> password-user non-patient surveys as plaintext via `legacy-1.0`
> declarations (0055), per-survey X25519 submission keypairs with
> public-key response encryption — server can encrypt, cannot decrypt —
> (0056 + crypto layer), keypair generation wired into all encryption
> setup flows, submission paths encrypting answers + demographics for
> keypair surveys, and CSV export decryption. Documentation updated.
> Still to come: publish-flow audience prompt + declaration UI,
> analytics unlock-gating, and the interactive migration command for
> legacy encrypted surveys (§4.3 phase 3).

This document is the planning record for a security posture upgrade: extending
AES-256-GCM at-rest encryption from patient-data surveys only, to **all**
survey responses on the platform.

It is the prerequisite PR for the reporting work
(`docs/reporting-planning.md`) and is intended to be merged first.

## 1. Why this change

CheckTick's stated USP is NHS-grade security for all survey data, not only
patient-identifiable data. The current implementation does not fully deliver
this:

- `Survey.requires_whole_response_encryption()` returns `True` only when
  `collects_patient_data()` is `True` — i.e. only surveys with a
  `patient_details_encrypted` question group encrypt the answer payload at
  rest.
- For all other surveys, `SurveyResponse.answers` is a plaintext `JSONField`,
  even though the survey has a KEK configured.
- `docs/security-overview.md` A02 reflects this: "AES-256-GCM encryption for
  **patient-identifiable fields**" (L90), and "Respondent answers are stored
  in a `JSONField` on `SurveyResponse`" (L191) as the general case.
- The test `test_non_patient_survey_requires_encryption` documents the
  current behaviour explicitly: *"Non-patient surveys don't use whole
  response encryption… can store answers in plaintext during testing/draft
  phase."*

All surveys **do** require encryption to be *configured* before publishing
(KEK / password / recovery set up), but configuration ≠ at-rest encryption
of answers. This is the gap the upgrade closes.

The infrastructure to do this already exists: per-survey KEKs, the
`store_answers(survey_key, answers)` / `load_answers(survey_key)` methods on
`SurveyResponse`, and the Vault integration for enterprise key escrow. The
change is to make whole-response encryption the default for **most**
surveys, with a controlled opt-out for the narrow case where it is genuinely
unnecessary (see §3).

### 1.1 The audience gap

The current `collects_patient_data()` predicate is a **schema** check: it
returns `True` only when a `patient_details_encrypted` question group is
present. It cannot detect the case where a survey is sent to patients and
contains no patient-identifier fields, but collects free-text responses
that may inadvertently contain identifiable content (e.g. a patient
feedback survey with a single "tell us about your care" question — a
patient may write "I saw Dr X on Tuesday about my diabetes").

This is the canonical NHS patient-experience survey pattern, and it is not
covered by the current encryption boundary. The upgrade closes this gap by
introducing an explicit **audience** declaration on `Survey` and basing the
encryption decision on schema **or** audience (Option C — see §3.3).

## 2. Scope

### 2.1 In scope

- New `respondent_audience` field on `Survey` (`staff` / `patient` /
  `public`), with a publish-time prompt for surveys missing it.
- Revised `Survey.requires_whole_response_encryption()` predicate (Option C,
  §3.3): returns `True` if `collects_patient_data()` OR `audience in
  {patient, public}` OR the survey is owned by an SSO user (default-on for
  SSO, §3.1).
- Creator declaration flow for password users on staff-audience surveys
  without patient identifiers (§3.2): explicit acknowledgement that the
  survey is not patient-facing and does not collect data that could
  identify respondents, in order to opt out of encryption.
- Response submission path stores answers via `store_answers(survey_key,
  answers)` for all surveys where the predicate is `True`.
- All read paths (dashboard analytics, CSV export, the new summary view,
  progress restore) call `load_answers(survey_key)` unconditionally for
  encrypted surveys.
- Migration of existing plaintext `answers` rows to `enc_answers` (see §4).
- Documentation updates (`security-overview.md`, `reporting-and-exports.md`,
  `encryption-technical-reference.md`, `encryption-for-users.md`,
  `compliance/opt-out.md`, `compliance/individual-rights-procedure.md`).
- Test updates.

### 2.2 Out of scope

- **Demographics / IMD / professional fields**: these are already encrypted
  via `enc_demographics` for surveys that collect them. No change.
- **Key management architecture**: the KEK / DEK / Vault escrow design is
  unchanged. This PR only changes *what* gets encrypted with the existing
  keys, not how keys are derived or stored.
- **Survey progress (`SurveyProgress.partial_answers`)**: partial in-progress
  answers are a separate field and a separate threat model (transient,
  user-owned, deleted on submission). Out of scope for this PR; flagged in
  §7 for future consideration.
- **Response freeze logs, audit logs**: these store metadata, not answer
  content. No change.
- **Encrypting survey builder content** (question text, options): out of
  scope; flagged in §7.

## 3. Encryption decision semantics

The encryption decision is a function of three factors: the survey owner's
authentication method, the survey's declared audience, and the survey's
schema. The rules below implement the agreed compromise.

### 3.1 Authentication method

- **SSO / OIDC users**: encryption is **default-on for all surveys**, with
  **no opt-out**. The unlock friction is absorbed by OIDC auto-unlock
  (`encrypted_kek_oidc`), so there is no UX cost to justify an opt-out.
  This applies regardless of audience or schema.
- **Username / password users**: encryption is **opt-out by default** for
  staff-audience surveys without patient identifiers, but **opt-in is
  actively encouraged** at sign-up, on creation of each new survey, and
  again at publication. For patient / public audience surveys, or surveys
  with the `patient_details_encrypted` group, encryption is **mandatory**
  with no opt-out (§3.2).

### 3.2 Creator declaration (password users, staff audience, no patient
identifiers)

For the narrow case where a password user wishes to opt out of encryption
on a staff-audience survey that does not collect patient identifiers, they
must make an **explicit declaration** at publish time acknowledging:

- the survey is not patient-facing, and
- the survey does not gather data that could identify respondents.

The declaration is **logged in the audit trail** (metadata only: survey id,
user id, timestamp, declaration version) and is **required** to complete the
opt-out. This places the controller-side determination with the survey
creator — who is the Data Controller per `docs/compliance/opt-out.md` and
`docs/compliance/individual-rights-procedure.md` — rather than with the
platform. The platform provides the technical capability; the controller
decides whether the data warrants encryption.

If the creator declares that the survey **does** gather potentially
identifying data, encryption is applied with an **explainer** of what that
entails (KEK setup, password / recovery phrase, unlock requirement for
dashboard insights and export, irrecoverability if credentials are lost).
The explainer is shown inline in the publish flow.

### 3.3 The predicate (Option C)

`Survey.requires_whole_response_encryption()` returns `True` if **any** of:

1. `collects_patient_data()` is `True` (existing schema check — surveys
   with a `patient_details_encrypted` question group), OR
2. `respondent_audience in {patient, public}` (new audience check —
   surveys sent to patients or the public, regardless of schema), OR
3. the survey owner authenticates via SSO / OIDC (default-on for SSO,
   §3.1).

It returns `False` only when **all** of:

- the owner is a password user, AND
- `respondent_audience == staff`, AND
- `collects_patient_data()` is `False`, AND
- the creator has made the explicit opt-out declaration (§3.2).

This is the **only** path to plaintext storage under the new model, and it
requires a logged, affirmative controller-side decision. The default for
password users is opt-out-by-default-with-encouragement, but the opt-out is
not silent — it is a declared, audited choice.

### 3.4 Draft surveys

Drafts may store plaintext answers during testing, regardless of the above.
This preserves the existing developer / test workflow and avoids breaking
draft-mode imports. (Drafts are not live data; the threat model is
different.) The predicate above applies once a survey has accepted a real
submission or is published, whichever is earlier.

### 3.5 Why audience, not content inference

An earlier alternative considered was to infer identifiability from question
types (treat any survey with free-text questions as potentially
identifiable). This was rejected because:

- It catches low-stakes staff surveys (the coffee survey) as well as
  patient feedback forms.
- It pushes the decision onto the system rather than the creator, who
  actually knows the audience.
- The creator declaration (§3.2) is a cleaner controller-side determination
  and aligns with the platform / controller split in the compliance docs.

The audience field puts the decision where it belongs: the creator declares
who fills the survey in, and the system enforces encryption based on that
declaration. The creator does not have to understand that free text can
de-anonymise; they only have to correctly say "patients will fill this in",
which they know.

## 4. Migration

Existing published surveys with plaintext `answers` must be migrated where
the new predicate (§3.3) requires encryption. Surveys that legitimately
opt out under §3.2 (password user, staff audience, no patient identifiers,
declaration made) may remain plaintext.

### 4.1 Approach

A data migration (or management command, given the volume) that:

1. Iterates `SurveyResponse` rows where `enc_answers IS NULL` and
   `answers != {}`.
2. For each, evaluates the survey against the new predicate (§3.3).
3. For surveys that now require encryption, loads the survey's KEK (via the
   existing recovery / escrow path — see §4.2).
4. Calls `store_answers(survey_key, answers)` and saves, then clears
   `answers`.
5. For surveys that legitimately opt out (§3.2), leaves plaintext in place
   and records the opt-out declaration in the audit log if not already
   present.

### 4.2 The KEK problem

The KEK is not stored in plaintext; it is wrapped per encryption option
(password, recovery, OIDC, org escrow). To migrate existing plaintext
responses we need a KEK for each survey. Options:

- **Org escrow (`encrypted_kek_org`)**: if the survey belongs to an
  organisation with a master key, the org admin can unwrap the KEK and
  run the migration. This is the cleanest path for org-owned surveys.
- **OIDC (`encrypted_kek_oidc`)**: for SSO-owned surveys, the OIDC-derived
  key can be used programmatically if the OIDC identity is available to
  the migration process. This covers the SSO default-on case (§3.1)
  without owner interaction.
- **Owner password / recovery**: requires the owner to enter their
  password or recovery phrase. Not automatable as a background migration;
  would require a one-time interactive flow.
- **Self-hosted admin key escrow**: if a platform-level escrow exists
  (Vault), the admin can unwrap. Confirm whether this is configured.

### 4.3 Recommended migration strategy

Three-phase, ordered by automation feasibility:

1. **Automated phase (OIDC)**: migrate all SSO-owned surveys using the
   OIDC-derived key. This covers the SSO default-on population with no
   owner interaction.
2. **Automated phase (org escrow)**: migrate all org-owned surveys with
   `encrypted_kek_org` set, using the org master key. Covers the majority
   of remaining production surveys if org escrow is configured.
3. **Interactive phase**: for password-owned surveys without org escrow,
  surface a "Complete security upgrade" banner to the survey owner on
   next login, requiring them to enter their password / recovery phrase
   to trigger migration of their surveys' remaining plaintext responses.
   Block new submissions to unmigrated published surveys until complete,
   or accept a grace period — to be decided (see §6).

Surveys that cannot be migrated (owner lost password and recovery phrase,
no escrow) are already unrecoverable under the existing model; their
plaintext answers remain readable by anyone with DB access. This is no
worse than today, and the migration does not make it worse. Document this
clearly. Note that under §3.3 such surveys are now in scope for encryption
(if they are patient / public audience or SSO-owned); the inability to
migrate them is an availability risk, not a confidentiality regression.

### 4.4 Backfill safety

- The migration must be **idempotent**: re-running on an already-encrypted
  row is a no-op.
- It must be **resumable**: process in batches, record progress, survive
  interruption.
- It must **never delete plaintext `answers` until `enc_answers` is
  verified** by a round-trip `load_answers` check.
- Audit-log each migration batch with metadata only (survey id, response
  count, timestamp) — never the answer content.
- The opt-out declaration (§3.2) must be recorded for any survey left
  plaintext, so the audit trail reflects the controller-side decision.

## 5. Code changes

### 5.1 Models (`surveys/models.py`)

- Add `respondent_audience` field to `Survey` (`staff` / `patient` /
  `public`), default `staff`, with a publish-time prompt for surveys where
  it has not been explicitly set.
- Add `encryption_opt_out_declaration` model (or fields on `Survey`):
  stores the creator's opt-out declaration (§3.2) — declaration text
  version, timestamp, user id — for staff-audience password-user surveys
  without patient identifiers. Audit-logged.
- `Survey.requires_whole_response_encryption()`: change predicate per §3.3
  (Option C).
- `SurveyResponse` submission path: ensure `store_answers` is called for
  all qualifying surveys. The submission view / API endpoint is the main
  site; audit all callers of `response.answers = …` and route them through
  `store_answers`.
- `SurveyResponse.load_answers(survey_key)`: already falls back to
  plaintext. Keep the fallback for draft surveys, unmigrated rows, and
  legitimately opted-out surveys; do not remove it (removal is a future
  cleanup, §7).

### 5.2 Publish flow

- Add audience selection to the publish wizard / flow.
- For password users on staff-audience surveys without patient identifiers:
  present the opt-out decision point with the declaration (§3.2). Default
  is opt-out-by-default-with-encouragement; the creator must actively
  confirm the opt-out declaration to keep plaintext.
- For patient / public audience surveys, or surveys with patient
  identifiers: show the encryption explainer (what it entails) and apply
  encryption. No opt-out offered.
- For SSO users: encryption is applied silently (OIDC auto-unlock handles
  the UX); no opt-out offered.

### 5.3 Read paths

Audit every read of `response.answers` and route through
`load_answers(survey_key)`:

- `services/response_analytics.py` — currently reads `response.answers`
  directly (L111). Must accept and use `survey_key`.
- `services/export_service.py` — already handles this correctly via
  `load_complete_response`; verify.
- `views.py` dashboard and the new summary view.
- Progress restore (`SurveyProgress` — out of scope per §2.2, but check
  no cross-read occurs).
- Any API endpoints that return answer content.

### 5.4 Analytics unlock-gate change

`compute_response_analytics` currently runs without unlock because it
reads plaintext `answers`. After this change, it requires `survey_key` for
any survey with encrypted responses. This means **the dashboard analytics
become unlock-gated** for encrypted surveys. For SSO users this is
invisible (OIDC auto-unlock); for password users it is a behaviour change
worth calling out in the PR and the user-facing changelog: the dashboard
distribution charts will only render after unlock for encrypted surveys.

This is acceptable and consistent: the charts expose answer content
(option labels and counts), not just response metadata. Treating them as
unlock-gated is the correct posture. Staff-audience password-user surveys
that have legitimately opted out (§3.2) remain plaintext and the charts
render without unlock, preserving the current behaviour for that narrow
case.

#### 5.4.1 What is and is not affected on the dashboard

The unlock gate applies **only to reads of answer content**
(`response.answers` / `enc_answers`). The rest of the dashboard reads
response **metadata** — row counts and timestamps — and is unaffected by
the encryption posture. Concretely, for a password user viewing an
encrypted survey's dashboard without unlock:

| Dashboard component | Data source | Reads answers? | After upgrade |
|---|---|---|--- |
| Total responses | `survey.responses.count()` | No | Unchanged |
| Today's submissions | `filter(submitted_at__gte=…).count()` | No | Unchanged |
| Last 7 days | same | No | Unchanged |
| Sparkline (responses) | per-day count of `submitted_at` | No | Unchanged |
| Sparkline (invites) | per-day count of `access_tokens.created_at` | No | Unchanged |
| Invites sent / pending | counts on `access_tokens` | No | Unchanged |
| Survey status | survey fields | No | Unchanged |
| Question groups list | `question_groups` | No | Unchanged |
| Distribution charts / insights | `response.answers` via `compute_response_analytics` | **Yes** | Unlock-gated |
| Summary report (reporting PR) | `response.answers` via `load_answers` | **Yes** | Unlock-gated |
| CSV export | `response.answers` via `load_complete_response` | **Yes** | Already unlock-gated |

So the counts and sparkline render without unlock; only answer-content
views (insights charts, summary report, export) require the password.

#### 5.4.2 Why the unlock step is desirable, not just necessary

Requiring password users to enter their passphrase to view collected
answer content is a **positive reinforcement of the data controller
role**, not merely a friction cost. The survey creator is the Data
Controller under UK GDPR (per `docs/compliance/opt-out.md` and
`docs/compliance/individual-rights-procedure.md`); the platform is
processor. Forcing an affirmative unlock step before answer content is
displayed:

- makes the controller's access to respondent data a deliberate, audited
  act rather than a passive page load;
- mirrors the existing unlock requirement for CSV export, so the posture
  is consistent across all answer-content surfaces (charts, summary,
  export);
- keeps the metadata-only dashboard useful for the common "is anything
  happening?" glance without exposing answer content to a passing viewer
  of an unlocked screen.

This framing should be reflected in the user-facing changelog: the unlock
step is a security feature that reinforces the creator's responsibility
for the data they collect, not a regression. For SSO users the step is
absorbed by OIDC auto-unlock and is invisible, which is the intended
trade-off for the lower-friction SSO path.

#### 5.4.3 Split UX on the dashboard

When the reporting PR ships and the insights charts render, a password
user with an encrypted survey will see the dashboard counts and sparkline
immediately (no unlock), but the distribution charts will show a
placeholder ("Enter your password to view answer distributions") until
they unlock. This split is correct — counts are metadata, chart content
is answer data — but the placeholder should be explicit and helpful rather
than a silent omission, so users understand why one section is gated and
the other is not.

## 6. Open questions

- **Grace period for unmigrated surveys**: once the migration is deployed,
  do we block new submissions to published surveys with remaining
  plaintext responses (where the new predicate requires encryption) until
  the owner completes migration, or allow a grace period? Blocking is more
  secure but risks locking users out of live surveys if the owner is
  unavailable. Recommend a grace period with a prominent banner, hard
  cut-off after N days — confirm with product.
- **Draft survey encryption**: §3.4 permits plaintext for drafts. Should
  drafts be encrypted on first save rather than first publish? Tighter,
  but breaks the no-KEK draft creation flow. Recommend keeping §3.4 as
  written.
- **`SurveyProgress.partial_answers`**: out of scope for this PR, but
  should be addressed in a follow-up. Partial answers can contain
  sensitive content and are currently plaintext. Flag in §7.
- **Self-hosted instances**: the migration assumes OIDC, org escrow, or
  owner interaction. Self-hosted instances without OIDC or org escrow will
  rely entirely on the interactive owner flow. Confirm this is acceptable
  for the self-hosting community and document it in `docs/self-hosting-*`.
- **Opt-out declaration wording**: the declaration text (§3.2) should be
  reviewed by the DPO. It is a controller-side acknowledgement and may
  have legal weight under UK GDPR / DSPT. Confirm the wording with
  compliance before shipping.
- **Audience default for existing surveys**: when migrating, existing
  surveys have no `respondent_audience` set. Defaulting to `staff` is the
  least disruptive but may under-encrypt patient-facing surveys whose
  creators never declared an audience. Alternative: prompt for audience on
  next publish and require migration then. Recommend the prompt approach
  over a silent default, to avoid under-encryption.

## 7. Future work (out of scope, flagged)

- Encrypt `SurveyProgress.partial_answers` for in-progress responses.
- Remove the plaintext `answers` fallback in `load_answers` once
  migration is confirmed complete across all deployments.
- Encrypt survey builder content (question text, options) at rest —
  currently plaintext. Lower priority (not respondent data) but
  consistent with the USP.
- Per-field encryption granularity (currently whole-answer-blob). Not
  needed for this PR; the whole-blob approach is sufficient and matches
  the existing patient-data path.

## 8. Documentation changes

As part of this PR:

- **`docs/security-overview.md`** A02: update "patient-identifiable
  fields" → describe the Option C predicate (schema OR audience OR SSO);
  update the answer-storage description (L191) to reflect `enc_answers` as
  the default, with the narrow staff-audience password-user opt-out path.
- **`docs/reporting-and-exports.md`**: update the "How Encryption Affects
  Exports" section to reflect that encryption applies to patient / public
  audience surveys and all SSO surveys, not just patient-data surveys.
- **`docs/encryption-technical-reference.md`** and
  **`docs/encryption-for-users.md`**: update to describe whole-response
  encryption as the default, the audience field, and the opt-out
  declaration path for password users.
- **`docs/business-continuity.md`**: update recovery scenarios to cover
  non-patient surveys (they now also require the KEK for recovery) and
  the opt-out case (plaintext surveys remain recoverable by DB admin).
- **`docs/data-governance-*.md`**: review for any "plaintext answers"
  assumptions and update.
- **`docs/compliance/opt-out.md`**: cross-link the creator declaration
  (§3.2) — the platform provides the technical capability for encryption;
  the controller (survey creator) decides whether to opt out for
  staff-audience surveys. The declaration is the controller-side record
  of that decision.
- **`docs/compliance/individual-rights-procedure.md`**: note that SARs
  for encrypted non-patient surveys follow the same unlock-and-decrypt
  path as patient-data surveys.
- Add a user-facing changelog entry: dashboard distribution charts now
  require unlock for encrypted surveys (invisible for SSO users); all
  patient / public audience surveys and all SSO surveys are now encrypted
  at rest; password users may opt out for staff-audience surveys via a
  logged declaration.

## 9. Testing

- `requires_whole_response_encryption()` returns `True` for:
  - patient-data surveys (existing, no regression);
  - patient / public audience surveys without patient-data groups (new);
  - SSO-owned surveys regardless of audience or schema (new).
- `requires_whole_response_encryption()` returns `False` only for
  password-user, staff-audience, no-patient-identifiers surveys with a
  recorded opt-out declaration.
- Submission path stores `enc_answers` and clears `answers` for surveys
  where the predicate is `True`.
- `load_answers` round-trips correctly for newly-encrypted surveys.
- Migration command: idempotent, resumable, verifies before deleting
  plaintext, audit-logs metadata only, records opt-out declarations for
  surveys left plaintext.
- Read paths (analytics, export, summary, API) all route through
  `load_answers` and fail safe when `survey_key` is missing for an
  encrypted survey.
- Dashboard analytics are unlock-gated for encrypted surveys; render
  without unlock for legitimately opted-out surveys.
- Draft surveys still accept plaintext answers (no regression in builder
  loop).
- Existing patient-data survey behaviour unchanged (no regression).
- Publish flow: audience selection presented; opt-out declaration
  required for the narrow opt-out case; encryption explainer shown for
  patient / public audience surveys; SSO surveys encrypted silently.
- Opt-out declaration is audit-logged with metadata only.

## 10. Ordering and risk

This PR is the prerequisite for `docs/reporting-planning.md`. It is a
data-migration PR with non-trivial risk:

- **Data loss risk** if migration deletes plaintext before verifying
  ciphertext. Mitigated by the round-trip check in §4.4.
- **Lockout risk** if owners cannot provide a KEK and the survey has no
  escrow. No worse than today's recovery model for patient-data surveys,
  but the migration extends the encrypted population to patient / public
  audience and SSO surveys, so the lockout surface grows. The OIDC and
  org-escrow automated phases (§4.3) cover the bulk of this without owner
  interaction.
- **Behaviour change**: dashboard analytics become unlock-gated for
  encrypted surveys. Invisible for SSO users; a real change for password
  users on newly-encrypted surveys. Call out in changelog.
- **Under-encryption risk during migration window**: existing
  patient-facing surveys without a declared audience default to `staff`
  until the owner is prompted. Mitigated by the publish-time audience
  prompt (§6) rather than a silent default.

Recommend a staged rollout: run on a staging deployment with a full
production data snapshot first; verify migration completeness; then
production with the grace-period banner (§6).
