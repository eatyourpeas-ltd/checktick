---
title: Survey Builder Workflow — Implementation Plan
category: development
priority: 5
---

# Survey Builder Workflow — Implementation Plan

**Status**: Living document — this plan will change as we learn.
**Date**: August 2026
**Scope**: Tier 1 of the Survey Builder Workflow Design. Tier 2/3 are outlined but not committed.
**Parent design**: [Survey Builder Workflow Design](/docs/survey-builder-workflow-design/)

This is a commit plan, not a design doc. The design doc describes *what* and *why*; this describes *how*, *in what order*, and *what "done" means per commit*. Each commit is atomic: it builds, it tests green, it leaves the docs consistent.

---

## Decisions resolved

| OQ | Decision | Rationale |
|---|---|---|
| OQ2 — UI label | **Section (recommended)** — pending product owner confirmation | See design doc review. "Group" is workable but "Section" matches the existing orientation strip, the "chapters" metaphor in `surveys.md`, and mainstream survey tools. The plan is identical either way; only the template string changes. |
| OQ3 — dashboard CTA target | **Per-group builder first**, then migrate to unified builder in Tier 2 | Avoids a hard dependency on Tier 2. The dashboard CTA points at the existing `group_builder` route for the default group. |
| i18n | **Defer translation files and `COMPLETE_STRINGS_LIST.md` updates.** Templates must use `{% trans %}` / `{% blocktrans %}` for all new/changed strings, but we do not update `.po` files or the languages docs in Tier 1. | The i18n is out of date already; a separate i18n refresh ticket will catch up. New `{% trans %` strings will fall back to English until then, which is the current behaviour for stale strings. |
| `builder.html` | **Remove it.** Confirmed unused: no route in `urls.py`, no `render()` call in `views.py`, no test exercises it. The XSS test comment that names `builder.html` actually tests `group_builder.html` via `surveys:group_builder`. | Dead code; removing it reduces confusion before Tier 2. |

---

## Pre-flight (no commits)

These are investigations or decisions, not code changes.

