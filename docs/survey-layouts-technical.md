---
title: Survey Layouts (Technical)
category: development
priority: 17
---

Technical reference for the survey layouts feature. For the user-facing
guide, see [Survey Layouts](survey-layouts.md).

## Overview

The layout feature adds a `layout` field to `Survey` and two related
models (`SectionMenu`, `SectionMenuItem`) that configure the Section menu
layout. The runtime applies a selection filter in the ordering pipeline
so that only chosen sections (plus mandatory ones) are rendered.

## Prerequisite

The progress-tracking feature (PR #319, v0.12.0) must be merged. The
following fields already exist and must NOT be re-added:

- `Survey.allow_resume` (BooleanField, default True)
- `Survey.allow_response_redaction` (BooleanField, default True)
- `SurveyProgress.selected_group_ids` (JSONField, default list)
- `SurveyProgress.resume_token`, `status`, `current_repeat_index`,
  `completed_at` (see `docs/survey-progress-tracking-technical.md`)
- Migration `0059_progress_resume_and_redaction_fields` is applied.

## Data model

```python
class Survey(models.Model):
    ...
    layout = models.CharField(
        max_length=20,
        choices=[("linear", "Linear"), ("section_menu", "Section menu")],
        default="linear",
    )

    # Already exists (v0.12.0, migration 0059) — do not re-add
    allow_resume = models.BooleanField(default=True)
    allow_response_redaction = models.BooleanField(default=True)


class SectionMenu(models.Model):
    survey = models.OneToOneField(
        Survey, related_name="section_menu", on_delete=models.CASCADE,
    )
    prompt_text = models.CharField(
        default="Which sections would you like to complete?",
    )
    min_selected = models.PositiveIntegerField(default=1)
    max_selected = models.PositiveIntegerField(null=True, blank=True)  # null = no cap
    order_mode = models.CharField(
        max_length=20,
        choices=[("authored", "As authored"), ("participant", "In pick order")],
        default="authored",
    )
    show_select_all = models.BooleanField(default=False)
    show_estimated_time = models.BooleanField(default=False)


class SectionMenuItem(models.Model):
    menu = models.ForeignKey(SectionMenu, related_name="items", on_delete=models.CASCADE)
    group = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE)
    is_pickable = models.BooleanField(default=True)  # False = mandatory
    order = models.PositiveIntegerField(default=0)
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("menu", "group")
        ordering = ["order", "id"]
```

`SectionMenuItem` rows are only created for surveys with
`layout = section_menu`. A `linear` survey has no rows and renders exactly
as it did before v0.13.0.

**Migration:** `0060_survey_layouts` (single squashed migration that adds
the `layout` field and both models, including `BigAutoField` on the new
tables).

## Runtime — why no new branching action is needed

The picker is a **pre-step**, not a branching rule. When the participant
submits their selection:

1. The chosen group IDs (plus the mandatory ones) are stored on the
   progress record as `selected_group_ids` (already exists on
   `SurveyProgress` — see prerequisite note).
2. The runtime ordering pipeline (`_resolved_group_order_ids` in
   `checktick_app/surveys/views.py`) accepts an optional
   `selected_group_ids` parameter. When provided, it filters the ordered
   group list to only those IDs. This is the single hook the
   `section_menu` layout adds to the runtime.
3. `_order_questions_by_group` passes `selected_group_ids` through to
   `_resolved_group_order_ids`, and drops questions from non-selected
   groups (including the "remaining groups" fallback).
4. The branching config (`_build_branching_config`) is built from the
   filtered question list, so `jump_to` / `show` / `hide` conditions
   that target a now-absent section are simply never triggered.
5. Repeats work unchanged — a repeatable section the participant didn't
   pick just isn't in their path.

This keeps the **Survey Map = Preview = Live** ordering contract intact.
The Survey Map shows the full authored survey (it is an authoring-time
view); the live route applies the selection filter on top.

### Picker route and template

The picker is a step inside the existing take view
(`_handle_participant_submission`), not a separate URL. When
`survey.layout == "section_menu"` and the participant has no
`selected_group_ids` on their progress record, the take view renders the
picker template instead of the question list:

- **Template:** `surveys/section_menu_picker.html`
- **POST action:** `action=select_sections` with `selected_groups` as a
  list of group IDs. The handler:
  1. Validates min/max against the `SectionMenu` config.
  2. Unions in mandatory section IDs.
  3. Orders the final selection (authored order or participant tick
     order, depending on `order_mode`).
  4. Stores the IDs on `SurveyProgress.selected_group_ids`.
  5. Re-renders the take view, which now shows the filtered question list.
- **POST action:** `action=change_sections` clears `selected_group_ids`
  and returns to the picker.
- **On resume:** if `selected_group_ids` is already populated, skip the
  picker and go straight to the questions. A "Change sections" link in
  the progress bar on `detail.html` returns to the picker.

### Preview

The preview view (`survey_preview`) accepts a `?simulate_groups=1,3`
query parameter. When present, the questions are filtered to those groups
(plus mandatory ones) via `_order_questions_by_group`. A "Simulate
section selection" panel on `detail.html` (shown only in preview mode)
provides checkboxes for pickable sections and an Apply button.

### Item sync

`_sync_section_menu_items(menu, survey)` is called on every Organise
page visit and Survey Map visit when `layout == section_menu`. It
ensures one `SectionMenuItem` per survey group, preserving existing
flags (is_pickable, estimated_minutes) and order. Groups removed from
the survey are cascade-deleted via the FK.

## Outline grammar

The `SECTION_MENU` block is parsed in
`parse_bulk_markdown_with_collections` (`markdown_import.py`), alongside
the existing `REPEAT` parsing.

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

- The `~ pickable` suffix is placed on the actual content group headings
  (not on separate lines in the `SECTION_MENU` block). This avoids
  duplicate group headings and keeps the parser single-pass.
- `~` is used (not `?`) because `?` is already the condition prefix in
  the outline grammar; reusing it would be ambiguous.
- Estimated time can be appended: `~ pickable, 5 min`.
- Groups without `~` under a `SECTION_MENU` block are mandatory.
- Config lines are indented (spaces or `>` blockquote markers).
- A blank line ends the config block.

The export side (`_export_survey_to_markdown` in `views.py`) emits the
`SECTION_MENU` block at the top and appends `~ pickable` suffixes to
pickable group headings. The config survives export → import round-trips.

The bulk upload view applies the parsed `section_menu` config: sets
`survey.layout`, creates/updates the `SectionMenu` + items, and applies
per-group pickable/estimated_minutes flags.

## Issues and edge cases

| Issue | Why it matters | Handling |
|---|---|---|
| Branching targets a pickable section | A `jump_to` to a section the participant didn't pick is a dead branch. | Live warning on the Organise page configuration card. Checks both `target_group` (section jumps) and `target_question` (question jumps into pickable sections). Non-blocking — just warns. Links to Survey Map for review. |
| Repeats inside non-selected sections | A repeat that's never reached. | Handled automatically by the filter. Survey Map still shows the full structure. |
| Empty selection | `min_selected=0` with no mandatory sections = blank survey. | Warning on save: at least one section must be mandatory OR `min_selected ≥ 1`. |
| Single-section surveys | A menu with one pickable section is pointless. | Hide the Section menu card hint when the survey has < 2 sections; warn on switch. |
| Save progress + selection | A participant who picks 3 sections, leaves, and returns must not have to re-pick. | `selected_group_ids` already exists on `SurveyProgress` (v0.12.0). On resume, skip the picker if it's populated. |
| Min/Max drift | Author lowers `max_selected` after a participant has already saved 4 picks. | On resume, clamp to the new max and prompt the participant to drop one. Edge case — worth a test. |
| Mandatory sections can't be deselected | Picker must disable their checkboxes. | Render as locked rows, not checkboxes. |
| Outline round-trip | Menu config must survive export → import. | `SECTION_MENU` block in the outline grammar + round-trip test in `test_outline_section_menu.py`. |
| Preview | Author must be able to try the picker without a real participant. | "Simulate selection" panel on the preview page with `?simulate_groups=` query param. |
| Naming | "Template" is already used for published sections. | This feature is called **Layout**. Do not reuse "template". |
| Survey Map | The map is authoring-time and shows the full survey. | Pickable/mandatory badge summary above the visualiser. No change to the runtime map. |
| String options in export | `_export_survey_to_markdown` crashed on questions with string options (not dicts). | Fixed with `isinstance(option, dict)` guards before all `.get()` calls. |

## Publication workflow

The `allow_resume` and `allow_response_redaction` toggles already exist
on `Survey` (added in v0.12.0, migration `0059`). They are presented in
the publication workflow alongside the existing visibility and audience
declarations.

The layout feature does not add new publication-workflow toggles — the
`Survey.layout` field is set on the Organise page, not in the publication
workflow.

## Build order (completed)

All steps are complete. Step 1 was done in PR #319 (v0.12.0); steps 2–10
were done in PR #320 (v0.13.0).

1. ~~**Save-and-resume**~~ — merged in PR #319 (v0.12.0).
2. ~~**`Survey.layout` field** + migration~~
3. ~~**Section menu card on the Organise page**~~
4. ~~**`SectionMenu` / `SectionMenuItem` models** + admin~~
5. ~~**Picker page** + selection filter in `_resolved_group_order_ids`~~
6. ~~**Builder layout label**~~
7. ~~**Outline grammar** + import/export round-trip~~
8. ~~**Warnings**~~
9. ~~**Survey Map badges** + preview simulate panel~~
10. ~~**Docs updates**~~

## Open questions

- **"Change sections" after starting.** Allowing it is more flexible but
  risks discarded answers. Default to allow-with-confirm, or lock the
  selection after Continue? Worth a quick user test.

## Randomised (RCT) layout

The RCT layout is the system-assigned counterpart to Section menu. Instead
of the participant choosing which sections to complete, the system assigns
them to an **arm** at first access, and the arm's group set becomes their
`selected_group_ids`. The runtime hook (`_resolved_group_order_ids`
filtering by `selected_group_ids`) is reused unchanged — RCT only changes
*who* populates `selected_group_ids`, not how the pipeline consumes it.

### Data model

```python
class Survey(models.Model):
    class Layout(models.TextChoices):
        LINEAR = "linear", "Linear"
        SECTION_MENU = "section_menu", "Section menu"
        RCT = "rct", "Randomised (RCT)"


class RandomisedMenu(models.Model):
    survey = models.OneToOneField(
        Survey, related_name="randomised_menu", on_delete=models.CASCADE,
    )

    class AllocationStrategy(models.TextChoices):
        BALANCED = "balanced", "Balanced (blocked)"
        SIMPLE = "simple", "Simple (weighted)"

    allocation_strategy = models.CharField(
        max_length=20,
        choices=AllocationStrategy.choices,
        default=AllocationStrategy.BALANCED,
    )
    seed = models.BigIntegerField(
        null=True, blank=True,
        help_text=(
            "Optional fixed seed for deterministic allocation across "
            "runs. Blank = system-generated per participant."
        ),
    )


class RandomisedArm(models.Model):
    menu = models.ForeignKey(
        RandomisedMenu, related_name="arms", on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    allocation_ratio = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    groups = models.ManyToManyField(
        QuestionGroup, related_name="arms", blank=True,
    )

    class Meta:
        unique_together = ("menu", "name")
        ordering = ["order", "id"]


class SurveyProgress(models.Model):
    ...
    # [Planned] RCT arm assignment. Only populated for surveys with
    # layout = rct (see docs/survey-layouts.md). Null for other layouts.
    randomisation_seed = models.BigIntegerField(
        null=True, blank=True,
        help_text="Stable seed used for RCT arm allocation (set on first access)",
    )
    assigned_arm = models.ForeignKey(
        "RandomisedArm", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_records",
        help_text="The RCT arm this participant was assigned to at first access",
    )
```

A `linear` or `section_menu` survey has no `RandomisedMenu` row and the
new `SurveyProgress` fields stay null.

**Migration:** `0061_randomised_layout` (adds the `Layout.RCT` choice,
both models, the M2M through table, and both `SurveyProgress` fields).

### Allocation strategy

`_assign_arm_for_progress(progress, menu)` is a standalone pluggable
allocator in `views.py` (kept separate from the runtime pipeline so a
future Delphi `RoundAllocator` can sit next to it without touching RCT).

- **Balanced (blocked):** builds permuted blocks of size
  `sum(arm.allocation_ratio)`, walks the block by allocation count for
  the survey. Deterministic from `(seed, allocation_count)`.
- **Simple (weighted):** weighted random pick from `seed`. Deterministic
  from `seed` alone.

`allocation_count` is `SurveyProgress.objects.filter(survey=…,
assigned_arm__in=arms).count()` — there is a known race window if two
participants hit first-access simultaneously. For the first RCT PR this
is acceptable; a follow-up can serialise allocation under a
`select_for_update` or a per-survey allocation counter.

The seed lives on `SurveyProgress.randomisation_seed` and is set on first
access if absent (system-generated, `random.randint(0, 2**63-1)`). If the
author sets `RandomisedMenu.seed`, it is used as the salt for every
allocation — useful for reproducible dry-runs but should be left blank
for real trials to avoid arm predictability.

### Runtime hook

In `_handle_participant_submission`, when `survey.layout == RCT` and
`progress.assigned_arm is None`, the runtime:

1. Ensures a `RandomisedMenu` exists (creates a default with two empty
   arms if missing — "Intervention" and "Control" — so a freshly
   switched survey is at least runnable).
2. Calls `_assign_arm_for_progress(progress, menu)`.
3. Resolves `selected_group_ids` from the arm's `groups` (M2M), ordered
   by `_resolved_group_order_ids` so the arm's sections keep the
   Organise-page order.
4. Stores both `assigned_arm_id` and `selected_group_ids` on
   `SurveyProgress` and re-renders the take view.

On resume (`assigned_arm` already set), the picker/assignment is skipped
and the take view renders with the previously-resolved
`selected_group_ids`. There is no picker page for RCT — the participant
never sees their arm.

### Outline grammar

The `RANDOMISED` block sits at the top of the outline (analogous to
`SECTION_MENU`) and the `~ arm:<name>` suffix marks which arm(s) a
section belongs to:

```text
RANDOMISED
  strategy: balanced
  seed: 7

# Demographics {demographics}    ~ arm:intervention, arm:control
## Name {name}
(text)

# Intervention {intervention}    ~ arm:intervention
## Dose {dose}
(text)

# Control {control}    ~ arm:control
## Placebo {placebo}
(text)
```

- `strategy` is `balanced` or `simple`.
- `seed` is optional (an integer; omit for system-generated).
- `~ arm:<name>` may repeat (a section in multiple arms). Sections with
  no `~ arm:` suffix are reachable by all arms (the union of all arm
  group sets); the configuration warns if a section is unreachable.
- A blank line ends the config block.

The export side emits the `RANDOMISED` block and `~ arm:<name>` suffixes,
and the config survives export → import round-trips.

### Warnings

- **No arms configured** — the survey cannot be taken; block the take
  view with a clear error and warn on the Organise page.
- **Single arm** — RCT with one arm is degenerate; warn (don't block —
  the author may be mid-setup).
- **Allocation ratio sum zero** — every arm has ratio 0; warn.
- **Unreachable section** — a section not in any arm's group set is
  never seen by any participant; warn.
- **Branching targets an arm-exclusive section** — a `jump_to` into a
  section not in the participant's assigned arm is a dead branch; warn
  (non-blocking, links to Survey Map).
- **All arms share the same group set** — the RCT is structurally
  identical to a linear survey; warn.

### Preview

`survey_preview` accepts `?simulate_arm=<arm_id>`. When present, the
questions are filtered to that arm's groups (ordered by
`_resolved_group_order_ids`). A "Simulate arm" panel on `detail.html`
(preview mode only) lists the arms as radio buttons and applies the
filter on submit.

