---
title: Dataset API Reference
category: api
priority: 3
---

This document covers the Dataset API endpoints for programmatic read access to datasets.

> **The dataset API is read-only.** Creating, editing, customising, snapshotting, publishing, and deleting datasets are performed through the web app (see [Datasets and Dropdowns](/docs/datasets-and-dropdowns/)). Non-safe HTTP methods (POST/PATCH/PUT/DELETE) are rejected for all dataset endpoints.

## Base URL

```
/api/datasets/
```

## Authentication

All dataset endpoints (read and write) require authentication — there is no anonymous access. Anonymous survey respondents never call this API: dataset options are rendered server-side into the survey page. See [API Documentation](/docs/api/) for authentication details.

```http
Authorization: Bearer <your_jwt_token>
```

## Endpoints

### List Datasets

Get all datasets accessible to the current user.

```http
GET /api/datasets/
```

**Query Parameters:**

- `category` - Filter by category: `nhs_dd`, `rcpch`, `external_api`, `user_created`
- `tags` - Filter by comma-separated tags (AND logic)
- `search` - Search in name and description
- `is_global` - Filter global datasets: `true` or `false`
- `page` - Page number for pagination
- `page_size` - Items per page (default: 20)

**Examples:**

```bash
# Get all NHS DD datasets
curl https://checktick.example.com/api/datasets/?category=nhs_dd

# Get datasets with specific tags
curl https://checktick.example.com/api/datasets/?tags=paediatric,medical

# Search datasets
curl https://checktick.example.com/api/datasets/?search=hospital

# Combine filters
curl https://checktick.example.com/api/datasets/?category=nhs_dd&tags=demographic
```

**Response:**

```json
{
  "count": 48,
  "next": "http://checktick.example.com/api/datasets/?page=2",
  "previous": null,
  "results": [
    {
      "key": "main_specialty_code",
      "name": "Main Specialty Code",
      "description": "NHS Data Dictionary - Main Specialty Code",
      "category": "nhs_dd",
      "source_type": "scrape",
      "is_custom": false,
      "is_global": true,
      "parent": null,
      "parent_name": null,
      "organization": null,
      "organization_name": null,
      "tags": ["medical", "specialty", "NHS"],
      "options_count": 75,
      "created_at": "2024-11-15T10:00:00Z",
      "updated_at": "2024-11-15T10:00:00Z",
      "last_synced_at": null,
      "last_scraped": "2024-11-16T05:00:00Z",
      "is_editable": false,
      "reference_url": "https://www.datadictionary.nhs.uk/data_elements/main_specialty_code.html"
    }
  ]
}
```

### Get Dataset Detail

Retrieve a specific dataset with full options.

```http
GET /api/datasets/{key}/
```

**Example:**

```bash
curl https://checktick.example.com/api/datasets/main_specialty_code/
```

**Response:**

```json
{
  "key": "main_specialty_code",
  "name": "Main Specialty Code",
  "description": "NHS Data Dictionary - Main Specialty Code",
  "category": "nhs_dd",
  "source_type": "scrape",
  "is_custom": false,
  "is_global": true,
  "parent": null,
  "parent_name": null,
  "organization": null,
  "organization_name": null,
  "tags": ["medical", "specialty", "NHS"],
  "options": {
    "100": "General Surgery",
    "101": "Urology",
    "110": "Trauma & Orthopaedics",
    ...
  },
  "format_pattern": "code - description",
  "created_at": "2024-11-15T10:00:00Z",
  "updated_at": "2024-11-15T10:00:00Z",
  "last_synced_at": null,
  "last_scraped": "2024-11-16T05:00:00Z",
  "is_editable": false,
  "reference_url": "https://www.datadictionary.nhs.uk/data_elements/main_specialty_code.html"
}
```

### Get Available Tags

Get all tags with usage counts for filtering.

```http
GET /api/datasets/available-tags/
```

**Example:**

```bash
curl https://checktick.example.com/api/datasets/available-tags/
```

**Response:**

```json
[
  {"tag": "NHS", "count": 48},
  {"tag": "medical", "count": 35},
  {"tag": "paediatric", "count": 15},
  {"tag": "administrative", "count": 22},
  {"tag": "demographic", "count": 8}
]
```

## Permissions Summary

| Endpoint | Anonymous | Individual User | Team Member | Org Member |
|----------|-----------|-----------------|-------------|------------|
| List datasets | ❌ | Global + personal | Global + personal + own teams | Global + personal + own teams + own org |
| Get dataset detail | ❌ | Global + personal | Global + personal + own teams | Global + personal + own teams + own org |
| Available tags | ❌ | ✅ | ✅ | ✅ |

**Role Definitions:**

- **Individual User**: Authenticated user not part of any organisation or team
- **Team Member**: Sees datasets shared with their teams (all roles); only team ADMIN/CREATOR can manage them (via the web app)
- **Org Member**: Sees their organisation's datasets (all roles); only org ADMIN/CREATOR can manage them (via the web app)

Write operations (create, edit, clone, snapshot, delete) are web-app only — see the [dataset permissions table](/docs/datasets/) for who can do what, including the Pro-tier requirement for individual users. The read-only serializer includes `is_editable` and `can_publish` fields reflecting the current user's web-app permissions for each dataset, plus `team` / `team_name` for team-shared datasets.

## Error Responses

### 400 Bad Request

Invalid data or business logic violation:

```json
{
  "detail": "Cannot delete published dataset that has custom versions created by others"
}
```

### 403 Forbidden

Unauthenticated request, or a write method (the dataset API is read-only):

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 404 Not Found

Dataset doesn't exist or isn't accessible:

```json
{
  "detail": "Not found."
}
```

## Examples

### Find Paediatric Datasets

```bash
# Filter by tag and search
curl "https://checktick.example.com/api/datasets/?tags=paediatric&search=hospital" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Fetch a Dataset's Options

```bash
# Retrieve the full option list for a dataset by key
curl https://checktick.example.com/api/datasets/hospitals_england_wales/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

To create, customise, or manage datasets, use the web app: navigate to **Datasets** from the main menu. See [Datasets and Dropdowns](/docs/datasets-and-dropdowns/).

## Related Documentation

- [Datasets and Dropdowns](/docs/datasets-and-dropdowns/) - User guide for using datasets in surveys
- [API Overview](/docs/api/) - Authentication and general API info
- [Self-hosting Datasets](/docs/self-hosting-datasets/) - Setup and sync commands
