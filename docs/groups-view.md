# Groups View (Question Groups)

This page lets survey editors order question groups and create "repeats" (collections) from selected groups. It replaces any previous Collections screen.

For information about importing pre-built question groups from validated questionnaires, see the [Question Group Template Library](question-group-template-library.md) documentation.

## Who can access

- Owner of the survey
- Organization ADMINs of the survey's organization

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

## Bulk upload syntax (optional)

You can also create repeats from the bulk upload parser:

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
- If the selection highlight doesn’t show, check your theme's primary color; we derive selection styles from the primary token.
- If you see a CSP error in the browser console, ensure static files are collected and the CSP settings include the SortableJS CDN.
