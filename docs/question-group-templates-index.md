---
title: Global Question Group Templates
category: None
---

# Global Question Group Templates

This appendix lists validated questionnaires and instruments available as global templates in CheckTick.

## Available Templates

### PHQ-9 (Patient Health Questionnaire-9)

**Depression Screening Questionnaire**

- **Citation**: Kroenke K, Spitzer RL, Williams JB. The PHQ-9: validity of a brief depression severity measure. J Gen Intern Med. 2001 Sep;16(9):606-13. doi: [10.1046/j.1525-1497.2001.016009606.x](https://doi.org/10.1046/j.1525-1497.2001.016009606.x). PMID: [11556941](https://pubmed.ncbi.nlm.nih.gov/11556941/)
- **License**: Public domain
- **Questions**: 9 items (4-point Likert scale)
- **Tags**: mental-health, depression, screening, validated

[View PHQ-9 Template →](/docs/question-group-templates-phq9/)

---

## Template File Format

Global templates are stored as markdown files in the `docs/` directory with the naming pattern `question-group-templates-{slug}.md`.

### Required Structure

Each template file must contain:

1. **YAML Frontmatter** with metadata:
   ```yaml
   ---
   title: "Questionnaire Name"
   description: "Brief description of the questionnaire"
   attribution:
     authors: "Author names"
     citation: "Full citation"
     doi: "DOI if available"
     pmid: "PubMed ID if available"
     license: "License information"
   tags:
     - tag1
     - tag2
   ---
   ```

2. **Markdown Content** using the bulk upload format (see [Import Documentation](/docs/import/))

### Syncing Templates

Templates are automatically synchronized during deployment:

```bash
python manage.py sync_global_question_group_templates
```

This command:
- Scans `docs/question-group-templates-*.md` files
- Extracts YAML frontmatter metadata
- Validates markdown format
- Creates/updates global templates in the database

### Contributing Templates

See [Publishing Question Groups](/docs/publish-question-groups/#contributing-global-templates) for contribution guidelines.

## Maintenance

Global templates are version-controlled in the repository and synced on deployment. To update a template:

1. Edit the markdown file in `docs/`
2. Update version or metadata in YAML frontmatter if needed
3. Test parsing: `python manage.py sync_global_question_group_templates --dry-run`
4. Commit and deploy

The sync command will detect changes and update the published template automatically.