### Survey Map

The Survey Map shows the full authored survey. When `layout == rct`, a
badge summary above the visualiser lists each arm and its sections, so
the author can see at a glance which sections are arm-exclusive.

### Issues and edge cases

| Issue | Why it matters | Handling |
|---|---|---|
| Allocation race | Two participants hitting first access simultaneously could both compute the same `allocation_count`. | Acceptable for first PR. Document; follow-up can `select_for_update`. |
| Author edits arms after enrolment | A participant already enrolled keeps their `assigned_arm`; the `RandomisedArm` FK protects them via `SET_NULL` only if the arm is deleted. | Warn on arm deletion: enrolled participants keep their stored `selected_group_ids` even if the arm is removed. |
| Empty arm | An arm with no groups yields an empty survey. | Warn on save; block the take view if the assigned arm has no groups (fall back to all sections). |
| Min/Max drift analogue | Author shrinks an arm's group set after enrolment. | Stored `selected_group_ids` is preserved on resume; the arm's current group set is only consulted on first assignment. |
| Outline round-trip | Arm assignment must survive export → import. | `RANDOMISED` block + `~ arm:` suffixes; round-trip test in `test_outline_randomised.py`. |
| Determinism | Authors running dry-runs want reproducible allocation. | Optional `RandomisedMenu.seed` salts the allocator; blank in real trials. |

### Delphi compatibility

The RCT design is deliberately shaped so the planned Delphi workflow can
reuse its ingredients:

- `SurveyProgress.assigned_arm` (FK, set at first access, queryable for
  analysis) is the direct precedent for `SurveyProgress.delphi_round`
  (FK to a future `DelphiRound` model). Same shape, separate field —
  arms and rounds are orthogonal dimensions.
- `SurveyProgress.randomisation_seed` is the precedent for Delphi's
  per-participant stable identifier used to keep round-N+1 assignment
  stable across resume.
