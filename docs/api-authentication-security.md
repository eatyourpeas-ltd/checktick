---
title: API Authentication Security — Review & Improvement Plan
category: security
priority: 1
---

# API Authentication Security — Review & Improvement Plan

> This document summarises findings from the March 2026 penetration test relating to API authentication and sets out the improvement roadmap.

## Current Authentication Model

### Mechanism

- **JWT (Bearer)** via `djangorestframework-simplejwt`
- Token obtained at `POST /api/token` using email (username) + password
- Access token: **30 minutes**; Refresh token: **7 days**
- Refresh token rotation is **off** — a stolen refresh token is valid for its full 7-day lifetime
- Both `JWTAuthentication` and `SessionAuthentication` are active as DRF backends

### Brute-force / Rate-limit Controls

| Control | Applies to web login | Applies to `/api/token` |
|---|---|---|
| `django-axes` (5 fail lockout) | ✅ Yes | ❌ No |
| `django-ratelimit` | ✅ Yes | ❌ No |
| DRF throttle (60 anon / 120 user per min) | — | ✅ Yes (but too permissive) |

### MFA / 2FA

- `django_otp` (TOTP) is installed and enforced for web UI sessions via `OTPMiddleware`
- The `POST /api/token` endpoint **completely bypasses MFA** — a valid password alone issues a bearer token

### Tier Enforcement

- Survey and collaboration limits are checked per-request inside views
- **FREE tier users are not blocked from obtaining a JWT** — any account, regardless of tier, can call `/api/token`
- Team and Org role restrictions are not checked at token-issuance time

---

## Pen Test Findings

1. **Brute force on `/api/token`** — `django-axes` is not wired to the DRF token endpoint, so there was no lockout after repeated failed attempts.
2. **MFA bypass** — An attacker with a valid username and password could obtain a bearer token, entirely bypassing the TOTP requirement enforced for web sessions.
3. **FREE tier and non-admin team members not blocked** — Any registered user can get a working API token.

---

## Target Access Model

| Account tier | API access | Who can generate credentials |
|---|---|---|
| **FREE** | ❌ None | N/A |
| **PRO** | ✅ Full | User self-serves (must be MFA-authenticated) |
| **TEAM Small / Medium / Large** | ✅ Team ADMIN only | Team admin via MFA-authenticated web UI |
| **ORGANISATION** | ✅ Org admin by default; admin can grant access to named members | Org admin via web UI |
| **ENTERPRISE** | ✅ As Organisation + SSO token exchange | Org admin / SSO |

---

## Recommended Approach: Named API Keys

Rather than retrofitting TOTP codes onto every API call (complex for machine-to-machine use), the recommended model — used by GitHub, Stripe, and the NHS developer portal — is:

> **Issue named, scoped API keys through the MFA-protected web UI. Block direct username + password access to `/api/token`.**

This means MFA is "baked in" at key issuance rather than required on every request, which is practical for automated/scripted API consumers.

### API Key Model

- A `UserAPIKey` model stores a per-user, named key as a **secure hash** (never stored in plaintext)
- The raw key is shown **once** at creation and never again
- Keys are **revocable** by the user or an admin at any time
- Key creation requires a fully MFA-authenticated web session
- All key creation, use, and revocation is written to the audit log

### Organisation-level Delegation

An `OrganisationAPIKeyGrant` model allows org admins to nominate specific members who may generate API keys:

- Org admin grants access to a named user in the web UI
- Only granted users can generate a key
- Admin can revoke grants at any time
- Useful for separating "who administers the org" from "who automates against the API"

---

## Improvement Roadmap

### 🔴 Immediate (now — before next pen test)

1. **Wire `AxesBackend`** into `AUTHENTICATION_BACKENDS` so `django-axes` lockout applies to `/api/token` as well as the web login form.
2. **Add a dedicated strict throttle** on `/api/token` — e.g. `5 attempts/minute` per IP, separate from the general `anon`/`user` rates.
3. **Enable refresh token rotation and blacklisting**:
   ```python
   SIMPLE_JWT = {
       ...
       "ROTATE_REFRESH_TOKENS": True,
       "BLACKLIST_AFTER_ROTATION": True,
   }
   ```
   A stolen refresh token can then only be used once before it is invalidated.

### 🟠 Soon (next sprint)

4. **Custom `TokenObtainPairView`** that, after successful authentication, enforces:
   - Reject FREE tier users with `403 Forbidden` + upgrade message
   - Reject Team members who are not ADMIN with `403 Forbidden`
   - Reject Org members who are not ADMIN (unless granted access) with `403 Forbidden`
5. **Document and communicate** the tier restrictions to existing API users.

### 🟡 Planned (this quarter)

6. **`UserAPIKey` model** — hashed API key storage, expiry, per-key scoping.
7. **API key management UI** in the web dashboard (generate, name, revoke).
8. **`OrganisationAPIKeyGrant`** — org admin delegation of API key access.
9. **Replace `JWTAuthentication`** with `APIKeyAuthentication` as the primary DRF backend. Keep `SessionAuthentication` for Swagger UI.

### 🟢 Later (next quarter)

10. **Remove (or heavily restrict) `/api/token`** in production — username + password token issuance replaced entirely by API keys.
11. **SSO token exchange** for Enterprise tier — allow OIDC-authenticated sessions to mint API keys without a separate password.

---

## Should MFA be required on every API call?

**No — but it should gate key issuance.** Adding a TOTP field to every `POST /api/token` request:

- Breaks all existing machine-to-machine integrations
- Is impractical for automated scripts and CI pipelines
- Provides limited benefit once `/api/token` is properly rate-limited and restricted to paid tiers

The correct control is: **you cannot generate an API key unless you are in an MFA-verified web session**. The key then acts as the long-lived credential. This is the same security model used by GitHub PATs, Stripe API keys, and AWS IAM access keys.

---

## Related Documents

- [API Reference](api.md)
- [Authentication & Permissions](authentication-and-permissions.md)
- [Audit Logging and Notifications](audit-logging-and-notifications.md)
- [OIDC SSO Setup](oidc-sso-setup.md)
- [Pen Test Preparation](PENTEST-PREPARATION.md)
