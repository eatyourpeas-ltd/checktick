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

## Planned layouts

The following layouts are planned for future releases. See
[Survey Layouts](survey-layouts.md#planned-layouts) for the user-facing
descriptions. Technical notes:

### Randomised (RCT)

- System assigns section order or section subset based on a random seed
  stored on `SurveyProgress` at first access.
- Natural extension of `selected_group_ids` — system assigns instead of
  participant choosing.
- May need a `RandomisedMenu` model (arms, allocation ratio, seed
  strategy) alongside `SectionMenu`.
- Priority: high — unblocks clinical trial use case.

### Guided (one question at a time)

- Primarily a rendering change: one question per screen with Next/Back.
- The runtime already has the question sequence and progress tracking.
- The section_menu picker could serve as the first screen.
- May need a `guided` layout value and a new template variant of
  `detail.html`.
- Priority: medium — improves participant experience across all layouts.

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
