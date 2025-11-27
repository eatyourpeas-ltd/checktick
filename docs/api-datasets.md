---
title: Dataset API Reference
category: api
priority: 3
---

This document covers the Dataset API endpoints for programmatic access to dataset management.

## Base URL

```
/api/datasets/
```

## Authentication

All write operations require JWT authentication. See [API Documentation](/docs/api/) for authentication details.

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

### Create Custom Version

Create a customized copy of a global dataset.

```http
POST /api/datasets/{key}/create-custom/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Our Custom Hospital List",
  "organization": 123
}
```

**Requirements:**

- User must be ADMIN or CREATOR in the organization
- Source dataset must be global (is_global=True)

**Example:**

```bash
curl -X POST https://checktick.example.com/api/datasets/hospitals_england_wales/create-custom/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "London Hospitals (Custom)",
    "organization": 5
  }'
```

**Response:**

```json
{
  "key": "hospitals_england_wales_custom_5_1731744000",
  "name": "London Hospitals (Custom)",
  "description": "Custom version of Hospitals (England & Wales)",
  "category": "user_created",
  "source_type": "manual",
  "is_custom": true,
  "is_global": false,
  "parent": "hospitals_england_wales",
  "parent_name": "Hospitals (England & Wales)",
  "organization": 5,
  "organization_name": "Our Organization",
  "tags": ["hospitals"],
  "options": {
    "RXX01": "Guy's Hospital",
    "RXX02": "Royal London Hospital",
    ...
  },
  "is_editable": true
}
```

You can now edit this dataset without affecting the original.

### Update Dataset

Update a dataset you own (organization-owned or user-created).

```http
PATCH /api/datasets/{key}/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Name",
  "description": "Updated description",
  "tags": ["new", "tags"],
  "options": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

**Restrictions:**

- Cannot update NHS DD datasets (read-only)
- Can only update datasets your organization owns
- User must be ADMIN or CREATOR

**Example:**

```bash
curl -X PATCH https://checktick.example.com/api/datasets/our_custom_list/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "options": {
      "RXX01": "Guy'\''s Hospital",
      "RXX03": "St Thomas'\'' Hospital"
    }
  }'
```

### Publish Dataset Globally

Make an organization-owned dataset available to all users.

```http
POST /api/datasets/{key}/publish/
Authorization: Bearer <token>
```

**Requirements:**

- User must be ADMIN or CREATOR in the dataset's organization
- Dataset must be organization-owned (not already global)
- Cannot publish NHS DD datasets

**Example:**

```bash
curl -X POST https://checktick.example.com/api/datasets/our_specialty_codes/publish/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**

```json
{
  "key": "our_specialty_codes",
  "name": "Our Specialty Codes",
  "is_global": true,
  "published_at": "2024-11-16T14:30:00Z",
  "organization": 5,
  "organization_name": "Our Organization"
}
```

Once published:

- Dataset becomes visible to all users
- Organization retains attribution and edit rights
- Cannot be deleted while others have created custom versions from it

### Delete Dataset

Soft-delete a dataset you own.

```http
DELETE /api/datasets/{key}/
Authorization: Bearer <token>
```

**Restrictions:**

- Cannot delete NHS DD datasets
- Cannot delete published datasets if others have created custom versions from them
- User must be ADMIN or CREATOR

**Example:**

```bash
curl -X DELETE https://checktick.example.com/api/datasets/old_custom_list/ \
  -H "Authorization: Bearer YOUR_TOKEN"
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

| Endpoint | Anonymous | Individual User | Org VIEWER | Org CREATOR/ADMIN |
|----------|-----------|-----------------|------------|-------------------|
| List datasets | ❌ | Global + own | Global + org | Global + org |
| Get dataset detail | Global only | Global + own | Global + org | Global + org |
| Create dataset | ❌ | ✅ | ❌ | ✅ (for org) |
| Create custom version | ❌ | ✅ | ❌ | ✅ |
| Update dataset | ❌ | ✅ (own only) | ❌ | ✅ (own org) |
| Publish dataset | ❌ | ✅ (own only) | ❌ | ✅ (own org) |
| Delete dataset | ❌ | ✅ (own only) | ❌ | ✅ (own org) |

**Role Definitions:**

- **Individual User**: Authenticated user not part of any organization
- **Org VIEWER**: Read-only access to organization datasets
- **Org CREATOR/ADMIN**: Full dataset management for their organization

**Note:** Dataset creation and management is not subject to tier limits. All authenticated users can create custom datasets for their own use.

## Error Responses

### 400 Bad Request

Invalid data or business logic violation:

```json
{
  "detail": "Cannot delete published dataset that has custom versions created by others"
}
```

### 403 Forbidden

Insufficient permissions:

```json
{
  "detail": "You do not have permission to modify NHS Data Dictionary datasets"
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

### Create a Custom Regional Hospital List

```bash
# 1. Find the global hospitals dataset
curl https://checktick.example.com/api/datasets/hospitals_england_wales/

# 2. Create a custom version
curl -X POST https://checktick.example.com/api/datasets/hospitals_england_wales/create-custom/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "North West Hospitals",
    "organization": 5
  }'

# Response includes new key: hospitals_england_wales_custom_5_1731744000

# 3. Update to include only North West hospitals
curl -X PATCH https://checktick.example.com/api/datasets/hospitals_england_wales_custom_5_1731744000/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "options": {
      "RW3XX": "Royal Manchester Children'\''s Hospital",
      "RW6XX": "Alder Hey Children'\''s Hospital"
    },
    "tags": ["hospitals", "northwest", "paediatric"]
  }'
```

### Publish a Curated List

```bash
# 1. Create your dataset
curl -X POST https://checktick.example.com/api/datasets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "specialty_codes_cardiology",
    "name": "Cardiology Specialty Codes",
    "category": "user_created",
    "description": "Curated list of cardiology-related specialty codes",
    "tags": ["cardiology", "specialty", "curated"],
    "options": {
      "320": "Cardiology",
      "321": "Paediatric Cardiology",
      "325": "Cardiac Surgery"
    },
    "organization": 5
  }'

# 2. Publish globally to share with community
curl -X POST https://checktick.example.com/api/datasets/specialty_codes_cardiology/publish/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Related Documentation

- [Datasets and Dropdowns](/docs/datasets-and-dropdowns/) - User guide for using datasets in surveys
- [API Overview](/docs/api/) - Authentication and general API info
- [Self-hosting Datasets](/docs/self-hosting-datasets/) - Setup and sync commands
