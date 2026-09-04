---
title: Datasets Setup
category: self-hosting
priority: 5
---

This guide covers the setup and maintenance of datasets for self-hosted CheckTick instances.

## Overview

CheckTick provides five types of datasets for dropdown questions:

1. **NHS Data Dictionary** - standardised medical codes (scraped from NHS DD website)
2. **RCPCH NHS Organisations** - Organisational data (synced from RCPCH API)
3. **SNOMED CT** - Live clinical terminology served from a local snomed.db (optional — requires TRUD API key)
4. **Reference Data** - Geographic and administrative lists (static or synced from the ONS Open Geography Portal)
5. **User-Created** - Custom lists created by organisations

NHS DD, RCPCH and reference datasets are stored in the database for fast access. SNOMED CT options are served live from a local SQLite file on the `snomed-data` volume — no data is copied into Postgres.

## Dataset Catalogue

This is the **single reference table** for all built-in datasets. When adding a new dataset, add a row here.

### RCPCH NHS Organisations API (daily sync)

| Key | Name | Contents | Notes |
|---|---|---|---|
| `hospitals_england_wales` | Hospitals (England & Wales) | ~500 hospitals | ODS codes as keys |
| `nhs_trusts` | NHS Trusts | ~240 trusts | ODS codes as keys |
| `welsh_lhbs` | Welsh Local Health Boards | 7 boards + hospitals | ODS codes; indented hierarchy |
| `london_boroughs` | London Boroughs | 33 boroughs | GSS codes as keys |
| `nhs_england_regions` | NHS England Regions | 7 regions | ODS codes as keys |
| `paediatric_diabetes_units` | Paediatric Diabetes Units | ~175 units | PZ/ODS codes as keys |
| `integrated_care_boards` | Integrated Care Boards (ICBs) | 42 ICBs | ODS codes as keys |

### Static reference data (built locally, no network fetch)

| Key | Name | Contents | Notes |
|---|---|---|---|
| `countries_iso3166` | Countries (ISO 3166-1) | 249 countries | ISO alpha-2 codes as keys; built from the `pycountry` package at sync time |
| `uk_countries` | UK Countries | England, Scotland, Wales, Northern Ireland | ONS GSS codes as keys |

### ONS Open Geography Portal (monthly sync)

| Key | Name | Contents | ONS service | Fields | Notes |
|---|---|---|---|---|---|
| `uk_counties` | UK Counties (Ceremonial) | 218 areas (UK-wide) | `Counties_and_Unitary_Authorities_December_2023_Boundaries_UK_BUC` | `CTYUA23CD/NM` | GSS codes as keys |
| `local_authorities` | Local Authority Districts | 361 areas (UK-wide) | `Local_Authority_Districts_December_2023_Boundaries_UK_BUC` | `LAD23CD/NM` | GSS codes as keys |
| `upper_tier_authorities` | Upper Tier Local Authorities | 187 areas (UK-wide) | `Upper_Tier_Local_Authorities_December_2022_Boundaries_UK_BUC` | `UTLA22CD/NM` | Covers Scottish council areas and NI districts; Dec 2022 is the latest UK-wide release |
| `combined_authorities` | Combined Authorities | 10 areas (England) | `Combined_Authorities_December_2023_Boundaries_EN_BUC` | `CAUTH23CD/NM` | GSS codes as keys |
| `regions_england` | Regions of England | 9 regions (ITL1) | `Regions_December_2023_Boundaries_EN_BUC` | `RGN23CD/NM` | Statistical regions — differ from `nhs_england_regions` |

> **Bumping the ONS release:** ONS publishes boundary releases with versioned service names (e.g. the `December_2023` suffix and the `23CD/23NM` fields). When a new release is published, update the `service`, `code_field` and `name_field` entries in `ONS_DATASETS` in `checktick_app/surveys/external_datasets.py` and the table above. Service names can be browsed at <https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services> (owner: ONSGeography_data).

### Other sources

| Source | Storage | Sync |
|---|---|---|
| NHS Data Dictionary (`nhs_dd`) | 48 scraped datasets in Postgres | Weekly scrape |
| SNOMED CT (`snomed`) | 22 descriptors; options live from `snomed.db` | On TRUD release |
| User-created (`user_created`) | Postgres | — |

## Initial Setup

Run these commands once when first setting up your CheckTick instance.

