---
title: Branching Targets by Section
category: development
priority: 5
---

# Branching Targets by Section

- **Status**: In progress (branch `branch-to-section`)
- **Date**: August 2026
- **Origin**: Deferred from the Survey Builder Workflow redesign (originally Tier 3.2). The workflow design and implementation-plan docs have been retired; their reference content is now captured in the canonical docs (`docs/surveys.md`, `docs/groups-view.md`, `docs/branching-technical.md`).
- **Related**: [Branching Logic & Repeating Questions](/docs/branching-and-repeats/) · [Branching Logic - Technical Guide](/docs/branching-technical/) · [Sections](/docs/groups-view/)

---

> This is the planning document for the branching refactor. It tracks the commit checklist below. **When every item is addressed, this file is deleted** and the canonical docs (`branching-and-repeats.md`, `branching-technical.md`) become the sole source of truth.

## Summary

This feature does four related things, all touching the same subsystem:

1. **Rename `SKIP` → `HIDE`** (stored value `"skip"` → `"hide"`). `SHOW`/`HIDE` become an obvious visibility-override pair; `JUMP_TO` is the only navigation verb.
2. **Add a `hidden_by_default` toggle on `SurveyQuestion`.** A question's default visibility is declared on the question itself, not derived from incoming conditions. `SHOW` conditions are only valid against hidden-by-default questions; `HIDE` conditions only against shown-by-default questions. Contradictory conditions become impossible by construction.
3. **Add section-level targets for `JUMP_TO`.** Authors pick "jump to the Symptoms section" rather than "jump to Q47"; the section resolves to its first question at config-build time. The evaluation engine is unchanged.
4. **Add outline action keywords** (`show` / `hide` / `end`) and a `HIDDEN` question flag, so the outline can express everything the Builder can. Section targets use `-> #section-name` (heading-style, consistent with outline section syntax).

## Final sanctioned verb set

| Verb | Stored value | Direction | Target | Gated by |
|---|---|---|---|---|
| `SHOW` | `"show"` | visibility override → visible | Question only | target's `hidden_by_default = True` |
| `HIDE` | `"hide"` (was `"skip"`) | visibility override → hidden | Question only | target's `hidden_by_default = False` |
| `JUMP_TO` | `"jump_to"` | navigation, **forward only** | Question or Section | target must be later in resolved order |
| `END_SURVEY` | `"end_survey"` | termination | None | n/a |

`SHOW`/`HIDE` are visibility overrides on a single question. `JUMP_TO` is the only navigation verb and the only action that can target a section. Sections never have a visibility toggle — you navigate to them with `JUMP_TO`.

## The `hidden_by_default` model

Today a question is "hidden by default" only as a side-effect of another question having a `SHOW` condition targeting it. The default is implicit and scattered. This refactor makes it explicit:

- `SurveyQuestion.hidden_by_default` (bool, default `False`) declares the default visibility on the question.
- `SHOW` conditions are only valid when the target is `hidden_by_default = True` (override hidden → visible).
- `HIDE` conditions are only valid when the target is `hidden_by_default = False` (override shown → hidden).
- A hidden-by-default question with no incoming `SHOW` condition is a dead question — the Builder warns on this.

The data migration backfills `hidden_by_default = True` for any question that currently has an incoming `SHOW` condition, preserving existing behaviour exactly.

## Section targets

"Jump to section S" is semantically "jump to the first question in section S". The engine resolves the section target to a question ID at config-build time (`_build_branching_config`, `branching_data_api`), so `branching.py` / `branching.js` see a normal `jump_to` with a `target_question`. No new action type, no new participant-facing code path.

The `target_group` FK is re-added in this refactor (it was removed in migration `0031` after being unused). When set, the section resolves to its first question at config-build time (`_build_branching_config`, `branching_data_api`), so the evaluation engine sees a normal `jump_to` with a `target_question`. No new action type, no new participant code path.

### `JUMP_TO` is forward-only

