---
title: Branching Targets by Section
category: development
priority: 5
---

# Branching Targets by Section

- **Status**: Proposed (not yet implemented)
- **Date**: August 2026
- **Origin**: Deferred from the Survey Builder Workflow redesign (originally Tier 3.2). The workflow design and implementation-plan docs have been retired; their reference content is now captured in the canonical docs (`docs/surveys.md`, `docs/groups-view.md`, `docs/branching-technical.md`).
- **Related**: [Branching Logic & Repeating Questions](/docs/branching-and-repeats/) · [Branching Logic - Technical Guide](/docs/branching-technical/) · [Sections](/docs/groups-view/)

---

## Summary

Today, when a user adds a branching "jump to…" condition in the Builder, the target picker lists every other question in the survey as a flat list. This feature adds a **"jump to section"** target type so the user can pick a section by name, and at runtime the engine resolves it to the first question in that section.

This matches the user's mental model: they think "skip ahead to the Symptoms section," not "skip ahead to question 47."

## Problem

The current branching target picker (`question_conditions_panel.html`) is a flat `<select>` of all questions in the survey, each labelled `Q3 • What is your age? (Demographics)`. The section name is a parenthetical suffix, not the organising concept.

This is workable for small surveys but breaks down as surveys grow:

- A 50-question survey with 6 sections produces a 49-option flat list with no grouping.
- The user must know which question is "first in the Symptoms section" to jump there.
- The section — which is the user's navigational concept — is not a first-class target.

## Proposal

Add a **section-level target** alongside the existing question-level target. The user picks whether to target a question or a section; if section, they pick from a list of section names.

### User-facing behaviour

In the Builder's condition panel, the "Target" field becomes a two-step picker:

1. **Target type**: "Question" or "Section" (radio or select). Defaults to "Question" (preserves existing behaviour).
2. **Target**:
   - If "Question": the existing flat question picker (optionally grouped by section — see "Future enhancement" below).
   - If "Section": a `<select>` of section names (`Demographics`, `Symptoms`, …), excluding the section the triggering question belongs to (jumping within the same section is equivalent to a question-level jump).

The live preview reads: *"If [answer] → jump to the Symptoms section"* rather than *"jump to Q47 • Pain score"*.

### Runtime resolution

"Jump to section S" is semantically **"jump to the first question in section S"**. The engine resolves the section target to a question ID at config-build time, not at evaluation time, so the branching engine (`branching.py` / `branching.js`) needs no new action type — it still sees a `jump_to` with a `target_question`.

This keeps the evaluation engine unchanged and avoids a new participant-facing code path.

## Data model

`SurveyQuestionCondition` already has a `target_group` FK (migration `0010_surveyquestioncondition.py`), added speculatively but never wired up. This feature uses it.

| Field | Current state | After this feature |
|---|---|---|
| `target_question` | Used by `show`, `jump_to`, `skip` | Used when target type = "Question" |
| `target_group` | Dormant (not read by any code path) | Used when target type = "Section"; resolved to `target_question` at config-build time |
| `action` | `show`, `jump_to`, `skip`, `end_survey` | Unchanged — section targets use `jump_to` (and optionally `skip` to skip a whole section) |

### Validation

`SurveyQuestionCondition.clean()` (models.py L2422) currently requires `target_question` unless `action == END_SURVEY`. The new rule:

