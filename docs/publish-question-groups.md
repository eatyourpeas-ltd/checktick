---
title: Publishing Question Bank Templates
category: None
---

This guide explains how to publish your sections as reusable templates that can be shared with your organisation.

> **Note:** For an overview of sections and their features, see [Sections](/docs/groups-view/). To browse and import templates, see [Question Bank Template Library](/docs/question-group-template-library/).

## Publication Levels

### Organisation Templates

Publish templates visible only to your organisation members:

- Share validated questionnaires within your team
- Maintain consistent data collection across projects
- Available immediately after publishing

### Global Templates (curated — admin-only)

Global templates are visible to all CheckTick users, but they are **curated, not self-published**. There is no user-facing option to publish globally: global instruments are added by CheckTick and ship with the product from [`docs/question-group-templates/`](/docs/question-group-templates-index/).

If you would like an instrument added to the global Question Bank, [submit it for review](/docs/question-group-template-library/#submitting-an-instrument-for-review). Global publication is only possible where copyright already permits it (openly licensed, out of copyright) or where the submitter is the rights holder and happy to share it without restriction. Third-party instruments without permission are rejected at review.

## Publishing a section

1. Go to your survey's Sections page
2. Click **Share as template** (labelled **Publish to Question Bank** in some views) next to any section
3. Add attribution information:
   - Author names and ORCID IDs (optional)
   - Publication title and journal
   - DOI and PubMed ID (if applicable)
   - Copyright and license information
4. Add tags for discoverability
5. Preview the markdown representation
6. Confirm publication

The action still creates a `PublishedQuestionGroup` and uses the `question_group_publish` view — only the user-facing label has changed from "Publish" to "Share as template" / "Publish to Question Bank".

**Note:** Publishing requires the survey to belong to an organisation — templates are published at organisation level only. On a personal (non-organisation) survey the publish action is hidden with guidance to link the survey to an organisation. Importing global templates from the Question Bank is unaffected and available to any authenticated user.

**Rate limit:** 10 publications per day per user

## Browsing Templates

Access the template library from:

- Survey Sections page: **Browse & Import Templates** button
- Outline page: Link in the information banner

Filter templates by:

- Publication level (Organisation/Global)
- Tags (categories)
- Search by name or description

## Importing Templates

1. Browse the template library
2. Click on a template to view details
3. Review the markdown and attribution
4. Click **Import into Survey**
5. Select which survey to import into
6. The section is added to your survey
7. Customize as needed in the builder

**Rate limit:** 50 imports per hour per user

**Note:** Imported sections are independent copies. Changes to your copy don't affect the original template or other imports.

## Managing Your Published Templates

View your published templates in the template library filtered by your organisation or username (coming soon).

To update a template:

- Make changes to your original section
- Publish again with the same slug (existing template is updated)

To delete a template:

- Access the template detail page
- Click **Delete Template**
- Confirm deletion

**Note:** Deleting a template doesn't affect sections that were imported from it.

## Attribution and Copyright

When publishing templates containing copyrighted or validated instruments:

### Required Information

- Complete author list with affiliations
- Full publication citation (journal, year, DOI, PMID)
- Copyright notice
- License or permissions

### Best Practices

- Only publish instruments you have rights to distribute
- Prefer public domain or openly licensed instruments
- Include all required copyright attributions
- Link to original sources via DOI/PMID
- Use ORCID IDs to properly credit authors

### Public Domain and Open Instruments

Many validated questionnaires are in the public domain or have open licenses:

- Instruments developed with government funding (e.g., NIMH)
- Explicitly open-licensed scales
- Historical instruments where copyright has expired

Always verify the copyright status before publishing.

## Global Template Repository

Curated global templates are maintained in the project repository at `docs/question-group-templates/`. These templates are:

- Validated instruments with published psychometric properties
- Properly licensed for distribution
- Automatically synced to all Checktick deployments
- Version controlled via Git

See the [Global Templates Index](/docs/question-group-templates-index/) for the complete list of available templates.

### Contributing Global Templates

Global templates are **curated**: they are added by CheckTick after review, not published directly by users. To propose an instrument, see [Submitting an instrument for review](/docs/question-group-template-library/#submitting-an-instrument-for-review).

Open-source contributors who prefer GitHub can [open a template request issue](https://github.com/eatyourpeas-ltd/checktick/issues/new?template=question_group_template_request.yml) (labelled `question-group-template`) with the complete markdown (including YAML frontmatter with attribution) — but note that an issue posts the instrument publicly, so it is only appropriate when the rights position is already clear. CheckTick reviews every submission for rights/licence, attribution completeness, clinical appropriateness, outline-grammar validity, and language/accessibility, and tells submitters why a submission was rejected — no silent drops.

All contributions must meet quality standards for validated instruments. See the [templates index](/docs/question-group-templates-index/) for the file format and requirements.

## Technical Details

### Markdown Format

Templates are stored as text using the Outline format:

```markdown
# Section Name {group-id}

## Question text {question-id}
(question type)
- Option 1
- Option 2
```

See [Outline Documentation](/docs/import/) for complete syntax.

### Template Metadata

Global templates include YAML frontmatter with:

- Title, slug, description
- Complete attribution (authors, DOI, PMID, etc.)
- Tags for categorization
- Copyright and license information

### Syncing Global Templates

Administrators can sync templates from the repository:

```bash
python manage.py sync_global_question_group_templates
```

This should run on deployment to ensure all instances have the latest templates.

## Related Documentation

- [Outline](/docs/import/) - Text format syntax for questions
- [Sections](/docs/groups-view/) - Managing sections
- [Global Templates Index](/docs/question-group-templates-index/) - Available templates
- [Collections](/docs/collections/) - Repeatable sections