- The runtime hook (`_resolved_group_order_ids` filtering by
  `selected_group_ids`) is unchanged. Delphi will resolve
  `selected_group_ids` from the current round's section set instead of
  an arm's group set — same hook, different allocator.
- `_assign_arm_for_progress` is a standalone pluggable function; a
  future `_assign_round_for_progress` sits next to it without touching
  RCT.
- The `?simulate_arm=` preview path is the precedent for Delphi's
  round preview (`?simulate_round=`). The RCT arm preview only *filters*
  questions by arm group IDs — it does not aggregate responses. A
  response-aggregation helper (`aggregate_responses_by_group` in a future
  `delphi.py`) is **not yet built**; it is the one Delphi-critical pattern
  that no earlier layout exercised, and is the first thing the Delphi
  build adds (see §Delphi (consensus rounds) below). Inter-round
  aggregate feedback itself is rendered via content blocks (see
  §Content blocks) whose `options.body_md` is substituted from the
  previous round's aggregated responses at view time.
- Qualitative aggregation (thematic summary of free-text responses) is
  handled by the existing `theme_analyzer.summarise_themes()` function,
  which is already opt-in, unlock-gated, sanitised, and gracefully
  degrades. Delphi reuses it per long-text question when the author
  generates inter-round feedback.
- RCT does **not** introduce scheduling, anonymity-beyond-aggregation,
  or convergence tracking — those are Delphi-only and stay out of this
  PR to keep RCT scope tight.

## Guided layout

The Guided layout shows one question per screen with Next/Back
navigation, instead of scrolling through all questions on a single
page. It is primarily a **rendering change** layered on top of the
existing ordering pipeline — no new model, no new `SurveyProgress` field,
and no new runtime hook. The migration (`0062_guided_layout`) only adds
the `guided` choice to `Survey.layout`.

### Rendering contract

All questions still render in the DOM (so branching, repeats, follow-ups,
autosave, and the save-and-resume buttons all work unchanged). A
client-side `guided.js` module shows one step at a time by toggling data
attributes that the scoped CSS in `detail.html` reacts to:

- `data-guided` on the form (gates the scoped CSS).
- `data-guided-group` on each group fieldset (so the section header
  shows for the current question's group).
- `data-guided-extra` on patient/professional details fieldsets (final
  steps before submit).
- `data-guided-current` / `data-guided-current-group` /
  `data-guided-current-instance` markers set by `guided.js` on the
  visible step and its ancestors.
- A sticky guided nav bar (Back / step indicator / Next, with a real
  Submit button revealed on the last step so native form validation
  runs).

### Visibility contract with branching.js

`branching.js` sets inline `style.display` on `[data-question-id]`
(`""` = visible, `"none"` = hidden by a condition). The guided layer
uses data attributes + stylesheet rules, never inline display, so the
two never fight: a question hidden by branching stays hidden (inline
`none` beats CSS); a question shown by branching but not current is
hidden by the CSS rule (inline `""` removes the inline style so the
stylesheet `display:none` applies). The guided nav skips
branching-hidden questions so the participant never lands on one.

### Orthogonality and Delphi compatibility

Guided is orthogonal to the selection mechanism (linear,
section_menu, rct, or a future Delphi round allocator): it operates on
whatever `[data-question-id]` / `[data-guided-extra]` elements the
pipeline produced, regardless of how `selected_group_ids` was
populated. This means:

- A future Delphi round allocator can reuse `guided.js` unchanged —
  it just renders a different subset of questions per round, and the
  guided nav walks them one at a time.
- Guided composes with section_menu and rct: a section_menu survey in
  guided layout shows the picker first, then walks the chosen
  sections one question at a time; an rct survey in guided layout
  walks the assigned arm's sections one question at a time.

### Save and resume

The guided layer does not change the submit path or the save/resume
buttons. The scoped CSS only hides the default `button[type="submit"]`
that is a direct child of `form[data-guided]` (replaced by the guided
nav's own submit button on the last step). The AJAX-driven "Save and
come back later" button is `type="button"` and is not a direct-child
submit, so it is unaffected. Autosave (`save_draft`) fires on
`input`/`change` events that bubble to the form regardless of which
step is visible.

## Staged (longitudinal) layout

The Staged layout unlocks sections over time in defined phase windows.
Each phase has a window measured in integer days from an anchor
(participant enrolment or survey open). The runtime recomputes the
open phases on each access and resolves `selected_group_ids` from their
union, reusing the same `_resolved_group_order_ids` filtering hook as
section_menu and rct. Unlike rct (fixed arm assignment), the open set
changes over time, so `selected_group_ids` is recomputed and
overwritten each visit — never read from a stored value.

### Data model

```python
class Survey(models.Model):
    class Layout(models.TextChoices):
        LINEAR = "linear", "Linear"
        SECTION_MENU = "section_menu", "Section menu"
        RCT = "rct", "Randomised (RCT)"
        GUIDED = "guided", "Guided"
        STAGED = "staged", "Staged (longitudinal)"


class StagedMenu(models.Model):
    survey = models.OneToOneField(
        Survey, related_name="staged_menu", on_delete=models.CASCADE,
    )

    class Anchor(models.TextChoices):
        ENROLMENT = "enrolment", "From participant enrolment"
        SURVEY_OPEN = "survey_open", "From survey open date"

    anchor = models.CharField(
        max_length=20, choices=Anchor.choices, default=Anchor.ENROLMENT,
    )


class StagedPhase(models.Model):
    menu = models.ForeignKey(
        StagedMenu, related_name="phases", on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    start_offset_days = models.PositiveIntegerField(default=0)
    end_offset_days = models.PositiveIntegerField(
        null=True, blank=True,  # null = open-ended
    )
    groups = models.ManyToManyField(
        QuestionGroup, related_name="phases", blank=True,
    )

    class Meta:
        unique_together = ("menu", "name")
        ordering = ["order", "id"]
```

A `linear` / `section_menu` / `rct` / `guided` survey has no `StagedMenu`
row. No new `SurveyProgress` field is needed: unlike rct (fixed arm
assignment), staged recomputes the open set each access.

**Migration:** `0063_staged_layout` (adds the `Layout.STAGED` choice and
both models, including `BigAutoField` on the new tables and the M2M
through table).

### Phase resolution

`checktick_app/surveys/staged.py` holds pure, testable functions used
by the take view. Kept separate from the runtime pipeline so a future
Delphi round scheduler can sit next to it without touching the take
view (see §Delphi compatibility below).

- `anchor_time(menu, enrolment, survey_start)` — the reference time for
  phase windows. For `enrolment`, the participant's
  `SurveyProgress.created_at` (falling back to `survey_start` on first
  access). For `survey_open`, `Survey.start_at`.
- `is_phase_open(phase, anchor, now)` — True when
  `anchor + start <= now < anchor + end` (end null = open-ended).
- `open_phases(menu, enrolment, survey_start, now)` — ordered list of
  open phases.
- `open_group_ids(menu, enrolment, survey_start, now)` — ordered,
  de-duplicated group IDs from currently-open phases.

All offsets are integer days. `datetime` arithmetic uses timezone-aware
values throughout.

### Runtime hook

In `_handle_participant_submission`, when `survey.layout == STAGED` and
`progress is not None`, the runtime:

1. Computes `open_ids` via `staged.open_group_ids(menu, enrolment,
   survey_start, now)`.
2. Orders the final selection via `_resolved_group_order_ids(survey)` so
   the open phases' sections keep the Organise-page order.
3. Stores the result on `SurveyProgress.selected_group_ids` (overwriting
   any previous value — staged recomputes each visit).
4. If the open set is empty, renders `surveys/staged_no_phases.html` (a
   friendly "check back later" page) instead of an empty form. The
   progress row is preserved so resume works when a phase opens later.

On resume, the open phases are recomputed — if a new phase has opened
since the last visit, the participant sees it; if a phase has closed,
they no longer see it. There is no picker for staged — the open set is
system-controlled.

### Outline grammar

The `STAGED` block sits at the top of the outline (analogous to
`SECTION_MENU` / `RANDOMISED`) and the `~ phase:<name>` suffix marks
which phase(s) a section belongs to:

```text
STAGED
  anchor: enrolment
  phase Baseline: 0 .. 14
  phase Follow-up: 14 .. 28
  phase Review: 180

# Demographics {demographics}    ~ phase:Baseline, phase:Follow-up
## Name {name}
(text)

# Baseline {baseline}    ~ phase:Baseline
## BQ {bq}
(text)

# Follow-up {followup}    ~ phase:Follow-up
## FQ {fq}
(text)
```

- `anchor` is `enrolment` or `survey_open`.
- `phase <name>: <start> [.. <end>]` defines a phase window in integer
  days. `<end>` is optional (open-ended). Phases referenced only via
  `~ phase:` suffixes (no config line) default to `start=0, end=None`.
- `~ phase:<name>` may repeat (a section in multiple phases). Sections
  with no `~ phase:` suffix under a `STAGED` block are in no phase
  (unreachable; warned on the Organise page).
- A blank line ends the config block.

The export side emits the `STAGED` block and `~ phase:<name>` suffixes,
and the config survives export → import round-trips.

### Warnings

- **No phases configured** — the survey has no phases; add at least one.
- **Single phase** — structurally identical to a linear survey.
- **survey_open anchor with no start date** — anchor is None, nothing
  ever opens.
- **Unreachable section** — a section not in any phase.
- **Overlapping phase windows for the same section** — the runtime
  unions them, so the section stays open across both (flagged so the
  author knows).
- **Branching targets a phased section** — a `jump_to` into a phased
  section is a dead branch when the phase is closed.

### Preview

`survey_preview` accepts `?simulate_phase=<phase_id>`. When present, the
questions are filtered to that phase's groups (ordered by
`_resolved_group_order_ids`) regardless of whether the phase is
currently open. A "Simulate phase" panel on `detail.html` (preview mode
only) lists the phases as radio buttons and applies the filter on
submit.

### Survey Map

The Survey Map shows the full authored survey. When `layout == staged`,
a **phase composition** badge summary appears above the visualiser
listing each phase, its day-window, and its sections, so the author can
see at a glance which sections belong to which phase.

### Issues and edge cases

| Issue | Why it matters | Handling |
|---|---|---|
| Recompute vs store | Unlike rct (fixed arm), the open set changes over time. | Recompute `selected_group_ids` on every access; never read a stored value. |
| No phases open | A participant arrives between phases. | Render `staged_no_phases.html`; preserve the progress row so resume works when a phase opens. |
| No StagedMenu configured | A freshly-switched survey has no phases. | Render `staged_no_phases.html`; the organise-view warnings flag the misconfiguration. |
| survey_open anchor, no start_at | Anchor is None, nothing ever opens. | Warn on the Organise page; the take view renders the no-phases page. |
| Overlapping phase windows | A section in two overlapping phases stays open across both. | Warn (non-blocking); the runtime unions the open phases. |
| Outline round-trip | Phase config must survive export → import. | `STAGED` block + `~ phase:` suffixes; round-trip test in `test_outline_staged.py`. |
| Future-phase leakage | Participants must not see sections from phases that haven't opened. | The take view only resolves groups from currently-open phases; future phases are never in `selected_group_ids`. |

### Delphi compatibility

The Staged design is deliberately shaped so the planned Delphi workflow
can reuse its ingredients:

- `StagedPhase` (with `start_offset_days` / `end_offset_days` and an M2M
  to `QuestionGroup`) is the direct precedent for a future `DelphiRound`
  model. Same shape, separate model — phases and rounds are orthogonal
  dimensions.
- The runtime hook (`_resolved_group_order_ids` filtering by
  `selected_group_ids`) is unchanged. Delphi will resolve
  `selected_group_ids` from the current round's section set instead of
  the open phases' union — same hook, different scheduler.
- `staged.py`'s pure functions (`anchor_time`, `is_phase_open`,
  `open_phases`, `open_group_ids`) are the precedent for Delphi's
  round-scheduling helpers. A future `delphi.py` sits next to it without
  touching staged.
