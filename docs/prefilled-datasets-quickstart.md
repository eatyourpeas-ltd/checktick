# Quick Start - Prefilled Datasets

## What Are Prefilled Datasets?

Prefilled datasets provide ready-to-use dropdown options for survey questions, saving time and ensuring consistency. CheckTick supports three types:

1. **NHS Data Dictionary** - Standardized medical codes (e.g., specialty codes, ethnic categories)
2. **External APIs** - Live data from RCPCH and other sources (e.g., hospitals, NHS trusts)
3. **Custom Lists** - Organization-specific lists you create

## What's Already Available ✅

### NHS Data Dictionary Datasets

Pre-loaded standardized codes:
- **Main Specialty Code** (75 options)
- **Treatment Function Code** (73 options)
- **Ethnic Category** (17 options)

### External API Datasets

Live data from RCPCH NHS Organisations API:
- **Hospitals (England & Wales)** (~2000 options)
- **NHS Trusts** (~200 options)
- **Welsh Local Health Boards** (~20 options)
- **London Boroughs** (33 options)
- **NHS England Regions** (7 options)
- **Paediatric Diabetes Units** (~200 options)
- **Integrated Care Boards** (42 options)

## Using Prefilled Datasets

### 1. Add a Dropdown Question

1. Log in to your CheckTick app
2. Create or edit a survey
3. Add a new question
4. Set type to **"Dropdown (single choice)"**

### 2. Load a Dataset

1. Check **"Use prefilled options"**
2. Select a dataset from the dropdown
3. Click **"Load Options"**
4. Options will populate automatically!

### 3. Optional: Customize

After loading, you can:
- Add extra options manually
- Remove unwanted options
- Reorder options
- The question will remember the source dataset for future updates

## Creating Custom Lists

### Quick Method: Django Admin

1. Navigate to `/admin/surveys/dataset/`
2. Click "Add Dataset"
3. Fill in:
   - **Key**: Unique ID (e.g., `our_departments`)
   - **Name**: Display name (e.g., "Our Departments")
   - **Category**: Select "User Created"
   - **Options**: Enter your list items
4. Save

Your custom list will immediately appear in the dataset selector!

### From NHS DD Template

Create a custom version of an NHS DD standard:

```python
# In Django shell: docker compose exec web python manage.py shell
from checktick_app.surveys.models import DataSet, Organization
from django.contrib.auth import get_user_model

User = get_user_model()

# Get NHS DD dataset
nhs_dd = DataSet.objects.get(key='main_specialty_code')

# Create customized version
user = User.objects.get(username='your_username')
org = Organization.objects.get(name='Your Hospital')
custom = nhs_dd.create_custom_version(user=user, organization=org)

# Modify as needed
custom.options = custom.options[:20]  # Keep only first 20
custom.name = "Our Specialty Codes"
custom.save()
```

## Format Examples

Datasets use consistent formatting:

**NHS DD & External APIs:**
```
General Surgery (100)
Urology (101)
ADDENBROOKE'S HOSPITAL (RGT01)
AIREDALE NHS FOUNDATION TRUST (RCF)
```

**Welsh LHBs (hierarchical):**
```
Swansea Bay University Health Board (7A3)
  MORRISTON HOSPITAL (7A3C7)
  SINGLETON HOSPITAL (7A3A6)
```

## Configuration

Your `.env` file needs these settings for external APIs:

```bash
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk/nhs-organisations/v1
EXTERNAL_DATASET_API_KEY=  # Leave empty (no key required)
```

These are already configured in `.env.example`.

## Key Features

**Database Storage**
- All datasets stored in database for consistency
- 24-hour cache for API data to minimize external calls
- Version tracking for dataset updates

**Organization Support**
- Global datasets available to all organizations
- Organization-specific custom lists
- NHS DD standards remain read-only

**Smart Integration**
- Database checked first for fastest response
- Falls back to API if data needs refresh
- Backward compatible with existing hardcoded datasets

## Status

**All core functionality is complete!** ✅

The system now:
- ✅ Stores datasets in database
- ✅ Fetches data from RCPCH API
- ✅ Supports NHS DD standardized codes
- ✅ Allows custom list creation
- ✅ Shows spinner during loading
- ✅ Saves dataset selection with questions
- ✅ Restores dataset selection when editing
- ✅ 29 passing tests covering all scenarios

## Related Documentation

- [Managing Datasets](./adding-external-datasets.md) - Full dataset management guide
- [Prefilled Datasets Setup](./prefilled-datasets-setup.md) - Technical configuration
- [Getting Started](./getting-started.md) - Environment setup
