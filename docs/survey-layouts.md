---
title: Survey Layouts
category: features
priority: 7
status: implemented
---

> **Status: Design document, ready to implement.** The `linear` layout is
> the current behaviour; the `section_menu` layout is the new feature.
>
> **Prerequisite merged.** The progress-tracking feature (PR #319,
> v0.12.0) is merged to `main`. The following fields already exist and
> must NOT be re-added:
> - `Survey.allow_resume` (BooleanField, default True)
> - `Survey.allow_response_redaction` (BooleanField, default True)
> - `SurveyProgress.selected_group_ids` (JSONField, default list)
> - `SurveyProgress.resume_token`, `status`, `current_repeat_index`,
>   `completed_at` (see `docs/survey-progress-tracking-technical.md`)
> - Migration `0059_progress_resume_and_redaction_fields` is applied.
>
> See [Survey Progress Tracking](survey-progress-tracking.md) for the
> user-facing guide and [Survey Progress Tracking (Technical)](survey-progress-tracking-technical.md)
> for the developer reference.
>
> **Implementation conventions.** Run all code in the Docker `web` container.
> Use `s/test --no-a11y` and `s/lint` before each commit. Commit often
> with tests for each step. Documentation sweep at the end.

## Overview

A **Survey Layout** is the high-level shape of a survey — how its sections
are offered to the participant. Today every CheckTick survey uses one
implicit layout: sections flow in the order the author arranges them in the
Builder. This document proposes making that choice explicit and adding a
second layout, **Section menu**, where the participant picks which sections
to complete.

The name **Layout** is deliberately distinct from **Template**, which is
already used in CheckTick for *published sections* shared into the Question
Bank (see [Publish Question Groups](publish-question-groups.md)). Layouts
describe the survey's flow; templates describe reusable content.

## Layouts

### 1. Default (linear)

The current behaviour. Sections render in the order defined by the
Builder rail / Organise page. Branching, repeats, and follow-ups all work
as documented in [Branching & Repeats](branching-and-repeats.md).

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│ Demograph. │──▶│ Medical    │──▶│ Medications│──▶│  Closing   │
└────────────┘   └────────────┘   └────────────┘   └────────────┘
```

- **When to use:** most surveys, audits, validated instruments where every
  respondent answers every question.
- **Authoring:** identical to today. No new controls.

### 2. Section menu (proposed)

The survey opens on a **picker page**. The author has marked some sections
as *pickable* (the participant chooses) and some as *mandatory* (always
included, e.g. consent or demographics). After the participant confirms
their selection, only the chosen sections (plus the mandatory ones) are
walked through, in the configured order.

```
                    ┌─────────────────────┐
                    │   Section picker    │
                    │  (which sections?)   │
                    └──────────┬──────────┘
                               │
        ┌──────────┬──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼          ▼
   ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
   │ Demogr. ││ Medical ││  Meds   ││Lifestyle││ Closing │
   │ (req'd) ││ (picked)││ (picked)││         ││ (req'd) │
   └─────────┘└─────────┘└─────────┘└─────────┘└─────────┘
```

- **When to use:** patient-reported outcome measures where the respondent
  knows which domains apply; triage forms where only relevant modules are
  shown; long assessments where forcing every section causes drop-off.
- **Authoring:** a Section menu configuration card on the Organise page
  (see below). The Builder rail is unchanged — sections are still authored
  normally; the layout only decides *which* sections the participant sees.

## Where the choice lives: the Organise page

The Builder opens by default exactly as it does today. The only new
Builder-side affordance is a small, dismissible label above the rail:

```
┌──────────────────────────────────────────────────────────┐
│  Builder — "Patient intake"                  [Preview] …  │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Layout: Default (linear)   Need a different layout? │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

Clicking **"Need a different layout?"** links to the Organise page, which
gains a **Layout** section at the top: a row of cards, one per layout,
each with a cartoon wireframe and a short description. Selecting a card
sets the survey's layout and reveals layout-specific controls below.

```
Survey layout

┌───────────────────────────┐  ┌───────────────────────────┐
│  Default (linear)    ✓    │  │  Section menu             │
│                           │  │                           │
│  ▢─▢─▢─▢─▢                │  │      ▢                    │
│  │ │ │ │ │                │  │    ╱ │ ╲                  │
│  ▢ ▢ ▢ ▢ ▢                │  │  ▢   ▢   ▢                │
│                           │  │  │   │   │                │
│  Sections flow in order.  │  │  ▢   ▢   ▢                │
│  Every respondent sees    │  │                           │
│  every section.           │  │  Participant picks which   │
│                           │  │  sections to complete.    │
│  [ Use this layout ]      │  │  [ Use this layout ]      │
└───────────────────────────┘  └───────────────────────────┘
```