A backward `JUMP_TO` is a silent no-op in the current engine (the forward-pass traversal can't revisit questions). This refactor enforces forward-only at validation time (`SurveyQuestionCondition.clean()`) and in the outline parser, turning the silent no-op into a clear authoring error. Backward navigation, if ever needed, is a separate feature with its own verb and loop-detection design.

## Outline grammar

Question-level — new `HIDDEN` flag:

```markdown
## Pain score {pain-score}
(text_long)
HIDDEN
```

Condition-level — `show` / `hide` / `end` keywords, with `jump_to` as the implicit default (existing outlines parse unchanged):

```markdown
## Do you have symptoms? {has-symptoms}
(yesno)
? show when equals "Yes" -> {pain-score}   # valid: target is HIDDEN
? hide when equals "No"  -> {follow-up}     # valid: target is NOT HIDDEN
? when equals "No" -> #Symptoms             # jump_to section (default action)
? end  when equals "N/A"                     # end survey (no target)
```

Validation:
- `show` targeting a non-`HIDDEN` question → rejected.
- `hide` targeting a `HIDDEN` question → rejected.
- `show` / `hide` with a `#section` target → rejected (sections are not show/hide-able).
- `jump_to` targeting an earlier question → rejected (forward-only).

## Resolved open questions

1. **Should `skip`/`hide` also support section targets?** No. `HIDE` is question-level by nature. Ship `jump_to` section targets first; "hide a whole section" would need range logic that doesn't exist today and is deferred.
2. **Empty target section?** Block at validation time with a clear error — "cannot jump to an empty section." Resolving to the next non-empty section would be surprising.
3. **Exclude the source section from the section picker?** Yes — jumping within your own section is a no-op. Same as the question picker excludes the triggering question.
4. **Outline grammar for section targets?** `-> #section-name` (heading-style), consistent with the existing outline section syntax and visually distinct from `{question-id}`.
5. **Default target type for new `jump_to` conditions?** Section (leads with the section mental model). Existing conditions keep their resolved state.
6. **Group the question picker by section?** Yes — render the flat question `<select>` as `<optgroup>` blocks grouped by section name. Cheap quick-win folded into this feature.
7. **Survey Map edges for section jumps?** Draw to the section header band, not the first question node. Promoted from optional to in-scope so the two target types feel like one coherent feature.

## Implementation scope

### Commit checklist

Each commit includes the docs and tests for its section. `s/lint` before committing.

- [x] **1. Migration: `hidden_by_default` + rename `skip`→`hide`** (commit `fc0eb8b`)
  - Add `SurveyQuestion.hidden_by_default` (bool, default `False`).
  - Rename `SurveyQuestionCondition.action` value `"skip"` → `"hide"` on all rows.
  - Backfill `hidden_by_default = True` for questions with incoming `SHOW` conditions.
  - Update `Action` enum: `SKIP` → `HIDE` (stored `"hide"`), keep `SHOW`/`JUMP_TO`/`END_SURVEY`.
  - Files: new migration, `surveys/models.py`.
  - Tests: migration backfill correctness; enum value round-trip.

- [x] **2. Engine: toggle-based visibility + forward-only validation** (commit `6595152`)
  - Rewrite `should_show_question` around `hidden_by_default` (symmetric SHOW/HIDE override logic).
  - Update `branching.py` and `static/js/branching.js` for the `skip`→`hide` rename.
  - Add forward-only `JUMP_TO` validation in `SurveyQuestionCondition.clean()`.
  - Add `target_group` validation in `clean()` (same survey, not source group, non-empty).
  - Files: `surveys/branching.py`, `surveys/models.py`, `static/js/branching.js`.
  - Tests: toggle visibility both directions; backward jump rejected; `HIDE` on hidden-by-default rejected and vice versa.

- [x] **3. Builder UI: question toggle + constrained action picker + relabel** (commit `f2d38b8`)
  - Add "Hidden by default" toggle to the question edit form, with help text.
  - Constrain the condition action picker based on the target's toggle (SHOW for hidden-by-default, HIDE for shown-by-default).
  - Relabel `SKIP` → `HIDE` across templates and preview strings.
  - Warn on hidden-by-default questions with no incoming SHOW condition.
  - Files: `surveys/views.py`, `surveys/templates/surveys/partials/question_conditions_panel.html`, question edit template, `static/js/builder.js`.
  - Tests: toggle persists; action picker constrained; preview text; dead-question warning; XSS on section name; 403/405.

- [x] **4. Outline: `HIDDEN` flag + action keywords + section targets** (commit `da45c8a`)
  - Add `HIDDEN` keyword on questions in `markdown_import.py`.
  - Add `show` / `hide` / `end` action keywords; `jump_to` remains the default.
  - Add `-> #section-name` section targets, resolved to `target_group` at import time.
  - Reject `show`/`hide` on sections, `show` on non-HIDDEN, `hide` on HIDDEN, backward `jump_to`.
  - Update the live structure preview (`static/js/bulk-upload-preview.js`) to parse and render the new notation: `HIDDEN` badge on questions, action keyword in the branch row, `#section` target badge distinct from `{question}`.
  - Update the format guide in `surveys/templates/surveys/bulk_upload.html` to document the new notation with examples (HIDDEN flag, `show`/`hide`/`end` keywords, `#section` targets, forward-only rule).
  - **Rename user-facing "group" → "section" wording** in the outline builder: the format guide in `bulk_upload.html` ("# Group Title" → "# Section Title", "group description" → "section description", "group ID" → "section ID", etc.) and the preview strings in `bulk-upload-preview.js` ("Untitled group" → "Untitled section", "Ungrouped" → "Unsectioned", "N groups" → "N sections", the empty-state hint, and the warning about a question appearing before any heading). Internal JS variable names (`groups`, `currentGroup`) stay as-is — only user-facing strings change.
  - Files: `surveys/markdown_import.py`, `static/js/bulk-upload-preview.js`, `surveys/templates/surveys/bulk_upload.html`.
  - Tests: each keyword round-trips; section target resolves; all rejections; existing outlines parse unchanged; preview JS renders the new badges (unit-tested where feasible, otherwise covered by import tests).

- [x] **5. Section targets: config resolution + Builder picker + Survey Map edges + export** (commit `76e4679`)
  - Re-add `target_group` FK to `SurveyQuestionCondition` (removed in migration `0031`).
  - Wire `target_group` → first question resolution in `_build_branching_config` and `branching_data_api`.
  - Builder condition panel: target-type picker (Section default / Question), section `<select>` excluding source section, `<optgroup>` question picker.
  - Survey Map: draw section-jump edges to the section header band; question-jump edges to the node as today.
  - **Update `_export_survey_to_markdown`** to emit the new grammar: action keywords (`show`/`hide`/`end`), `HIDDEN` flags, and `#section` targets (from `target_group`). The current export only emits `? when ... -> {target_ref}` with no action keyword, which causes SHOW/HIDE/END conditions to silently become JUMP_TO on round-trip. Slugs are already regenerated from current names on export, so renaming a section in the Builder and opening the Outline tab shows the new slug — no stale-ID problem.
  - Files: new migration, `surveys/models.py`, `surveys/views.py`, `question_conditions_panel.html`, `static/js/branching-visualizer.js`, `static/js/builder.js`.
  - Tests: config resolution; participant JS receives normal `jump_to`; section picker excludes source; visualiser edge endpoints; export round-trip preserves action/HIDDEN/section targets; 403/405.

- [ ] **6. Final docs polish + delete this planning doc**
  - Ensure `branching-and-repeats.md` examples use the new notation throughout.
  - Ensure `branching-technical.md` reflects the shipped code.
  - Delete `docs/branching-targets-by-section.md`.
  - Update `docs/README.md` / index if it references the planning doc.

## Related documentation

- [Branching Logic & Repeating Questions](/docs/branching-and-repeats/) — user-facing branching guide
- [Branching Logic - Technical Guide](/docs/branching-technical/) — evaluation engine, models, config build, builder route security
- [Sections](/docs/groups-view/) — the Organise page and Builder rail
