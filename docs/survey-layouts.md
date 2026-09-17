---
title: Survey Layouts
category: features
priority: 7
---

A **Survey Layout** is the high-level shape of a survey — how its sections
are offered to the participant. CheckTick supports eight layouts:

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
- **Staged (longitudinal)** — sections unlock over time in defined
  phase windows (baseline now, follow-up in 2 weeks, 6-month review
  later). Each phase has a window measured in days from an anchor
  (participant enrolment or survey open). The participant sees only the
  currently-open phase; future phases are hidden until their window
  opens. Builds on the progress tracking feature's lifecycle status and
  timestamps.
- **Matrix (free navigation)** — all sections visible as cards on a
  landing page. The participant jumps in and out of any section in any
  order, with completion indicators showing which sections are done.
  Different from Section menu (pick once, then linear through the chosen
  set) — matrix is ongoing free navigation throughout the survey.
- **Delphi (consensus rounds)** — multi-round structured consensus
  workflow. Participants complete rounds, see aggregate feedback between
  rounds, and revise their answers. Used for expert consensus-building
  in clinical research, guideline development, and priority-setting.
  See the [Delphi guide](delphi.md) for a full walkthrough.
- **Diary (EMA)** — repeated short surveys on a fixed schedule (daily,
  4×/day) or event-triggered, with compliance tracking. Used for pain
  diaries, mood tracking, medication adherence, and symptom monitoring
  in clinical trials. See the [Diary / EMA guide](diary-ema.md) for a
  full walkthrough.

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

### Staged (longitudinal)

Use the Staged layout when:

- **Audit cycles** where you collect baseline data now and follow-up
  data at fixed intervals.
- **Longitudinal research** with repeated-measures designs at multiple
  time points.
- **Multi-phase quality improvement** projects where participants
  shouldn't see future phases.

Staged is a selection mechanism like Section menu and RCT, but the
selection changes over time. The runtime recomputes the open phases on
each access and resolves the visible sections from their union — unlike
RCT (fixed arm assignment), the open set changes over time. When no
phase is currently open, the participant sees a friendly "check back
later" page; their progress row is preserved so resume works when a
phase opens later. Participants never see future-phase sections.

Staged composes with Guided: a staged survey in guided layout walks the
currently-open phase's sections one question at a time.

### Delphi (consensus rounds)

Use the Delphi layout when:

- **Expert consensus-building** — you need a panel of experts to reach
  agreement on clinical guidelines, diagnostic criteria, or priority
  areas.
- **Modified Delphi studies** — you want structured multi-round input
  with quantitative feedback (medians, distributions) between rounds.
- **Nominal group technique variants** — you want participants to
  revise their answers after seeing the group's aggregate response.

Delphi is a selection mechanism like Section menu and RCT, but the
selection changes over rounds. Each round has a set of sections; the
participant sees only the current round's sections. Between rounds,
the author generates aggregate feedback (quantitative distributions +
optional LLM thematic summaries) which participants see in the next
round via a content block marked as feedback. When no round is open,
the participant sees a friendly "check back later" page.

See the [Delphi guide](delphi.md) for a full walkthrough of the creator
workflow and participant experience.

### Diary (EMA)

Use the Diary layout when:

- **Pain diaries** — daily or multiple-times-daily pain ratings over
  a study period.
- **Mood tracking** — IAPT/mental-health monitoring with repeated
  administrations.
- **Medication adherence** — daily check-ins confirming medication
  was taken.
- **Symptom monitoring in clinical trials** — high-frequency symptom
  tracking with compliance tracking for regulatory submissions.

Diary is different from Staged (which is phase-based: baseline →
2-week → 6-month). Diaries are high-frequency repeated measures with
burst scheduling, compliance tracking (missed entries), and
reminder emails. Each window opens the same short instrument; the
participant completes it and the entry is timestamped. When no window
is open, the participant sees a friendly "check back later" page.

See the [Diary / EMA guide](diary-ema.md) for a full walkthrough of
the creator workflow and participant experience.

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

## Staged (longitudinal)

For audit cycles and longitudinal research, sections unlock over time in
defined phase windows. Each phase has a window measured in integer days
from an anchor (participant enrolment or survey open). The runtime
recomputes the open phases on each access and resolves the visible
sections from their union. Unlike RCT (fixed arm assignment), the open
set changes over time — a participant who returns in two weeks sees a
different set of sections than they did today.

**When to use:** audit cycles, longitudinal research, multi-phase
quality improvement projects where you don't want participants seeing
future phases.

