---
title: Survey Builder Workflow — Implementation Plan
category: development
priority: 5
---

# Survey Builder Workflow — Implementation Plan

**Status**: Living document — this plan will change as we learn.
**Date**: August 2026
**Scope**: Tier 1 ✅ merged. Tier 2 is the current focus. Tier 3 outlined.
**Parent design**: [Survey Builder Workflow Design](/docs/survey-builder-workflow-design/)

This is a commit plan, not a design doc. The design doc describes *what* and *why*; this describes *how*, *in what order*, and *what "done" means per commit*. Each commit is atomic: it builds, it tests green, it leaves the docs consistent.

---

## Decisions resolved

| OQ | Decision | Rationale |
|---|---|---|
| OQ2 — UI label | **Section** ✅ | Resolved in Tier 1. Matches the existing orientation strip, the "chapters" metaphor in `surveys.md`, and mainstream survey tools. |
| OQ3 — dashboard CTA target | **Per-group builder first** ✅ (Tier 1) → **Unified builder** (Tier 2) | Tier 1 points at `group_builder` for the default group. Tier 2 migrates to the unified builder. |
| i18n | **Defer translation files and `COMPLETE_STRINGS_LIST.md` updates.** ✅ | Templates use `{% trans %}` / `{% blocktrans %}` for all new/changed strings. `.po` files and `docs/languages/*.md` are out of date; a separate i18n refresh ticket will catch up. New `{% trans %}` strings fall back to English until then. |
| `builder.html` | **Removed** ✅ | Confirmed unused and deleted in Tier 1 commit 1. Tier 2 builds the unified builder fresh. |
| OQ1 — left rail vs. dividers | **Left rail** (Tier 2) | A left rail matches the master-detail pattern, scales to many sections, and gives a permanent home for "Add section". Inline dividers are simpler but don't scale and don't provide a persistent section switcher. The rail will collapse to a dropdown on mobile. |
| OQ5 — keep standalone Groups page? | **Keep for now** (Tier 2) | The Groups page is the only surface for bulk reorder + repeat management. Folding it into the builder is a Tier 4 idea, not Tier 2. The unified builder will link to it for bulk operations. |
| OQ6 — publishing from single-section survey | **Top-level builder action** (Tier 3) | When the section layer is hidden, "Share as template" will be a top-level builder action that implicitly acts on the single section. Deferred to Tier 3. |

---

## Pre-flight (no commits)

These are investigations or decisions, not code changes.

- ~~**Confirm OQ2 with product owner.**~~ ✅ Resolved: "Section".
- ~~**Confirm `builder.html` removal is acceptable.**~~ ✅ Done — removed in Tier 1.
- ~~**Spike `builder.html` before scoping Tier 2.**~~ ✅ Done — `builder.html` was dead code and has been removed. Tier 2 builds the unified builder fresh.
- **Resolve OQ1 (left rail vs. dividers).** ✅ Resolved: left rail (see decisions table above).

---

## Tier 1 commits ✅ (merged)

Tier 1 is complete and merged to `main`. The commits below are preserved for reference; see git history for details.

| # | Commit | Tests added | Docs updated |
|---|---|---|---|
| 1 | Remove `builder.html` | None | None |
| 2 | Auto-create default group | 3 | None |
| 3 | Dashboard CTA → "Add questions" | 2 | None |
| 4 | Reframe templates to "Sections" | 4 | None |
| 5 | Rewrite empty state + rename capability | 4 | None |
| 6 | One-line "why" hint | 2 | None |
| — | Breadcrumb label: "Manage Question" → "Questions" | 1 | None |
| 7 | Participant single-section header suppression | 2 + a11y | None |
| 8 | Docs sweep | None | 10 doc files |

**Total Tier 1**: 9 commits, 18 tests, 10 doc files updated.

---

## Tier 2 commits — The unified builder

**Goal**: Replace the "create group → navigate in → add question" dance with a single master-detail builder page. Left rail = sections (in order, with "Add section"); main area = questions in the selected section with "Add question". For single-section surveys, the rail is hidden and the user sees a flat question list.

**Architecture decision**: The unified builder is a **new route + new view + new template**, not a modification of `group_builder`. The existing `group_builder` route/view/template stays intact as a fallback and for deep links from the Groups page. The unified builder reuses the existing `question_row.html` partial and the question-create/edit HTMX endpoints — it does not duplicate them.

**Route**: `/<slug>/builder/` → `views.survey_builder` → `surveys/survey_builder.html`. The `gid` is optional (defaults to the first group); the rail handles section switching via HTMX partial swaps.

---

### Commit 2.1 — Unified builder view + route

**Scope**: Create the new view, route, and a minimal template that renders the master-detail layout. No section-hiding or fancy interactions yet — just the structure.