- **Confirm OQ2 with product owner.** Block commit 5 until resolved.
- **Confirm `builder.html` removal is acceptable** to anyone who might have local branches referencing it. (It's dead in `main`.)

---

## Tier 1 commits

### Commit 1 — Remove unused `builder.html` template

**Scope**: Delete dead code before touching anything else, so Tier 2 starts clean.

**Files**:
- `checktick_app/surveys/templates/surveys/builder.html` — delete.
- `checktick_app/surveys/tests/test_xss_creation_forms.py` L734–768 — fix the misleading comment that names `builder.html` when it actually tests `group_builder.html`.

**Tests**: No new tests. Existing test suite must stay green (confirms nothing depended on the file).

**Exit criteria**:
- `builder.html` no longer exists.
- The XSS test comment accurately names `group_builder.html`.
- `s/test --no-a11y` passes.

**Docs**: None. (The design doc's "Affected surfaces" table mentions `builder.html` as a Tier 2 starting point — update that row in commit 9 to say "removed in commit 1, Tier 2 starts fresh".)

---

### Commit 2 — Auto-create a default `QuestionGroup` on survey creation

**Scope**: Tier 1.1. The single most important change — removes the "name a group first" gate.

**Files**:
- `checktick_app/surveys/views.py` — in `survey_create` (or a helper), after the `Survey` is created, create one `QuestionGroup` with the default name (see OQ2 — `Section 1` if Section, `Group 1` if Group).
- `checktick_app/surveys/models.py` — only if a helper belongs here; otherwise no model change.

**Tests** (`checktick_app/surveys/tests/`):
- `test_survey_create_creates_default_group` — after `survey_create`, the new survey has exactly one `QuestionGroup`, with the default name.
- `test_existing_surveys_unaffected` — a survey created before this change (fixture) still renders N groups; no migration runs.
- `test_default_group_is_renameable_and_deletable` — the default group behaves like any other group (rename, delete when empty).

**Exit criteria**:
- New survey → exactly one group exists, no user action required.
- Existing surveys unchanged.
- `s/test --no-a11y` passes.

**Docs**: None yet. Docs sweep is commit 9.

---

### Commit 3 — Dashboard CTA → "Add questions", pointing at per-group builder

**Scope**: Tier 1.2. Stop sending users to the Groups page as the "builder".

**Files**:
- `checktick_app/surveys/templates/surveys/dashboard.html` — rename the "Question Builder" card to **"Add questions"**; point it at `surveys:group_builder` for the survey's first group (the default group from commit 2). If the survey has no groups (legacy), fall back to `surveys:groups` so we never 404.

**Tests**:
- `test_dashboard_cta_points_at_group_builder` — the "Add questions" link resolves to `group_builder` for the default group on a new survey.
- `test_dashboard_cta_fallback_for_legacy_survey` — a survey with no groups (edge case) falls back to the groups page, not a 404.

**Exit criteria**:
- Clicking "Add questions" on a new survey lands on a page where a question can be added immediately.
- No 404s on legacy surveys.
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 4 — Reframe user-facing templates to the chosen UI term

**Scope**: Tier 1.3. Template-string work only. **Block on OQ2 resolution.**

**Files** (template changes — all `{% trans %}` wrapped):
- `checktick_app/surveys/templates/surveys/groups.html` — heading "Question Groups" → "Sections" (or "Groups"); orientation strip already says "Sections" so no change there if we pick Section.
- `checktick_app/surveys/templates/surveys/group_builder.html` — breadcrumbs, headings, "Question Group" → "Section".
- `checktick_app/surveys/templates/surveys/dashboard.html` — any remaining "Question Group" references in card labels.
- `checktick_app/templates/components/breadcrumbs.html` or the example labels in `themes.md` — only if the breadcrumb component itself hardcodes the label (check first; it likely takes labels as params).
- `checktick_app/surveys/templates/surveys/question_group_publish.html` — heading "Publish a Question Group" → "Share as template" / "Publish to Question Bank" (per the design doc's naming table).
- `checktick_app/surveys/templates/surveys/published_templates_list.html` — page `<h1>` "Question Group Template Library" → "Question Bank" (align with navbar).
- `checktick_app/surveys/templates/surveys/published_template_detail.html` — any "Question Group" references in user-facing headings.

**What NOT to change**:
- Route names (`group_builder`, `question_group_publish`, `published_templates_list`).
- URL paths (`/surveys/templates/`, `/surveys/<slug>/groups/`).
- Model names, API endpoints, view function names.
- `.po` files, `COMPLETE_STRINGS_LIST.md`, `docs/languages/*.md` — deferred per the i18n decision.

**Tests**:
- `test_groups_page_heading_says_sections` — GET `surveys:groups`, assert the heading text is the new term.
- `test_group_builder_breadcrumb_says_sections` — GET `surveys:group_builder`, assert breadcrumb label.
- `test_question_bank_page_title` — GET `surveys:published_templates_list`, assert `<h1>` says "Question Bank".
- `test_publish_page_heading` — GET `surveys:question_group_publish`, assert heading says "Share as template" (or chosen label).
- No regression: existing view tests still pass (they check status codes and routes, not labels — confirm).

**Exit criteria**:
- All user-facing headings use the chosen term.
- All new strings are `{% trans %}`-wrapped.
- No route, URL, model, or view name changes.
- `s/test --no-a11y` passes.
- `s/lint` passes.

**Docs**: None yet. Docs sweep is commit 9.

---

### Commit 5 — Rewrite the Groups page empty state

**Scope**: Tier 1.4. Lead with "Add your first question"; default group already exists (commit 2).

**Files**:
- `checktick_app/surveys/templates/surveys/groups.html` — empty state section. Replace "Create from scratch → name a group" as the primary action with "Add your first question" (linking to `group_builder` for the default group). Keep "Browse the Question Bank" as the secondary path (already present).

**Tests**:
- `test_groups_empty_state_leads_with_add_question` — a survey with the default group and no questions shows "Add your first question" as the primary CTA.
- `test_groups_empty_state_keeps_question_bank_link` — the "Browse the Question Bank" link is still present and resolves to `published_templates_list`.

**Exit criteria**:
- A new survey's Groups page leads with "Add your first question".
- The Question Bank link is preserved.
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 6 — Add the one-line "why" at first use

**Scope**: Tier 1.5. Teach the section concept at the moment of relevance.

**Files**:
- `checktick_app/surveys/templates/surveys/group_builder.html` — a one-line contextual hint near the section label, e.g. *"Sections group related questions — that's what lets you skip ahead or repeat a block."* Shown only when the survey has ≥1 question (so it doesn't clutter the empty state).
- `checktick_app/surveys/templates/surveys/groups.html` — the same hint on the Groups page, in the orientation strip area.

**Tests**:
- `test_builder_shows_why_hint_with_questions` — a group with ≥1 question shows the hint.
- `test_builder_hides_why_hint_when_empty` — an empty group does not show the hint.

**Exit criteria**:
- The hint appears at the moment of relevance and is `{% trans %}`-wrapped.
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 7 — Suppress redundant single-section header in participant view

**Scope**: The respondent-side polish item from the design doc review. Folded into Tier 1 because shipping the builder change without it creates an author/participant inconsistency.

**Files**:
- The participant-facing survey template (locate via `grep` for the section header rendering — likely `checktick_app/surveys/templates/surveys/` participant template, or a partial).
- Add a conditional: if `survey.question_groups.count == 1`, suppress the section header so the participant sees "just questions".

**Tests**:
- `test_participant_view_single_section_no_header` — a single-section survey renders no section header for the participant.
- `test_participant_view_multi_section_shows_headers` — a multi-section survey still renders section headers.
- A11y: `test_accessibility.py` — add a single-section participant scenario to the axe-core suite to confirm no landmark/heading-order regression (per the design doc's a11y acceptance criterion).

**Exit criteria**:
- Single-section participant view has no redundant header.
- Multi-section participant view unchanged.
- `s/test --a11y-only --serial` passes (this is the commit that needs the a11y suite).

**Docs**: None yet.

---

### Commit 8 — Docs sweep

**Scope**: Update all docs touched by Tier 1, per the references table in the design doc.

**Files** (per the design doc's "Question-group references across `docs/`" table):
- `docs/groups-view.md` — reframe to "Sections"; update the heading, "Managing Groups in the Groups View" section, and any "Question Groups" references in user-facing prose. Keep technical references to `QuestionGroup`.
- `docs/surveys.md` — update "Question groups vs questions" section heading and prose; the "chapters" metaphor stays. Update "Repeats are managed from the Groups page" if the Groups page is still the home (it is, until Tier 2).
- `docs/themes.md` — update breadcrumb example labels (L539, L553, L592) and the `{% blocktrans %}Groups for {{ survey.name }}{% endblocktrans %}` example (L615) to use the new term.
- `docs/publish-question-groups.md` — reframe user-facing prose to "Share as template" / "Publish to Question Bank"; keep the markdown format `# Question Group Name {group-id}` and `PublishedQuestionGroup` references.
- `docs/question-group-template-library.md` — align page title to "Question Bank"; reframe UI labels; keep import semantics descriptions.
- `docs/branching-and-repeats.md` — update "repeating question groups" prose and "Using the Groups View" heading.
- `docs/survey-builder-workflow-design.md` — update the "Affected surfaces" table to note `builder.html` was removed (commit 1); mark OQ2, OQ3, and the i18n decision as resolved.

**What NOT to change**:
- `docs/languages/*.md` and `docs/languages/COMPLETE_STRINGS_LIST.md` — deferred per the i18n decision.
- `docs/api.md`, `docs/testing-api.md`, `docs/testing-webapp.md` — technical references; keep `QuestionGroup` and test-suite names.
- `docs/self-hosting*.md`, `docs/question-group-templates-index.md` — admin/ops; keep technical names.

**Tests**: None (docs only).

**Exit criteria**:
- Every "Copy" row in the design doc's references table is updated.
- Every "Keep" row is verified unchanged.
- No broken internal links.

---

## Tier 2 outline (not committed yet)

Tier 2 depends on Tier 1 landing clean and a spike of the unified-builder approach. Outline only:

- **Spike**: prototype the unified builder as a new route + template (do not resurrect `builder.html` — it's gone). Decide left-rail vs. inline dividers (OQ1).
- **Commit 2.1**: unified builder view + template, master-detail, section rail with "Add section", main pane with "Add question".
- **Commit 2.2**: hide section layer for single-section surveys in the builder (with the a11y visually-hidden-heading rule as a blocking acceptance criterion + axe-core scenario).
- **Commit 2.3**: migrate dashboard CTA from per-group builder (commit 3) to unified builder.
- **Commit 2.4**: docs update for Tier 2.

## Tier 3 outline (not committed yet)

- **Commit 3.1**: move "Create repeat" into the section's context menu in the builder.
- **Commit 3.2**: frame branching "jump to…" targets as sections by friendly name.
- **Commit 3.3**: first-run nudge — open builder with "Add question" form focused.
- **Commit 3.4**: move "Share as template" to per-section action (relocate from Groups page).
- **Commit 3.5**: docs update for Tier 3.

---

## Commit ordering summary

| # | Commit | Depends on | Tests added | Docs updated |
|---|---|---|---|---|
| 1 | Remove `builder.html` | — | None (existing suite stays green) | None (design doc updated in commit 8) |
| 2 | Auto-create default group | — | 3 | None |
| 3 | Dashboard CTA → "Add questions" | 2 | 2 | None |
| 4 | Reframe templates to chosen term | OQ2 resolved | 4 | None |
| 5 | Rewrite empty state | 2, 4 | 2 | None |
| 6 | One-line "why" hint | 4 | 2 | None |
| 7 | Participant single-section header suppression | — | 2 + 1 a11y | None |
| 8 | Docs sweep | 1–7 | None | 7 doc files |

**Total Tier 1**: 8 commits, ~16 tests, 7 doc files updated.

---

## Notes

- **Run `s/lint` before every commit.** Per `AGENTS.md`, any feature or bug fix must be completed by running `s/lint` before committing.
- **Run `s/test --no-a11y` after every code commit.** Commit 7 additionally needs `s/test --a11y-only --serial`.
- **Atomic commits mean each commit builds and tests green on its own.** If commit 4 needs commit 2 to make sense (it does — the empty state in commit 5 assumes the default group exists), that's fine; the dependency is in the ordering, not in the commit being non-functional in isolation.
- **The i18n deferral is intentional.** New `{% trans %}` strings will fall back to English in non-English locales until a separate i18n refresh ticket updates `.po` files and `docs/languages/*.md`. This matches the current state of stale strings.
- **OQ2 is the only blocking decision.** Everything else is resolved. If you pick "Group" instead of "Section", commit 4 swaps the word and the rest of the plan stands unchanged.
