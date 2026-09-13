---
title: Survey Layouts
category: features
priority: 7
---

A **Survey Layout** is the high-level shape of a survey — how its sections
are offered to the participant. CheckTick supports four layouts:

- **Default (linear)** — sections flow in the order you arrange them. Every
  respondent sees every section. This is how all surveys worked before
  v0.13.0.
- **Section menu** — the survey opens on a picker page where the
  participant chooses which sections to complete. You mark some sections
  as *mandatory* (always included) and some as *pickable* (the
  participant decides).
- **Randomised (RCT)** — the system assigns each participant to an **arm**
  at first access. Each arm has its own set of sections, and the
  participant only sees the sections in their assigned arm. Use this for
  clinical trials and A/B testing where arm assignment must be
  system-controlled.
- **Guided** — one question per screen with Next/Back navigation, instead
  of scrolling through all questions on a single page. Reduces scroll
  fatigue on long or mobile-first surveys. Guided composes with the
  other layouts: a Section menu or RCT survey in guided layout still
  shows the picker / assigns the arm first, then walks the chosen
  sections one question at a time.

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

### Randomised (RCT)

Use the Randomised layout when:

- **Clinical trials** where participants must be randomised to intervention
  vs control arms.
- **A/B testing of question wording** where different arms see different
  phrasings of the same question.
- **Randomised controlled trials** where arm assignment must be
  system-controlled and not participant-chosen.

Randomisation is a common reason researchers reach for Qualtrics or REDCap
instead of simpler tools. This layout unblocks that use case natively in
CheckTick.

### Guided

Use the Guided layout when:

- **Long patient-facing surveys** where scroll fatigue causes drop-off.
- **Mobile-first surveys** where a single-question focus reduces
  cognitive load.
- **Validated instruments** where a one-question-at-a-time presentation
  matches the intended administration.

Guided is a rendering change, not a selection mechanism — it composes
with the other layouts. A Section menu survey in guided layout shows the
picker first, then walks the chosen sections one question at a time; an
RCT survey in guided layout walks the assigned arm's sections one
question at a time. Branching, repeats, follow-ups, autosave, and
save-and-resume all work unchanged.

## Choosing a layout

The layout choice lives on the [Organise](groups-view.md) page
(`/surveys/<slug>/groups/`), not in the Builder. The Organise page has
a **Survey layout** section at the top with a card per layout. Each
card has a wireframe icon and a short description. Click **Use this
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

The Section menu layout can be configured directly in the [Outline / bulk
upload](import.md#section-menu-layout) text editor using a `SECTION_MENU`
block. The layout config survives export → import round-trips.

## Randomised (RCT)

For clinical trials and research, the system randomly assigns each
participant to an **arm** (e.g. intervention vs control). Each arm has its
own set of sections, and the participant only sees the sections in their
assigned arm. Unlike the Section menu layout where the participant
chooses, the system chooses based on a random seed stored on the
participant's progress record at first access.

**When to use:** clinical trials, A/B testing of question wording,
randomised controlled trials where arm assignment must be
system-controlled and not participant-chosen.

**Why it matters:** randomisation is a common reason researchers reach
for Qualtrics or REDCap instead of simpler tools. This layout unblocks
that use case natively in CheckTick.

### Configuring an RCT

On the Organise page, choose the **Randomised (RCT)** layout card. A
configuration card appears where you:

- **Add arms** — name each arm (e.g. "Intervention", "Control").
- **Set allocation ratio** per arm (e.g. 1:1, 2:1). The system balances
  assignment across arms per the ratios.
- **Choose allocation strategy** — *Balanced (blocked)* (default; keeps
  arm counts close to the ratios) or *Simple (weighted)* (independent
  random draw per participant).
- **Assign sections to arms** — tick which sections each arm sees. A
  section can be in multiple arms (e.g. a demographics section shared
  by all arms).
- **Optional seed** — set a fixed seed for reproducible dry-runs. Leave
  blank for real trials so allocation is unpredictable.

### Warnings

The configuration card shows live warnings when:

- **Single arm** — RCT with one arm is degenerate; add a second arm.
- **Allocation ratio sum zero** — every arm has ratio 0; set at least one
  arm's ratio to 1 or higher.
- **Unreachable section** — a section not in any arm's group set is
  never seen by any participant.
- **All arms share the same sections** — the RCT is structurally
  identical to a linear survey.
- **Branching targets an arm-exclusive section** — a `jump to` into a
  section not in the participant's assigned arm is a dead branch for
  other arms.

### Participant experience

The participant never sees the picker or their arm. They open the survey
and see the sections in their assigned arm, in the authored order. On
resume, they return to the same sections. There is no "Change sections"
link — the assignment is fixed for the lifetime of their progress record.

### Previewing an RCT survey

The preview page includes a **Simulate arm** panel that lets you pick
an arm and see exactly what a participant assigned to that arm would
see. Useful for verifying arm composition before going live.

### Survey Map

The [Survey Map](branching-and-repeats.md#the-survey-map) shows the full
authored survey. When using the RCT layout, an **arm composition** badge
summary appears above the visualiser listing each arm, its allocation
ratio, and its sections, so you can see at a glance which sections are
arm-exclusive.

### Outline syntax

The RCT layout can be configured directly in the [Outline / bulk
upload](import.md#randomised-rct-layout) text editor using a `RANDOMISED`
block. The layout config survives export → import round-trips.

## Planned layouts

The following layouts are planned for future releases. They are not yet
implemented.

### Staged (longitudinal)

Sections unlock over time — baseline now, follow-up in 2 weeks, 6-month
review later. Each section group has a defined phase window. The
participant sees only the current phase. This builds on the progress
tracking feature, which already has lifecycle status and timestamps on
`SurveyProgress`.

**When to use:** audit cycles, longitudinal research, multi-phase
quality improvement projects where you don't want participants seeing
future phases.

**Why it matters:** staged surveys are common in clinical audit and
research. This layout would make CheckTick suitable for repeated-measures
designs without requiring separate surveys for each time point.

### Matrix (free navigation)

All sections visible as cards on a landing page. The participant jumps
in and out of any section in any order, with completion indicators
showing which sections are done. Different from Section menu (pick
once, then linear through the chosen set) — matrix is ongoing free
navigation.

**When to use:** audits where a clinician fills in different sections
at different times during a patient encounter; complex assessments
where the participant needs to revisit and revise earlier sections.

**Why it matters:** some clinical workflows don't fit a linear or
pick-once model. Matrix gives the participant agency over navigation
order throughout the survey, not just at the start.

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
