# Prefilled Datasets Feature - Setup Guide

## Overview

The prefilled datasets feature allows users to load dropdown options from multiple sources when creating survey questions:

1. **NHS Data Dictionary** - Standardized medical codes stored in the database
2. **RCPCH NHS Organisations API** - Live data from external API with caching
3. **Custom Lists** - User-created and organization-specific datasets

All datasets are stored in the `DataSet` model for consistency and fast access.

## Database Storage

### DataSet Model

All datasets are stored in `surveys_dataset` table with these key fields:

- `key` - Unique identifier (e.g., `main_specialty_code`)
- `name` - Display name shown in UI
- `category` - `nhs_dd`, `external_api`, `rcpch`, or `user_created`
- `source_type` - `manual`, `api`, or `import`
- `is_custom` - Whether dataset is user-created/modified
- `is_global` - Whether available to all organizations
- `parent` - Reference to NHS DD original if customized
- `organization` - Organization that owns this dataset (if not global)
- `options` - JSON array of option strings
- `last_synced_at` - When API dataset was last updated

### Seeding NHS DD Datasets

Pre-populate NHS Data Dictionary standards:

```bash
docker compose exec web python manage.py seed_nhs_datasets

# Or clear existing and re-seed
docker compose exec web python manage.py seed_nhs_datasets --clear
```

This creates read-only NHS DD datasets:
- Main Specialty Code (75 options)
- Treatment Function Code (73 options)
- Ethnic Category (17 options)

## External API Integration

### API Details

- **Base URL**: `https://api.rcpch.ac.uk/nhs-organisations/v1`
- **Authentication**: No API key required (public API)
- **Endpoints**:
  - `/organisations/limited` - Hospitals (England, Wales, and combined)
  - `/trusts` - NHS Trusts
  - `/local_health_boards` - Welsh Local Health Boards

### API Response Formats

#### Hospitals (`/organisations/limited`)
```json
[
  {
    "ods_code": "RGT01",
    "name": "ADDENBROOKE'S HOSPITAL"
  },
  {
    "ods_code": "RCF22",
    "name": "AIREDALE GENERAL HOSPITAL"
  }
]
```

#### NHS Trusts (`/trusts`)
```json
[
  {
    "ods_code": "RCF",
    "name": "AIREDALE NHS FOUNDATION TRUST",
    "address_line_1": "AIREDALE GENERAL HOSPITAL",
    "address_line_2": "SKIPTON ROAD",
    "town": "KEIGHLEY",
    "postcode": "BD20 6TD",
    "country": "ENGLAND",
    "telephone": null,
    "website": null,
    "active": true,
    "published_at": null
  }
]
```

#### Welsh Local Health Boards (`/local_health_boards`)
```json
[
  {
    "ods_code": "7A3",
    "boundary_identifier": "W11000031",
    "name": "Swansea Bay University Health Board",
    "organisations": [
      {
        "ods_code": "7A3LW",
        "name": "CHILD DEVELOPMENT UNIT"
      },
      {
        "ods_code": "7A3C7",
        "name": "MORRISTON HOSPITAL"
      }
    ]
  }
]
```

## Configuration

### Environment Variables

The following environment variables should be set in your `.env` file:

```bash
# External Dataset API Configuration
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk/nhs-organisations/v1
EXTERNAL_DATASET_API_KEY=  # Leave empty - no key required
```

These are already configured in `.env.example` with the correct defaults.

### Django Settings

The service layer (`checktick_app/surveys/external_datasets.py`) reads these settings with appropriate defaults:

- `EXTERNAL_DATASET_API_URL` - Defaults to RCPCH API
- `EXTERNAL_DATASET_API_KEY` - Defaults to empty string (no auth required)

## Available Datasets

The system supports 5 dataset types:

1. **hospitals_england** - Hospitals (England)
2. **hospitals_wales** - Hospitals (Wales)
3. **hospitals_england_wales** - Hospitals (England & Wales)
4. **nhs_trusts** - NHS Trusts
5. **welsh_lhbs** - Welsh Local Health Boards

**Note**: Currently all hospital datasets use the same endpoint (`/organisations/limited`) as the API doesn't provide country filtering in the limited response format. If country-specific filtering is needed, this can be implemented when the API supports it.

## Data Transformation

The service layer transforms API responses into user-friendly dropdown options:

- **Hospitals & Trusts**: `NAME (ODS_CODE)`
  Example: `ADDENBROOKE'S HOSPITAL (RGT01)`

- **Welsh LHBs**: Includes both the health board and its constituent organisations
  Example:
  - `Swansea Bay University Health Board (7A3)`
  - `  MORRISTON HOSPITAL (7A3C7)` (indented)

