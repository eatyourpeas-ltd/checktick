---
title: API Reference
category: api
priority: 1
---

Use the interactive documentation for the full, always-up-to-date list of endpoints and schemas:

[![Swagger UI](/static/docs/swagger-badge.svg)](/api/docs)
[![ReDoc](/static/docs/redoc-badge.svg)](/api/redoc)
[![OpenAPI JSON](/static/docs/openapi-badge.svg)](/api/schema)

Notes:

- We link out to interactive docs instead of embedding them directly into this Markdown to respect our strict Content Security Policy (no inline scripts in docs pages).

## Authentication

- JWT (Bearer) authentication via SimpleJWT. Obtain tokens at `/api/token` and `/api/token/refresh` and pass the access token in `Authorization: Bearer <token>`.

## Account Tier Limits

The API enforces the same tier-based limits as the web interface:

### Survey Creation Limits

- **FREE tier**: Maximum 3 surveys
- **PRO tier**: Unlimited surveys
- **ORGANIZATION tier**: Unlimited surveys
- **ENTERPRISE tier**: Unlimited surveys

Attempting to create a survey beyond your tier limit will return a `403 Forbidden` error with a message indicating the upgrade path.

**Example error response:**
```json
{
  "detail": "You've reached the limit of 3 surveys for your Free tier. Upgrade to Pro for unlimited surveys."
}
```

### Collaboration Limits

Adding collaborators via `POST /api/survey-memberships/` enforces tier-based restrictions:

- **FREE tier**: Cannot add any collaborators
- **PRO tier**:
  - Can add EDITOR role (up to 10 collaborators per survey)
  - Cannot add VIEWER role
- **ORGANIZATION tier**:
  - Can add both EDITOR and VIEWER roles
  - Unlimited collaborators per survey
- **ENTERPRISE tier**: Same as ORGANIZATION

Attempting to add collaborators beyond your tier permissions will return a `403 Forbidden` error with upgrade guidance.

**Example error responses:**
```json
// FREE user trying to add collaborators
{
  "detail": "Adding collaborators requires Pro tier. Upgrade to add editors to your surveys."
}

// PRO user trying to add viewers
{
  "detail": "Adding viewers requires Organization tier. Pro tier supports editors only."
}

// PRO user exceeding 10 collaborators
{
  "detail": "You've reached the limit of 10 collaborators for this survey on Pro tier. Upgrade to Organization for unlimited collaborators."
}
```

## Permissions matrix (summary)

- Owner
  - List: sees own surveys
  - Retrieve/Update/Delete: allowed for own surveys
- Org ADMIN
  - List: sees all surveys in their organization(s)
  - Retrieve/Update/Delete: allowed for surveys in their organization(s)
- Org CREATOR/VIEWER
  - List: sees only own surveys
  - Retrieve: allowed for surveys they're a member of
  - Update/Delete: only creators can update; viewers are read-only
  - Publish GET: allowed for creators and viewers (view permission)
  - Publish PUT: allowed for creators (and owner/org ADMIN)
  - Metrics GET: allowed for creators and viewers (view permission)
- Anonymous
  - List: empty array
  - Retrieve/Update/Delete: not allowed

### Dataset permissions

The DataSet API (`/api/datasets-v2/`) manages shared dropdown option lists for surveys. See the [Dataset API Reference](api-datasets.md) for detailed endpoint documentation.

- **Anonymous users**
  - List/Retrieve: only global datasets (is_global=True)
  - Create/Update/Delete: not allowed
- **Authenticated users (any role)**
  - List/Retrieve: global datasets + their organization's datasets
- **Org ADMIN and CREATOR**
  - Create: can create datasets for their organization
  - Update: can update their organization's datasets (except NHS DD datasets)
  - Delete: can soft-delete their organization's datasets (except NHS DD datasets)
- **Org VIEWER**
  - Create/Update/Delete: not allowed (read-only access)
- **NHS Data Dictionary datasets**
  - Category `nhs_dd` datasets are read-only for all users
  - Cannot be modified or deleted via the API
  - Provide standardized NHS terminology and codes

**Note:** The `/api/datasets/` and `/api/datasets/{key}/` endpoints (without `-v2`) are legacy function-based views for fetching dropdown options. Use `/api/datasets-v2/` for full CRUD operations.

## Error codes

- 401 Unauthorized — not authenticated for unsafe requests
- 403 Forbidden — authenticated but not authorized (object exists)
- 404 Not Found — resource doesn’t exist

## Throttling

- Enabled via DRF: `AnonRateThrottle` and `UserRateThrottle`.
- Rates configured in `checktick_app/settings.py` under `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`.

## CORS

- Disabled by default. To call the API from another origin, explicitly set `CORS_ALLOWED_ORIGINS` in settings.

## Encryption requirements for publishing

