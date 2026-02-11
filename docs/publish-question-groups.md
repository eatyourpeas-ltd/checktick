---
title: Publishing Question Groups
category: None
---

This guide explains how to publish your question groups as reusable templates that can be shared with your organisation or the global CheckTick community.

> **Note:** For an overview of question groups and their features, see [Question Groups](/docs/groups-view/). To browse and import templates, see [Question Group Template Library](/docs/question-group-template-library/).

## Publication Levels

### Organisation Templates

Publish templates visible only to your organisation members:

- Share validated questionnaires within your team
- Maintain consistent data collection across projects
- Available immediately after publishing

### Global Templates

Publish templates visible to all Checktick users:

- Contribute validated instruments to the community
- Increase visibility and citations of your work
- Available immediately after publishing

**Note:** Organisation VIEWER role cannot publish templates (view-only access).

## Publishing a Question Group

1. Go to your survey's question groups page
2. Click **Publish** next to any question group
3. Choose publication level (Organisation or Global)
4. Add attribution information:
   - Author names and ORCID IDs (optional)
   - Publication title and journal
   - DOI and PubMed ID (if applicable)
   - Copyright and license information
5. Add tags for discoverability
6. Preview the markdown representation
7. Confirm publication

**Rate limit:** 10 publications per day per user

## Browsing Templates

Access the template library from:

- Survey question groups page: **Browse & Import Templates** button
- Text Entry page: Link in the information banner

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
6. The question group is added to your survey
7. Customize as needed in the question builder

**Rate limit:** 50 imports per hour per user

**Note:** Imported question groups are independent copies. Changes to your copy don't affect the original template or other imports.

## Managing Your Published Templates

View your published templates in the template library filtered by your organisation or username (coming soon).

To update a template:
- Make changes to your original question group
- Publish again with the same slug (existing template is updated)

To delete a template:
- Access the template detail page
- Click **Delete Template**
- Confirm deletion

**Note:** Deleting a template doesn't affect question groups that were imported from it.

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

See the [Global Templates Appendix](/docs/question-group-templates-index/) for the complete list of available templates.

### Contributing Global Templates

Community members can contribute validated instruments:

**Via GitHub Issue:**
1. Create an issue: "New Global Template: [Name]"
2. Provide complete markdown with YAML frontmatter
3. Include validation evidence and copyright status
4. Tag with `template-request`

**Via Pull Request:**
1. Add template file to `docs/question-group-templates/`
2. Include complete YAML frontmatter with attribution
3. Test with `sync_global_question_group_templates --dry-run`
4. Submit PR with questionnaire description

All contributions must meet quality standards for validated instruments. See the [templates index](/docs/question-group-templates-index/) for the file format and requirements.

## Technical Details

### Markdown Format

Templates are stored as text using the Text Entry format:

```markdown
# Question Group Name {group-id}

## Question text {question-id}
(question type)
- Option 1
- Option 2
```

See [Text Entry Documentation](/docs/import/) for complete syntax.

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

- [Text Entry Format](/docs/import/) - Text format syntax for questions
- [Groups View](/docs/groups-view/) - Managing question groups
- [Global Templates Appendix](/docs/question-group-templates-index/) - Available templates
- [Collections](/docs/collections/) - Repeatable question groups