- The `?simulate_phase=` preview path is the precedent for Delphi's
  round preview (`?simulate_round=`). Inter-round aggregate feedback
  is rendered via content blocks (see §Content blocks) — no new
  feedback model in Delphi.
- Staged does **not** introduce anonymity-beyond-aggregation or
  convergence tracking — those are Delphi-only and stay out of this
  PR to keep Staged scope tight.

## Matrix (free navigation) layout

The Matrix layout shows all sections as cards on a landing page. The
participant jumps in and out of any section in any order, with completion
indicators showing which sections are done. Unlike the other layouts (which
filter `selected_group_ids` and render a single take page that submits the
whole survey at once), matrix has a **landing page + per-section take pages +
a final submit**. This is the biggest layout change since section_menu.

### Data model

```python
class Survey(models.Model):
    class Layout(models.TextChoices):
        ...
        MATRIX = "matrix", "Matrix (free navigation)"


class MatrixMenu(models.Model):
    survey = models.OneToOneField(
        Survey, related_name="matrix_menu", on_delete=models.CASCADE,
    )
    prompt_text = models.CharField(
        max_length=255,
        default="Click a section to begin. You can complete them in any order.",
    )

    class OrderMode(models.TextChoices):
        AUTHORED = "authored", "As authored"
        PARTICIPANT = "participant", "In visit order"

    order_mode = models.CharField(
        max_length=20, choices=OrderMode.choices, default=OrderMode.AUTHORED,
    )
    allow_revisit = models.BooleanField(default=True)


class SurveyProgress(models.Model):
    ...
    completed_group_ids = models.JSONField(
        default=list, blank=True,
        help_text=(
            "Section IDs the participant has marked complete in a matrix "
            "survey (soft indicator; final submit re-validates)."
        ),
    )
```

A `linear` / `section_menu` / `rct` / `guided` / `staged` survey has no
`MatrixMenu` row and `completed_group_ids` stays empty.

**Migration:** `0064_matrix_layout` (adds the `Layout.MATRIX` choice, the
`MatrixMenu` model, and the `SurveyProgress.completed_group_ids` field).

### Runtime hook

Matrix does **not** use the `selected_group_ids` filtering hook the way the
other layouts do. Instead, it has a dedicated runtime path in
`_handle_participant_submission`:

1. **GET without `?section=<gid>`** → renders `matrix_landing.html` (cards
   with completion indicators). Each card shows the section state
   (`complete` / `in_progress` / `not_started`) computed from
   `partial_answers` + `completed_group_ids`.
2. **GET with `?section=<gid>`** → filters `selected_group_ids` to just
   that one group so `detail.html` renders only that section's questions.
   The template shows "Save and complete section" + "Back to overview"
   buttons instead of the standard Submit.
3. **POST `action=complete_section`** → collects answers, validates the
   section's required questions, marks `completed_group_ids`, redirects to
   the landing page.
4. **POST `action=save_draft`** → saves answers; if the section was
   complete, un-marks it (editing → back to "in progress").
5. **POST `action=submit_survey`** → final whole-survey submission.
   Re-validates all required questions across all sections (hard gate —
   `completed_group_ids` is a soft indicator and can lie). Builds the
   `SurveyResponse` from `progress.partial_answers` (accumulated across
   section visits) plus demographics/professional from POST.

For public/unlisted surveys without a credential, a session-based
`SurveyProgress` row is created on first access (matrix requires
server-side completion tracking). This mirrors the section_menu picker's
throwaway progress row handling.

### Section states

`checktick_app/surveys/matrix.py` holds pure, testable functions used by
the take view. Kept separate from the runtime pipeline so a future Delphi
round scheduler can sit next to it without touching the take view.

- `section_state(progress, survey_id, group_id)` — returns `complete`,
  `in_progress`, or `not_started`.
- `missing_required_question_ids(partial_answers, survey_id, group_id)` —
  used by `complete_section` (validates before marking complete) and by the
  final `submit_survey` (re-validates all sections).
- `landing_card_states(progress, survey_id, group_ids)` — one card-state
dict per group, in order.
- `all_sections_complete(progress, survey_id, group_ids)` — soft check;
  final submit re-validates as a hard gate.
- `add_completed_group` / `remove_completed_group` — idempotent list
  helpers.

### Outline grammar

The `MATRIX` block sits at the top of the outline (analogous to
`SECTION_MENU` / `RANDOMISED` / `STAGED`) and carries only config lines.
No `~` suffixes are needed — every section in the survey is a card on the
matrix landing page by default.

```text
MATRIX
  prompt: "Choose a section to begin"
  order: participant
  allow_revisit: false

# Demographics {demographics}
## Name {name}
(text)

# History {history}
## Condition {condition}
(text)
```

- `prompt` is the landing-page prompt text (quoted).
- `order` is `authored` or `participant`.
- `allow_revisit` is `true` or `false`.
- A blank line ends the config block.

The grammar is **optional** — the Organise page UI is the primary config
path. The grammar exists so the AI builder and power users can
import/export matrix surveys via the outline.

The export side emits the `MATRIX` block with config lines, and the config
survives export → import round-trips.

### Warnings

- **Single-section survey** — matrix with < 2 sections is pointless; warn
  on layout switch.
- **Cross-section branching** — a `jump_to` that targets a question in a
  *different* section is meaningless in matrix (the participant navigates
  via the landing page, not linearly). Same-section jumps work normally.
  Non-blocking; links to Survey Map for review.

### Preview

`survey_preview` accepts `?simulate_section=<gid>`. When present, the
questions are filtered to that one section so the author can preview what
a participant would see when they open that card. A "Simulate section"
panel on `detail.html` (preview mode only) lists the sections as radio
buttons.

### Survey Map