**Important:** The API enforces encryption requirements for surveys collecting patient data.

- Surveys that collect patient data (using `patient_details_encrypted` question groups) **must have encryption configured** before they can be published via the API.
- Attempting to publish a patient data survey without encryption will return a `400 Bad Request` error with details.
- **Recommended workflow:**
  1. Create and configure your survey structure via the API
  2. Use the **web interface** to set up encryption for the first publish (this creates the necessary encryption keys and recovery mechanisms)
  3. Once encryption is set up, you can use the API to update publish settings, change visibility, etc.

- Surveys that do NOT collect patient data can be published directly via the API without encryption setup.

**Rationale:** The API uses JWT authentication (username/password), not SSO. Interactive encryption setup (displaying recovery phrases, etc.) is only available through the web interface. This ensures patient data is always protected while keeping the API simple and focused on administrative operations.

## Example curl snippets (session + CSRF)

See `docs/authentication-and-permissions.md` for a step-by-step session login and CSRF flow using curl.

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
- Users see organization-level templates from their own organization(s)

**Query Parameters:**

- `publication_level` (string): Filter by 'global' or 'organization'
- `language` (string): Filter by language code (e.g., 'en', 'cy')
- `tags` (string): Comma-separated list of tags to filter by
- `search` (string): Search in template name and description
- `ordering` (string): Order results by 'name', '-name', 'created_at', '-created_at', 'import_count', or '-import_count'

**Response:** Array of template objects with fields:

- `id`: Template ID
- `name`: Template name
- `description`: Template description
- `markdown`: Markdown representation of questions
- `publication_level`: 'global' or 'organization'
- `publisher_username`: Username of publisher
- `organization_name`: Name of organization (for org-level templates)
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

#### Publish Question Group

```http
POST /api/question-group-templates/publish/
```

Publishes a question group as a reusable template.

**Request Body:**

```json
{
  "question_group_id": 456,
  "name": "Depression Screening (PHQ-9)",
  "description": "Standard 9-item depression screening questionnaire",
  "publication_level": "organization",
  "organization_id": 789,
  "language": "en",
  "tags": ["mental-health", "screening", "validated"],
  "attribution": {
    "original_author": "Dr. Smith",
    "source": "Clinical Guidelines 2023"
  },
  "show_publisher_credit": true
}
```

**Required Fields:**

- `question_group_id`: ID of the question group to publish
- `name`: Template name
- `publication_level`: 'global' or 'organization'
- `organization_id`: Required if publication_level is 'organization'

**Optional Fields:**

- `description`: Template description (default: empty string)
- `language`: Language code (default: 'en')
- `tags`: Array of tags (default: empty array)
- `attribution`: Attribution metadata (default: empty object)
- `show_publisher_credit`: Show publisher name (default: true)

**Access Control:**

- User must have edit permission on the survey containing the question group
- Cannot publish question groups that were imported from other templates (copyright protection)
- **Organization-level** publication requires ADMIN role in the target organization
- **Global** publication requires superuser status

**Response:** Created template object (201 Created)

**Example:**

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question_group_id": 456,
    "name": "Anxiety Screening (GAD-7)",
    "description": "7-item anxiety screening tool",
    "publication_level": "organization",
    "organization_id": 789,
    "language": "en",
    "tags": ["mental-health", "anxiety", "validated"]
  }' \
  "https://example.com/api/question-group-templates/publish/"
```

### Permission Matrix

| Action | Anonymous | Authenticated | Org Admin | Superuser |
|--------|-----------|---------------|-----------|-----------|
| List templates | ❌ | ✅ (global + own org) | ✅ (global + own org) | ✅ (all) |
| Retrieve template | ❌ | ✅ (global + own org) | ✅ (global + own org) | ✅ (all) |
| Publish (org-level) | ❌ | ❌ | ✅ (own org only) | ✅ |
| Publish (global) | ❌ | ❌ | ❌ | ✅ |

### Copyright Protection

The API prevents publishing question groups that were imported from other templates. This protects against:

- Copyright violations
- Circular attribution issues
- Confusion about original sources

If you need to share an imported question group, either:

1. Credit the original template in your documentation
2. Significantly modify the questions to create original content
3. Contact the original publisher for permission

### Error Responses

```json
// 400 Bad Request - Missing required field
{
  "error": "name is required"
}

// 400 Bad Request - Cannot publish imported group
{
  "error": "Cannot publish question groups that were imported from templates. This protects copyright and prevents circular attribution issues."
}

// 403 Forbidden - Not an org admin
{
  "error": "You must be an ADMIN in the organization to publish at organization level"
}

// 403 Forbidden - Not a superuser
{
  "error": "Only administrators can publish global templates"
}

// 404 Not Found - Question group doesn't exist
{
  "error": "Question group not found"
}
```
