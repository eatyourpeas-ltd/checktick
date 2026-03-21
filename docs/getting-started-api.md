---
title: Getting Started with API
category: getting-started
priority: 3
---

This guide shows how to authenticate with an API key and call the read-only API using curl, plus a small Python example.

Prerequisites:

- The app is running (Docker or `python manage.py runserver`)
- You have a user account on a paid tier (Pro, Team, or Organisation)
- MFA must be configured on your account before you can create API keys
- Base URL in examples: `https://localhost:8000`

## Interactive documentation

[![ReDoc](/static/docs/redoc-badge.svg)](/api/redoc)
[![OpenAPI JSON](/static/docs/openapi-badge.svg)](/api/schema)

## Obtaining an API key

API keys are managed through the web interface and require MFA to be active on your account.

1. Log in and complete MFA verification.
2. Navigate to **Account → API Keys**.
3. Click **Generate new key**, give it a descriptive name (e.g. "CI pipeline", "ETL script"), and optionally set an expiry date.
4. Copy the key immediately — it is shown **once only** and cannot be retrieved again.

API keys are **not available on free tier** accounts. See [account tiers](getting-started-account-types.md) for details.

## Authenticating with curl

Pass the key in the `Authorization` header:

```sh
API_KEY=ct_live_<your_key>

# List your surveys
curl -k -s -H "Authorization: Bearer $API_KEY" https://localhost:8000/api/surveys/
```

Keys are prefixed `ct_live_` so they are identifiable if accidentally exposed.

## curl examples

1. List surveys accessible to your key:

```sh
API_KEY=ct_live_<your_key>
curl -k -s -H "Authorization: Bearer $API_KEY" https://localhost:8000/api/surveys/
```

2. Get a specific survey:

```sh
SURVEY_ID=<ID>
curl -k -s -H "Authorization: Bearer $API_KEY" https://localhost:8000/api/surveys/$SURVEY_ID/
```

3. Get aggregate response metrics (no PII):

```sh
SURVEY_ID=<ID>
curl -k -s -H "Authorization: Bearer $API_KEY" \
  https://localhost:8000/api/surveys/$SURVEY_ID/metrics/responses/
```

The API is read-only. Survey creation, publishing, and user management are performed through the web interface.

## Python example (requests)

```python
import requests

base = "https://localhost:8000"
api_key = "ct_live_<your_key>"

session = requests.Session()
session.verify = False  # for local self-signed certs; remove in production
session.headers.update({"Authorization": f"Bearer {api_key}"})

# List surveys
print(session.get(f"{base}/api/surveys/").json())

# Get a specific survey
survey_id = "<ID>"
print(session.get(f"{base}/api/surveys/{survey_id}/").json())

# Get response metrics
print(session.get(f"{base}/api/surveys/{survey_id}/metrics/responses/").json())
```

## Permissions recap

- List returns surveys accessible to the key owner (own surveys and any where they are an org ADMIN).
- Retrieve requires ownership or org ADMIN role.
- Users without rights on a resource get 403; non-existent resources return 404.

## Troubleshooting

- 401: missing or invalid API key — check the `Authorization: Bearer ct_live_...` header.
- 403: authenticated but not authorised for that resource.
- 404: resource does not exist or is not accessible to your key.
- CORS errors in browser: CORS is disabled by default; allow origins explicitly in settings.
- SSL cert complaints with curl/requests: examples use `-k`/`verify=False` for local development only; remove in production.