The Survey Map shows the matrix configuration badges above the visualiser:
prompt text, order mode, and revisit toggle.

### Issues and edge cases

| Issue | Why it matters | Handling |
|---|---|---|
| Soft vs hard completion | `completed_group_ids` can lie if the participant edits a section after marking it complete. | `save_draft` on a completed section un-marks it. Final `submit_survey` re-validates all required questions regardless of `completed_group_ids`. |
| Per-section validation | The participant should not be able to mark a section complete with missing required questions. | `complete_section` validates required questions before marking complete; redirects back to the section with an error if any are missing. |
| Accumulated answers | Answers are spread across multiple section visits, not in a single POST. | `SurveyProgress.partial_answers` accumulates across visits. `submit_survey` builds the `SurveyResponse` from `partial_answers`, not from POST. |
| Public/unlisted surveys | Matrix requires server-side completion tracking, but `_get_or_create_progress` returns None for public/unlisted without credentials. | Create a session-based `SurveyProgress` row on first access (mirrors section_menu picker handling). |
| Demographics/professional | These fields are not per-section question answers. | Collected from POST on `submit_survey` (the landing page's submit form includes them). |
| Outline round-trip | Matrix config must survive export → import. | `MATRIX` block + config lines; round-trip test in `test_outline_matrix.py`. |
| Cross-section branching | `jump_to` to a different section is meaningless. | Warn on the Organise page (non-blocking). |

### Delphi compatibility

The Matrix design is deliberately shaped so the planned Delphi workflow can
reuse its ingredients:

- `SurveyProgress.completed_group_ids` is the reusable ingredient for
  Delphi's within-round completion tracking. A future
  `delphi_completed_rounds` field would have the same shape (list of IDs,
  soft indicator, hard gate on final submit). Matrix proves the pattern:
  accumulate → validate → submit.
- The per-section take + `complete_section` pattern is the precedent for
  Delphi's per-round take + `complete_round`. The runtime hook
  (`_handle_participant_submission` branching on layout) is unchanged —
  Delphi will add another branch, not modify matrix's.
- `matrix.py`'s pure functions (`section_state`,
  `missing_required_question_ids`, `landing_card_states`) are the
  precedent for Delphi's round-state helpers. A future `delphi.py` sits
  next to it without touching matrix.
- The `?simulate_section=` preview path is the precedent for Delphi's
  round preview (`?simulate_round=`). Inter-round aggregate feedback
  is rendered via content blocks (see §Content blocks) — no new
  feedback model in Delphi.
- Matrix does **not** introduce convergence tracking or
  anonymity-beyond-aggregation — those are Delphi-only and stay out
  of this PR to keep Matrix scope tight.

## Content blocks (cross-layout)

Content blocks are a `SurveyQuestion` type (`content_block`) that renders
static content — heading, Markdown body, and hyperlinks — with no answer
input. They go anywhere a question goes: any group, any position, multiple
per group, any layout. A content block placed first in the first section is
a landing page; one placed between substantive sections is an interstitial
disclosure; one placed last is a closing acknowledgement.

### Data model

```python
class SurveyQuestion(models.Model):
    class Types(models.TextChoices):
        ...
        CONTENT_BLOCK = "content_block", "Content block"
```

A `content_block` question's `options` JSONField holds:

```python
{
    "heading": str,           # rendered heading (optional — block can have no heading)
    "subtitle": str,          # rendered subtitle (optional)
    "body_md": str,           # Markdown body (optional)
    "image_id": int | None,   # FK to QuestionImage (optional, builder-only upload)
    "links": [                # reference / disclosure links (optional, zero or more)
        {"label": str, "url": str},
        ...
    ],
    "consent": {              # consent checkbox (optional)
        "question_id": int,   # FK to a linked yesno question
        "statement": str,     # consent statement text
        "required": bool,     # if True, participant must agree to progress
    } | None,
    "render_once": bool,      # default True; render once even in repeatable groups
}
```

All components are optional — the author includes only what they need.

