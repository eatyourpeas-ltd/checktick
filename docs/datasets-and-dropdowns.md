# Datasets and Dropdowns

When creating surveys, you often need validated dropdown lists of options. CheckTick's dataset system makes this easy by providing ready-to-use lists and the ability to create your own.

## Why Use Datasets?

Instead of manually typing options for every dropdown question, datasets let you:

- **Use standardized lists** from NHS Data Dictionary and RCPCH APIs
- **Ensure consistency** across multiple surveys
- **Save time** by reusing options
- **Customize global lists** to fit your organization's specific needs
- **Share your lists** with the entire CheckTick community

## Types of Datasets

### Global Datasets

These are available to all CheckTick users:

- **NHS Data Dictionary**: 40+ standardized medical codes (specialties, ethnicities, smoking status, etc.)
- **RCPCH Organizations**: Hospitals, NHS Trusts, Health Boards, Diabetes Units
- **Administrative**: UK counties, London boroughs, NHS regions

### Organization Datasets

Created by your organization and available only to your team members. Perfect for internal lists like:

- Local clinics or departments
- Custom classifications
- Organization-specific codes

### Individual Datasets

Private datasets you create for your own use.

## Using Datasets in Your Survey

When creating a dropdown question:

1. Select the **Dropdown** or **Multi-choice** question type
2. Click **"Use Dataset"** instead of manually entering options
3. Browse or search for the dataset you need
4. The dropdown will automatically populate with the dataset options

## Finding the Right Dataset

### Filter by Tag

Use tags to quickly find relevant datasets:

- `medical` - Clinical codes and classifications
- `administrative` - Organizational and administrative data
- `demographic` - Population and demographic information
- `paediatric` - Pediatric-specific datasets
- `NHS` - NHS-specific data

### Filter by Source

Filter by where the data comes from:

- `nhs_dd` - NHS Data Dictionary datasets
- `rcpch` - Royal College of Paediatrics data
- `user_created` - Community-created datasets

### Search

Use the search box to find datasets by name or description.

## Creating Custom Datasets

### Creating from Scratch

1. Navigate to **Datasets** from the main menu
2. Click **"Create New Dataset"**
3. Fill in the details:
   - **Name**: A clear, descriptive name
   - **Description**: What the dataset contains and when to use it
   - **Options**: Your key-value pairs (code: display name)
   - **Tags**: Help others find your dataset
   - **Organization** (optional): Share with your team

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

If a global dataset is *almost* what you need but requires modifications:

1. Find the global dataset
2. Click **"Create Custom Version"**
3. Modify the options as needed
4. Save to your organization or personal workspace

**Example**: Customize the NHS hospital list to only include hospitals in your region.

## Publishing Your Datasets

Once you've created a valuable dataset, consider sharing it with the community:

1. Open your dataset
2. Click **"Publish Globally"**
3. Confirm publication

### ⚠️ Important Publishing Rules

- **Cannot be deleted after publication** if others are using it
- **Can still be updated** to fix errors or add options
- **Organization attribution** is preserved
- Only **ADMIN** or **CREATOR** roles can publish

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

Developers can access datasets programmatically through the API. See the [Dataset API Reference](/docs/api-datasets/) for full details on:

- Listing available datasets
- Creating datasets via API
- Updating dataset options
- Publishing and managing datasets

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
- Organization (e.g., `NHS`, `RCPCH`)

### Descriptions

Write helpful descriptions that explain:

- What the dataset contains
- When to use it
- Any limitations or special considerations

## Frequently Asked Questions

**Q: Can I use the same dataset in multiple surveys?**
A: Yes! That's one of the main benefits. Any changes to the dataset will automatically appear in all surveys using it.

**Q: What happens if a global dataset gets updated?**
A: Surveys using that dataset will automatically reflect the changes. If you need a frozen version, create a custom copy.

**Q: Can I share datasets between organizations?**
A: Not directly, but you can publish your dataset globally to make it available to everyone, or the other organization can create their own custom version of your published dataset.

**Q: How often are NHS DD datasets updated?**
A: They're automatically synchronized on a scheduled basis (typically weekly). You can see the last sync date on each dataset's detail page.

**Q: Can I delete options from my custom dataset?**
A: Yes, as long as it's not published and actively being used by others. Be careful with published datasets - removing options might break existing surveys.
