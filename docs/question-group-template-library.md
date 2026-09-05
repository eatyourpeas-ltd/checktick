---
title: Question Bank Template Library
category: None
---

The template library lets you discover, browse, and import validated questionnaires and question collections into your surveys.

> **Tip:** When you [import a survey from a document](/docs/import/#import-from-document), CheckTick suggests templates that closely match the converted outline — for example, a document asking for job title and workplace will suggest the Professional details template. Template content is never added automatically; you choose whether to import it here.

> **Note:** For an overview of sections, see [Sections](/docs/groups-view/). To publish your own templates, see [Publishing Question Bank Templates](/docs/publish-question-groups/).

## Who can access

Any authenticated user can:

- Browse the global template library
- Search and filter templates
- Import templates into their surveys

Users can only import into surveys they own.

## Browsing templates

Access the library from:

- Survey dashboard: "Browse the Question Bank" button
- Direct URL: `/surveys/templates/`

The library shows:

- **Template name**: Title of the section
- **Description**: Brief overview of what the template measures
- **Questions**: Number of questions in the template
- **Language**: Primary language of the template
- **Level**: Publication level (Global or Organisation)
- **Imports**: Count of how many times the template has been imported
- **Attribution**: Icon indicating if the template has formal attribution (authors, citations)

## Searching and filtering

### Search

- Search box finds matches in template name, description, and tags
- Search is case-insensitive and matches partial words

### Filters

- **Language**: Filter by language code (en, cy, fr, etc.)
- **Publication Level**: Show only Global or Organisation templates
- **Order by**: Sort by name, imports, or date created

### Tags

- Click any tag to filter templates by that category
- Common tags: PHQ-9, GAD-7, Depression, Anxiety, Screening, etc.

## Importing templates

### Import workflow

1. **Select a template**: Click "Import" dropdown button in the template list or "View Details" to see more information
2. **Choose a survey**: Select which survey to import the template into from the dropdown menu
3. **Confirm import**: Review the template details and confirm the import

### What gets imported

When you import a template:

- **All questions** from the template are imported as a complete section
- Questions maintain their original:
  - Question text and help text
  - Question type and options
  - Required/optional status
  - Order within the group
- The section is added to your survey
- You can edit or delete individual questions after import

### Important notes

- **Complete groups**: Templates import as complete sections. Validated instruments (like PHQ-9, GAD-7) should be used in their entirety for clinical validity.
- **Editable after import**: You can modify questions after import, but be aware this may affect the validity of standardised instruments.
- **Attribution preserved**: If the template has attribution (authors, citations, licenses), this information is preserved with the imported section.
- **No republishing**: You cannot republish sections that were imported from templates. This protects copyright and prevents circular attribution issues.

## Template details page

Click "View Details" on any template to see:

- Full description
- Complete question preview in markdown format
- Publisher information
- Attribution details (if applicable):
  - Authors
  - Title of original work
  - Year published
  - Citations
  - License information
  - Original URL
- Import button with survey selector
- Delete option (if you published the template)

## Attribution

Some templates represent published, validated instruments (e.g., PHQ-9, GAD-7). These templates include:

- **Authors**: Original developers of the instrument
- **Citation**: How to cite the original work
- **License**: Usage rights and restrictions
- **URL**: Link to original publication or licensing information

When you import an attributed template:

- Attribution information is preserved
- You should cite the original work in any publications
- Check the license for usage restrictions
- The publisher credit shows who published the template to CheckTick, separate from the original authors

## Publishing your own templates

Organisation admins can publish sections from their surveys as templates. Published templates can be:

- **Organisation-level**: Visible only to your organisation members
- **Global**: Visible to all CheckTick users

For detailed instructions on publishing templates, including attribution requirements and copyright protection, see [Publishing Question Bank Templates](/docs/publish-question-groups/).

## Specialist templates vs. section templates

The template library contains **section templates** - complete questionnaires with multiple questions. This is different from **specialist templates** (Patient Details, Professional Details) which are:

- Single composite questions with multiple fields
- Added individually through the "Special Templates" tab in the question builder
- Not imported from the library
- Used for collecting structured data sets (demographics, professional information)

### Address lookup (UK postcode → address prefill)

Both specialist templates can optionally collect a full address. In the template's "Configure template fields" panel, enable **Address lookup**:

- **Patient Details**: requires the "Post code" field to be selected (the same field also powers the optional IMD lookup).
- **Professional Details**: adds a postcode field plus address fields to the template.

Respondents enter their postcode and click **Find address**; matching addresses are shown in a dropdown and the address fields (line 1, line 2, town/city, county) are prefilled. The fields always remain editable, so manual entry works when:

- The postcode isn't found (e.g. Northern Ireland `BT` and Channel Islands `GY`/`JE` postcodes are not covered)
- The lookup service is unavailable or not configured

> **Note:** the open postcodes.io service (and the RCPCH postcode API, which mirrors it) only provides **postcode metadata** — district, ward, IMD, coordinates. It does **not** include delivery-point addresses. For full address prefill, set `OSDATAHUB_API_URL` / `OSDATAHUB_API_KEY` to the **OS Places API** (e.g. `https://api.os.uk/search/places/v1/` — any URL under `search/places/v<n>/` is normalised to the `postcode` endpoint at call time, and the key is appended per-request, so no need to embed it in the URL). Both postcodes.io-style and OS Places DPA-style responses are supported. The lookup is proxied through CheckTick (respondents never call the API directly) and rate limited; without an address-capable source the widget still supports manual entry.

## Troubleshooting

### "No surveys available" message

- You need to create at least one survey before you can import templates
- Go to the survey dashboard and click "Create New Survey"

### Import button disabled

- Ensure you're logged in
- Check that you own at least one survey
- Verify the template hasn't been deleted

### Cannot find a template

- Check your search terms and filters
- Try clearing all filters
- Some templates may be organisation-level and only visible to specific users

### Questions appear in wrong order

- Questions are imported in the order defined in the template
- You can reorder questions after import using the builder
- Use the Sections page to reorder entire sections

## Related documentation

- [Sections](/docs/groups-view/) - Overview and managing sections
- [Publishing Bank Templates](/docs/publish-question-groups/) - How to publish templates
- [Global Templates Index](/docs/question-group-templates-index/) - List of available global templates
- [Surveys](/docs/surveys/) - Creating and managing surveys
- [Collections](/docs/collections/) - Using repeats for multiple entries
