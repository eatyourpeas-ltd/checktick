---
title: API Authentication Security — Implementation Plan
category: security
priority: 1
---

# API Authentication Security — Implementation Plan

> **Origin**: March 2026 penetration test. This document records the findings, the decisions made in response, and the two-phase implementation plan.

---

## Pen Test Findings

The March 2026 pen test identified three failures in the current JWT (`/api/token`) approach:

1. **Brute force on `/api/token`** — `django-axes` was not wired to the DRF token endpoint. There was no lockout after repeated failed password attempts.
2. **MFA bypass** — A valid username and password alone issued a bearer token, completely bypassing the TOTP requirement enforced for web sessions.
3. **No tier or role enforcement at token issuance** — FREE tier users, non-admin team members, and non-admin org members could all obtain valid bearer tokens.

---

## Decisions Made

Two separate decisions were made in response:

**Decision 1 — Narrow the API scope to read-only**

The API surface is reduced to read-only data retrieval. The only confirmed external integration use case is embedding surveys in or fetching survey data from external systems. All write operations, user management, publication, and response access are confined to the web application. This eliminates the highest-risk surfaces from any authentication compromise.

**Decision 2 — Replace JWT authentication with named, role-scoped API keys**

The `/api/token` endpoint is removed and replaced with named API keys issued through the MFA-protected web UI. MFA gates key issuance, not every API call. This closes the MFA bypass and brute force findings, and makes tier and scope enforcement explicit at the point of key creation.

The `scope_context` field is included in the initial model but the full delegation model (`OrganisationAPIKeyGrant`) is deferred until write endpoints are reintroduced — at read-only scope, the existing queryset filtering is sufficient.

---

## Target API Surface

### Permitted endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/surveys/` | List surveys accessible to the key |
| `GET` | `/api/surveys/{id}/` | Survey structure and metadata |
| `GET` | `/api/surveys/{id}/metrics/responses/` | Aggregate response counts (no PII) |
| `GET` | `/api/datasets/` | Dataset / dropdown data |
| `GET` | `/api/datasets/{id}/` | Single dataset |
| `GET` | `/api/question-group-templates/` | Published question group templates |
| `GET` | `/api/question-group-templates/{id}/` | Single template |
| `GET` | `/api/health` | Health check (public) |
| `GET` | `/api/docs`, `/api/redoc`, `/api/schema` | API documentation (public) |

### Removed endpoints

| Endpoint(s) | Reason |
|---|---|
| `POST/PUT/PATCH/DELETE /api/surveys/` | Survey creation, editing, deletion — web app only |
| `POST /api/surveys/{id}/seed/` | Question seeding — web app only |
| `POST /api/surveys/{id}/publish/` | Publication — web app only |
| `GET/POST /api/surveys/{id}/tokens/` | Invite token management — web app only |
| `POST/PUT/DELETE /api/org-memberships/` | Org membership management — web app only |
| `POST/PUT/DELETE /api/survey-memberships/` | Survey membership management — web app only |
| `GET/POST /api/users/` | User listing and lookup — web app only |
| `POST /api/scoped-users/*/create` | User creation — web app only |
| `* /api/recovery/` | Key recovery management — web app only |

---

## Target Access Model (API keys)

| Account tier | API access | Who can generate credentials |
|---|---|---|
| **FREE** | ❌ None | N/A |
| **PRO** | ✅ Read-only | User self-serves via MFA-verified web session |
| **TEAM Small / Medium / Large** | ✅ Team ADMIN only by default | Team admin via web UI |
| **ORGANISATION** | ✅ Org admin by default | Org admin via web UI |
| **ENTERPRISE** | ✅ As Organisation + SSO token exchange option | Org admin / SSO |

---

## Phase 1 — Endpoint Removal

**Goal**: A passing test suite against a correctly narrowed read-only API. No new infrastructure required. Shippable independently of Phase 2.

### Step 1 — Delete test files for removed endpoints

These files test only endpoints being removed. Delete them entirely:

- `tests/test_api_questions_and_groups.py` — 35 tests, all `POST /api/surveys/{id}/seed/`
- `tests/test_user_api.py` — 8 tests, all covering `org-memberships`, `survey-memberships`, `scoped-users`

### Step 2 — Remove tests for removed endpoints from mixed files

**`tests/test_api_permissions.py`** — remove these 3 tests, keep the rest:

- `test_update_forbidden_without_rights` (PATCH endpoint removed)
- `test_seed_action_permissions` (seed endpoint removed)
- `test_create_returns_one_time_key` (POST survey creation removed)

**`tests/test_api_editor_permissions.py`** — remove PATCH assertions:

- `test_api_editor_permissions`: remove the PATCH/update assertion; keep the GET retrieve assertion
- `test_api_viewer_permissions`: remove the PATCH/403 assertion; keep the GET retrieve assertion

**`tests/test_api_access_controls.py`** — remove 6 tests for removed endpoints, keep only `test_healthcheck_public`:

- `test_org_memberships_anonymous_blocked`
- `test_org_memberships_non_admin_forbidden_on_mutations`
- `test_survey_memberships_anonymous_blocked`
- `test_survey_memberships_non_manager_forbidden_on_mutations`
- `test_scoped_user_create_org_permissions`
- `test_scoped_user_create_survey_permissions`

**`tests/test_api_cross_org_security.py`** — remove 1 test for a removed endpoint:

- `test_user_cannot_publish_other_org_survey` (publish endpoint removed)

### Step 3 — Restrict `checktick_app/api/views.py`

**`SurveyViewSet`** — convert from `ModelViewSet` to `ReadOnlyModelViewSet`:

- Remove `perform_create`, `perform_destroy`, `create` override
- Remove `seed` action
- Remove `publish_settings` action
- Remove `tokens` action
- Keep `responses_metrics` action (read-only)

**`DataSetViewSet`** — restrict to read-only:

- Override `http_method_names` to `["get", "head", "options"]`, or convert to `ReadOnlyModelViewSet`
- Remove `create-custom` action and `available-tags` action if write-only
- Keep list and retrieve

**`PublishedQuestionGroupViewSet`** — already `ReadOnlyModelViewSet`, no changes needed.

**Remove entirely** (classes and all associated serializers that are only used by them):

- `OrganizationMembershipViewSet` + `OrganizationMembershipSerializer`
- `SurveyMembershipViewSet` + `SurveyMembershipSerializer`
- `UserViewSet` + `UserSerializer`
- `ScopedUserViewSet` + `ScopedUserCreateSerializer`
- `RecoveryViewSet` and all recovery-related serializers

### Step 4 — Update `checktick_app/api/urls.py`

Remove these router registrations:

```python
# Remove:
router.register(r"org-memberships", views.OrganizationMembershipViewSet, ...)
router.register(r"survey-memberships", views.SurveyMembershipViewSet, ...)
router.register(r"users", views.UserViewSet, ...)
router.register(r"scoped-users", views.ScopedUserViewSet, ...)
router.register(r"recovery", views.RecoveryViewSet, ...)
```

### Step 5 — Run tests

All remaining tests should pass. The test suite now covers:

- Survey list/retrieve (with org scoping)
- Response metrics (read-only counts)
- Cross-org isolation (read-only)
- Editor/viewer read permissions
- Healthcheck
- API docs pages
- OpenAPI schema

### Step 6 — Update `docs/user-management.md`

Remove the "API endpoints" section (lines covering `org-memberships`, `survey-memberships`, `scoped-users`). Replace with a note that all user management is performed through the web application at `/surveys/manage/users/`, `/surveys/org/<org_id>/users/`, and `/surveys/{slug}/users/`.

---

## Immediate Hardening (parallel to Phase 1)

These mitigations close the pen test findings on the existing JWT endpoint while Phase 2 is in progress. They do not depend on Phase 1 completing first.

**1. Wire `django-axes` to `/api/token`**

In `checktick_app/settings.py`, add `AxesStandaloneBackend` to `AUTHENTICATION_BACKENDS`:

```python
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
```

**2. Strict throttle on `/api/token`**

Add a `TokenObtainThrottle` class at `5/minute` per IP in `checktick_app/api/throttles.py` and apply it to the token view in `api/urls.py`.

**3. Enable refresh token rotation**

In `checktick_app/settings.py`:

```python
SIMPLE_JWT = {
    ...
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

Ensure `rest_framework_simplejwt.token_blacklist` is in `INSTALLED_APPS`.

**4. Tier block at token issuance**

Create a custom `TokenObtainPairView` subclass that checks `user.profile.account_tier` after authentication and returns `403 Forbidden` for FREE tier users. Apply to the `token` URL pattern.

---

## Phase 2 — JWT → API Key Authentication

**Goal**: Replace JWT with named, MFA-gated API keys. The `/api/token` endpoint is removed.

### Step 1 — `UserAPIKey` model + migration

Create `checktick_app/core/models.py` → `UserAPIKey`:

```
id              UUIDField primary key
user            FK → User
name            CharField — human label ("CI pipeline", "ETL script")
key_hash        CharField(64) — SHA-256 of the raw key; unique; indexed
prefix          CharField(12) — first 12 chars of raw key, stored plaintext for display
scope_context   CharField(100, nullable) — reserved; "pro_full" | "team:{id}:{role}" | "org:{id}:{role}"
created_at      DateTimeField auto_now_add
last_used_at    DateTimeField null
expires_at      DateTimeField null — None means no expiry
revoked         BooleanField default False
revoked_at      DateTimeField null
revoked_by      FK → User null
```

- Raw key format: `ct_live_<secrets.token_urlsafe(40)>`
- Generated once, shown once, never stored
- `scope_context` is nullable and unused at Phase 2; wired up in Phase 3 when write endpoints return

Run `manage.py makemigrations` and `manage.py migrate`.

### Step 2 — Write API key authentication tests (TDD)

Create `tests/test_api_key_auth.py` before implementing the backend. Tests should cover:

- Valid key in `Authorization: Bearer ct_live_...` header → 200, correct user resolved
- Invalid / unknown key → 401
- Revoked key → 401
- Expired key (past `expires_at`) → 401
- No `Authorization` header → 401 (or 403 from permission class)
- FREE tier user cannot generate a key (web UI gate, not auth layer)
- Key `last_used_at` is updated on each authenticated request

### Step 3 — Implement `APIKeyAuthentication` backend

Create `checktick_app/api/authentication.py`:

```python
class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request).decode()
        if not header.startswith("Bearer ct_live_"):
            return None  # fall through to next auth class
        raw_key = header[7:]  # strip "Bearer "
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = UserAPIKey.objects.select_related("user").get(
                key_hash=key_hash,
                revoked=False,
            )
        except UserAPIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key.")
        if api_key.expires_at and api_key.expires_at < timezone.now():
            raise AuthenticationFailed("API key has expired.")
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])
        return (api_key.user, api_key)
