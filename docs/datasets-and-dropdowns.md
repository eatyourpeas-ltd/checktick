---
title: Datasets and Dropdowns
category: features
priority: 5
---

When creating surveys, you often need validated dropdown lists of options. CheckTick's dataset system makes this easy by providing ready-to-use lists and the ability to create your own.

## Why Use Datasets?

Instead of manually typing options for every dropdown question, datasets let you:

- **Use standardised lists** from NHS Data Dictionary and RCPCH APIs
- **Ensure consistency** across multiple surveys
- **Save time** by reusing options
- **Customise global lists** to fit your organisation's specific needs
- **Share your lists** with the entire CheckTick community

## Types of Datasets

### Global Datasets

These are available to all CheckTick users:

- **NHS Data Dictionary**: 40+ standardised medical codes (specialties, ethnicities, smoking status, etc.)
- **RCPCH Organisations**: Hospitals, NHS Trusts, Health Boards, Diabetes Units
- **SNOMED CT Refsets**: Expert-curated clinical terminology lists (QOF drug lists, paediatric condition sets, and more)
- **Geography & Administration**: Countries (ISO 3166), UK countries, UK ceremonial counties, local authority districts, upper tier local authorities, combined authorities, regions of England, London boroughs, NHS England regions

> For the full list of built-in datasets — including the ONS sources and sync frequencies — see the [Dataset Catalogue](/docs/self-hosting-datasets/#dataset-catalogue) in the self-hosting guide.

### SNOMED CT Datasets

CheckTick integrates with SNOMED CT — the NHS standard clinical terminology — to provide expert-curated reference sets (refsets) as dropdown options. Unlike the full SNOMED drug dictionary or anatomy hierarchy, CheckTick only surfaces **validated refsets**: curated subsets assembled by clinical experts for a specific purpose.

Examples of supported refsets:

- QOF Antiepileptic Drug List
- QOF Diabetic Drug List
- QOF Asthma / COPD Drug List
- Paediatric Neurology & Neurodisability Disorders
- Paediatric Respiratory Conditions
- Paediatric Endocrine & Metabolic Conditions
- And more — see [SNOMED CT Integration](/docs/snomed-integration/) for the full list

SNOMED options are always fetched live from a local `snomed.db` database (the NHS TRUD UK Monolith Edition). When a respondent selects a SNOMED option, the stored value is the **SCTID** — a stable, unambiguous identifier that does not change when terminology is updated. The human-readable preferred term is recovered at any time from `snomed.db`.

> **Self-hosted instances**: SNOMED CT requires a separate setup step. See [SNOMED CT Integration](/docs/snomed-integration/) for installation instructions.

### Organisation Datasets

Created by your organisation and available only to your team members. Perfect for internal lists like:

- Local clinics or departments
- Custom classifications
- Organisation-specific codes

### Individual Datasets

Private datasets you create for your own use.

## Using Datasets in Your Survey

When creating a dropdown question:

1. Select the **Dropdown** or **Multi-choice** question type
2. Click **"Use Dataset"** instead of manually entering options
3. Browse or search for the dataset you need
4. The dropdown will automatically populate with the dataset options

> **Follow-ups with datasets:** per-option follow-up text inputs don't scale to long dataset lists. When options come from a dataset, the builder instead offers a single question-level toggle — **"Offer a follow-up text box after the options"** — which shows one optional free-text box below the answers once the respondent has made a selection. See [Follow-up Text Inputs](/docs/branching-and-repeats/#follow-up-text-inputs).

## Finding the Right Dataset

### Filter by Tag

Use tags to quickly find relevant datasets:

- `medical` - Clinical codes and classifications
- `administrative` - Organisational and administrative data
- `demographic` - Population and demographic information
- `paediatric` - Paediatric-specific datasets
- `NHS` - NHS-specific data
- `snomed` - SNOMED CT refsets

### Filter by Source

Filter by where the data comes from:

- `nhs_dd` - NHS Data Dictionary datasets
- `rcpch` - Royal College of Paediatrics data
- `snomed` - SNOMED CT expert-curated refsets
- `reference` - Geography and administrative reference data (ONS, ISO)
- `user_created` - Community-created datasets

### Search

Use the search box to find datasets by name or description.

## Creating Custom Datasets

> **Who can create datasets?** Individual users on a **Pro or higher** tier, team members with the **ADMIN** or **CREATOR** role, and organisation members with the **ADMIN** or **CREATOR** role. Read-only roles (**VIEWER**, **DATA_CUSTODIAN**) and FREE-tier individual users can browse and use datasets but cannot create, customise, or snapshot them. See the [permissions table](/docs/datasets/) for details.
>
> **Sharing:** when creating a dataset, choose **Personal** (only you), a **team** (visible to all team members), or an **organisation** (visible to all org members). A dataset can be shared with one team or one organisation, not both.
>
> **Downgrades:** if you downgrade from Pro to FREE, your existing datasets stay active and keep working in your surveys — you can still view and delete them, but you cannot edit them or create new ones until you upgrade again.

### Creating from Scratch

1. Navigate to **Datasets** from the main menu
2. Click **"Create New Dataset"**
3. Fill in the details:
   - **Name**: A clear, descriptive name
   - **Description**: What the dataset contains and when to use it
   - **Options**: Your key-value pairs (code: display name)
   - **Tags**: Help others find your dataset
   - **Organisation** (optional): Share with your team

4. Click **Create**

**Example - Local Clinics:**

```json
{
  "clinic_a": "Main Outpatient Clinic",
  "clinic_b": "Satellite Clinic - North",
  "clinic_c": "Satellite Clinic - South"
}
```

### Customizing a Global Dataset

If a global dataset is _almost_ what you need but requires modifications:

1. Find the global dataset
2. Click **"Create Custom Version"**
3. Modify the options as needed
4. Save to your organisation or personal workspace

**Example**: Customize the NHS hospital list to only include hospitals in your region.

### Snapshotting a SNOMED CT Dataset

SNOMED CT datasets are fetched live from `snomed.db`, so their options can change when the terminology is updated. If you need a **frozen** copy:

1. Open the SNOMED dataset
2. Click **"Snapshot to Custom Dataset"** (shown in place of "Create Custom Version" for SNOMED datasets)
3. A new custom dataset is created with the options fixed at snapshot time, linked back to the original refset

Snapshots follow the same permission rules as creating datasets: if you're an organisation ADMIN or CREATOR the snapshot belongs to your organisation; individual users get a personal dataset.

## Publishing Your Datasets

Once you've created a valuable dataset, consider sharing it with the community. Global publication is currently handled by the platform administrators — contact the CheckTick team (or open a GitHub issue) to request that your dataset be published globally.

### ⚠️ Important Publishing Rules

- **Cannot be deleted after publication** if others are using it
- **Can still be updated** to fix errors or add options
- **Organisation attribution** is preserved
- Only datasets owned by an **ADMIN** or **CREATOR** (or an individual user) are eligible

Think carefully before publishing - is this dataset useful to others? Is it complete and accurate?

## Managing Your Datasets

### Editing

You can edit datasets you created or have permissions for:

- Update the name and description
- Add or modify options
- Add tags
- **Cannot edit**: NHS DD datasets (maintained by automated sync)

### Deleting

You can delete your unpublished datasets anytime. Published datasets can only be soft-deleted if no other users are referencing them.

## API Access

Developers can read datasets programmatically through the API. The dataset API is **read-only** — creating and managing datasets is done through the web app. See the [Dataset API Reference](/docs/api-datasets/) for full details on:

- Listing and searching available datasets
- Fetching a dataset's options
- Listing available tags

## Contributing to the Community

### Request New NHS DD Datasets

If you need an NHS Data Dictionary list that isn't currently available:

1. Visit the [Datasets page](/surveys/datasets/)
2. Click **"Request NHS DD Dataset"**
3. Fill out the GitHub issue with:
   - Dataset name and NHS DD URL
   - Your use case
   - Suggested tags

See the full list of [available NHS DD datasets](/docs/nhs-data-dictionary-datasets/) and how to request new ones.

### Suggest Other Data Sources

Have an authoritative data source that would benefit the CheckTick community?

- **GitHub Issues**: For specific dataset requests
- **GitHub Discussions**: For broader conversations about new data sources

Visit [Getting Help](/docs/getting-help/) to learn about the difference and how to contribute.

## Best Practices

### Naming Conventions

- Use clear, descriptive names: `"UK Hospital Trusts"` not `"Trusts"`
- Include the scope: `"London Diabetes Units"` not `"Diabetes Units"`
- Be specific: `"Adult Main Specialties"` if not all specialties

### Organizing Options

- Use meaningful codes as keys: `"opt_a"` isn't helpful, `"diabetes"` is
- Keep display names consistent in style
- Order options logically (alphabetically or by frequency of use)

### Tagging

Add multiple relevant tags to help others find your dataset:

- Clinical area (e.g., `cardiology`, `mental-health`)
- Data type (e.g., `demographic`, `administrative`)
- Population (e.g., `paediatric`, `adult`)
- Organisation (e.g., `NHS`, `RCPCH`)

### Descriptions

Write helpful descriptions that explain:

- What the dataset contains
- When to use it
- Any limitations or special considerations

## Frequently Asked Questions

**Q: Can I use the same dataset in multiple surveys?**
A: Yes! That's one of the main benefits. Any changes to the dataset will automatically appear in all surveys using it.

**Q: What happens if a global dataset gets updated?**
A: Surveys using that dataset will automatically reflect the changes. If you need a frozen version, create a custom copy — or for SNOMED CT datasets, use **"Snapshot to Custom Dataset"**.

**Q: Can I share datasets between organisations?**
A: Not directly, but you can request global publication of your dataset to make it available to everyone, or the other organisation can create their own custom version of your published dataset.

**Q: How often are NHS DD datasets updated?**
A: They're automatically synchronized on a scheduled basis (typically weekly). You can see the last sync date on each dataset's detail page.

**Q: Can I delete options from my custom dataset?**
A: Yes, as long as it's not published and actively being used by others. Be careful with published datasets - removing options might break existing surveys.
