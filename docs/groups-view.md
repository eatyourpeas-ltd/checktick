---
title: Sections
category: features
priority: 6
---

Sections are containers that organise related questions together in your surveys. They help structure your questionnaires logically (e.g., "Demographics", "Medical History", "PHQ-9 Depression Screening") and enable powerful features like repeating sections and template sharing.

> **Technical note:** In the code, API, and data model, sections are called `QuestionGroup`. The user-facing label is "Sections". This page covers the user-facing workflow; technical references throughout the docs retain `QuestionGroup`.

## The Builder

The primary place to build and edit questions is the **Builder** (`/surveys/<slug>/builder/`). It shows a master-detail layout:

- **Desktop (md+):** A left rail lists your sections in order. Click a section to see its questions in the main area. Use "Add section" at the bottom of the rail to create a new section.
- **Mobile (<md):** A dropdown at the top of the page lets you switch sections.
- **Single-section surveys:** The rail is hidden — you just see a flat list of questions. The section layer appears automatically when you add a second section.

The Builder is where you add, edit, reorder, and delete questions. For bulk section operations (reordering, repeats, publishing), use the Sections page described below.

## What are sections?

A section is a named collection of questions that:

- **Organises questions logically** - Group related questions together for easier management
- **Enables repeating sections** - Create "collections" that participants can fill out multiple times (e.g., "Add another medication", "Add family member")
- **Can be published and shared** - Publish validated questionnaires as reusable templates for your organisation or the entire CheckTick community
- **Maintains question order** - Questions within a section stay together and maintain their sequence
- **Supports attribution** - When importing validated instruments, attribution information is preserved

## Key Features

### 1. Section Management

The Sections page lets you:

- **Reorder sections** - Drag and drop to arrange sections in your survey
- **Rename sections** - Click the "Rename" button on any section to edit its name and description
- **Create repeats (collections)** - Turn sections into repeatable sections
- **Nest repeats** - Create one level of nesting (e.g., "People" containing "Visits")
- **Remove from repeats** - Unlink sections from collections

### 2. Publishing Templates

Share your sections with others:

- **Organisation templates** - Share validated questionnaires within your team
- **Global templates** - Contribute to the community library of validated instruments
- **Attribution support** - Include proper citations for published instruments (PHQ-9, GAD-7, etc.)
- **Copyright protection** - Prevent republishing of imported templates

See [Publishing Question Groups](/docs/publish-question-groups/) for detailed publishing instructions.

### 3. Question Bank

Browse and import pre-built sections:

- **Search and filter** - Find templates by name, tags, or language
- **View details** - Preview questions and attribution before importing
- **One-click import** - Add complete questionnaires to your surveys
- **Global repository** - Access curated validated instruments maintained by CheckTick

See [Question Group Template Library](/docs/question-group-template-library/) for browsing and importing templates.

## Managing sections in the Sections view

### Who can access

- Owner of the survey
- Organisation ADMINs of the survey's organisation

Viewers, participants, or outsiders cannot access or modify this page.

## Reordering sections

- Use the drag handle on each row to rearrange sections.
- Click "Save order" to persist. The order is stored on the survey and used for rendering.

## Renaming a section

- Click the "Rename" button on any section row.
- In the modal, edit the section name and optional description.
- Click "Save" to persist. The change takes effect immediately.

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

## Security and CSP

- The page uses external JS for selection logic to comply with the Content Security Policy (no inline scripts).
- Drag-and-drop uses SortableJS via a CDN allowed by CSP.

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
