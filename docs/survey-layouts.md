---
title: Survey Layouts
category: features
priority: 7
---

A **Survey Layout** is the high-level shape of a survey — how its sections
are offered to the participant. CheckTick supports two layouts:

- **Default (linear)** — sections flow in the order you arrange them. Every
  respondent sees every section. This is how all surveys worked before
  v0.13.0.
- **Section menu** — the survey opens on a picker page where the
  participant chooses which sections to complete. You mark some sections
  as *mandatory* (always included) and some as *pickable* (the
  participant decides).

The name **Layout** is deliberately distinct from **Template**, which is
already used for published sections shared into the Question Bank (see
[Publish Question Groups](publish-question-groups.md)). Layouts describe
the survey's flow; templates describe reusable content.

## When to use each layout

### Default (linear)

Most surveys, audits, and validated instruments where every respondent
should answer every question. This is the default — no configuration
needed.

### Section menu

Use the Section menu layout when:

- **Patient-reported outcome measures** where the respondent knows which
  domains apply to them.
- **Triage forms** where only relevant modules should be shown.
- **Long assessments** where forcing every section causes drop-off.
- **"Rank your priorities" surveys** where the participant's pick order
  matters (use the *In pick order* setting).

## Choosing a layout

The layout choice lives on the [Organise](groups-view.md) page
(`/surveys/<slug>/groups/`), not in the Builder. The Organise page gains
a **Survey layout** section at the top with two cards — one per layout.
Each card has a wireframe icon and a short description. Click **Use this
layout** to switch.

The Builder shows a small, dismissible label above the section rail
indicating the current layout, with a link to the Organise page if you
want to change it.

> **Single-section guard:** The Section menu card shows a hint when the
> survey has fewer than 2 sections, since a menu with one pickable
> section is pointless. Add more sections first.

## Configuring the Section menu

When Section menu is selected, a configuration card appears below the
layout cards on the Organise page. Here you control:

- **Picker prompt** — the text shown at the top of the picker page
  (e.g. "Which areas would you like to cover today?").
- **Per-section toggle** — mark each section as **Mandatory** (always
  included, cannot be deselected) or **Pickable** (the participant
  chooses). Mandatory sections are shown as locked rows on the picker.
- **Min / Max pickable selected** — constrain how many pickable sections
  the participant must/may choose. Min ≥ 1 unless at least one section
  is mandatory and you explicitly allow zero picks.
- **Order after selection** — *As authored* (use the Organise page order)
  or *In pick order* (use the order the participant ticked the boxes).
- **Show "Select all" button** — adds a convenience button on the picker.
- **Show estimated time per section** — optional per-section estimated
  completion time (e.g. "~5 min") shown on the picker.
- **Estimated minutes** — per-section, shown when the estimated time
  toggle is on.

### Warnings

The configuration card shows live warnings when:

- **Branching targets a pickable section** — a `jump to` condition that
  targets a section the participant might not pick is a dead branch. The
  warning is non-blocking; click **Review in Survey Map** to investigate.
- **Empty selection possible** — no mandatory sections and `min_selected`
  set to 0 means a participant could end up with an empty survey.

## Participant experience

### Picker page

When a participant opens a Section menu survey, they see the picker page
instead of the first question:

- Mandatory sections are listed as "Included automatically" — locked,
  not checkboxes.
- Pickable sections are checkboxes with optional estimated times.
- The **Continue** button is disabled until the participant has selected
  at least `min` and at most `max` pickable sections.
- If enabled, a **Select all** button ticks all pickable sections at once.

### After selection

The participant walks through the chosen sections (plus mandatory ones)
in the configured order. Branching, repeats, follow-ups, and the Survey
Map all behave exactly as they do in a linear survey — the layout only
decides which sections are in the path.

### Changing sections

A **"Change sections"** link in the progress bar returns the participant
to the picker. Deselecting a section that already has answers will
discard those answers — the participant is asked to confirm before this
happens.

### Saving progress

The picker selection is saved automatically. If a participant leaves and
returns, they skip the picker and go straight to their chosen sections.
See [Survey Progress Tracking](survey-progress-tracking.md) for more on
save-and-resume.

## Previewing a Section menu survey

The preview page includes a **Simulate section selection** panel that
lets you pre-tick a subset of pickable sections. This shows you exactly
what a participant would see for a given selection, without needing a
real participant. Click **Apply** to filter the preview, or **Reset** to
show all sections.

## Survey Map

The [Survey Map](branching-and-repeats.md#the-survey-map) shows the full
authored survey (all sections, regardless of layout). When using the
Section menu layout, a badge summary appears above the visualiser showing
which sections are pickable and which are mandatory, so you can see at a
glance which sections are optional.

## Outline syntax

When using the [bulk upload / text editor](bulk-upload.md), you can
configure the Section menu layout directly in the outline:

```text
SECTION_MENU
  prompt: "Which areas would you like to cover?"
  min: 1
  max: 4
  order: authored
  select_all: true
  estimated_time: true

# Demographics {demographics}
## Name {name}
(text)

# Medical history {medical-history}    ~ pickable
## Condition {condition}
(text)

# Medications {medications}    ~ pickable, 5 min
## Drug {drug}
(text)
```

- The `SECTION_MENU` block goes at the top of the outline, before any
  section headings.
- Config lines are indented: `prompt`, `min`, `max`, `order`
  (`authored` or `participant`), `select_all`, `estimated_time`.
- Place `~ pickable` after the section heading (and after the `{id}` if
  present) to mark a section as pickable.
- Add `, N min` to set an estimated time (e.g. `~ pickable, 5 min`).
- Sections without `~` are mandatory.
- A blank line ends the config block.

The layout config survives export → import round-trips, so you can
export a Section menu survey, edit the outline, and re-import without
losing the configuration.

## Related documentation

- [Organise](groups-view.md) — the page where layout is configured.
- [Branching & Repeats](branching-and-repeats.md) — branching is a
  sibling feature; a `jump to` into a non-selected section is a no-op at
  runtime.
- [Survey Progress Tracking](survey-progress-tracking.md) — save-and-resume
  carries the section selection.
- [Survey Layouts (Technical)](survey-layouts-technical.md) — developer
  reference for the data model, runtime pipeline, and implementation
  details.
