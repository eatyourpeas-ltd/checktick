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
  "show me round N aggregate" inter-round feedback view. A small
  `_aggregate_responses_by_group(survey, group_ids)` helper added for
  the arm-preview panel is reusable for Delphi's median/IQR/themes.
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

## Planned layouts

The following layouts are still planned for future releases. See
[Survey Layouts](survey-layouts.md#planned-layouts) for the user-facing
descriptions. Technical notes:

### Staged (longitudinal)

- Each section group has a defined phase window (start/end offsets from
  survey open or from participant enrolment).
- Builds on `SurveyProgress` lifecycle status and timestamps.
- May need a `StagedMenu` model with phase definitions per section.
- Priority: medium — makes CheckTick suitable for repeated-measures
  designs.

### Matrix (free navigation)

- All sections visible as cards; participant navigates freely.
- Different from section_menu (pick once, then linear) — matrix is
  ongoing free navigation with completion indicators.
- May need a `MatrixMenu` model or reuse `SectionMenu` with a different
  `order_mode`.
- Priority: low — niche workflow but useful for clinical audits.

## Related documentation

- [Survey Layouts](survey-layouts.md) — user-facing guide.
- [Organise](groups-view.md) — the page this feature lives on.
- [Branching Technical Guide](branching-technical.md) — runtime ordering
  pipeline, builder route security, outline grammar.
- [Survey Progress Tracking (Technical)](survey-progress-tracking-technical.md)
  — the prerequisite feature that carries `selected_group_ids`.