**Files**:
- `checktick_app/surveys/urls.py` — add route `path("<slug:slug>/builder/", views.survey_builder, name="survey_builder")`.
- `checktick_app/surveys/views.py` — add `survey_builder(request, slug, gid=None)` view:
  - Loads the survey, all groups (ordered via `_resolved_group_order_ids`), and the selected group's questions.
  - If no `gid`, defaults to the first group.
  - Passes `groups`, `active_group`, `questions`, `can_edit`, and the same builder context as `group_builder` (datasets, patient/professional templates, etc.).
  - Renders `surveys/survey_builder.html`.
- `checktick_app/surveys/templates/surveys/survey_builder.html` — new template:
  - Extends `base.html`.
  - Breadcrumbs: Surveys > Survey Dashboard > Builder.
  - Layout: `grid md:grid-cols-4` — left rail (`md:col-span-1`) = section list + "Add section" button; main area (`md:col-span-3`) = includes the existing question list + question-create form from `group_builder.html` (extracted into a shared partial or included directly).
  - The rail lists sections in order, with the active section highlighted. Clicking a section navigates to `/<slug>/builder/?gid=<gid>` (full page load for now; HTMX swap in commit 2.3).
  - "Add section" button posts to `survey_group_create` and returns to the builder.

**Tests**:
- `test_survey_builder_view_renders` — GET `surveys:survey_builder` returns 200 with the section rail and question list.
- `test_survey_builder_defaults_to_first_group` — no `gid` param → first group is active.
- `test_survey_builder_selects_group_by_gid` — `?gid=<gid>` → that group is active and its questions are shown.
- `test_survey_builder_requires_edit_permission` — a viewer gets 403.

**Exit criteria**:
- `/<slug>/builder/` renders a master-detail page with a section rail and question list.
- The existing `group_builder` route still works unchanged.
- `s/test --no-a11y` passes.

**Docs**: None yet. Docs sweep is commit 2.4.

---

### Commit 2.2 — Hide the section rail for single-section surveys

**Scope**: Implement the "invisible until needed" mechanic in the builder. When the survey has ≤1 section, the rail is hidden and the main area takes full width.

**Files**:
- `checktick_app/surveys/views.py` — in `survey_builder`, compute `single_section = len(distinct_group_ids) <= 1` (same pattern as commit 7).
- `checktick_app/surveys/templates/surveys/survey_builder.html` — wrap the rail in `{% if not single_section %}`. When `single_section`, the main area is `md:col-span-4` (full width) and a visually-hidden `<h2>` announces the section name for assistive tech (per the a11y acceptance criterion).

**Tests**:
- `test_survey_builder_single_section_hides_rail` — a survey with one group renders no section rail.
- `test_survey_builder_single_section_has_visually_hidden_heading` — the section name is present in a visually-hidden element for screen readers.
- `test_survey_builder_multi_section_shows_rail` — a survey with two groups renders the rail.
- A11y: add a single-section builder scenario to `tests/test_accessibility.py` (axe-core, `wcag22aa` tags).

**Exit criteria**:
- Single-section builder: no visible rail, full-width question list, visually-hidden heading for a11y.
- Multi-section builder: rail visible, main area in 3/4 width.
- `s/test --a11y-only --serial` passes.

**Docs**: None yet.

---

### Commit 2.3 — HTMX section switching + "Add section" inline

**Scope**: Make section switching feel instant via HTMX, and let "Add section" work without a full page reload.

**Files**:
- `checktick_app/surveys/views.py` — add a partial endpoint `survey_builder_section(request, slug, gid)` that returns just the main-area HTML (question list + create form) for HTMX swaps. The view detects HTMX requests via `HX-Request` header and returns a partial instead of the full page.
- `checktick_app/surveys/templates/surveys/survey_builder.html` — section links use `hx-get="/surveys/<slug>/builder/sections/<gid>/"` with `hx-target="#builder-main"` and `hx-swap="innerHTML"`. The "Add section" form uses `hx-post` to `survey_group_create` and swaps the rail + main area.
- `checktick_app/surveys/urls.py` — add route for the partial: `path("<slug:slug>/builder/sections/<int:gid>/", views.survey_builder_section, name="survey_builder_section")`.

**Tests**:
- `test_section_switch_via_htmx_returns_partial` — HTMX GET to the section endpoint returns 200 with just the question list HTML (not the full page).
- `test_section_switch_non_htmx_returns_full_page` — a non-HTMX GET to the section endpoint redirects to the full builder URL.
- `test_add_section_via_htmx` — POSTing to `survey_group_create` with HTMX headers returns the updated rail.

**Exit criteria**:
- Clicking a section in the rail swaps only the main area (no full page reload).
- "Add section" creates a new group and updates the rail without a full reload.
- Non-HTMX requests still work (graceful degradation).
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 2.4 — Migrate dashboard CTA to unified builder

**Scope**: Point the dashboard "Add questions" card at the unified builder instead of the per-group builder.

**Files**:
- `checktick_app/surveys/templates/surveys/dashboard.html` — change the "Add questions" link from `surveys:group_builder` to `surveys:survey_builder` (no `gid` needed — the builder defaults to the first group).
- Keep the fallback: if the survey has no groups (legacy), fall back to `surveys:groups`.