### 1. Sync NHS Data Dictionary Datasets

Create NHS DD dataset records and scrape initial data in one command:

```bash
# Create datasets and scrape data from NHS DD website (takes 1-2 minutes)
docker compose exec web python manage.py sync_nhs_dd_datasets
```

This creates 48 NHS DD datasets including:

- Main Specialty Code (75 options)
- Treatment Function Code (73 options)
- Ethnic Category (17 options)
- Smoking Status Code (6 options)
- Clinical Frailty Scale (9 options)
- Plus 40+ additional standardised lists

See the [NHS DD Dataset Reference](nhs-data-dictionary-datasets.md) for the complete list.

### 2. Sync External API and Reference Datasets

Fetch organisational data from the RCPCH API and geographic reference data from ONS (creates datasets on first run):

```bash
# Fetch data from RCPCH API + ONS, build static datasets
# (takes 2-3 minutes, creates datasets automatically)
docker compose exec web python manage.py sync_external_datasets
```

This creates and populates 14 datasets:

- Hospitals (England & Wales) - ~500 hospitals
- NHS Trusts - ~240 trusts
- Welsh Local Health Boards - 7 boards
- London Boroughs - 33 boroughs
- NHS England Regions - 7 regions
- Paediatric Diabetes Units - ~175 units
- Integrated Care Boards - 42 ICBs
- Countries (ISO 3166-1) - 249 countries (built locally from `pycountry`)
- UK Countries - 4 countries (static)
- UK Counties (Ceremonial) - 218 areas (ONS)
- Local Authority Districts - 361 areas (ONS)
- Upper Tier Local Authorities - 187 areas (ONS)
- Combined Authorities - 10 areas (ONS)
- Regions of England - 9 regions (ONS)

