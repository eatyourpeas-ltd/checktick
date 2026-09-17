---
title: Delphi (Consensus Rounds)
category: features
priority: 8
---

The Delphi layout implements a structured multi-round consensus workflow —
the classic Delphi method used for expert consensus-building in clinical
research, guideline development, and priority-setting.

Participants complete a series of rounds. Between rounds, they see
aggregate feedback from the previous round (quantitative distributions and
optional qualitative themes) and revise their answers. The author
controls the number of rounds, the section set per round, the round
windows, and when to generate inter-round feedback.

This guide covers the creator workflow and the participant experience.
For the technical data model and runtime pipeline, see
[Survey Layouts (Technical)](survey-layouts-technical.md#delphi-consensus-rounds-layout).

## When to use Delphi

- **Expert consensus-building** — a panel of experts needs to reach
  agreement on clinical guidelines, diagnostic criteria, or priority
  areas.
- **Modified Delphi studies** — structured multi-round input with
  quantitative feedback (medians, distributions) between rounds.
- **Nominal group technique variants** — participants revise their
  answers after seeing the group's aggregate response.

Delphi is different from [Staged](survey-layouts.md#staged-longitudinal)
(which unlocks sections over time in phases) and from
[Section menu](survey-layouts.md#section-menu) (where the participant
picks sections once). In Delphi, the author controls which sections are
in each round, and the participant sees aggregate feedback between
rounds.

## Creator workflow

### 1. Build your sections

Build your survey sections in the [Builder](builder.md) as you would
for any survey. You need at least 2 sections for Delphi to be useful.

A typical Delphi survey has:

- **Shared sections** — e.g. demographics, that appear in every round.
- **Round-specific sections** — the questions that change between
  rounds. Round 1 might ask participants to rate the importance of
  items; Round 2 asks them to re-rate after seeing the group's
  distribution.
- **Feedback content blocks** — a content block marked as "Delphi
  feedback" in Round 2+ that renders the aggregate feedback from the
  previous round. See [Inter-round feedback](#inter-round-feedback)
  below.

### 2. Switch to the Delphi layout

Go to the [Organise](groups-view.md) page
(`/surveys/<slug>/groups/`). In the **Survey layout** section at the
top, click **Use this layout** on the Delphi card.

A configuration card appears below the layout picker.

### 3. Configure the Delphi menu

The configuration card has:

- **Round windows measured from** — *Participant enrolment* (each
  participant's rounds start from their first access) or *Survey open
  date* (all participants move through rounds on the same calendar
  schedule). Use *Survey open date* when you want everyone on the same
  schedule.
- **Min rounds / Max rounds** — the minimum and maximum number of
  rounds before the survey can complete.
- **Show participants which round they are in** — displays a round
  indicator to participants.
- **Allow participants to revise previous-round answers** — when on,
  participants can see and change their previous-round answers in the
  current round. When off, previous-round questions render blank in
  subsequent rounds.

### 4. Add rounds and assign sections

Click **Add round** to create rounds. For each round:

- **Name** — e.g. "Round 1", "Initial survey", "Revision round".
- **Start (days)** — days after the anchor when this round opens. 0 =
  opens at the anchor time.
- **End (days)** — days after the anchor when this round closes. Leave
  blank for an open-ended round (never closes automatically).
- **Sections in this round** — tick the checkboxes to assign sections
  to this round. A section can appear in multiple rounds (e.g. a
  demographics section in every round).

Click **Save configuration** when done.

### 5. Add a feedback content block (optional but recommended)

To show participants the aggregate feedback between rounds, add a
[content block](survey-layouts.md#content-blocks) in Round 2+ and mark
it as Delphi feedback:

1. In the Builder, add a content block to a section that appears in
   Round 2+.
2. Configure the content block with a heading (e.g. "Inter-round
   feedback") and an optional body (this will be replaced by the
   feedback summary at view time).
3. In the content block's configure panel, enable **Delphi feedback**.
   This marks the block with `is_delphi_feedback = True` in its options.

When a participant views Round 2+, the content block's body is replaced
with a combined summary of all feedback from the most recently closed
round — medians, IQRs, distributions for quantitative questions, and
LLM theme summaries (if generated) for free-text questions.

### 6. Publish and run rounds

1. [Publish](publish-and-collection.md) the survey as you would for any
   survey.
2. Participants access the survey and are assigned to the current open
   round automatically.
3. When a round's window has passed (or you manually close it), the
   participant advances to the next open round.

### 7. Close rounds and generate feedback

After a round closes (either by its window expiring or by you manually
setting `closed_at`), the **Inter-round feedback** section on the
Organise page shows two buttons per closed round:

- **Generate feedback** — aggregates the closed round's responses
  (quantitative stats: medians, IQRs, distributions) and caches the
  result. Optionally tick **with LLM themes** to also generate
  LLM-based thematic summaries of free-text responses (opt-in,
  tier-gated, unlock-gated). The cached feedback is shown to
  participants in the next round via the feedback content block.
- **Download comments** — downloads all free-text responses for the
  round as a CSV file (one row per response, columns for question text
  and response text). Always available — no LLM required, no tier
  gate. Use this for manual thematic analysis in NVivo, Excel, or SPSS.

You can regenerate feedback at any time (e.g. after more responses
come in). The old feedback rows are replaced.

## Inter-round feedback

Inter-round feedback has two components:

### Quantitative (always computed, no LLM)

For each question in the closed round:

- **Likert / numeric**: median, IQR (Q1/Q3), min, max, mean, standard
  deviation, distribution (value → count).
- **Yes/No**: yes count, no count, don't know count, yes percentage.
- **Multiple choice / dropdown**: frequency distribution, mode.
- **Free text**: responses collected for LLM thematic analysis or
  manual download.

The quantitative feedback is always generated when you click
"Generate feedback" — it requires no LLM and no special tier.

### Qualitative (opt-in LLM or manual download)

For free-text questions, you have two options:

1. **Manual thematic analysis** (always available, default) — click
   "Download comments" to get a CSV of all free-text responses. Code
   themes manually in NVivo, Excel, or SPSS. This is the default path
   for researchers who want to do their own analysis, which is
   particularly important for publication-grade Delphi work where the
   LLM's paraphrasing is not auditable enough.

2. **LLM thematic analysis** (opt-in, tier-gated) — when you click
   "Generate feedback" with the **with LLM themes** checkbox ticked,
   the system calls the LLM theme analysis service per free-text
   question. The LLM generates a sanitised, paraphrased summary of
   recurring themes (no verbatim quotes, no identifiable content).
   This is opt-in — the LLM is never called automatically. If the LLM
   is unavailable, the quantitative feedback still renders; the
   qualitative section shows a "download the comments to review
   manually" message.

The dual approach respects that thematic analysis is a research
method, not just a feature. Researchers who publish Delphi results in
peer-reviewed journals are often required to describe their coding
process; an LLM-generated summary cannot be audited or reproduced with
the same rigour as manual coding. By making the download always
available and the LLM explicitly opt-in, CheckTick supports both
workflows without forcing one on the researcher.

### How feedback is displayed

Feedback is cached on `DelphiRoundFeedback` rows when you click
"Generate feedback". When a participant views the next round, any
content block marked as "Delphi feedback" has its body replaced with
the combined feedback summary from the most recently closed round. The
summary includes per-question stats and themes, rendered as Markdown.

If no feedback has been generated yet, the content block shows "No
inter-round feedback has been generated yet."

## Participant experience

### First access

When a participant first accesses a Delphi survey:

1. They are assigned to the **current open round** automatically.
2. They see only that round's sections (ordered as arranged on the
   Organise page).
3. If the survey has `show_progress` enabled, they see a round
   indicator (e.g. "Round 1 of 3").

### Between rounds

When the current round closes (by window or manual close):

1. If the next round is open, the participant advances automatically on
   their next access.
2. If no round is open, they see a friendly "No round available right
   now — please check back when the next round is due" page. Their
   progress is preserved so resume works when the next round opens.
3. In the next round, any feedback content blocks show the aggregate
   feedback from the previous round (if generated by the author).

### Revising answers

If `allow_revision` is enabled (the default), participants can see and
change their previous-round answers in the current round. If disabled,
previous-round questions render blank in subsequent rounds.

### Save and resume

Save-and-resume works as it does for any survey. The participant's
round assignment is preserved across resume. If the round has closed
while they were away, they advance to the next open round on resume.

### Last round

After the last round closes, the survey is complete for that
participant. Their `SurveyProgress.status` is set to `completed`.

## Outline syntax

The Delphi layout can be configured directly in the [Outline / bulk
upload](import.md) text editor using a `DELPHI` block. The grammar is
optional (the Organise page UI is the primary config path) but useful
for the AI builder and power users.

```text
DELPHI
  anchor: enrolment
  min_rounds: 2
  max_rounds: 3
  show_progress: true
  allow_revision: true
  round Round 1: 0 .. 14
  round Round 2: 14 .. 28

# Demographics {demographics}    ~ round:Round 1, round:Round 2
## Age {age}
(text)

# Round 1 questions {r1-questions}    ~ round:Round 1
## Importance {importance}
(likert) 1-5

# Round 2 questions {r2-questions}    ~ round:Round 2
## Revised importance {revised-importance}
(likert) 1-5
```

- The `~ round:<name>` suffix on group headings assigns a group to a
  round. A group can appear in multiple rounds.
- The `round <name>: <start> [.. <end>]` config lines define the round
  windows (day offsets from the anchor; end is optional for
  open-ended rounds).
- Groups without `~ round:` under a `DELPHI` block are not in any round
  (unreachable; warned on the Organise page).

The grammar round-trips through export → import like the other
layouts.

## Preview

On the [preview](survey-layouts.md#previewing-a-section-menu-survey)
page, a **Simulate round** panel lets you pick a round to preview what
a participant would see when that round is open. This previews the
round regardless of whether it is currently open.

## Survey Map

The [Survey Map](survey-layouts.md#survey-map) shows a **Delphi — round
composition** card listing each round, its window (days from the
anchor), and its sections. Warnings appear for misconfigured surveys
(no rounds, no sections in a round, unreachable sections).

## Warnings

The Organise page surfaces non-blocking warnings for common
misconfigurations:

- **No rounds configured** — add at least one round and assign
  sections to it.
- **Only one round** — a Delphi survey with a single round is
  structurally identical to a linear survey.
- **Survey open anchor with no start date** — set a start date or
  switch the anchor to *Participant enrolment*.
- **Section not in any round** — no participant will see it.
- **Overlapping round windows** — a section in two rounds whose
  windows overlap will stay open across both.
- **Branching targets a round section** — a `jump to` into a round
  section will be skipped when that round is closed.

## Anonymity

Delphi often requires anonymous responses. Aggregation never reveals
individual responses. The LLM prompt explicitly forbids verbatim
quotes and identifiable content. Authors can mark a survey as
"anonymous" (existing field) to hide participant identity from the
author too.

## Related documentation

- [Survey Layouts](survey-layouts.md) — overview of all layouts.
- [Survey Layouts (Technical)](survey-layouts-technical.md) — developer
  reference for the Delphi data model, runtime pipeline, and
  implementation details.
- [Content blocks](survey-layouts.md#content-blocks) — the question
  type used for inter-round feedback display.
- [Organise](groups-view.md) — the page where Delphi is configured.
- [Branching & Repeats](branching-and-repeats.md) — branching is a
  sibling feature; a `jump to` into a non-open round section is a
  no-op at runtime.
- [Survey Progress Tracking](survey-progress-tracking.md) — save-and-resume
  carries the round assignment.
