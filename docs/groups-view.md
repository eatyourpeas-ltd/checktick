---
title: Question Groups
category: features
priority: 6
---

Question groups are containers that organize related questions together in your surveys. They help structure your questionnaires logically (e.g., "Demographics", "Medical History", "PHQ-9 Depression Screening") and enable powerful features like repeating sections and template sharing.

## What are Question Groups?

A question group is a named collection of questions that:

- **Organizes questions logically** - Group related questions together for easier management
- **Enables repeating sections** - Create "collections" that participants can fill out multiple times (e.g., "Add another medication", "Add family member")
- **Can be published and shared** - Publish validated questionnaires as reusable templates for your organisation or the entire CheckTick community
- **Maintains question order** - Questions within a group stay together and maintain their sequence
- **Supports attribution** - When importing validated instruments, attribution information is preserved

## Key Features

### 1. Question Group Management

The Groups View page lets you:
- **Reorder groups** - Drag and drop to arrange groups in your survey
- **Create repeats (collections)** - Turn groups into repeatable sections
- **Nest repeats** - Create one level of nesting (e.g., "People" containing "Visits")
- **Remove from repeats** - Unlink groups from collections

### 2. Publishing Templates

Share your question groups with others:
- **Organisation templates** - Share validated questionnaires within your team
- **Global templates** - Contribute to the community library of validated instruments
- **Attribution support** - Include proper citations for published instruments (PHQ-9, GAD-7, etc.)
- **Copyright protection** - Prevent republishing of imported templates

See [Publishing Question Groups](/docs/publish-question-groups/) for detailed publishing instructions.

### 3. Template Library

Browse and import pre-built question groups:
- **Search and filter** - Find templates by name, tags, or language
- **View details** - Preview questions and attribution before importing
- **One-click import** - Add complete questionnaires to your surveys
- **Global repository** - Access curated validated instruments maintained by CheckTick

See [Question Group Template Library](/docs/question-group-template-library/) for browsing and importing templates.

## Managing Groups in the Groups View

### Who can access

- Owner of the survey
- Organisation ADMINs of the survey's organisation

Viewers, participants, or outsiders cannot access or modify this page.

## Reordering groups

- Use the drag handle on each row to rearrange groups.
- Click "Save order" to persist. The order is stored on the survey and used for rendering.

## Selecting groups

- Click anywhere on a row (or tick the checkbox) to select/deselect.
- A sticky toolbar appears at the top showing the count and a Clear button.
- Selected rows are highlighted and show a small repeat icon.

## Creating a repeat from selection

- After selecting one or more groups, click "Create repeat from selection".
- In the modal:
  - Name the repeat (e.g. "People", "Visits").
  - Optionally set min/max items; max=1 means a single item, blank = unlimited.
  - Optionally nest under an existing repeat (one-level nesting is supported).
- Submit to create the repeat. The selected groups are added to that repeat in the order selected.

## Removing a group from a repeat

- Rows that are part of a repeat show a "Repeats" badge and a small remove (✕) control.
- Removing a group from a repeat will also clean up empty repeats automatically.

## Text Entry syntax (optional)

You can also create repeats using Text Entry:

- Use `REPEAT-5` above the groups you want to repeat. `-5` means maximum five items; omit to allow unlimited.
- For one level of nesting, indent the nested repeat line with `>`.

Example:

```text
Demographics
Allergies
REPEAT-5 People
> REPEAT-3 Visits
Vitals
```

## Security and CSP

- The page uses external JS for selection logic to comply with the Content Security Policy (no inline scripts).
- Drag-and-drop uses SortableJS via a CDN allowed by CSP.

## Troubleshooting

- If buttons are disabled, ensure at least one row is selected.
- If the selection highlight doesn't show, check your theme's primary color; we derive selection styles from the primary token.
- If you see a CSP error in the browser console, ensure static files are collected and the CSP settings include the SortableJS CDN.

## Related Documentation

- [Publishing Question Groups](/docs/publish-question-groups/) - Share your question groups as templates
- [Question Group Template Library](/docs/question-group-template-library/) - Browse and import templates
- [Global Templates Index](/docs/question-group-templates-index/) - List of curated global templates
- [Text Entry Format](/docs/import/) - Text format syntax for importing questions
- [Collections](/docs/collections/) - Advanced repeat and nesting features
- [Surveys](/docs/surveys/) - Creating and managing surveys