See the [Dataset Catalogue](#dataset-catalogue) above for the full reference.

### 3. Seed SNOMED CT Datasets (Optional)

> **Requires**: `TRUD_API_KEY` and `SNOMED_DB_PATH` set, and `snomed.db` built by the `sct` binary.
> If SNOMED CT is not configured, skip this step — the command exits cleanly.

```bash
# Download UK Monolith and build snomed.db (~1.8 GB, takes several minutes)
docker compose exec web python manage.py update_snomed_db --force

# If snomed.db already exists on the volume, just seed the descriptors:
docker compose exec web python manage.py seed_snomed_datasets
```

This creates 22 curated SNOMED CT dataset descriptors, including:

- QOF drug lists (epilepsy, diabetes, AF, asthma/COPD)
- dm+d drug hierarchies (GLP-1 agonists, SGLT2 inhibitors, insulins, VTM, VMP)
- QOF disease registers (10 clinical areas)
- Common body sites and administration routes

**No SNOMED data is stored in Postgres.** The descriptor rows record the refset ID and query type; options are served live from `snomed.db` at request time via `SnomedResolver`.

See [SNOMED CT Integration](snomed-integration.md) for the full architecture and refset strategy.

## Scheduled Synchronization

CheckTick uses **three automated cron jobs** to keep datasets up-to-date:

1. **NHS Data Dictionary Scraping** - Scrapes NHS DD website for standardised codes
2. **External API Sync** - Syncs organisational data from the RCPCH API, geographic reference data from the ONS Open Geography Portal, and builds the static datasets (ISO countries, UK countries) locally
3. **SNOMED CT Update** *(optional)* - Checks TRUD for new releases and rebuilds snomed.db

Both NHS DD and RCPCH commands automatically create dataset records on first run, then update them on subsequent runs. No separate seeding commands needed.

### NHS Data Dictionary Sync

**Recommended schedule:** Weekly (Sundays at 5 AM UTC)

**What it does:**

- Reads dataset list from `docs/nhs-data-dictionary-datasets.md`
- Creates any new dataset records (if added to markdown)
- Scrapes NHS DD website for each dataset
- Updates options with latest codes and descriptions

```cron
0 5 * * 0 cd /app && python manage.py sync_nhs_dd_datasets
```

**Northflank setup:**

1. Create a new Cron Job service
2. Configure:
   - **Name**: `checktick-nhs-dd-sync`
   - **Schedule**: `0 5 * * 0` (weekly)
   - **Command**: `python manage.py sync_nhs_dd_datasets`
3. Copy environment variables from web service
4. Deploy

See [Self-hosting Scheduled Tasks](/docs/self-hosting-scheduled-tasks/) for full setup details.

### External API Sync

**Recommended schedule:** Daily (4 AM UTC)

**What it does:**

- Fetches latest organisational data from RCPCH API
- Updates hospitals, trusts, health boards, etc.
- Increments version numbers for change tracking

```cron
0 4 * * * cd /app && python manage.py sync_external_datasets
```

**Northflank setup:**

1. Create a new Cron Job service
2. Configure:
   - **Name**: `checktick-dataset-sync`
   - **Schedule**: `0 4 * * *` (daily)
   - **Command**: `python manage.py sync_external_datasets`
3. Copy environment variables from web service
4. Deploy

See [Self-hosting Scheduled Tasks](/docs/self-hosting-scheduled-tasks/) for full setup details.

## Management Commands

### sync_nhs_dd_datasets

**Combined seed + scrape command** - Reads dataset definitions from `docs/nhs-data-dictionary-datasets.md`, creates/updates records, and scrapes data from NHS DD website.

```bash
# Sync all datasets (create records + scrape data)
python manage.py sync_nhs_dd_datasets

# Sync a specific dataset
python manage.py sync_nhs_dd_datasets --dataset smoking_status_code

# Force re-scrape all datasets
python manage.py sync_nhs_dd_datasets --force

# Preview what would be synced (dry-run)
python manage.py sync_nhs_dd_datasets --dry-run
```

**Options:**

- `--dataset KEY` - Sync only a specific dataset
- `--force` - Re-scrape even if recently updated (default: skips if scraped within 7 days)
- `--dry-run` - Preview changes without saving

**What it does:**

1. Reads `docs/nhs-data-dictionary-datasets.md` and creates/updates dataset records
2. Fetches HTML from NHS DD website for each dataset
3. Parses tables/lists to extract codes and descriptions
4. Updates dataset options in database
5. Records `last_scraped` timestamp

**Example output:**

```text
📊 Found 48 dataset(s) to process

  Fetching: https://www.datadictionary.nhs.uk/data_elements/smoking_status_code.html
  Found 6 items
✓ Scraped: Smoking Status Code

  Fetching: https://www.datadictionary.nhs.uk/data_elements/ethnic_category.html
  Found 17 items
↻ Updated: Ethnic Category

============================================================
✓ Successfully scraped: 42
↻ Successfully updated: 6
============================================================
```

**When to use:**

- Initial setup (creates datasets from markdown and scrapes them)
- Scheduled weekly sync
- After NHS DD publishes updates
- Manual refresh of specific dataset

### sync_external_datasets

Sync external datasets from the RCPCH API and the ONS Open Geography Portal, and build the static reference datasets locally. **Automatically creates dataset records** if they don't exist.

```bash
# Sync all external datasets
python manage.py sync_external_datasets

# Sync a specific dataset
python manage.py sync_external_datasets --dataset hospitals_england_wales
python manage.py sync_external_datasets --dataset uk_counties
python manage.py sync_external_datasets --dataset countries_iso3166

# Force sync even if recently synced
python manage.py sync_external_datasets --force

# Preview changes without saving
python manage.py sync_external_datasets --dry-run
```

**Options:**

- `--dataset KEY` - Sync only a specific dataset (see the [Dataset Catalogue](#dataset-catalogue))
- `--force` - Bypass sync frequency check
- `--dry-run` - Preview without saving

**What it does:**

1. Creates dataset records if they don't exist (first run)
2. Fetches data from the RCPCH API (daily sync frequency) and ONS (monthly sync frequency)
3. Builds static datasets from local data (`countries_iso3166` via `pycountry`, `uk_countries`)
4. Transforms into CheckTick format (code → name)
5. Updates dataset options in database
6. Records `last_synced_at` timestamp and increments `version`
7. Static datasets are only updated when their options actually change, so frequent runs are cheap

> **Tip:** the command is safe to run daily on a cron. RCPCH datasets re-sync daily, ONS datasets only re-fetch when their 720-hour (monthly) frequency elapses, and static datasets are skipped when unchanged.

**When to use:**

- Initial setup (creates and populates datasets)
- Scheduled daily sync
- Manual refresh when RCPCH API updates

**Example output:**

```text
Syncing 7 external datasets...

✓ Synced: Hospitals (England & Wales) - 487 options (version 2)
✓ Synced: NHS Trusts - 238 options (version 2)
✓ Synced: Welsh Local Health Boards - 7 options (version 2)
⊝ Skipped: London Boroughs (synced 2 hours ago, next sync in 22 hours)
...

Summary:
✓ Synced: 5
⊝ Skipped: 2
✗ Errors: 0
```

**When to use:**

- Initial setup (creates and populates datasets)
- Scheduled daily sync
- Manual refresh when API data changes

## Configuration

### Environment Variables

#### RCPCH API Configuration

```bash
# Optional: Override RCPCH API URL
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk/nhs-organisations/v1

# Optional: Add API key if required in future
EXTERNAL_DATASET_API_KEY=your_api_key_here
```

**Defaults:**

- `EXTERNAL_DATASET_API_URL`: `https://api.rcpch.ac.uk/nhs-organisations/v1`
- `EXTERNAL_DATASET_API_KEY`: Not required (public API)

#### Sync Frequency

Configure in dataset model (via Django admin or database):

```python
# sync_frequency_hours field (default: 24)
dataset.sync_frequency_hours = 24  # Daily sync
dataset.save()
```

## Database Schema

### DataSet Model Fields

Key fields for dataset management:

```python
# Identity
key = CharField(max_length=255, unique=True)
name = CharField(max_length=255)
description = TextField(blank=True)
category = CharField(choices=[...])  # nhs_dd, rcpch, external_api, user_created

# Source tracking
source_type = CharField(choices=[...])  # manual, api, imported, scrape
reference_url = URLField(blank=True)  # Source URL for NHS DD datasets
api_endpoint = CharField(blank=True)  # API endpoint for external datasets

# Options storage
options = JSONField(default=dict)  # Key-value pairs

# Sync metadata
last_synced_at = DateTimeField(null=True)  # For API datasets
last_scraped = DateTimeField(null=True)  # For NHS DD datasets
sync_frequency_hours = IntegerField(default=24)
version = IntegerField(default=1)

# Sharing
is_custom = BooleanField(default=False)
is_global = BooleanField(default=False)
parent = ForeignKey('self', null=True)  # For custom versions
organisation = ForeignKey(Organisation, null=True)

# Discovery
tags = JSONField(default=list)
```

## Troubleshooting

### NHS DD Scraping Issues

**Problem:** Scraper can't find options on NHS DD page

```text
✗ Error scraping Smoking Status Code: No valid options found on the page
```

**Solutions:**

1. Check if NHS DD page structure changed:

   ```bash
   curl https://www.datadictionary.nhs.uk/data_elements/smoking_status_code.html
   ```

2. Update scraper parsing strategies in `sync_nhs_dd_datasets.py`

3. Report issue to development team

**Problem:** HTTP errors when fetching NHS DD pages

```text
✗ Error scraping: HTTPError 503 Service Unavailable
```

**Solutions:**

1. Wait and retry (NHS DD might be temporarily down)
2. Check NHS DD website status
3. Run with `--force` to retry specific datasets

### External API Sync Issues

**Problem:** RCPCH API connection errors

```text
✗ Error syncing: ConnectionError
```

**Solutions:**

1. Check RCPCH API status: <https://api.rcpch.ac.uk/>
2. Verify `EXTERNAL_DATASET_API_URL` environment variable
3. Check firewall/proxy settings
4. Retry with `--force`

**Problem:** API rate limiting

```text
✗ Error syncing: 429 Too Many Requests
```

**Solutions:**

1. Reduce sync frequency
2. Stagger sync commands (don't run all at once)
3. Contact RCPCH for rate limit increase

### Performance

**Problem:** Syncing takes too long

**Solutions:**

1. Sync specific datasets instead of all:

   ```bash
   python manage.py sync_external_datasets --dataset hospitals_england_wales
   ```

2. Increase worker timeout for cron jobs

3. Run syncs during low-traffic periods

## Monitoring

### Check Dataset Status

Via Django admin:

1. Navigate to `/admin/surveys/dataset/`
2. Filter by `category` or `source_type`
3. Check `last_synced_at` / `last_scraped` timestamps
4. Review `version` numbers for update history

Via API:

```bash
# Get all datasets with sync status
curl https://checktick.example.com/api/datasets-v2/ | jq '.results[] | {key, last_synced_at, last_scraped}'
```

### Audit Logs

Dataset updates are logged in the audit log:

```python
from checktick_app.surveys.models import AuditLog

# Check recent dataset updates
AuditLog.objects.filter(
    action__in=['dataset_synced', 'dataset_scraped']
).order_by('-timestamp')
```

## Related Documentation

- [Datasets and Dropdowns](/docs/datasets-and-dropdowns/) - User guide for using datasets in surveys
- [Dataset API Reference](/docs/api-datasets/) - API endpoints for developers
- [NHS DD Dataset Reference](/docs/nhs-data-dictionary-datasets/) - Complete NHS DD list
- [Scheduled Tasks](/docs/self-hosting-scheduled-tasks/) - Cron job setup

## Developer Guide: Adding New NHS DD Datasets

### Process Overview

To add a new NHS Data Dictionary dataset, you only need to add an entry to the markdown table in `nhs-data-dictionary-datasets.md`. The automated scraping process handles everything else.

### Step-by-Step Process

1. **Locate the NHS DD page** for the dataset you want to add
   - Visit [NHS Data Dictionary](https://www.datadictionary.nhs.uk/)
   - Find the specific data element or supporting information page
   - Copy the full URL

2. **Add entry to the markdown table**
   - Open `docs/nhs-data-dictionary-datasets.md`
   - Add a new row to the table under "Available NHS DD Datasets"
   - Format: `| Dataset Name | NHS DD URL | Categories | Date Added | Last Scraped | NHS DD Published |`

3. **Example entry:**

   ```markdown
   | Patient Discharge Method | [Link](https://www.datadictionary.nhs.uk/data_elements/patient_discharge_method_code.html) | administrative, clinic | 2025-11-16 | Pending | - |
   ```

4. **Choosing categories/tags:**
   - Use existing tags for consistency: `medical`, `administrative`, `demographic`, `clinic`, `paediatric`, etc.
   - Separate multiple tags with commas
   - Keep tags lowercase for consistency

5. **Commit your changes:**

   ```bash
   git add docs/nhs-data-dictionary-datasets.md
   git commit -m "Add [Dataset Name] to NHS DD datasets"
   git push
   ```

### What Happens Next

The automated sync process will:

1. **Detect the new entry** in the markdown file
2. **Create a database record** for the dataset
3. **Scrape the NHS DD page** to extract options
4. **Populate the dataset** with codes and descriptions
5. **Make it available** to all users immediately

This happens during the next scheduled cron job run (see [Scheduled Tasks](self-hosting-scheduled-tasks.md)).

### Manual Trigger (Optional)

To immediately sync the new dataset without waiting for the cron job:

```bash
# Sync the new dataset (creates record + scrapes data)
docker compose exec web python manage.py sync_nhs_dd_datasets
```

### Scraping Requirements

For successful scraping, the NHS DD page must:

- ✅ Be a standard data element or supporting information page
- ✅ Contain a table with codes and descriptions
- ✅ Use consistent NHS DD table structure
- ⚠️ Pages with non-standard formats may require custom scraping logic

If scraping fails, check the logs:

```bash
docker compose logs web | grep "scrape_nhs_dd"
```

### Testing Your Addition

After scraping:

1. **Via Web UI:**
   - Navigate to Datasets page
   - Filter by `nhs_dd` source type
   - Verify your new dataset appears
   - Check that options are populated correctly

2. **Via Django Admin:**

   ```text
   /admin/surveys/dataset/
   ```

   - Find your dataset
   - Verify `options` field has data
   - Check `last_scraped` timestamp

3. **Via API:**

   ```bash
   curl https://checktick.example.com/api/datasets/?category=nhs_dd
   ```

### Common Issues

**Problem:** Dataset created but options are empty

**Solution:** The scraping logic may need updating for this page's specific HTML structure. Check `checktick_app/surveys/management/commands/sync_nhs_dd_datasets.py` and add custom handling if needed.

**Problem:** Duplicate dataset entries

**Solution:** The seed command is idempotent. It won't create duplicates if a dataset with the same key already exists.

**Problem:** Dataset not appearing in UI

**Solution:**

- Verify `is_active=True` in database
- Check that `category` is set to `nhs_dd`
- Ensure `is_global=True`

### Contributing Back

After successfully adding and testing a new dataset:

1. **Update this documentation** if you encountered any edge cases
2. **Submit a PR** with your changes
3. **Share in GitHub Discussions** to let the community know about the new dataset
