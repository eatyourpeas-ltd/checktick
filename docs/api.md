# API reference and protections

Use the interactive documentation for the full, always-up-to-date list of endpoints and schemas:

[![Swagger UI](/static/docs/swagger-badge.svg)](/api/docs)
[![ReDoc](/static/docs/redoc-badge.svg)](/api/redoc)
[![OpenAPI JSON](/static/docs/openapi-badge.svg)](/api/schema)

Notes:

- We link out to interactive docs instead of embedding them directly into this Markdown to respect our strict Content Security Policy (no inline scripts in docs pages).

## Authentication

- JWT (Bearer) authentication via SimpleJWT. Obtain tokens at `/api/token` and `/api/token/refresh` and pass the access token in `Authorization: Bearer <token>`.

## Permissions matrix (summary)

- Owner
  - List: sees own surveys
  - Retrieve/Update/Delete: allowed for own surveys
- Org ADMIN
  - List: sees all surveys in their organization(s)
  - Retrieve/Update/Delete: allowed for surveys in their organization(s)
- Org CREATOR/VIEWER
  - List: sees only own surveys
  - Retrieve: allowed for surveys they’re a member of
  - Update/Delete: only creators can update; viewers are read-only
  - Publish GET: allowed for creators and viewers (view permission)
  - Publish PUT: allowed for creators (and owner/org ADMIN)
  - Metrics GET: allowed for creators and viewers (view permission)
- Anonymous
  - List: empty array
  - Retrieve/Update/Delete: not allowed

### Dataset permissions

The DataSet API (`/api/datasets-v2/`) manages shared dropdown option lists for surveys.

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