The wireframes are intentionally cartoonish — they communicate shape, not
content. They render as inline SVG (no external assets, CSP-safe) and
inherit the current daisyUI theme tokens so they work in light/dark and
on the dashboard accessibility tester.

Rationale for housing this on the Organise page rather than the Builder:

- The Organise page already lists every section and is the home for
  bulk, survey-shape decisions (reordering, repeats, nesting). Layout is
  the same category of decision.
- The Builder stays focused on per-question authoring. The only Builder
  change is the dismissible label, which is cheap and reversible.
- The Organise page already enforces the right access contract
  (`require_can_edit`, owner / org admin only) — see
  [Branching Technical Guide](branching-technical.md) §Builder Route
  Security. Reusing it avoids a new permissioned route.

## Section menu configuration card

When **Section menu** is selected, the Organise page shows a configuration
card below the layout cards:

```
┌─────────────────────────────────────────────────────────────┐
│ Section menu configuration                                  │
│                                                             │
│ Picker prompt:                                              │
│ [Which areas would you like to cover today?         ]       │
│                                                             │
│ Sections                                                    │
│  ☑ Demographics        Mandatory   (8 questions)           │
│  ☐ Medical history     Pickable    (12 questions)          │
│  ☐ Medications         Pickable    (repeat, max 5)         │
│  ☐ Lifestyle           Pickable    (6 questions)           │
│  ☐ Family history      Pickable    (10 questions)          │
│  ☑ Closing             Mandatory   (2 questions)           │
│                                                             │
│ Selection rules                                             │
│  Min pickable selected: [1]   Max: [4]   (blank = no cap)   │
│  Order after selection:  (•) As authored  ( ) In pick order │
│  [ ] Show "Select all" button                               │
│  [ ] Show estimated time per section                        │
│                                                             │
│ Warnings                                                    │
│  ⚠ 2 branching conditions target pickable sections —        │
│    they will be skipped if the participant doesn't pick     │
│    that section. [Review in Survey Map]                     │
│                                                             │
│ [ Save layout ]   [ Switch back to Default ]               │
└─────────────────────────────────────────────────────────────┘
```

Controls:

- **Per-section toggle:** Mandatory / Pickable. Mandatory sections are
  always in the path and cannot be deselected by the participant.
- **Min / Max pickable selected:** constrains how many *pickable*
  sections the participant must/may choose. Min ≥ 1 unless at least one
  section is mandatory and the author explicitly allows zero picks.
- **Order after selection:** `authored` (use the Organise page order) or
  `participant` (use the order the participant ticked the boxes — useful
  for "rank your priorities" surveys).
- **Show "Select all" button:** convenience for the participant.
- **Show estimated time per section:** optional per-section
  `estimated_minutes` shown on the picker (e.g. "~5 min").
- **Warnings:** surfaced live from the existing branching data — see
  §Issues to bake in.

## Participant experience

### Picker page

The survey opens on the picker instead of the first question:

```
┌─────────────────────────────────────────────────────────────┐
│ Patient intake                                              │
│ Which areas would you like to cover today?                  │
│                                                             │
│ Included automatically:                                     │
│   ■ Demographics                                            │
│   ■ Closing                                                 │
│                                                             │
│ Choose any others (pick 1–4):                               │
│   ☐ Medical history        ~5 min                           │
│   ☐ Medications            ~3 min   (repeatable)            │
│   ☐ Lifestyle              ~2 min                           │
│   ☐ Family history         ~4 min                           │
│                                                             │
│   [ Select all ]   [ Continue ]                             │
│                                                             │
│  Step 1 of N · Choose sections                             │
└─────────────────────────────────────────────────────────────┘
```

- Mandatory sections are shown as locked/included, not as checkboxes.
- Validation: at least `min` and at most `max` pickable sections must be
  ticked before **Continue** is enabled.
- The picker is itself a step in the runtime, so it appears in the
  progress bar and is itself resumable (see
  [Survey Progress Tracking](survey-progress-tracking.md) §Resume links
  and section selection).

### After selection

The participant walks through the chosen sections in the configured order.
Branching, repeats, follow-ups, and the Survey Map all behave exactly as
they do today — the layout only decides which sections are in the path.