`SurveyQuestion.text` is the **internal builder label** (e.g. "Content
block", "Introduction") — it is NOT rendered to participants. This mirrors
the `template_patient` / `template_professional` pattern, where
`question.text` is the builder label and the rendered content comes from
`options`.

Image upload is **builder-only** — the outline grammar does not carry
image references. Authors upload images via the builder; the outline only
stores the question type and text.

A content block is **never `required`** — it has no answer. This is
enforced in three places (defence in depth):

1. **Parser** (`markdown_import.py`): forces `required=False` regardless
   of the `*` suffix.
2. **Special template creation** (`builder_group_template_add`): creates
   with `required=False`.
3. **Model** (`SurveyQuestion.clean()`): raises `ValidationError` if
   `required=True`.

`missing_required_question_ids` skips `content_block` questions
automatically (they are never `required`).

### Markdown sanitisation

`body_md` is rendered to HTML via
`checktick_app/core/markdown_safety.py:render_content_block_markdown`,
which runs Python-Markdown (``extra``, ``nl2br``, ``sane_lists``) then
`nh3.clean` with an explicit tag/attribute allowlist. No `<script>`,
`<style>`, `<iframe>`, `<form>`, or event-handler attributes survive.
Link `href`/`img src` URLs are restricted to `http`, `https`, and `mailto`
schemes. See `docs/security-overview.md` §A03 (S16/S17).

Content-block link URLs are validated against the same scheme allowlist
at save time via `sanitise_link_url` (builder form and parser).

### Consent

Consent is an optional component of a content block. When the author
configures consent (via the content block's configure panel), a linked
`yesno` question is created in the same group, hidden from the builder
list via a `_content_block_parent` marker in its options. The answer is
stored on the yesno question ("yes"/"no") — clean audit trail ("who
agreed to X?"), clean export, clean data-protection defence. The content
block renders the consent checkbox inline using the yesno question's form
field name. When the author sets "required", the participant cannot
progress until they agree (`missing_required_question_ids` validates it).

Clearing the consent statement in the configure panel deletes the linked
yesno question.

The `yesno` type already supports custom labels (see `markdown_import.py`).
A `boolean` checkbox type is not added — an unticked checkbox is ambiguous
(didn't see it vs. actively declined), which is exactly what a medical
app should avoid for consent. The parser's existing `boolean` alias maps
to `yesno`; if a real boolean type is ever added, that alias needs
forking.

### Rendering

`detail.html` renders a `content_block` question as a single block with
optional components in order: heading, subtitle, image, body, links,
consent checkbox. No standard answer input (except the consent checkbox
when configured). The standard `q.text` H2 is suppressed for content
blocks — the internal label is not shown to participants. The matrix
landing page composes with it — a content block as the first question in
the first section renders above the cards as a landing header (see
§Matrix layout).

For non-matrix layouts, a "landing page" or "section intro" is simply a
`QuestionGroup` whose only question is a `content_block` — the runtime
renders sections in order, so a single-content-block section renders as
a static page between question sections.

### Outline grammar

```text
## Introduction
(content_block)
heading: Welcome
variant: disclosure
link: Privacy notice|https://example.com/privacy
link: Study protocol|https://example.com/protocol

Welcome to the study. Please read the privacy notice and links above
before continuing.
```

- `heading` is optional (the rendered heading; `## Introduction` is the
  internal label, not rendered to participants).
- `variant` is optional (defaults to `text`).
- `render_once` is optional (defaults to `true`).
- `link:` lines are one per reference, `Label|URL` format.
- The body is everything after the config lines (multiline Markdown).
- A blank line after the config block starts the body; a new `#`/`##`
  heading ends it.

The export side emits the `(content_block)` type and config lines, and
the body survives export → import round-trips.

### Builder

Content blocks are a **Special Template** option in the builder (alongside
patient and professional details), not a regular question type. The author
adds a content block via the "Special Templates" tab, which creates a
question with `text="Content block"` and default (empty) options. A
"Configure content block" panel (in the question row, like the
patient/professional configure panels) provides all optional components:

- **Heading** input (the rendered heading, `options.heading`)
- **Subtitle** input (the rendered subtitle, `options.subtitle`)
- **Body** textarea (Markdown, `options.body_md`)
- **Image** upload (reuses `QuestionImage`, non-medical warning)
- **Links** repeater (parallel `link_label[]` / `link_url[]` lists, zero or more)
- **Consent** section (statement text + required toggle; creates a linked yesno question)
- **Render once** toggle (`options.render_once`)

`SurveyQuestion.text` is the internal builder label (e.g. "Content
block"), not rendered to participants. `options.heading` is the rendered
heading. `body_md` is the primary authored content of the block, rendered
as Markdown → HTML, and can be multiple paragraphs.

### Branching

Content blocks cannot be condition **sources** (they have no answer). As
condition **targets**:

- `JUMP_TO` a content block is fine (just renders the block).
- `SHOW`/`HIDE` on a content block produces a non-blocking warning on the
  Organise page (content blocks have no answer — consider `jump_to`
  instead).

### CSV export and reporting

Content blocks are skipped in CSV export (no column) and in the reporting
workflow (not in `CHARTABLE_TYPES` / `TEXT_TYPES` / `NUMERIC_TYPES`).

### Delphi compatibility

A content block whose `body_md` (and optionally `heading`) is rendered
from aggregate data (medians, IQRs, themes) instead of authored Markdown
is Delphi's inter-round feedback view. Same model, different body source
— the author marks the block as "aggregate feedback" (a flag in
`options`, no migration needed since `options` is a JSONField) and the
runtime substitutes `options.body_md` / `options.heading` from the
previous round's responses at view time. `question.text` (the internal
label) stays stable across rounds. No new model, no new `SurveyProgress`
field.

## Long text (textarea)

A `long_text` question type — a textarea version of `text` — gives
authors a "please describe..." / "any other comments" question with a
multi-line input. It landed in v0.16.1 (migration `0065_long_text`).

### Data model

```python
class SurveyQuestion(models.Model):
    class Types(models.TextChoices):
        ...
        LONG_TEXT = "long_text", "Long text (textarea)"
```

`long_text` is a new type, not a `text` variant — the existing pattern
is one type per rendering shape (see `template_patient` /
`template_professional`), and the builder, template, and export are all
type-dispatched already. The answer is stored as a string, same as
`text`. CSV export reuses the existing string answer path
(`_format_answer_for_export`).

### Builder

The builder form renders a `<textarea>` for `long_text` questions
(rows=4). No config section is shown (no options, no format variants).

### Outline grammar

```text
## Any other comments
(long_text)
```

- Aliases: `textarea`, `paragraph`, `long_text`.
- The question text is the label; the answer is a multi-line string.
- Round-trips through export → import like the other types.

### Migration

`0065_long_text` adds the `LONG_TEXT` choice to `SurveyQuestion.type`.
No new model, no new `SurveyProgress` field — just the type and the
builder/template/parser branches.

## Planned layouts

The following layouts are planned for future releases. See
[Survey Layouts](survey-layouts.md#planned-layouts) for the user-facing
descriptions. They are ordered by priority — the order CheckTick intends
to implement them, based on how often the use case is the reason a
research team reaches for REDCap or Qualtrics instead of a simpler tool.

### Delphi (consensus rounds) — priority: high (next)

Multi-round structured consensus workflow. Participants complete rounds,
see aggregate feedback between rounds, and revise their answers. The
classic Delphi method for expert consensus-building in clinical
research, guideline development, and priority-setting.

Builds on the ingredients proven by the earlier layouts:

- `SurveyProgress.assigned_arm` (RCT) → `delphi_round` FK to a
  `DelphiRound` model. Same shape, separate field — arms and rounds are
  orthogonal dimensions.
- `StagedPhase` (start/end offsets, M2M to groups) → `DelphiRound`
  (round windows, group membership). Same shape, separate model.
- `SurveyProgress.completed_group_ids` (Matrix) →
  `delphi_completed_rounds` (within-round completion tracking). Same
  shape (list of IDs, soft indicator, hard gate on final submit).
- `matrix.py` / `staged.py` pure helpers → `delphi.py` round-state
  helpers. Sits next to them without touching them.
- `?simulate_section=` / `?simulate_phase=` preview → round preview
  (`?simulate_round=`).
- Inter-round aggregate feedback is rendered via content blocks (see
  §Content blocks) whose `options.body_md` is substituted from the
  previous round's aggregated responses at view time. No new feedback
  *rendering* model — but a `DelphiRoundFeedback` cache model stores the
  pre-computed aggregate (see below).
- Qualitative aggregation (thematic summary of free-text responses)
  reuses the existing `theme_analyzer.summarise_themes()` function,
  which is already opt-in, unlock-gated, sanitised, and gracefully
  degrades. The LLM thematic analysis is **author-triggered and
  pre-computed** at round close, not per-participant-view — see the
  full design below.

**The one ingredient not yet proven by an earlier layout** is
response aggregation. The RCT arm preview only *filters* questions by
arm group IDs; no layout has needed to collect responses across
participants and compute medians/IQRs/distributions. The Delphi build
therefore starts with a pure `aggregate_responses_by_group()` helper in
`delphi.py`, tested in isolation before any Delphi-specific model or
runtime hook is added.

Priority: high — this is the next layout to implement. The full
technical design is in §Delphi (consensus rounds) — full design below.

### Diary / EMA (ecological momentary assessment) — priority: high

Repeated short surveys triggered on a fixed schedule (daily, 4×/day) or
by events (symptom onset). Used for pain diaries, mood tracking,
medication adherence, and symptom monitoring in clinical trials.

Distinct from Staged (which is phase-based: baseline → 2-week →
6-month). Diaries are high-frequency repeated measures with burst
scheduling, compliance tracking (missed entries), and time-stamp
integrity for regulatory submissions. The scheduling semantics are
fundamentally different from phase windows.

Builds on: Staged phase windows + repeats + progress tracking, but
needs a scheduling engine (cron-like trigger windows) and a compliance
dashboard. Substantial new runtime logic.

Technical notes:
- New `DiaryMenu` model (OneToOne to `Survey`) holding the schedule
  type (`fixed_interval`, `event_triggered`, `burst`), the interval
  (e.g. every 6 hours), the burst schedule (e.g. 7 days on, 7 days off),
  and a compliance threshold (e.g. warn if < 80% of expected entries).
- New `DiaryEntry` model (one per participant per scheduled window)
  tracking the expected time, the actual submission time, and a link to
  the `SurveyProgress` row. This is the compliance audit trail.
- The runtime hook reuses `_resolved_group_order_ids` — a diary entry
  is just a short survey with the same group set each time. The
  difference is the *trigger*, not the *selection*.
- `?simulate_window=` preview path for authors to test the schedule.
- Does **not** introduce real-time push notifications in the first
  iteration — participants receive a reminder email/SMS at the window
  start, and the diary landing page shows the current window's status.

### Two-stage screening / eligibility routing — priority: medium

A brief screener determines eligibility, then routes to the full
survey, an exit page, or an alternative survey. Ubiquitous in clinical
recruitment (e.g. "Are you 18+? Have you had symptoms for >2 weeks?").

Could be done with branching today, but the eligibility → consent →
survey → exit pattern is so common that a dedicated layout gives
researchers a structured template, automatic CONSORT-style flow
diagram data, and clean screen-fail tracking.

Builds on: Branching + content blocks (for consent). Low effort, high
usability payoff. May ship as a layout *template* (pre-configured
branching + content blocks) rather than a full new runtime hook.

Technical notes:
- New `ScreeningMenu` model (OneToOne to `Survey`) holding the
  eligibility rule (a branching expression evaluated against the
  screener answers), the eligible redirect (the full survey slug or
  `"inline"` to continue in the same survey), and the ineligible
  redirect (an exit content block or a separate survey slug).
- New `ScreeningResult` model (one per participant) recording the
  screener answers, the eligibility decision, and the redirect taken.
  This is the CONSORT flow diagram data source.
- The runtime hook is a pre-step in `_handle_participant_submission`
  (like the section_menu picker): if the screener is incomplete, render
  the screener; if complete, evaluate eligibility and redirect.
- `?simulate_eligible=` / `?simulate_ineligible=` preview paths.

### Computer-Adaptive Testing (CAT) — priority: medium

The next question is selected algorithmically based on prior responses
using item-response theory (IRT). Used for PROMIS, NIH Toolbox, and
other validated clinical outcome measures. Enables shorter, more
precise instruments.

Distinct from branching (which is rule-based: if Q3=yes, show Q5). CAT
is statistical — the engine estimates a latent trait (e.g. depression
severity) and selects the next item to minimise uncertainty. This is a
fundamentally different selection mechanism.

Builds on: Guided (one-question-per-screen rendering), but needs an
IRT scoring engine and an item bank with difficulty/discrimination
parameters. Substantial new domain logic.

Technical notes:
- New `CatBank` model (OneToOne to `Survey`) holding the IRT model
  type (`rasch`, `2pl`, `grm`), the stopping rule (SE threshold, max
  items, or both), and the prior distribution parameters.
- New `CatItemParam` model (one per question in the bank) holding the
  difficulty (`b`), discrimination (`a`), and guessing (`c`, 3PL only)
  parameters.
- The runtime hook replaces `_resolved_group_order_ids` for CAT
  surveys: instead of a fixed order, the next question is selected by
  the IRT engine after each response. This is the first layout that
  does **not** reuse the fixed-order pipeline — it is a genuine
  alternative selection mechanism.
- `?simulate_theta=` preview path for authors to test the engine at a
  given trait level.
- High effort. Worth it if CheckTick wants to attract clinical outcomes
  researchers who need PROMIS-capable instruments.

### Crossover / within-subject RCT — priority: medium

Each participant experiences all conditions in sequence (AB, ABA, ABAB)
with washout periods between. Common in clinical pharmacology and
behavioural interventions.

Distinct from RCT (between-subject: one arm per participant). Crossover
is within-subject: all conditions, sequenced. Requires carryover
control, period scheduling, and sequence-balanced allocation (Latin
squares, Williams designs).

Builds on: RCT allocation engine + Staged phase windows, but the
allocation logic (sequence assignment, not arm assignment) and the
per-period analysis are distinct.

Technical notes:
- New `CrossoverMenu` model (OneToOne to `Survey`) holding the design
  type (`latin_square`, `williams`, `counterbalanced`), the number of
  periods, and the washout duration.
- New `CrossoverSequence` model (one per possible sequence) holding the
  ordered list of condition labels.
- `SurveyProgress` gets a `crossover_sequence` FK (like
  `assigned_arm`) and a `crossover_period` integer (current period).
- The runtime hook resolves `selected_group_ids` from the current
  period's condition in the participant's assigned sequence — same
  hook, different allocator.
- `?simulate_sequence=` / `?simulate_period=` preview paths.

### Conjoint / Discrete Choice Experiment (DCE) — priority: low

Choice-based experiments where participants make trade-off choices
between attribute profiles. Used in health economics, patient
preference studies, and HTA submissions.

Requires a fractional-factorial experimental design engine, choice-card
rendering (profile A vs profile B), and specialised analysis
(conditional/mixed logit). None of the current layouts touch this.

Technical notes:
- New `ConjointDesign` model (OneToOne to `Survey`) holding the
  attributes, levels, and the fractional-factorial design matrix.
- New question type `choice_card` rendering two profiles side by side.
- The runtime hook generates choice cards from the design matrix —
  each participant sees a different subset determined by their
  `randomisation_seed` (reusing the RCT seed field).
- Niche but high-value for health economics teams. Significant new
  rendering + design logic.

### Stepped wedge / cluster-randomised — priority: low

Clusters (sites, wards, practices) cross from control to intervention
in a randomised sequence over time. Common in implementation science
and cluster RCTs.

Randomisation is at cluster level, not individual. Participants within
a cluster receive the arm the cluster is currently in. Requires
cluster-level scheduling and a cluster registry.

Builds on: RCT + Staged, but the cluster entity and cluster-level
scheduling are new.

Technical notes:
- New `Cluster` model (one per site/ward/practice) with a
  `cluster_arm` FK that changes over time per the stepped wedge
  schedule.
- New `SteppedWedgeMenu` model (OneToOne to `Survey`) holding the
  number of steps, the step interval, and the randomisation sequence
  of clusters.
- Participants are linked to a cluster (via a profile field or a
  survey-level question); their `selected_group_ids` is resolved from
  the cluster's current arm.
- `?simulate_step=` / `?simulate_cluster=` preview paths.

### 360° / multi-rater assessment — priority: low

Multiple respondents (peers, supervisors, patients) rate a single
subject. Common in medical education and clinician appraisal.

Requires a subject identifier, role-based routing (each rater sees a
different question set about the same subject), and aggregation across
raters. Could be a section_menu variant with a subject-linking step,
but the role-based question routing is distinct.

Technical notes:
- New `MultiRaterMenu` model (OneToOne to `Survey`) holding the rater
  roles (e.g. `self`, `peer`, `supervisor`, `patient`).
- The runtime hook resolves `selected_group_ids` from the rater's role
  (each role sees a different subset of sections about the same
  subject).
- A subject identifier is collected at the start (or via an invite
  token) so responses can be grouped for aggregation.
- Could ship as a section_menu variant with role-based item flags
  rather than a full new model.

### Think-aloud / cognitive interview mode — priority: low

Qualitative interview mode for instrument validation — the researcher
probes while the participant thinks aloud. Usually audio-recorded.

This is interview-mediated, not self-administered. Probably better as a
"mode" flag on the survey than a full layout, but noted here for
completeness.

Technical notes:
- A `mode` field on `Survey` (`self_administered` vs `interview_mediated`).
- In interview mode, the take page renders a simplified view for the
  researcher to drive, with a probe field per question and an optional
  audio recording link.
- Low effort, but narrow use case. May remain a pattern rather than a
  first-class layout.

## Delphi (consensus rounds) — full design

This section is the full technical design for the Delphi layout, the
next layout to be implemented. It is written ahead of implementation so
the design can be reviewed before code is written. Each subsection maps
to a planned commit.

### Overview

The Delphi layout implements a structured multi-round consensus
workflow. Participants complete a series of rounds; between rounds they
see aggregate feedback from the previous round (quantitative
distributions + qualitative themes) and revise their answers. The
author controls the number of rounds, the section set per round, the
round windows, and when to generate inter-round feedback.

The design reuses the runtime hook proven by section_menu / rct /
staged / matrix: `_resolved_group_order_ids` filtering by
`selected_group_ids`. Delphi resolves `selected_group_ids` from the
current round's section set — same hook, different allocator.

### Response aggregation (the first commit)

No earlier layout has needed to collect responses across participants
and compute aggregate statistics. This is the one Delphi-critical
pattern that is unproven, so the Delphi build starts with it in
isolation.

A new `checktick_app/surveys/delphi.py` module exposes pure functions:

```python
def aggregate_responses_by_group(
    survey_id: int,
    group_ids: list[int],
    *,
    submission_filter: Callable[[QuerySet], QuerySet] | None = None,
) -> dict[int, dict[int, dict]]:
    """Collect and aggregate responses for the given groups.

    Returns a nested dict: {group_id: {question_id: stats}}.

    Per question type:
    - likert / numeric: median, IQR (Q1/Q3), min, max, count,
      distribution (value -> count).
    - mc_single / dropdown: frequency distribution, mode, count.
    - mc_multi: frequency per option, co-occurrence top-3, count.
    - yesno: yes_count, no_count, yes_pct, count.
    - long_text: list of response strings (for LLM thematic analysis).
    - text: list of response strings (short, for collation only).
    - content_block: skipped (no answer).

    ``submission_filter`` is an optional callable that filters the
    SurveyProgress/Submission queryset — used by Delphi to scope to a
    specific round's submissions. Defaults to all completed submissions.
    """
```

The function is pure (no side effects, no LLM calls) and tested in
isolation with synthetic responses. It reads decrypted answers via the
existing answer-access layer (the same path the CSV export and summary
report use), so the unlock gate is the caller's responsibility.

### LLM thematic analysis (the second commit)

Qualitative aggregation reuses the existing
`theme_analyzer.summarise_themes()` function, which is already:

- **Opt-in**: a button, never automatic.
- **Unlock-gated**: only decrypted content is sent to the LLM.
- **Per-question**: bounded token volume, one question at a time.
- **Sanitised** through `sanitize_markdown()` before rendering.
- **Graceful degradation**: if the LLM is unavailable, the caller falls
  back to plain collation.

For Delphi, the LLM thematic analysis is **author-triggered and
pre-computed** at round close, not per-participant-view. This preserves
the opt-in principle while avoiding re-running the LLM for every
participant who views round N+1.

The flow:

1. Author closes round N (sets the round's `closed_at`).
2. The organise page shows a "Generate inter-round feedback" button
   (opt-in, tier-gated, unlock-gated).
3. Author clicks → the view calls `aggregate_responses_by_group()` for
   the round's groups, then calls `summarise_themes()` per long-text
   question.
4. The result (quantitative stats + sanitised qualitative theme
   markdown) is cached on a `DelphiRoundFeedback` model.
5. Participants in round N+1 see the cached feedback via content blocks
   whose `options.body_md` is substituted from the cached markdown at
   view time.

The cached content is aggregate, sanitised, and non-identifiable — safe
to store. Raw responses are never stored in the feedback; only the
LLM's paraphrased themes and the quantitative distributions. If the LLM
is unavailable, quantitative feedback still renders; qualitative shows
a graceful "themes unavailable" message.

Audit logging records metadata only (round id, question id, response
count, token count, model name, success/failure, duration) — never the
free-text input or the LLM output verbatim, per the medical-app logging
rules in `AGENTS.md`.

### Data model

```python
class Survey(models.Model):
    ...
    layout = models.CharField(
        max_length=20,
        choices=[
            ("linear", "Linear"),
            ("section_menu", "Section menu"),
            ("rct", "Randomised (RCT)"),
            ("guided", "Guided"),
            ("staged", "Staged (longitudinal)"),
            ("matrix", "Matrix (free navigation)"),
            ("delphi", "Delphi (consensus rounds)"),
        ],
        default="linear",
    )


class DelphiMenu(models.Model):
    """Configuration for a survey with ``layout = delphi``."""
    survey = models.OneToOneField(
        Survey, related_name="delphi_menu", on_delete=models.CASCADE,
    )
    anchor = models.CharField(
        max_length=20,
        choices=[("enrolment", "Participant enrolment"),
                 ("survey_open", "Survey open")],
        default="enrolment",
    )
    min_rounds = models.PositiveIntegerField(default=2)
    max_rounds = models.PositiveIntegerField(default=3)
    show_progress = models.BooleanField(
        default=True,
        help_text="Show participants which round they are in.",
    )
    allow_revision = models.BooleanField(
        default=True,
        help_text="Allow participants to revise previous-round answers "
                  "in the current round.",
    )


class DelphiRound(models.Model):
    """A single round of a Delphi survey.

    Like ``StagedPhase`` (start/end offsets, M2M to groups) but for
    consensus rounds. Each round has a window and a section set. The
    author opens and closes rounds manually (or via the window offsets).
    """
    menu = models.ForeignKey(
        DelphiMenu, related_name="rounds", on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=100, default="Round 1")
    start_offset_days = models.PositiveIntegerField(default=0)
    end_offset_days = models.PositiveIntegerField(null=True, blank=True)
    groups = models.ManyToManyField(QuestionGroup, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("menu", "order")
        ordering = ["order", "id"]


class DelphiRoundFeedback(models.Model):
    """Pre-computed inter-round feedback cache.

    Created when the author clicks "Generate inter-round feedback" after
    closing a round. Stores the aggregated quantitative stats and the
    sanitised qualitative theme markdown so participant views don't
    re-run the LLM. One row per round per question (or one row per
    round with a JSON blob — see implementation note below).
    """
    round = models.ForeignKey(
        DelphiRound, related_name="feedback", on_delete=models.CASCADE,
    )
    question = models.ForeignKey(
        "SurveyQuestion", on_delete=models.CASCADE,
    )
    stats_json = models.JSONField(default=dict)
    theme_markdown = models.TextField(
        blank=True,
        help_text="Sanitised LLM theme summary (qualitative questions only).",
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    llm_model = models.CharField(max_length=100, blank=True)
    llm_token_count = models.PositiveIntegerField(default=0)
    llm_success = models.BooleanField(default=False)

    class Meta:
        unique_together = ("round", "question")


class SurveyProgress(models.Model):
    ...
    # [Planned] Delphi round assignment. Only populated for surveys with
    # layout = "delphi". Null for other layouts. The precedent is
    # ``assigned_arm`` (RCT) — same shape, separate field.
    delphi_round = models.ForeignKey(
        "DelphiRound", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_rows",
    )
    # [Planned] Delphi within-round completion tracking. The precedent is
    # ``completed_group_ids`` (Matrix) — same shape (list of IDs).
    delphi_completed_rounds = models.JSONField(default=list, blank=True)
```

**Migration:** `0067_delphi_layout` (adds the `delphi` choice to
`Survey.layout`, the `DelphiMenu` / `DelphiRound` /
`DelphiRoundFeedback` models, and the `SurveyProgress` fields).

### Allocation strategy

Delphi round assignment is simpler than RCT arm allocation: there is no
randomisation. The participant is assigned to the **current open round**
on first access, and advances to the next round when the current round
closes and the next opens. The assignment is stable across resume
(`delphi_round` FK is preserved).

```python
def current_round(menu: DelphiMenu, *, enrolment, survey_start, now) -> DelphiRound | None:
    """Return the currently-open round, or None if no round is open."""


def next_round(menu: DelphiMenu, progress: SurveyProgress) -> DelphiRound | None:
    """Return the next round the participant should advance to."""


def assign_round_for_progress(
    progress: SurveyProgress, menu: DelphiMenu, *, now
) -> DelphiRound | None:
    """Assign and persist the current round for ``progress``.

    Idempotent: if ``progress.delphi_round`` is already set and still
    open, returns it. If the assigned round has closed, advances to the
    next open round. If no round is open, returns None (participant sees
    a "check back later" page, like Staged).
    """
```

These sit in `delphi.py` next to `staged.py` and `matrix.py` — pure
functions, no side effects except `assign_round_for_progress` which
persists the FK.

### Runtime hook

The runtime hook is a new branch in `_handle_participant_submission`,
analogous to the staged branch:

```python
if survey.layout == Survey.Layout.DELPHI and progress is not None:
    menu = getattr(survey, "delphi_menu", None)
    current = assign_round_for_progress(progress, menu, now=timezone.now())
    if current is None:
        # No round open — render "check back later" page.
        return _render_delphi_waiting(request, survey, progress)
    # Resolve selected_group_ids from the current round's groups.
    round_group_ids = set(current.groups.values_list("id", flat=True))
    selected_group_ids = [
        g for g in _resolved_group_order_ids(survey)
        if g in round_group_ids
    ]
```

The inter-round feedback is rendered via content blocks whose
`options.body_md` is substituted from the `DelphiRoundFeedback` cache
at view time — no new feedback rendering model, just a body source
swap in `_annotate_question_render_sequence`.

### Outline grammar

```text
DELPHI
  anchor: enrolment
  min_rounds: 2
  max_rounds: 3
  show_progress: true
  allow_revision: true

  round: Round 1
    start: 0
    end: 14

  round: Round 2
    start: 14
    end: 28

# Demographics {demographics}    ~ round:1, round:2
## Name {name}
(text)

# Round 1 questions {r1-questions}    ~ round:1
## Importance {importance}
(likert) 1-5

# Round 2 questions {r2-questions}    ~ round:2
## Revised importance {revised-importance}
(likert) 1-5
```

The `~ round:<N>` suffix on group headings assigns a group to a round.
A group can appear in multiple rounds (e.g. demographics in every
round). The `round:` config lines inside the `DELPHI` block define the
round windows. The grammar round-trips through export → import like
the other layouts.

### Warnings

| Issue | Why it matters | Handling |
|---|---|---|
| No rounds configured | A Delphi survey with no rounds is unrunnable. | Block take view with a clear error; warn on Organise page. |
| Round with no groups | A round with an empty group set renders nothing. | Warn on Organise page; block take view. |
| Overlapping round windows | Rounds are meant to be sequential. | Warn if two rounds' windows overlap; non-blocking. |
| Group in no round | A group not assigned to any round is unreachable. | Warn on Organise page (like Staged). |
| Feedback not generated | Round N+1 opens but round N has no `DelphiRoundFeedback`. | Warn on Organise page; participants see content blocks with empty body (graceful). |
| LLM unavailable for themes | Qualitative feedback can't be generated. | Quantitative feedback still renders; qualitative shows "themes unavailable". Non-blocking. |
| Participant hasn't completed round N | Advancing to round N+1 without completing N loses revision context. | Gate round advancement on `delphi_completed_rounds` containing the current round. |
| Revision disabled | `allow_revision=False` but round N+1 re-shows round N's questions. | Hide previous-round answers in round N+1 (render blank). Warn the author. |

### Preview

`?simulate_round=<round_id>` filters the questions to that round's
groups (ordered by `_resolved_group_order_ids`). A "Simulate round"
panel on the preview page lets the author pick a round without a real
participant. `?simulate_round=<id>&with_feedback=1` also substitutes
the `DelphiRoundFeedback` body into content blocks so the author can
preview the inter-round feedback view.

### Survey Map

The Survey Map shows the full authored survey with round badges per
group (like the phase badges in Staged and the arm badges in RCT). A
round-summary card above the visualiser lists the rounds, their
windows, and whether feedback has been generated.

### Issues and edge cases

| Issue | Why it matters | Handling |
|---|---|---|
| Round windows vs manual open/close | The author can both set window offsets and manually open/close. | Manual open/close overrides the window. If `opened_at` is set, the window is ignored for that round. |
| Participant mid-round when round closes | The round closes while the participant is still answering. | Grace period: the participant can submit for 24h after `closed_at`. After that, their progress is frozen for that round. |
| Last round | No next round to advance to. | After the last round closes, the survey is complete for that participant. `SurveyProgress.status` → `completed`. |
| Min/max rounds drift | Author changes `max_rounds` after participants have completed 3 rounds. | Clamp to the new max; warn the author. Existing progress is preserved. |
| Feedback regeneration | Author regenerates feedback after more responses come in. | Delete the old `DelphiRoundFeedback` rows and recreate. Participants in round N+1 see the updated feedback on next view. |
| Anonymity | Delphi often requires anonymous responses. | Aggregation never reveals individual responses. The LLM prompt explicitly forbids verbatim quotes. Authors can mark a survey as "anonymous" (existing field) to hide participant identity from the author too. |

### Delphi compatibility

Delphi is the destination layout — the earlier layouts were shaped to
reuse their ingredients here. Delphi does **not** need to be compatible
with a future layout; it is the consumer of the patterns proven by
RCT, Staged, Matrix, and Content blocks.


## Related documentation

- [Survey Layouts](survey-layouts.md) — user-facing guide.
- [Organise](groups-view.md) — the page this feature lives on.
- [Branching Technical Guide](branching-technical.md) — runtime ordering
  pipeline, builder route security, outline grammar.
- [Survey Progress Tracking (Technical)](survey-progress-tracking-technical.md)
  — the prerequisite feature that carries `selected_group_ids`.