**Why it matters:** staged surveys are common in clinical audit and
research. This layout makes CheckTick suitable for repeated-measures
designs without requiring separate surveys for each time point.

### Configuring a Staged survey

On the Organise page, choose the **Staged (longitudinal)** layout card.
A configuration card appears where you:

- **Choose the anchor** — *From participant enrolment* (default; each
  participant's clock starts at their first access) or *From survey open
  date* (all participants move through phases on the same calendar
  schedule, offset from `Survey.start_at`).
- **Add phases** — name each phase (e.g. "Baseline", "Follow-up",
  "6-month review").
- **Set phase windows** — each phase has a `start_offset_days` and an
  optional `end_offset_days` (blank = open-ended). Windows are
  half-open: `[anchor + start, anchor + end)`.
- **Assign sections to phases** — tick which sections each phase sees. A
  section can be in multiple phases (e.g. a demographics section open in
  every phase).

### Warnings

The configuration card shows live warnings when:

- **No phases configured** — the survey has no phases; add at least one.
- **Single phase** — a staged survey with one phase is structurally
  identical to a linear survey.
- **survey_open anchor with no start date** — phase windows are measured
  from `Survey.start_at` but the survey has no start date; set one or
  switch the anchor to enrolment.
- **Unreachable section** — a section not in any phase is never seen by
  any participant.
- **Overlapping phase windows for the same section** — a section in two
  phases whose windows overlap will stay open across both (the runtime
  unions them). Usually fine, but flagged so you know.
- **Branching targets a phased section** — a `jump to` into a phased
  section is a dead branch when that phase is closed.

### Participant experience

The participant opens the survey and sees only the sections in the
currently-open phase, in the authored order. When no phase is currently
open, they see a friendly "check back later" page; their progress row is
preserved so resume works when a phase opens later. On resume, the open
phases are recomputed — if a new phase has opened since their last visit,
they see it; if a phase has closed, they no longer see it. Participants
never see future-phase sections. There is no picker — the open set is
system-controlled.

### Previewing a Staged survey

The preview page includes a **Simulate phase** panel that lets you pick
a phase and see exactly what a participant would see when that phase is
open. This previews the phase regardless of whether it is currently open,
so you can verify a future phase's composition without waiting for its
window.

### Survey Map

The [Survey Map](branching-and-repeats.md#the-survey-map) shows the full
authored survey. When using the Staged layout, a **phase composition**
badge summary appears above the visualiser listing each phase, its day
window, and its sections, so you can see at a glance which sections
belong to which phase.

### Outline syntax

The Staged layout can be configured directly in the [Outline / bulk
upload](import.md#staged-longitudinal-layout) text editor using a `STAGED`
block. The layout config survives export → import round-trips.

## Matrix (free navigation)

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

### How it works

1. The participant lands on a **cards page** showing every section with
   a state badge: *Not started*, *In progress*, or *Complete*.
2. They click a card to open that section. Only that section's questions
   are shown.
3. They fill in the answers and click **Save and complete section**.
   Required questions are validated before the section is marked
   complete.
4. They return to the landing page. The card now shows *Complete*.
5. They can revisit a completed section to edit answers — editing
   un-marks it as complete so the landing page shows *In progress*
   again.
6. When all sections are complete, the **Submit survey** button is
   enabled. Final submission re-validates all required questions across
   all sections (a hard gate — the completion indicators are a soft
   UX aid, not a guarantee).

### Configuration

On the [Organise](groups-view.md) page, the Matrix configuration card
lets you set:

- **Landing page prompt** — the text shown above the section cards.
- **Card order** — *As authored* (Organise page order) or *In visit
  order* (most-recently-visited last).
- **Allow participants to revisit and edit completed sections** — when
  unchecked, completed sections are locked.

### Outline syntax

The Matrix layout can be configured directly in the [Outline / bulk
upload](import.md#matrix-free-navigation-layout) text editor using a
`MATRIX` block. The grammar is optional (the Organise page UI is the
primary config path) but useful for the AI builder and power users.

## Content blocks

Content blocks are a special question type that renders static content —
a heading, a Markdown body, and reference links — with **no answer
input**. They go anywhere a question goes: any section, any position,
multiple per section, any layout.

### When to use content blocks

- **Landing page**: a content block as the only question in the first
  section renders as a welcome/intro page before the questions begin.
- **Interstitial disclosure**: a content block between substantive
  sections renders as a disclosure or information page.
- **Closing acknowledgement**: a content block as the last question
  renders as a thank-you or final acknowledgement.
- **Matrix landing**: in a matrix layout, a content block as the first
  question in the first section renders above the section cards as a
  landing header.

### Authoring

Content blocks are a **Special Template** in the builder (alongside
patient and professional details), not a regular question type. The author
adds a content block via the "Special Templates" tab, then configures it
via a "Configure content block" panel. All components are optional — include
only what you need:

- **Heading** (the rendered heading, optional)
- **Subtitle** (a short description or tagline, optional)
- **Body** (multiline Markdown, rendered to sanitised HTML, optional)
- **Image / logo** (uploaded via the builder; NOT encrypted — only use for
  non-medical, non-patient-identifying content)
- **Links** (label + URL pairs, zero or more, rendered as a list)
- **Consent** (a consent checkbox with a custom statement; when "required"
  is on, participants must agree to progress)
- **Render once** (default on — render once even in repeatable groups)

The question text (the internal label, e.g. "Content block") is not
rendered to participants — only the heading, subtitle, body, image,
links, and consent checkbox are shown.

Content blocks themselves are **never required** — they have no answer
(except the optional consent checkbox, which is a separate yesno question
behind the scenes for a clean audit trail).

### Markdown safety

The body is rendered to HTML via Python-Markdown then sanitised with
`nh3` (an allowlist-based HTML sanitiser). No `<script>`, `<style>`,
`<iframe>`, `<form>`, or event-handler attributes survive. Link URLs
are restricted to `http`, `https`, and `mailto` schemes. See
[Security Overview](/docs/security-overview/) §A03 for details.

### Outline syntax

Content blocks are supported in the outline grammar (used by the AI
builder and power users):

```text
## Introduction
(content_block)
heading: Welcome
variant: disclosure
link: Privacy notice|https://example.com/privacy

Welcome to the study. Please read the privacy notice before continuing.
```

The `## Introduction` heading is the internal label (not rendered to
participants). The `heading:` config line sets the rendered heading.
Image upload is builder-only — the outline grammar does not carry image
references.

## Planned layouts

The following layouts are planned for future releases. They are not yet
implemented. They are ordered by priority — the order CheckTick intends
to implement them, based on how often the use case is the reason a
research team reaches for REDCap or Qualtrics instead of a simpler tool.

### Two-stage screening / eligibility routing

A brief screener determines eligibility, then routes to the full survey,
an exit page, or an alternative survey. Ubiquitous in clinical
recruitment. May ship as a layout template (pre-configured branching +
content blocks) rather than a full new runtime hook.

### Computer-Adaptive Testing (CAT)

The next question is selected algorithmically based on prior responses
using item-response theory (IRT). Used for PROMIS, NIH Toolbox, and
other validated clinical outcome measures. Enables shorter, more
precise instruments.

### Crossover / within-subject RCT

Each participant experiences all conditions in sequence (AB, ABA, ABAB)
with washout periods between. Common in clinical pharmacology and
behavioural interventions. Different from RCT (between-subject) —
crossover is within-subject.

### Conjoint / Discrete Choice Experiment (DCE)

Choice-based experiments where participants make trade-off choices
between attribute profiles. Used in health economics, patient preference
studies, and HTA submissions.

### Stepped wedge / cluster-randomised

Clusters (sites, wards, practices) cross from control to intervention
in a randomised sequence over time. Common in implementation science
and cluster RCTs.

### 360° / multi-rater assessment

Multiple respondents (peers, supervisors, patients) rate a single
subject. Common in medical education and clinician appraisal.

### Think-aloud / cognitive interview mode

Qualitative interview mode for instrument validation — the researcher
probes while the participant thinks aloud. May remain a mode flag
rather than a full layout.

See [Survey Layouts (Technical)](survey-layouts-technical.md#planned-layouts)
for the full technical notes on each planned layout.

## Related documentation

- [Delphi guide](delphi.md) — full walkthrough of the Delphi consensus
  rounds layout (creator workflow + participant experience).
- [Diary / EMA guide](diary-ema.md) — full walkthrough of the Diary / EMA
  layout (creator workflow + participant experience).
- [Organise](groups-view.md) — the page where layout is configured.
- [Branching & Repeats](branching-and-repeats.md) — branching is a
  sibling feature; a `jump to` into a non-selected section is a no-op at
  runtime.
- [Survey Progress Tracking](survey-progress-tracking.md) — save-and-resume
  carries the section selection.
- [Survey Layouts (Technical)](survey-layouts-technical.md) — developer
  reference for the data model, runtime pipeline, and implementation
  details.