## Caching

- Dataset results are cached for **24 hours** using Django's cache framework
- Cache keys: `external_dataset:{dataset_key}`
- Cache is shared across all users (reference data)
- To clear cache manually, use `clear_dataset_cache(dataset_key)` from the service layer

## API Endpoints

### List Available Datasets
```
GET /api/datasets/
Authorization: Bearer <JWT_TOKEN>
```

Response:
```json
{
  "datasets": [
    {
      "key": "hospitals_england",
      "name": "Hospitals (England)"
    },
    ...
  ]
}
```

### Get Dataset Options
```
GET /api/datasets/{dataset_key}/
Authorization: Bearer <JWT_TOKEN>
```

Response:
```json
{
  "dataset_key": "hospitals_england",
  "options": [
    "ADDENBROOKE'S HOSPITAL (RGT01)",
    "AIREDALE GENERAL HOSPITAL (RCF22)",
    ...
  ]
}
```

Error responses:
- `400` - Invalid dataset key
- `502` - External API failure or invalid response format

## User Interface

### When to Show Prefilled Options

The "Use prefilled options" checkbox is only visible when:
- Question type is set to **dropdown** (single choice)

If the user changes the question type away from dropdown, the checkbox is automatically unchecked and the dataset selection is cleared.

### Loading Data

1. User checks "Use prefilled options"
2. User selects a dataset from the dropdown
3. User clicks "Load Options" button (primary color)
4. Button shows DaisyUI spinner: `<span class="loading loading-spinner loading-xs"></span> Loading...`
5. On success, options populate the textarea
6. On error, toast notification appears

## Testing

All 24 tests are passing, covering:

- Authentication requirements
- Permission checks (org admins, creators, viewers, and non-members)
- Error handling (invalid keys, external API failures)
- Caching behavior
- Response format validation

Run tests with:
```bash
docker compose exec web python -m pytest checktick_app/api/tests/test_dataset_api.py -v
```

## Next Steps

### 1. Question Persistence (Not Yet Implemented)

To save and restore prefilled dataset selections when editing questions:

**On Save:**
- Extract `dataset_key` from `optionsTextarea.dataset.prefilledDataset`
- Store in question's options JSON: `{"type": "prefilled", "dataset_key": "hospitals_england", "values": [...]}`

**On Edit:**
- Detect prefilled type in stored options
- Restore checkbox checked state
- Set dataset dropdown value
- Populate textarea with saved options

### 2. Testing with Real API

Test the complete flow:
1. Log in and create/edit a survey
2. Add a dropdown question
3. Check "Use prefilled options"
4. Select a dataset
5. Click "Load Options" (verify spinner appears)
6. Verify options populate correctly
7. Save the question
8. Edit the question again
9. Verify prefilled state is restored (when persistence is implemented)

## Troubleshooting

### API Connection Issues

If you see `502 Bad Gateway` errors:
- Check that `EXTERNAL_DATASET_API_URL` is correct
- Verify network connectivity to `api.rcpch.ac.uk`
- Check Django logs for detailed error messages

### Empty Options Lists

- Verify the API is returning data in the expected format
- Check the service layer transformation logic in `_transform_response_to_options()`
- Look for warning logs about skipped items

### Caching Issues

To force refresh from the API:
```python
from checktick_app.surveys.external_datasets import clear_dataset_cache

# Clear specific dataset
clear_dataset_cache("hospitals_england")

# Clear all datasets
clear_dataset_cache()
```

## Architecture

```
┌─────────────────┐
│   Frontend UI   │
│ (builder.js)    │
└────────┬────────┘
         │ Fetch /api/datasets/{key}/
         ▼
┌─────────────────┐
│  API Endpoint   │
│  (api/views.py) │
└────────┬────────┘
         │ Call fetch_dataset()
         ▼
┌─────────────────┐
│ Service Layer   │
│ (external_data  │
│  sets.py)       │
└────────┬────────┘
         │ HTTP GET
         ▼
┌─────────────────┐
│  RCPCH API      │
│  (External)     │
└─────────────────┘
```

## Files Modified

- `checktick_app/surveys/external_datasets.py` - Service layer with API integration
- `checktick_app/api/views.py` - API endpoints
- `checktick_app/api/urls.py` - URL routing
- `checktick_app/api/tests/test_dataset_api.py` - Comprehensive test suite
- `checktick_app/surveys/templates/surveys/group_builder.html` - UI components
- `checktick_app/static/js/builder.js` - Frontend logic with spinner
- `.env.example` - Configuration documentation