A **"Change sections"** link in the progress bar returns the participant
to the picker. Deselecting a section that already has answers prompts a
two-step confirm: *"This will discard your answers in Medical history
(4 answers). Continue?"* This is the trickiest UX call in the feature;
the default is to allow it but require confirmation.

## Data model

The layout choice is a survey-level field. The Section menu configuration
is a small related model that lives alongside `CollectionDefinition`.

> **Already exists (do not re-add):** `Survey.allow_resume`,
> `Survey.allow_response_redaction`, and `SurveyProgress.selected_group_ids`
> were added in v0.12.0 (migration `0059`). See the prerequisite note at
> the top of this doc.

```python
class Survey(models.Model):
    ...
    # NEW — add in the first migration of this feature
    layout = models.CharField(
        max_length=20,
        choices=[("linear", "Linear"), ("section_menu", "Section menu")],
        default="linear",
    )

    # ALREADY EXISTS (v0.12.0, migration 0059) — do not re-add
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
```

`SectionMenuItem` rows are only created for surveys with
`layout = section_menu`. A `linear` survey has no rows and renders exactly
as it does today.

## Runtime — why no new branching action is needed

The picker is a **pre-step**, not a branching rule. When the participant
submits their selection:

1. The chosen group IDs (plus the mandatory ones) are stored on the
   progress record as `selected_group_ids` (already exists on
   `SurveyProgress` — see prerequisite note).
2. The runtime ordering pipeline (`_resolved_group_order_ids` in
   `checktick_app/surveys/views.py`) already filters by
   `survey.style["group_order"]`. We add one extra filter: drop any group
   not in `selected_group_ids`. The filter goes in
   `_resolved_group_order_ids` (or a thin wrapper called from it),
   reading `selected_group_ids` from the `SurveyProgress` row passed
   through the view context.
3. The branching config (`_build_branching_config`) is built from the
   filtered question list, so `jump_to` / `show` / `hide` conditions that
   target a now-absent section are simply never triggered.
4. Repeats work unchanged — a repeatable section the participant didn't
   pick just isn't in their path.

This keeps the **Survey Map = Preview = Live** ordering contract intact.
The Survey Map shows the full authored survey (it is an authoring-time
view); the live route applies the selection filter on top.

### Picker route and template

The picker is a step inside the existing take view, not a separate URL.
When `survey.layout == "section_menu"` and the participant has no
`selected_group_ids` on their progress record, the take view renders the
picker template instead of the question list:

- **Template:** `surveys/section_menu_picker.html` (new)
- **POST action:** `action=select_sections` with `selected_groups` as a
  list of group IDs. The handler stores the IDs on
  `SurveyProgress.selected_group_ids` and re-renders the take view, which
  now shows the filtered question list.
- **On resume:** if `selected_group_ids` is already populated, skip the
  picker and go straight to the questions. A "Change sections" link in
  the progress bar returns to the picker.

### Preview

Preview needs a small addition: a "Simulate selection" panel that
pre-ticks a valid subset so the author can try the picker without a real
participant. This lives in the existing preview template
(`surveys/preview.html`) and the preview view
(`survey_preview` in `views.py`).

## Outline syntax (proposed)

For parity with the existing outline grammar, a `SECTION_MENU` block:

```text
SECTION_MENU
  prompt: "Which areas would you like to cover?"
  min: 1
  max: 4
  order: authored

# Demographics        # mandatory
# Medical history    ~ pickable
# Medications        ~ pickable, repeat 5
# Lifestyle          ~ pickable
```

- A section listed under `SECTION_MENU` without `~ pickable` is
  mandatory.
- `~` is used (not `?`) because `?` is already the condition prefix in
  the outline grammar; reusing it would be ambiguous.
- Estimated time can be appended: `~ pickable, 5 min`.

Implementation lives in `checktick_app/surveys/markdown_import.py`
alongside the existing `REPEAT` parsing, with a round-trip test added to
`test_outline_new_grammar.py`.

## Issues to bake into the design