- If `target_group` is set, `target_question` may be null at validation time (it's resolved later).
- `target_group` must belong to the same survey as the triggering question.
- `target_group` must not be the section the triggering question belongs to (no-op jump).

## Implementation scope

### Builder (authoring)

| File | Change |
|---|---|
| `checktick_app/surveys/templates/surveys/partials/question_conditions_panel.html` | Add target-type picker (Question / Section); conditionally render the section `<select>` when "Section" is chosen. Two places: create form and edit form. |
| `checktick_app/surveys/views.py` — `_serialize_question_for_builder` | Add `target_sections` to `condition_options`: list of `{id, name}` for groups in the survey, excluding the triggering question's group. |
| `checktick_app/surveys/views.py` — `_build_condition_payload` | Accept `target_group` from POST; validate it belongs to the survey and differs from the source group. |
| `checktick_app/static/js/builder.js` — `setupConditionForm` / `initConditionForms` | Toggle the target picker (Question vs Section) on target-type change; update the live preview to say "jump to the X section". |

### Config build (runtime resolution)

| File | Change |
|---|---|
| `checktick_app/surveys/views.py` — `_build_branching_config` | When serialising a condition for the participant JS, if `target_group` is set and `target_question` is null, resolve `target_question` to the first question in that group (by group order, then question order). Emit the resolved ID in `cond_data["target_question"]` so the participant JS sees a normal `jump_to`. |
| `checktick_app/surveys/views.py` — `branching_data_api` | Same resolution for the Survey Map visualiser. |

### Evaluation engine (no change)

| File | Change |
|---|---|
| `checktick_app/surveys/branching.py` — `get_visible_questions` | **No change.** It already handles `jump_to` with a `target_question`. The section target is resolved to a question ID before the engine sees it. |
| `checktick_app/static/js/branching.js` — `updateVisibility` | **No change.** Same reason. |
| `checktick_app/static/js/branching-visualizer.js` | **No change** (it consumes the resolved `target_question` from the API). Optionally: draw the edge to the section header node rather than the first question, but this is a visual polish item, not a functional requirement. |

### Outline / markdown import

| File | Change |
|---|---|
| `checktick_app/surveys/markdown_import.py` — `_parse_branch_line` | Extend the `? when <op> <value> -> {target-id}` grammar to accept a section reference (e.g. `-> #section-name` or `-> {group-id}`) in addition to a question reference. Resolve to `target_group` at import time. |

### Tests

| Area | Tests |
|---|---|
| Builder UI | Target-type picker renders; section `<select>` populated; preview text says "section"; XSS on section name. |
| Payload / validation | `target_group` accepted; rejected if wrong survey; rejected if same as source group; `target_question` still works when target type = "Question". |
| Config resolution | `_build_branching_config` resolves `target_group` → first question ID; participant JS receives a normal `jump_to`. |
| Runtime | `get_visible_questions` jumps to the first question of the target section (via the resolved `target_question`). |
| Permissions | 403 for non-editors; 405 for GET on POST-only endpoints. |
| Outline import | `-> #section-name` resolves to `target_group`. |

## Non-goals

- **No new action type.** "Jump to section" is `jump_to` with a resolved `target_question`, not a new `Action` enum value. This keeps the evaluation engine and participant JS unchanged.
- **No backward-incompatible change.** Existing conditions with `target_question` set and `target_group` null continue to work unchanged.
- **No change to `skip` or `show` semantics.** These remain question-level. (A future enhancement could add "skip section" / "show section", but that's out of scope here.)
- **No change to the Survey Map visualiser's data contract.** It receives resolved `target_question` IDs. Drawing edges to section headers is a possible visual polish item but not required.

## Open questions

1. **Should `skip` also support section targets?** "Skip the Symptoms section" is a plausible user request. The resolution is the same (skip all questions in that section), but `branching.py`'s `SKIP` path currently skips a single `target_question` — it would need to skip a range. Decide before implementing, or defer to a follow-up.
2. **What happens if the target section is empty (no questions)?** The config builder cannot resolve `target_group` → a `target_question`. Options: (a) block at validation time ("cannot jump to an empty section"), (b) resolve to the next non-empty section, (c) treat as `end_survey` if it's the last section. Recommendation: (a) — block at validation time with a clear error.
3. **Should the section picker exclude the source section?** Jumping to the section you're already in is a no-op (or equivalent to a question-level jump within the same section). Recommendation: exclude it to prevent confusion, same as the question picker excludes the triggering question itself.
4. **Outline grammar for section targets.** `-> #section-name` (heading-style) vs `-> {group-id}` (ID-style) vs `-> section:Name`. Needs a decision consistent with the existing `{custom-id}` grammar.

## Future enhancement: group the question picker by section

A smaller, presentation-only change (originally the literal Tier 3.2 item) is to render the existing flat question `<select>` as `<optgroup>` blocks grouped by section name, without adding a section target type. This is independent of the section-target feature and could be done first as a quick win.

## Related documentation

- [Branching Logic & Repeating Questions](/docs/branching-and-repeats/) — user-facing branching guide
- [Branching Logic - Technical Guide](/docs/branching-technical/) — evaluation engine, models, config build, builder route security, future enhancements
- [Sections](/docs/groups-view/) — the Organise page and Builder rail
