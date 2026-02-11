---
title: Using Datasets (Legacy)
category: None
---

Datasets provide ready-to-use dropdown options for survey questions, saving time and ensuring consistency. CheckTick offers three types of datasets that power your dropdown fields.

## Overview

Instead of manually typing dropdown options for every survey question, you can:

- **Use global datasets** from NHS Data Dictionary and RCPCH APIs
- **Request new datasets** from authoritative sources
- **Create custom lists** tailored to your organisation
- **Publish your lists** to share with the entire CheckTick community
- **Customize global datasets** to fit your specific needs

## Global Dataset Sources

CheckTick maintains three types of global datasets that are available to all users:

### 1. NHS Data Dictionary (NHS DD)

Authoritative medical codes and classifications from the [NHS Data Dictionary](https://www.datadictionary.nhs.uk/).

**Available datasets include:**
- Main Specialty Code (75 options)
- Treatment Function Code (73 options)
- Ethnic Category (17 options)
- Smoking Status Code (6 options)
- Clinical Frailty Scale (9 options)
- Plus 40+ additional standardized lists

**Characteristics:**
- ✅ Regularly synced from NHS DD website
- ✅ Read-only (maintains standardization)
- ✅ Full transparency with source URLs
- ✅ Can be used as templates for custom versions

See the [complete NHS DD dataset reference](nhs-data-dictionary-datasets.md) for the full list with source URLs and update dates.

### 2. RCPCH NHS Organisations

Organisational data automatically synced from the Royal College of Paediatrics and Child Health API:

- Hospitals (England & Wales) - ~500 hospitals
- NHS Trusts - ~240 trusts
- Welsh Local Health Boards - 7 health boards
- London Boroughs - 33 boroughs
- NHS England Regions - 7 regions
- Paediatric Diabetes Units - ~175 units
- Integrated Care Boards - 42 ICBs

**Characteristics:**
- ✅ Automatically updated daily
- ✅ Reliable, maintained data
- ✅ Offline-capable (cached in database)
- ✅ Can be used as templates

### 3. Community-Published Datasets

Curated lists shared by other organisations using CheckTick:

- Department-specific codes
- Specialty classifications
- Research cohort categories
- Regional resource lists

**Characteristics:**
- ✅ Created by the community
- ✅ Tagged for easy discovery
- ✅ Can be used as templates
- ✅ You can publish your own

### Requesting New Global Datasets

If you need an NHS DD list or other standardized dataset that isn't available:

1. Navigate to the **Datasets** page in CheckTick
2. Click **"Request New Dataset"**
3. Fill out the request form with:
   - Dataset name and source URL
   - Your use case
   - Suggested categorization tags
4. The development team will review and add it if:
   - The data is from an authoritative source
   - It can be reliably scraped or synced
   - It benefits the broader community

**Response time:** Typically reviewed within 1-2 weeks. Check the GitHub issue for status updates.

## Using Datasets in Surveys

### Adding a Dropdown with a Dataset

1. Create or edit a survey
2. Add a new question
3. Set type to **"Dropdown (single choice)"**
4. Check **"Use prefilled options"**
5. Browse or search for a dataset
6. Click **"Load Options"**

The dropdown will populate with all options from that dataset.

### Filtering and Search

Use the dataset selector to:
- **Filter by tags**: Click tag badges to filter by category (e.g., "medical", "administrative")
- **Search by name**: Type keywords to find specific datasets
- **View details**: See source, last updated, and number of options

## Creating Custom Datasets

You have two approaches for creating custom datasets:

### Option 1: Start from Scratch

Best for completely unique lists specific to your organisation.

**Steps:**
1. Navigate to Django Admin → Datasets
2. Click "Add Dataset"
3. Fill in:
   - **Name**: Display name (e.g., "Our Department Codes")
   - **Key**: Auto-generated unique identifier
   - **Category**: User Created
   - **Options**: Enter your list items
   - **Tags**: Add tags for discovery (optional)
4. Save

Your dataset immediately appears in the dropdown selector.

### Option 2: Customize a Global Dataset

Best when you want to modify an existing global dataset (NHS DD, RCPCH, or community-published).

**Steps:**
1. Find the global dataset you want to customize
2. Click **"Create Custom Version"**
3. Give it a new name (e.g., "Regional Hospitals")
4. The dataset is created with all options from the original
5. Edit to:
   - Remove unwanted options
   - Add custom options
   - Reorder items
6. Save

**Benefits:**
- Start with quality, standardized data
- Your changes don't affect the original
- Create multiple variants for different purposes

**Example:** Create "London Hospitals" from the global "Hospitals (England & Wales)" dataset by removing non-London entries.

## Publishing Datasets Globally

Share your curated lists with the entire CheckTick community.

### When to Publish

Consider publishing when you've created a dataset that:
- Would benefit other organisations
- Is high-quality and well-maintained
- Represents authoritative or curated data for a specific domain
- Fills a gap in existing global datasets

### How to Publish

1. Create and refine your dataset
2. Add descriptive tags for discovery
3. Write a clear description explaining the use case
4. Click **"Publish Globally"**

**What happens:**
- Your dataset becomes visible to all CheckTick users
- Your organisation is credited as the source
- Others can use it directly or create custom versions
- You retain full editing rights
- The dataset cannot be deleted while others depend on it

### Best Practices for Publishing

1. **Use descriptive names**: "London Teaching Hospitals" not "Hospital List 1"
2. **Add meaningful tags**: Help others discover your dataset (e.g., "regional", "teaching-hospitals", "london")
3. **Write clear descriptions**: Explain the purpose, scope, and any limitations
4. **Verify accuracy**: Double-check all entries before publishing
5. **Plan for maintenance**: Commit to keeping it updated if the data changes

## Tags and Discovery

Tags help organize and find datasets quickly.

### Common Tag Categories

- **Medical specialty**: `paediatrics`, `cardiology`, `oncology`
- **Data type**: `hospitals`, `codes`, `demographic`
- **Source**: `NHS`, `curated`, `research`
- **Region**: `england`, `wales`, `london`
- **Clinical domain**: `maternity`, `mental-health`, `neonatal`

### Using Tags

- **Click tags to filter**: On the datasets page, click any tag badge to show only datasets with that tag
- **Combine filters**: Click multiple tags to narrow results (uses AND logic)
- **See tag counts**: The tag selector shows how many datasets match each tag

## Permissions

| Action | Individual Users | Org VIEWER | Org CREATOR/ADMIN |
|--------|-----------------|------------|-------------------|
| View global datasets | ✅ | ✅ | ✅ |
| View org datasets | ❌ | ✅ (own org) | ✅ (own org) |
| Create datasets | ✅* | ❌ | ✅ |
| Edit own datasets | ✅ | ❌ | ✅ (own org) |
| Delete own datasets | ✅** | ❌ | ✅ (own org)** |
| Create custom versions | ✅* | ❌ | ✅ |
| Publish globally | ✅* | ❌ | ✅ (own org) |

*Individual users can create, customize, and publish datasets. In future releases, this will require a pro account.

**Cannot delete if published with dependents from other organisations

**Role clarifications:**

- **VIEWER**: Read-only access - can view datasets but cannot create or modify
- **CREATOR/ADMIN**: Full dataset management capabilities for their organisation

## Related Documentation

- **[NHS DD Dataset Reference](nhs-data-dictionary-datasets.md)** - Complete list with source URLs
- **[Dataset API Reference](api-datasets.md)** - API endpoints for programmatic access
- **[Self-hosting Setup](self-hosting-datasets.md)** - Initial setup and sync commands

## Getting Help

If you have questions about datasets:

1. Check this documentation
2. Review the [API examples](api-datasets.md)
3. Ask in [Discussions](https://github.com/eatyourpeas/checktick/discussions)
4. Report issues in [Issues](https://github.com/eatyourpeas/checktick/issues)
