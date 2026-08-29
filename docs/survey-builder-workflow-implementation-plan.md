---
title: Survey Builder Workflow — Implementation Plan
category: development
priority: 5
---

# Survey Builder Workflow — Implementation Plan

**Status**: Living document — this plan will change as we learn.
**Date**: August 2026
**Scope**: Tier 1 ✅ merged. Tier 2 ✅ implemented. Tier 3 in progress (3.1 ✅). Tier 4 (Survey Map route) ✅ implemented.
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
| OQ1 — left rail vs. dividers | **Left rail (desktop) + dropdown (mobile)** (Tier 2) | A left rail matches the master-detail pattern and scales to many sections on desktop. On mobile, the rail collapses to a sticky `<select>` dropdown ("Section: Demographics ▾") — compact, native, and doesn't add a navigation layer. This is the pattern Google Forms uses. Horizontal tabs break down at 4+ sections; a slide-out drawer hides the list behind a tap. |
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

**Architecture decision**: The unified builder **builds on `group_builder.html`**, not replaces it. The question list + question-create form (the "question pane") is extracted from `group_builder.html` into a shared partial (`surveys/partials/builder_question_pane.html`). Both `group_builder.html` and the new `survey_builder.html` include that partial. This avoids duplicating the ~250 lines of question-create form, dataset picker, template tabs, and conditions panel. The existing `group_builder` route stays intact for deep links from the Groups page; the unified builder adds the section rail around the shared pane.

**Route**: `/<slug>/builder/` → `views.survey_builder` → `surveys/survey_builder.html`. The `gid` is optional (defaults to the first group); the rail handles section switching via HTMX partial swaps.

---

### Commit 2.1 — Unified builder view + route

**Scope**: Create the new view, route, and a minimal template that renders the master-detail layout. No section-hiding or fancy interactions yet — just the structure.

**Files**:
- `checktick_app/surveys/templates/surveys/partials/builder_question_pane.html` — **new partial**: extract the question list (`#questions-list`) + question-create form (`#create-question-form`) from `group_builder.html` L36–327. This is the `md:col-span-2` main area + the sidebar form, verbatim.
- `checktick_app/surveys/templates/surveys/group_builder.html` — replace the extracted block with `{% include 'surveys/partials/builder_question_pane.html' %}`. No visual or behavioural change.
- `checktick_app/surveys/urls.py` — add route `path("<slug:slug>/builder/", views.survey_builder, name="survey_builder")`.
- `checktick_app/surveys/views.py` — add `survey_builder(request, slug, gid=None)` view:
  - Loads the survey, all groups (ordered via `_resolved_group_order_ids`), and the selected group's questions.
  - If no `gid`, defaults to the first group.
  - Passes `groups`, `active_group`, `questions`, `can_edit`, and the same builder context as `group_builder` (datasets, patient/professional templates, etc.).
  - Renders `surveys/survey_builder.html`.
- `checktick_app/surveys/templates/surveys/survey_builder.html` — new template:
  - Extends `base.html`.
  - Breadcrumbs: Surveys > Survey Dashboard > Builder.
  - Layout: `grid md:grid-cols-4` — left rail (`md:col-span-1`, hidden on mobile) = section list + "Add section" button; main area (`md:col-span-3`, full width on mobile) = `{% include 'surveys/partials/builder_question_pane.html' %}`.
  - **Responsive section switcher**:
    - Desktop (`md+`): vertical rail listing sections in order, with the active section highlighted. Drag handles for reorder (SortableJS, same as Groups page). "Add section" button at the bottom of the rail.
    - Mobile (`<md`): a sticky `<select>` dropdown at the top of the main area — *"Section: Demographics ▾"*. Tapping it shows all sections. Hidden on `md+` via `hidden md:hidden` / `md:block` utility classes. The dropdown's `onchange` triggers the same navigation as a rail click (full page load in 2.1; HTMX swap in 2.3).
  - Both desktop and mobile are driven by the same `groups` context variable.
  - Clicking a section (rail or dropdown) navigates to `/<slug>/builder/?gid=<gid>` (full page load for now; HTMX swap in commit 2.3).
  - "Add section" button posts to `survey_group_create` and returns to the builder.