```

Update `checktick_app/settings.py`:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "checktick_app.api.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # kept for Swagger UI
    ],
    ...
}
```

### Step 4 — Rewrite JWT-dependent tests

**`tests/test_api_cross_org_security.py`** — the 5 remaining tests authenticate via `/api/token`. Rewrite each test's `auth` setup to create a `UserAPIKey` fixture and pass the raw key as the `Authorization: Bearer` header. The cross-org isolation assertions themselves are unchanged.

Also rewrite any remaining auth setup in `tests/test_api_permissions.py` and `tests/test_api_editor_permissions.py` if they use `/api/token`.

### Step 5 — API key management web UI

**View**: `checktick_app/surveys/views.py` → `APIKeyListView`, `APIKeyCreateView`, `APIKeyRevokeView`
**Template**: `templates/surveys/api_keys.html`
**URL**: `Account → API Keys`

The **Generate new key** button renders only if:

- `request.user.is_verified()` (OTP check via `django_otp`)
- `user.profile.account_tier` is PRO, TEAM, ORGANISATION, or ENTERPRISE
- User has not exceeded the key limit for their tier

The raw key is displayed once in a copyable field with a confirmation gate. It cannot be retrieved again. All lifecycle events (create, revoke) are written to the audit log.

### Step 6 — Run tests

All tests should pass, including the new API key auth tests and the rewritten cross-org security tests.

### Step 7 — Remove `/api/token`

Remove the `path("token", ...)` and `path("token/refresh", ...)` URL patterns from `api/urls.py`.

Add a catch-all that returns `410 Gone` with a message pointing to the API keys documentation, so integrations break clearly rather than silently.

Update `docs/api.md` and `docs/authentication-and-permissions.md` to remove all JWT references and describe the API key model.

---

## Phase 3 — Deferred (when write endpoints return)

These items are explicitly deferred because at read-only scope, the existing queryset filtering is sufficient. They become necessary only when write operations are reintroduced.

- `OrganisationAPIKeyGrant` model — admin delegation of key issuance rights
- `scope_context` activation — wired into `can_edit_survey`, `can_manage_survey_users` permission helpers
- Org/team admin grant UI — `OrgMemberAPIAccessView`, `org_member_api_access.html`
- Key expiry email notifications (14- and 7-day warnings)
- Key rotation UI
- Platform admin API key dashboard
- SSO token exchange for Enterprise (OIDC session → API key mint)

---

## Encryption Constraints

All surveys are encrypted before publishing. The API is restricted to survey structure and response count data, neither of which involves encryption material. The full constraints are:

| Operation | API allowed? | Reason |
|---|---|---|
| List / read survey structure and metadata | ✅ Yes | No encryption material involved |
| Read aggregate response counts | ✅ Yes | No PII; count fields only |
| Read datasets and question group templates | ✅ Yes | |
| Fetch raw survey responses | ❌ No | Responses are encrypted blobs; decryption requires interactive MFA-verified session |
| Create, update, delete surveys | ❌ No | Web app only |
| Publish / unpublish | ❌ No | Web app only; encryption must be set up interactively first |
| Set up encryption | ❌ No | Recovery phrase display is interactive |
| Manage memberships or users | ❌ No | Web app only |

**Password change invalidation**: when a user changes their account password, all survey KEKs are re-wrapped. All API keys for that user are also revoked at the same time. The user must re-authenticate via MFA and generate new keys.

---

## Related Documents

- [API Reference](api.md)
- [Authentication & Permissions](authentication-and-permissions.md)
- [Encryption Technical Reference](encryption-technical-reference.md)
- [User Management](user-management.md)
- [Audit Logging and Notifications](audit-logging-and-notifications.md)
- [OIDC SSO Setup](oidc-sso-setup.md)
- [Pen Test Preparation](PENTEST-PREPARATION.md)