| Issue | Why it matters | Suggested handling |
|---|---|---|
| Branching targets a pickable section | A `jump_to` to a section the participant didn't pick is a dead branch. | Live warning on the configuration card (see wireframe). Do not block — just warn. Link to Survey Map for review. |
| Repeats inside non-selected sections | A repeat that's never reached. | Handled automatically by the filter. Survey Map still shows the full structure. |
| Empty selection | `min_selected=0` with no mandatory sections = blank survey. | Builder validation: at least one section must be mandatory OR `min_selected ≥ 1`. |
| Single-section surveys | A menu with one pickable section is pointless. | Hide the Section menu card when the survey has < 2 sections; show a hint. |
| Save progress + selection | A participant who picks 3 sections, leaves, and returns must not have to re-pick. | `selected_group_ids` already exists on `SurveyProgress` (v0.12.0). On resume, skip the picker if it's populated. |
| Min/Max drift | Author lowers `max_selected` after a participant has already saved 4 picks. | On resume, clamp to the new max and prompt the participant to drop one. Edge case, but worth a test. |
| Mandatory sections can't be deselected | Picker must disable their checkboxes. | Render as locked rows, not checkboxes. |
| Outline round-trip | Menu config must survive export → import. | Add `SECTION_MENU` to the outline grammar and a round-trip test. |
| Preview | Author must be able to try the picker without a real participant. | "Simulate selection" panel on the preview page. |
| Naming | "Template" is already used for published sections. | This feature is called **Layout**. Do not reuse "template". |
| Survey Map | The map is authoring-time and shows the full survey. | Add a small "pickable" badge on pickable section bands so authors can see at a glance which sections are optional. No change to the runtime map. |

## Suggested build order

Step 1 (save-and-resume) is **done** — merged in PR #319 (v0.12.0). Start
at step 2.

1. ~~**Save-and-resume**~~ — merged in PR #319 (v0.12.0). Includes
   `allow_resume`, `allow_response_redaction`, and
   `SurveyProgress.selected_group_ids`.
2. **`Survey.layout` field** + migration (default `linear`, no behaviour
   change).
3. **Section menu card on the Organise page** (read-only summary first,
   then editor).
4. **`SectionMenu` / `SectionMenuItem` models** + admin.
5. **Picker page on the participant route** + selection filter in the
   ordering pipeline (`_resolved_group_order_ids`).
6. **Builder "Need a different layout?" label** linking to Organise.
7. **Outline grammar** + import/export round-trip.
8. **Warnings** (branching targets pickable sections, empty selection,
   single-section guard).
9. **Survey Map "pickable" badges** + preview "Simulate selection" panel.
10. **Docs updates:** this file, `docs/groups-view.md` (Organise page
    gains a Layout section), `docs/branching-and-repeats.md` (note that
    branching into a non-selected section is a no-op at runtime).

    The `docs/privacy-notice.md` and
    `docs/compliance/data-subject-request-procedure.md` updates for
    opt-out tokens were done in PR #319 — no further changes needed
    unless the layout feature introduces new privacy implications.

## Publication workflow toggle

The `allow_resume` and `allow_response_redaction` toggles already exist on
`Survey` (added in v0.12.0, migration `0059`). They are presented in the
publication workflow alongside the existing visibility and audience
declarations.

```python
class Survey(models.Model):
    ...
    # Already exists (v0.12.0) — do not re-add
    allow_resume = models.BooleanField(default=True)
    allow_response_redaction = models.BooleanField(default=True)
```

- **`allow_resume`** — when `False`, no `SurveyProgress` row is created
  for any access tier, no resume token is issued, and the participant
  must complete in a single session. Useful for assessments with a
  fresh-state requirement.
- **`allow_response_redaction`** — when `False`, public-survey
  participants are not offered an opt-out token on the thank-you page.
  The original anonymity promise stands: the response cannot be linked
  to them and cannot be redacted. See
  [Survey Progress Tracking](survey-progress-tracking.md) §Resume Tokens
  and Opt-Out Tokens.

Both toggles default to `True` and are presented together in the
publication workflow. Creators who disable `allow_response_redaction`
for a public survey should be required to acknowledge that participants
will have no way to redact their response — mirroring the existing
encryption opt-out declaration pattern (audit-logged).

The layout feature does not add new publication-workflow toggles — the
`Survey.layout` field is set on the Organise page, not in the publication
workflow.

## Open questions

- **"Change sections" after starting.** Allowing it is more flexible but
  risks discarded answers. Default to allow-with-confirm, or lock the
  selection after Continue? Worth a quick user test.

## Related documentation

- [Organise](groups-view.md) — the page this feature lives on.
- [Branching & Repeats](branching-and-repeats.md) — user-facing branching
  guide; the Section menu is a sibling feature, not a branching action.
- [Branching Technical Guide](branching-technical.md) — runtime ordering
  pipeline, builder route security, outline grammar.
- [Survey Progress Tracking](survey-progress-tracking.md) — save-and-resume,
  which must land first and which carries `selected_group_ids`.
- [Publish Question Groups](publish-question-groups.md) — the existing
  meaning of "template", which this feature deliberately does not reuse.