**Tests**:
- `test_group_builder_still_works_after_extraction` — GET `surveys:group_builder` returns 200 and renders the question pane (confirms the extraction didn't break the existing route).
- `test_survey_builder_view_renders` — GET `surveys:survey_builder` returns 200 with the section rail and question list.
- `test_survey_builder_defaults_to_first_group` — no `gid` param → first group is active.
- `test_survey_builder_selects_group_by_gid` — `?gid=<gid>` → that group is active and its questions are shown.
- `test_survey_builder_mobile_dropdown_present` — the response contains a `<select>` for section switching (the mobile dropdown).
- `test_survey_builder_desktop_rail_present` — the response contains the vertical section rail.
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
- `checktick_app/surveys/templates/surveys/survey_builder.html` — section links (both the desktop rail and the mobile dropdown) use `hx-get="/surveys/<slug>/builder/sections/<gid>/"` with `hx-target="#builder-main"` and `hx-swap="innerHTML"`. The mobile dropdown uses `hx-trigger="change"` so selecting an option triggers the swap. The "Add section" form uses `hx-post` to `survey_group_create` and swaps the rail + main area.
- `checktick_app/surveys/urls.py` — add route for the partial: `path("<slug:slug>/builder/sections/<int:gid>/", views.survey_builder_section, name="survey_builder_section")`.

**Tests**:
- `test_section_switch_via_htmx_returns_partial` — HTMX GET to the section endpoint returns 200 with just the question list HTML (not the full page).
- `test_section_switch_non_htmx_returns_full_page` — a non-HTMX GET to the section endpoint redirects to the full builder URL.
- `test_add_section_via_htmx` — POSTing to `survey_group_create` with HTMX headers returns the updated rail.
- `test_mobile_dropdown_triggers_htmx_swap` — the mobile `<select>` has `hx-trigger="change"` pointing at the section endpoint.

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

## Tier 3 commits — Progressive disclosure and deprecation

Tier 3 depends on Tier 2 landing clean. Detailed plan below.

**Goal**: Polish the builder UX, rename the Sections page to "Organise", add rename to the rail, deprecate the old `group_builder` route, and update docs.

**Security requirements for all new/modified routes**:
- `@login_required` decorator on every view
- `require_can_edit(request.user, survey)` permission check — raises `PermissionDenied` (403) for non-editors
- `@require_http_methods(["GET"])` or `@require_http_methods(["POST"])` to limit HTTP verbs
- `{% csrf_token %}` on all POST forms
- No inline JS — all `hx-*` attributes are CSP-safe data attributes; script tags use `nonce`
- XSS: group names and descriptions are sanitised via `strip_tags()` in the view (existing pattern)
- Rate limiting: `@ratelimit` on any write endpoint (existing pattern from `question_group_publish`)
- Tests: every new/modified endpoint gets a permission test (403 for non-editors), an XSS test (script tags in group names are stripped), and a method test (wrong HTTP verb returns 405)

---

### Commit 3.1 — Replace builder empty state with question-type signposting ✅

**Scope**: The builder empty state currently shows the `how_to_build.html` explainer, which tells the user about the Outline and AI Assistant — but they're already in the builder. Replace it with signposting that's relevant to the builder context. Also fix two pre-existing layout bugs uncovered during implementation: the `tabs-lifted` class name (renamed to `tabs-lift` in daisyUI v5) and the three-column squish that left the Add Question form too narrow for tabs to render side-by-side.

**Files**:
- `checktick_app/surveys/templates/surveys/partials/builder_empty_state.html` — **new partial**:
  - Short intro: "Add your first question using the form." (direction-agnostic — the form is to the right on desktop, below on mobile).
  - `<div>`-based bullet list (not `<ul>/<li>`) of available question types (text, multiple choice, dropdown, likert, yes/no, image) — brief, one line each. Uses `<div>/<p>` with `•` bullets because the partial renders inside `<ul id="questions-draggable">` which SortableJS manages; nested `<li>` elements would be picked up as draggable items and break the drag handler.
  - Signpost the "Special Templates" tab: "Need patient demographics or professional details? See the Special Templates tab in the Add Question form." — "Special Templates" wrapped in `<span class="font-medium">` (not a link, so it doesn't look clickable, but visually distinct).
  - Signpost the Question Bank: "Looking for ready-made validated questionnaires? Browse the Question Bank." with link to `published_templates_list`.
  - Signpost sections: "Questions can be grouped into sections for branching, repeats, or sharing — see the Sections guide." with link to `/docs/groups-view/`.
  - All links use consistent `link underline font-semibold` styling.
  - All strings `{% trans %}`-wrapped. Short and punchy — links, not paragraphs.
- `checktick_app/surveys/templates/surveys/partials/builder_question_pane.html`:
  - Replace the `how_to_build.html` include in the empty state with `builder_empty_state.html`.
  - Update the empty-state intro line: left-align (remove `text-center`), link "Question Bank" to `published_templates_list`, and use direction-agnostic copy ("using the form" instead of "above").
  - Fix `tabs-lifted` → `tabs-lift` (daisyUI v5.6 renamed the class; `tabs-lifted` doesn't exist in the compiled CSS and caused the tab inputs to render as plain stacked radio buttons with no tab styling).
  - Change the question pane layout from `grid md:grid-cols-3` (which squeezed the Add Question form into ~25% of the viewport, too narrow for tabs) to `flex flex-col` — the questions list and Add Question form now stack vertically, each taking the full width of the main area. This matches the existing mobile layout and is the pattern Google Forms uses.
  - Add a `border-l-4 border-primary` accent to the Add Question form card (via `.builder-editor-card` CSS) so it's visually distinct from the questions list card. Both cards use `bg-base-100` (lighter than the `bg-base-200` page background); the coloured left border provides distinction without affecting text contrast.
- `checktick_app/surveys/templates/surveys/partials/builder_section_rail.html` — add `border-l-4 border-secondary` to the rail card so all three builder surfaces (rail, questions, form) have distinct visual identities.
- `checktick_app/static/css/daisyui_themes.css` — in `.builder-editor-card`, add `border-left: 4px solid var(--color-primary)` (kept in CSS rather than the template because the `.builder-editor-card` class already sets a `border` shorthand that would conflict with Tailwind's `border-l-4`).
- `checktick_app/surveys/tests/test_survey_builder_workflow.py` — update `test_how_to_build_explainer_present_in_builder_empty_state` to assert the explainer is *no longer* present (inverted), and add the 4 new signposting tests.

**Tests**:
- `test_how_to_build_explainer_present_in_builder_empty_state` (updated) — asserts "How it works" is *not* in the builder empty state (the generic explainer has been replaced).
- `test_builder_empty_state_signposts_question_types` — the empty state mentions question types (Likert, Multiple choice, Dropdown).
- `test_builder_empty_state_signposts_special_templates` — the empty state mentions "Special Templates".
- `test_builder_empty_state_signposts_question_bank` — the empty state links to the Question Bank.
- `test_builder_empty_state_signposts_sections` — the empty state links to the Sections guide.

**Exit criteria**:
- Builder empty state shows question-type signposting, not the generic "how to build" explainer.
- All links resolve.
- Tab headers render side-by-side (not stacked) in the Add Question form.
- The Add Question form has enough horizontal space for the tabs (full width of the main area).
- The three builder surfaces (section rail, questions list, Add Question form) are visually distinct via coloured left borders.
- `s/test --no-a11y` passes.

**Docs**: None yet. Docs sweep is commit 3.5.

---

### Commit 3.2 — Always render the section rail + add rename to rail items

**Scope**: The rail is currently hidden for single-section surveys. But the rail with one section and an "Add section" button is useful even with one section — it teaches the user that sections exist and lets them add more. Also add a rename button to each rail item so users can rename sections without leaving the builder. Finally, add a delete button to each rail item so users can remove sections they no longer need — but only for the second and subsequent sections (the first/only section cannot be deleted from the rail; a survey must always have at least one section).

**Files**:
- `checktick_app/surveys/views.py` — in `survey_builder`, change `single_section` to always be `False` (the rail always renders when there are groups). Keep the visually-hidden heading for a11y when there's only one section. In `survey_group_delete`, add `next` param handling (redirect to `next` if provided, else fall back to `surveys:groups`) and reject deletion of the last remaining section.
- `checktick_app/surveys/templates/surveys/survey_builder.html` — remove the `{% if groups|length > 1 %}` condition around the rail. Always render the rail when `groups` is non-empty.
- `checktick_app/surveys/templates/surveys/partials/builder_section_rail.html` — add a small pencil/rename icon next to each section name. Clicking it opens a modal (reuse the rename modal pattern from `groups.html`) or an inline edit form. Posts to `survey_group_edit` with `next` pointing back to the builder. Also add a trash/delete icon next to each section name, **hidden for the first section** (the survey must always retain at least one section). The delete button posts to `survey_group_delete` (existing route) with a confirmation step (modal or `confirm()`-style prompt) and `next` pointing back to the builder. If the deleted section was the active section, the builder redirects to the first remaining section.
- `checktick_app/surveys/templates/surveys/partials/builder_section_swap.html` — update the OOB rail swap to include the rename and delete buttons.
- `checktick_app/static/js/builder-rail.js` — **new external JS file** to wire the rename button to the modal and the delete button to its confirmation (CSP-compliant, nonce'd). Follows the same pattern as `groups-page.js`.

**Security**:
- `survey_group_edit` already has `@login_required`, `@require_http_methods(["POST"])`, `require_can_edit`, and `strip_tags()` on the name. No new endpoint — reusing the existing one with a `next` param.
- `survey_group_delete` already has `@login_required`, `@require_http_methods(["POST"])`, `require_can_edit`, and CSRF protection. No new endpoint — reusing the existing one, but the view needs a small change: accept a `next` param (falling back to `surveys:groups` for backward compatibility with the Groups page) and reject deletion of the last remaining section (return 400 or redirect with an error message).
- The rename and delete modal forms include `{% csrf_token %}`.
- No inline JS — the modal wiring is in an external JS file with `nonce`.

**Tests**:
- `test_rail_always_renders_for_single_section` — a single-section survey now shows the rail.
- `test_rail_has_rename_button` — each rail item has a rename button.
- `test_rail_has_delete_button_for_second_section` — a multi-section survey shows a delete button on the second and subsequent rail items.
- `test_rail_first_section_has_no_delete_button` — the first (or only) section's rail item does not show a delete button.
- `test_rename_from_builder_redirects_to_builder` — POSTing to `survey_group_edit` with `next=/surveys/<slug>/builder/` redirects back to the builder.
- `test_rename_from_builder_strips_xss` — a group name with `<script>` tags is sanitised.
- `test_delete_section_from_builder_redirects_to_builder` — POSTing to `survey_group_delete` with `next=/surveys/<slug>/builder/` deletes the section and redirects back to the builder.
- `test_delete_last_section_rejected` — attempting to delete the only remaining section is rejected (400 or redirect with error).

**Exit criteria**:
- The rail always renders when the survey has at least one group.
- Each rail item has a rename button that opens a modal.
- The second and subsequent rail items have a delete button (with confirmation); the first/only section does not.
- Renaming or deleting from the builder stays on the builder.
- The last remaining section cannot be deleted.
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 3.2a — Match builder card styling in Outline and AI Assistant views ✅

**Scope**: The builder's question pane and Add Question form now use a consistent card styling pattern: `bg-base-100` cards with coloured left-border accents (`border-l-4 border-primary` for the Add Question form, `border-l-4 border-secondary` for the section rail). The Outline and AI Assistant views should adopt the same pattern so all three building surfaces feel like parts of one tool.

**Background**: During commit 3.1/3.2 we discovered that the builder's three-column layout (`grid md:grid-cols-3`) was too cramped for the Add Question form's tabs. We switched to a vertical stack (`flex flex-col`) with full-width cards. The Outline and AI Assistant views already use a similar stacked layout but their cards don't have the coloured left-border accents or the `shadow-sm` treatment. This commit brings them in line.

**Files**:
- `checktick_app/surveys/templates/surveys/outline.html` (or equivalent) — apply `card bg-base-100 shadow-sm border-l-4 border-primary` to the main editing card, matching the builder's Add Question form. If the Outline view has a secondary card (e.g. a preview or help panel), give it `border-l-4 border-secondary` to match the section rail.
- `checktick_app/surveys/templates/surveys/ai_assistant.html` (or equivalent) — same treatment: `card bg-base-100 shadow-sm border-l-4 border-primary` for the main interaction card, `border-l-4 border-secondary` for any secondary panel.
- `checktick_app/static/css/daisyui_themes.css` — if the Outline or AI Assistant views use the `.builder-editor-card` class (or a similar custom class), ensure the `border-left` accent is applied consistently. If they don't use a custom class, add one (e.g. `.outline-editor-card`, `.ai-editor-card`) following the same pattern as `.builder-editor-card`.

**Styling rules** (established in commit 3.1/3.2, to be applied consistently):
- All building-surface cards use `bg-base-100` (lighter than the `bg-base-200` page background, so they stand out).
- The primary editing/interaction card in each view gets a 4px `border-primary` left border (via CSS, not Tailwind, if a custom class is involved — see `.builder-editor-card` in `daisyui_themes.css`).
- Secondary panels (rail, help, preview) get a 4px `border-secondary` left border.
- All cards use `shadow-sm` (not `shadow` or `shadow-lg`) for a subtle elevation.
- Tab content panels inside cards use `bg-base-100` (lighter inserts within the tinted card — but since the cards are now `bg-base-100` too, the tab panels blend seamlessly).
- Text remains `text-base-content` on `bg-base-100` — the same WCAG AA-compliant pair used throughout the app. The coloured borders are decorative and don't affect text contrast.

**Tests**:
- `test_outline_card_has_primary_border` — the Outline view's main card has the `border-primary` accent.
- `test_ai_assistant_card_has_primary_border` — the AI Assistant view's main card has the `border-primary` accent.
- (If secondary panels exist) `test_outline_secondary_panel_has_secondary_border` / `test_ai_assistant_secondary_panel_has_secondary_border`.

**Exit criteria**:
- All three building surfaces (Builder, Outline, AI Assistant) use the same card styling pattern.
- The coloured left-border accents provide visual distinction without affecting text contrast.
- `s/test --no-a11y` passes.

**Docs**: None yet. Docs sweep is commit 3.5.

---

### Commit 3.3 — Rename "Sections" page to "Organise" + replace orientation strip ✅

**Scope**: The Sections page needs a name ("Organise") and a page-specific explainer that describes what the page is for, not the old 3-step workflow.

**Files**:
- `checktick_app/surveys/templates/surveys/groups.html` — change the heading from "Sections for {survey}" to "Organise {survey}". Change the breadcrumb from "Sections" to "Organise". Replace the `how_to_build.html` include (if present) with a new `organise_explainer.html` partial.
- `checktick_app/surveys/templates/surveys/partials/organise_explainer.html` — **new partial**:
  - Short intro: "This is the Organise page. Use it to:"
  - Bullet list: reorder sections (drag and drop), create and manage repeats, set up branching, visualise the survey as a flow diagram, publish sections as reusable templates
  - Link back to the builder: "For adding and editing questions, use the Builder."
  - All strings `{% trans %}`-wrapped.
- `checktick_app/surveys/templates/surveys/survey_builder.html` — update the toolbar button label from "Organise sections" to "Organise" (shorter).
- `checktick_app/surveys/templates/surveys/dashboard.html` — if any links say "Sections", update to "Organise".

**Tests**:
- `test_organise_page_heading` — the heading says "Organise", not "Sections for".
- `test_organise_page_explainer` — the explainer mentions reordering, repeats, branching, visualising, and publishing.
- `test_organise_page_links_to_builder` — the explainer links back to the builder.

**Exit criteria**:
- The page is called "Organise" in the heading, breadcrumb, and toolbar button.
- The orientation strip is replaced with a page-specific explainer.
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 3.4 — Deprecate `group_builder` route ✅

**Scope**: The unified builder is now the primary surface. The `group_builder` route is no longer linked from any template. Update the Groups page section rows to link to `survey_builder?gid=<gid>` instead of `group_builder`. Keep the `group_builder` route working for bookmarked URLs but add a deprecation comment.

**Files**:
- `checktick_app/surveys/templates/surveys/groups.html` — change the section row link from `/surveys/<slug>/builder/groups/<gid>/` to `/surveys/<slug>/builder/?gid=<gid>`.
- `checktick_app/surveys/views.py` — add a deprecation comment to `group_builder` view: "Deprecated: use `survey_builder` instead. This route is kept for bookmarked URLs."
- `checktick_app/surveys/templates/surveys/group_builder.html` — add a deprecation comment at the top of the template.

**Security**:
- No new routes. The `survey_builder` route already has `@login_required` and `require_can_edit`.
- The `group_builder` route keeps its existing security (no change).

**Tests**:
- `test_groups_page_section_links_to_unified_builder` — the section row links point to `survey_builder?gid=<gid>`, not `group_builder`.
- `test_group_builder_route_still_works` — the old route still returns 200 (for bookmarked URLs).

**Exit criteria**:
- No template links to `group_builder`.
- The `group_builder` route still works (for bookmarks).
- `s/test --no-a11y` passes.

**Docs**: None yet.

---

### Commit 3.5 — Docs update for Tier 3 ✅

**Scope**: Update docs to reflect Tier 3 changes.

**Files**:
- `docs/groups-view.md` — rename page title to "Organise". Update the explainer. Reference the builder as the primary surface.
- `docs/surveys.md` — update references to "Sections page" → "Organise page".
- `docs/survey-builder-workflow-design.md` — mark Tier 3 as implemented. Update the affected surfaces table. Resolve OQ6.
- `docs/themes.md` — update breadcrumb examples to use "Organise".
- `docs/testing-webapp.md` — update test descriptions.

**Tests**: None (docs only).

**Exit criteria**:
- Docs reflect the "Organise" rename.
- Docs reflect the `group_builder` deprecation.
- No broken internal links.

---

## Tier 4 — Survey Map visualiser route ✅

**Goal**: Give the branching visualiser its own route (`/<slug>/survey-map/`) instead of embedding it at the bottom of the Organise page. The Organise page focuses on bulk reorder, repeats, and publishing; the Survey Map gets dedicated space and is linked from the builder toolbar, the dashboard, and the Organise page. Named "Survey Map" (matching the existing code's terminology). Security: `@login_required`, `require_can_edit`, `@require_http_methods(["GET"])`.

### Commit 4.1 — Survey Map route + standalone template ✅

**Scope**: Add the `survey_map` view, route, and template. The visualiser is still embedded on the Organise page at this point; the follow-up commit wires the new route in and removes the embedded copy.

**Files**:
- `checktick_app/surveys/views.py` — add `survey_map(request, slug)`: `@login_required` + `@require_http_methods(["GET"])` + `require_can_edit`. Renders `surveys/survey_map.html` with `survey` and `has_questions`.
- `checktick_app/surveys/urls.py` — add `path("<slug:slug>/survey-map/", views.survey_map, name="survey_map")`.
- `checktick_app/surveys/templates/surveys/survey_map.html` — **new template**: extends `base.html`, breadcrumbs (Surveys › Survey Dashboard › Survey Map), toolbar linking back to Builder / Organise / dashboard, a one-line explainer, and `{% include 'surveys/partials/branching_visualizer.html' %}`. Shows an empty-state signpost when the survey has no questions.
- `checktick_app/surveys/tests/test_survey_builder_workflow.py` — 6 tests: renders, empty state, toolbar links back, 403 for viewers, 405 for POST, login redirect for anonymous.

**Exit criteria**: `/<slug>/survey-map/` renders the visualiser on its own page; viewers get 403; POST gets 405; anonymous gets a login redirect.

---

### Commit 4.2 — Wire Survey Map into builder/dashboard/organise; remove embedded visualiser ✅

**Scope**: Surface the new route from the three building surfaces and stop embedding the visualiser on the Organise page.

**Files**:
- `checktick_app/surveys/templates/surveys/survey_builder.html` — add a "Survey Map" button to the builder toolbar.
- `checktick_app/surveys/templates/surveys/dashboard.html` — add a "Survey Map" button in the action row, gated on `can_edit` (the route requires edit; the dashboard is view-gated, so the link must not appear for view-only members).
- `checktick_app/surveys/views.py` — add `can_edit` to the `survey_dashboard` context.
- `checktick_app/surveys/templates/surveys/groups.html` — remove the embedded `branching_visualizer.html` include; add a "Survey Map" button to the quick-nav toolbar.
- `checktick_app/surveys/templates/surveys/partials/organise_explainer.html` — link the "Visualise the survey as a flow diagram" bullet to the Survey Map route.
- `checktick_app/surveys/tests/test_survey_builder_workflow.py` — 5 tests: organise page no longer embeds the canvas; organise page links to the route; builder toolbar links to the route; dashboard links to the route for editors; dashboard hides the link for view-only members.
- Docs: `docs/survey-builder-workflow-implementation-plan.md`, `docs/survey-builder-workflow-design.md`, `docs/groups-view.md`, `docs/testing-webapp.md`.

**Exit criteria**: The Survey Map is reachable from the builder toolbar, the dashboard (editors only), and the Organise page. The Organise page no longer embeds the visualiser. `s/test --no-a11y` passes.

---

## Deferred to a follow-up PR (post-Tier 3)

- **Move "Create repeat" into the section's context menu in the builder** (originally Tier 3.1 in the old plan).
- **Frame branching "jump to…" targets as sections by friendly name** (originally Tier 3.2 in the old plan).
- **First-run nudge** — open builder with "Add question" form focused (originally Tier 3.3 in the old plan).
- **Move "Share as template" to per-section action** in the builder (originally Tier 3.4 in the old plan). Includes the single-section publishing case (OQ6).

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
| 2.1 | Unified builder view + route (extract shared partial) | — | 7 | — |
| 2.2 | Hide section rail for single-section | 2.1 | 3 + a11y | — |
| 2.3 | HTMX section switching + inline "Add section" | 2.1 | 4 | — |
| 2.4 | Migrate dashboard CTA to unified builder | 2.1 | 2 | — |
| 2.5 | Docs update for Tier 2 | 2.1–2.4 | — | 5 files |
| 2.6 | Reimagine orientation strip as "How to build" explainer | — | 2 | — |
| 2.7 | De-emphasise building cards when survey has questions | — | 2 | — |
| 2.8 | Builder toolbar (links to Sections, Preview, Dashboard) | — | 2 | — |
| 2.9 | Quick link back to builder from Sections page | — | 1 | — |

**Total Tier 2**: 9 commits, ~23 tests, 5 doc files updated.

### Tier 3 (current)

| # | Commit | Depends on | Tests added | Docs updated |
|---|---|---|---|---|
| 3.1 | Replace builder empty state with question-type signposting | — | 4 | — |
| 3.2 | Always render rail + add rename to rail items | 2.1 | 4 | — |
| 3.3 | Rename "Sections" page to "Organise" + replace orientation strip | — | 3 | — |
| 3.4 | Deprecate `group_builder` route | 2.1 | 2 | — |
| 3.5 | Docs update for Tier 3 | 3.1–3.4 | — | 5 files |

**Total Tier 3**: 5 commits, ~13 tests, 5 doc files updated.

### Tier 4 (current)

| # | Commit | Depends on | Tests added | Docs updated |
|---|---|---|---|---|
| 4.1 | Survey Map route + standalone template | — | 6 | — |
| 4.2 | Wire Survey Map into builder/dashboard/organise; remove embedded visualiser | 4.1 | 5 | 4 files |

**Total Tier 4**: 2 commits, 11 tests, 4 doc files updated.

### Deferred (post-Tier 3 PR)

| # | Commit | Tests | Docs |
|---|---|---|---|
| — | Move "Create repeat" to builder context menu | TBD | TBD |
| — | Branching targets as sections by friendly name | TBD | TBD |
| — | First-run nudge (focus Add Question form) | TBD | TBD |
| — | "Share as template" per-section in builder | TBD | TBD |

---

## Notes

- **Run `s/lint` before every commit.** Per `AGENTS.md`, any feature or bug fix must be completed by running `s/lint` before committing.
- **Run `s/test --no-a11y` after every code commit.** Commit 2.2 additionally needs `s/test --a11y-only --serial`.
- **Atomic commits mean each commit builds and tests green on its own.** If commit 2.2 needs commit 2.1 to make sense (it does — the rail-hiding applies to the unified builder), that's fine; the dependency is in the ordering.
- **The i18n deferral is still in effect.** New `{% trans %}` strings will fall back to English in non-English locales until a separate i18n refresh ticket updates `.po` files and `docs/languages/*.md`.
- **The existing `group_builder` route is deprecated in Tier 3.** The route stays for bookmarked URLs but no template links to it. The Groups page section rows link to `survey_builder?gid=<gid>` instead.
- **The Groups page is renamed to "Organise" in Tier 3.** The route name (`surveys:groups`) and URL path (`/<slug>/groups/`) stay unchanged — only the user-facing label changes.
- **Security is a first-class concern for all new routes.** Every new view gets `@login_required`, `require_can_edit`, HTTP method restrictions, CSRF tokens on POST forms, no inline JS (CSP-safe), XSS sanitisation (`strip_tags`), and tests for permission (403), XSS, and method (405).
- **HTMX is the interaction layer.** Section switching and "Add section" use HTMX partial swaps. Non-HTMX requests gracefully degrade to full page loads. No inline JS — all script tags are external and CSP-compliant, matching the existing `groups-page.js` pattern.
