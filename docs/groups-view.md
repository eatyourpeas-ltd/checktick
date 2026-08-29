---
title: Organise
category: features
priority: 6
---

Sections are containers that organise related questions together in your surveys. They help structure your questionnaires logically (e.g., "Demographics", "Medical History", "PHQ-9 Depression Screening") and enable powerful features like repeating sections and template sharing.

## The Builder

The primary place to build and edit questions is the **Builder** (`/surveys/<slug>/builder/`). It shows a master-detail layout:

- **Desktop (md+):** A left rail lists your sections in order. Click a section to see its questions in the main area. Use "Add section" at the bottom of the rail to create a new section. Each rail item also has rename and delete buttons (delete is hidden for the first section — a survey must always have at least one).
- **Mobile (<md):** A dropdown at the top of the page lets you switch sections.
- **Single-section surveys:** The rail still renders (with one section and an "Add section" button) so users can see that sections exist and add more.

The Builder is where you add, edit, reorder, and delete questions. For bulk section operations (reordering, repeats, publishing), use the Organise page described below.

## What are sections?

A section is a named collection of questions that:

- **Organises questions logically** - Group related questions together for easier management
- **Enables repeating sections** - Create "collections" that participants can fill out multiple times (e.g., "Add another medication", "Add family member")
- **Can be published and shared** - Publish validated questionnaires as reusable templates for your organisation or the entire CheckTick community
- **Maintains question order** - Questions within a section stay together and maintain their sequence
- **Supports attribution** - When importing validated instruments, attribution information is preserved

## The Organise page

The **Organise** page (`/surveys/<slug>/groups/`) is for bulk section operations that are better done outside the Builder:

- **Reorder sections** - Drag and drop to arrange sections in your survey (also available in the Builder rail)
- **Create repeats (collections)** - Select multiple sections and make them repeatable together (single-section repeats can be done from the Builder rail)
- **Nest repeats** - Create one level of nesting (e.g., "People" containing "Visits")
- **Remove from repeats** - Unlink sections from collections
- **Visualise the survey** - View the survey as a flow diagram on the **Survey Map** page (`/surveys/<slug>/survey-map/`), linked from the quick-nav toolbar.
- **Publish sections as templates** - Share validated questionnaires

Renaming, deleting, and single-section repeats are done in the **Builder** rail. The Organise page focuses on bulk operations that affect multiple sections at once.

### Who can access

- Owner of the survey
- Organisation ADMINs of the survey's organisation

Viewers, participants, or outsiders cannot access or modify this page.

## Reordering sections

- In the Builder: Drag sections using the drag handle in the rail.
- On the Organise page: Use the drag handle on each row to rearrange sections.
- The order is saved automatically on drop and is used for rendering.

## Renaming a section

- In the Builder: Click the pencil icon next to the section name in the rail.
- In the modal, edit the section name and optional description.
- Click "Save" to persist. The change takes effect immediately.

Renaming is no longer available on the Organise page — use the Builder rail.

## Deleting a section

- In the Builder: Click the trash icon next to the section name in the rail (only available for the second and subsequent sections).
- A confirmation modal appears. Deleting a section also deletes all questions within it.
- The first (or only) section cannot be deleted — a survey must always have at least one section.

Deleting is no longer available on the Organise page — use the Builder rail.

## Selecting sections

- Click anywhere on a row (or tick the checkbox) to select/deselect.
- A sticky toolbar appears at the top showing the count and a Clear button.
- Selected rows are highlighted and show a small repeat icon.

## Creating a repeat from selection

- After selecting one or more sections, click "Create repeat from selection".
- In the modal:
  - Name the repeat (e.g. "People", "Visits").
  - Optionally set min/max items; max=1 means a single item, blank = unlimited.
  - Optionally nest under an existing repeat (one-level nesting is supported).
- Submit to create the repeat. The selected sections are added to that repeat in the order selected.

## Removing a section from a repeat

- Rows that are part of a repeat show a "Repeats" badge and a small remove (✕) control.
- Removing a section from a repeat will also clean up empty repeats automatically.

## Outline syntax (optional)

You can also create repeats using the Outline:

- Use `REPEAT-5` above the sections you want to repeat. `-5` means maximum five items; omit to allow unlimited.
- For one level of nesting, indent the nested repeat line with `>`.

Example:

```text
Demographics
Allergies
REPEAT-5 People
> REPEAT-3 Visits
Vitals
```

## Troubleshooting

- If buttons are disabled, ensure at least one row is selected.
- If the selection highlight doesn't show, check your theme's primary color; we derive selection styles from the primary token.
- If you see a CSP error in the browser console, ensure static files are collected and the CSP settings include the SortableJS CDN.

## Related Documentation

- [Publishing Question Groups](/docs/publish-question-groups/) - Share your sections as templates
- [Question Group Template Library](/docs/question-group-template-library/) - Browse and import templates (the Question Bank)
- [Global Templates Index](/docs/question-group-templates-index/) - List of curated global templates
- [Outline](/docs/import/) - Text format syntax for importing questions
- [Collections](/docs/collections/) - Advanced repeat and nesting features
- [Surveys](/docs/surveys/) - Creating and managing surveys