**Tests**:
- `test_dashboard_cta_points_at_unified_builder` — the "Add questions" link resolves to `survey_builder` (not `group_builder`).
- `test_dashboard_cta_fallback_for_legacy_survey` — still falls back to `surveys:groups` for surveys with no groups.

**Exit criteria**:
- Dashboard "Add questions" → unified builder.
- Legacy fallback preserved.
- `s/test --no-a11y` passes.

**Docs**: None yet. Docs sweep is commit 2.5.

---

### Commit 2.5 — Docs update for Tier 2

**Scope**: Update docs to reflect the unified builder.

**Files**:
- `docs/groups-view.md` — add a note that the unified builder (`/<slug>/builder/`) is now the primary building surface; the Groups page remains for bulk reorder, repeats, and publishing.
- `docs/surveys.md` — update the "Sections vs questions" section to reference the unified builder.
- `docs/survey-builder-workflow-design.md` — mark Tier 2 as implemented; update the "Affected surfaces" table; resolve OQ1 (left rail) and OQ5 (keep Groups page).
- `docs/themes.md` — update breadcrumb examples to include the unified builder route.
- `docs/testing-webapp.md` — add the unified builder to the test location list.

**Tests**: None (docs only).

**Exit criteria**:
- Docs reflect the unified builder as the primary building surface.
- The Groups page is documented as the home for bulk operations.
- No broken internal links.

## Tier 3 outline (not committed yet)

Tier 3 depends on Tier 2 landing clean. Outline only:

- **Commit 3.1**: move "Create repeat" into the section's context menu in the unified builder.
- **Commit 3.2**: frame branching "jump to…" targets as sections by friendly name.
- **Commit 3.3**: first-run nudge — open builder with "Add question" form focused.
- **Commit 3.4**: move "Share as template" to per-section action (relocate from Groups page). Includes the single-section publishing case (OQ6 — top-level builder action when rail is hidden).
- **Commit 3.5**: docs update for Tier 3.

---

## Commit ordering summary

### Tier 1 ✅ (merged)

| # | Commit | Tests | Docs |
|---|---|---|---|
| 1 | Remove `builder.html` | — | — |
| 2 | Auto-create default group | 3 | — |
| 3 | Dashboard CTA → "Add questions" | 2 | — |
| 4 | Reframe templates to "Sections" | 4 | — |
| 5 | Rewrite empty state + rename | 4 | — |
| 6 | One-line "why" hint | 2 | — |
| — | Breadcrumb label fix | 1 | — |
| 7 | Participant single-section header suppression | 2 + a11y | — |
| 8 | Docs sweep | — | 10 files |

### Tier 2 (current)

| # | Commit | Depends on | Tests added | Docs updated |
|---|---|---|---|---|
| 2.1 | Unified builder view + route | — | 4 | — |
| 2.2 | Hide section rail for single-section | 2.1 | 3 + a11y | — |
| 2.3 | HTMX section switching + inline "Add section" | 2.1 | 3 | — |
| 2.4 | Migrate dashboard CTA to unified builder | 2.1 | 2 | — |
| 2.5 | Docs update for Tier 2 | 2.1–2.4 | — | 5 files |

**Total Tier 2**: 5 commits, ~12 tests, 5 doc files updated.

### Tier 3 (outlined)

| # | Commit | Tests | Docs |
|---|---|---|---|
| 3.1 | Move "Create repeat" to builder | TBD | TBD |
| 3.2 | Branching targets as sections | TBD | TBD |
| 3.3 | First-run nudge | TBD | TBD |
| 3.4 | "Share as template" per-section | TBD | TBD |
| 3.5 | Docs update for Tier 3 | — | TBD |

---

## Notes

- **Run `s/lint` before every commit.** Per `AGENTS.md`, any feature or bug fix must be completed by running `s/lint` before committing.
- **Run `s/test --no-a11y` after every code commit.** Commit 2.2 additionally needs `s/test --a11y-only --serial`.
- **Atomic commits mean each commit builds and tests green on its own.** If commit 2.2 needs commit 2.1 to make sense (it does — the rail-hiding applies to the unified builder), that's fine; the dependency is in the ordering.
- **The i18n deferral is still in effect.** New `{% trans %}` strings will fall back to English in non-English locales until a separate i18n refresh ticket updates `.po` files and `docs/languages/*.md`.
- **The existing `group_builder` route stays.** It's not deleted in Tier 2 — it remains as a fallback and for deep links from the Groups page. The unified builder is additive.
- **The Groups page stays.** Per OQ5, the Groups page remains the home for bulk reorder, repeats, and publishing. The unified builder links to it for those operations.
- **HTMX is the interaction layer.** Section switching and "Add section" use HTMX partial swaps. Non-HTMX requests gracefully degrade to full page loads. No inline JS — all script tags are external and CSP-compliant, matching the existing `groups-page.js` pattern.
