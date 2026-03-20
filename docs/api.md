---
title: API Reference
category: api
priority: 1
---

Use the interactive documentation for the full, always-up-to-date list of endpoints and schemas:

[![ReDoc](/static/docs/redoc-badge.svg)](/api/redoc)
[![OpenAPI JSON](/static/docs/openapi-badge.svg)](/api/schema)

Notes:

- We link out to interactive docs instead of embedding them directly into this Markdown to respect our strict Content Security Policy (no inline scripts in docs pages).

## Authentication

The API uses named API keys issued through the MFA-protected web UI. API keys are not available to FREE tier accounts.

### Obtaining an API key

1. Log in to the web application and complete MFA verification.
2. Navigate to **Account → API Keys**.
3. Click **Generate new key**, give it a descriptive name (e.g. "CI pipeline", "ETL script"), and optionally set an expiry date.
4. Copy the key immediately — it is shown **once only** and cannot be retrieved again.

### Using an API key

Pass the raw key in the `Authorization` header:

```sh
curl -H "Authorization: Bearer ct_live_<your_key>" \
  https://example.com/api/surveys/
```

Keys have the prefix `ct_live_` so they are identifiable if accidentally committed.

### Revoking an API key

Revoke a key at any time from **Account → API Keys**. Revocation is immediate. Changing your password revokes all your keys.

### Account tier requirements

| Tier | API access |
|---|---|
| **FREE** | ❌ No API access |
| **PRO** | ✅ Read-only; self-serve key generation |
| **TEAM** (any size) | ✅ Read-only; team admin generates keys |
| **ORGANISATION** | ✅ Read-only; org admin generates keys |
| **ENTERPRISE** | ✅ Read-only; org admin or SSO token exchange |

## Available endpoints

The API is read-only. All write operations (survey creation, publication, membership management, user administration) are performed through the web UI.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/surveys/` | List surveys accessible to the key |
| `GET` | `/api/surveys/{id}/` | Survey structure and metadata |
| `GET` | `/api/surveys/{id}/metrics/responses/` | Aggregate response counts (no PII) |
| `GET` | `/api/datasets/` | Dataset / dropdown data |
| `GET` | `/api/datasets/{key}/` | Single dataset |
| `GET` | `/api/question-group-templates/` | Published question group templates |
| `GET` | `/api/question-group-templates/{id}/` | Single template |
| `GET` | `/api/health` | Health check (public, no auth required) |
| `GET` | `/api/docs`, `/api/redoc`, `/api/schema` | Interactive API documentation (public) |

## Permissions matrix (summary)

| Endpoint | Owner | Org ADMIN | Org CREATOR/VIEWER | No key / anonymous |
|---|---|---|---|---|
| Survey list | Sees own surveys | Sees all org surveys | Sees own surveys | Empty list / 401 |
| Survey retrieve | ✅ | ✅ | ✅ if member | 401 |
| Survey metrics | ✅ | ✅ | ✅ if member | 401 |
| Dataset list | ✅ (global + org) | ✅ (global + org) | ✅ (global + org) | Global only |
| Dataset retrieve | ✅ | ✅ | ✅ | ✅ (public datasets) |
| QG templates list | ✅ (global + own org) | ✅ (global + own org) | ✅ (global + own org) | 401 |
| QG templates retrieve | ✅ | ✅ | ✅ | 401 |
| Health check | ✅ | ✅ | ✅ | ✅ |

### Dataset permissions

The datasets API (`/api/datasets/`) provides read-only access to shared dropdown option lists. See the [Dataset API Reference](api-datasets.md) for details.

- **Anonymous / no key**: global datasets only (`is_global=True`)
- **Authenticated key holders**: global datasets + their organisation's datasets
- **NHS Data Dictionary datasets** (`category=nhs_dd`): read-only for all; cannot be modified via the API

## Error codes

- 401 Unauthorized — missing, invalid, revoked, or expired API key
- 403 Forbidden — authenticated but not authorized (FREE tier, or insufficient role on object)
- 404 Not Found — resource doesn't exist
- 405 Method Not Allowed — only GET requests are accepted on all endpoints

## Throttling

- Enabled via DRF: `AnonRateThrottle` and `UserRateThrottle`.
- Rates configured in `checktick_app/settings.py` under `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`.
- The `/api/token` endpoint (legacy, not yet removed) is additionally throttled at **5 requests/minute per IP**.

## CORS

- Disabled by default. To call the API from another origin, explicitly set `CORS_ALLOWED_ORIGINS` in settings.

## Encryption and read-only scope

The API is restricted to survey structure and aggregate response counts. Neither of these involves encryption material:

- Survey structure (`/api/surveys/`) contains question metadata only — no responses or PII.
- Response metrics (`/api/surveys/{id}/metrics/responses/`) returns counts only — no individual responses.

All encryption configuration, survey publication, and data export remain web-UI-only operations.

## Example curl snippets

See [Authentication & Permissions](authentication-and-permissions.md) for a complete guide to API key generation and usage.

## Question Group Template Library API

The Question Group Template API (`/api/question-group-templates/`) provides programmatic access to the template library for browsing and publishing reusable question group templates.

### Endpoints

#### List Templates

```http
GET /api/question-group-templates/
```

Returns a list of published question group templates visible to the authenticated user.

**Access Control:**

- Users see global templates (publication_level='global')
- Users see organisation-level templates from their own organisation(s)

**Query Parameters:**

- `publication_level` (string): Filter by 'global' or 'organisation'
- `language` (string): Filter by language code (e.g., 'en', 'cy')
- `tags` (string): Comma-separated list of tags to filter by
- `search` (string): Search in template name and description
- `ordering` (string): Order results by 'name', '-name', 'created_at', '-created_at', 'import_count', or '-import_count'

**Response:** Array of template objects with fields:

- `id`: Template ID
- `name`: Template name
- `description`: Template description
- `markdown`: Markdown representation of questions
- `publication_level`: 'global' or 'organisation'
- `publisher_username`: Username of publisher
- `organization_name`: Name of organisation (for org-level templates)
- `attribution`: Attribution metadata
- `tags`: Array of tags
- `language`: Language code
- `import_count`: Number of times imported
- `can_delete`: Boolean indicating if current user can delete this template
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

**Example:**

```bash
curl -H "Authorization: Bearer <token>" \
  "https://example.com/api/question-group-templates/?publication_level=global&language=en"
```

#### Retrieve Template

```http
GET /api/question-group-templates/{id}/
```

Returns detailed information about a specific template.

**Access Control:** Same as list endpoint (global + own org templates only)

**Example:**

```bash
curl -H "Authorization: Bearer <token>" \
  "https://example.com/api/question-group-templates/123/"
```

### Permission Matrix

| Action | No key / anonymous | API key holder |
|--------|-----------|---------------|
| List templates | ❌ | ✅ (global + own org) |
| Retrieve template | ❌ | ✅ (global + own org) |

> **Publishing question group templates** is a write operation and is performed through the web UI only (`/surveys/question-group-templates/publish/`).
