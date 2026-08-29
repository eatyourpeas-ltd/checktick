---
title: Survey Builder Workflow Design
category: development
priority: 5
---

# Survey Builder Workflow Design

- **Status**: Tier 1 & 2 implemented; Tier 3 implemented; Tier 4 (Survey Map route, builder rail reorder/repeat, Organise tidy) implemented — see [Implementation Plan](/docs/survey-builder-workflow-implementation-plan/)
- **Date**: August 2026
- **Scope**: The survey creation → building workflow, and how question groups (referred to as **sections** in the UI) are introduced to users
- **Related**: [Surveys](/docs/surveys/) · [Sections](/docs/groups-view/) · [Branching Logic & Repeating Questions](/docs/branching-and-repeats/) · [Repeats](/docs/collections/) · [Outline / Import](/docs/import/)

---

## Summary

Today, a new user who wants to build a survey is forced to learn and act on an abstract concept — the **question group** — before they can add a single question. The dashboard's "Question Builder" card leads to a page titled *"Question Groups"*, whose primary action is *naming a group*. Only after creating and opening a group can the user add questions.

This document proposes inverting that relationship: **let the user start with questions (their mental model), and let sections emerge as an optional organizing tool that is invisible until it is needed.** The full power of groups — branching targets, repeating blocks, template publishing — is preserved, but surfaced progressively at the moment of relevance rather than as an upfront wall.

The change is primarily a workflow and presentation change. It does **not** alter the data model: every question still belongs to exactly one `QuestionGroup`. The model already matches the target design; only the presentation and the "first question" path need to change.

---

## Problem

The friction is not that groups are hard to use — it is that the user must adopt CheckTick's three-level hierarchy (`Survey → Group → Question`) before they can do the one thing they came to do.

Concrete friction points observed in the current implementation:

1. **Labeling mismatch.** On the survey dashboard, the card is labelled **"Question Builder"** (`dashboard.html`) but links to the **Question Groups** page (`/surveys/<slug>/groups/`). A user clicks "Builder" expecting to build questions and instead lands on a page whose primary action is naming a group.
2. **Groups are a gate, not a tool.** To add the *first* question the user must: understand what a "question group" is → create one (give it a name) → click into it → *then* add a question. Three conceptual steps before any question exists.
3. **Jargon vs. the product's own metaphor.** The product's own language already uses the intuitive word: [Surveys](/docs/surveys/) describes groups as acting "like chapters", [Question Groups](/docs/groups-view/) calls them "containers that organise related questions together", and the orientation strip on the groups page says *"Sections that organise your survey."* But the page heading is "Question Groups." The correct, intuitive word is already in use — it just isn't applied consistently to the UI heading.
4. **Advanced power presented upfront.** The real value of groups (branching targets, repeats, publishing) is only relevant to *some* surveys. Leading with it intimidates the user who just wants a simple linear form.

### Current flow

```text
1. Survey Dashboard
        │  click "Question Builder"
        ▼
2. Question Groups page   ("Question Groups for {survey}")
        │  (no groups yet) → empty state: "Create from scratch"
        ▼
3. Name a group          ← user must understand & create a "question group"
        │
        ▼
4. Click into the group
        │
        ▼
5. Group Builder → add question 1, 2, 3 …
```

The dead-end is step 3: the user cannot reach step 5 without first doing step 3, and step 3 is the step they don't understand.

---

## Goals

- **G1 — Remove the gate.** A user can add their first question without naming or understanding a group.
- **G2 — Teach sections by use, not by reading.** The section concept is introduced only when organizing, with a concrete reason attached.
- **G3 — Preserve all group power.** Branching, repeats, and template publishing remain fully available; they are surfaced progressively, not removed.
- **G4 — Reduce jargon.** Use the word the user already understands ("section") in the UI.
- **G5 — Stay consistent with mainstream survey tools.** Google Forms, Typeform, and SurveyMonkey all let you add questions immediately and treat "sections" as an optional layer.

## Non-goals

- **No data-model migration.** `QuestionGroup` stays the canonical container; every question still has exactly one group. We change presentation and the first-question path, not the schema.
- **No change to the Outline / bulk-import or AI-assisted flows.** Those already create groups and questions in one step and are not part of the confusion.
- **No change to the respondent (participant) rendering contract** beyond optionally hiding a redundant single-section header (see *Edge cases*).
- **No rename of the `QuestionGroup` model, API fields, or docs terminology.** "Section" is a UI label only.

---

## Core concept: questions first, sections invisible until needed

The single most important idea: **the section layer should not be visible until the user has more than one section.**

- **One section (the default):** no section chrome at all. The builder shows a flat list of questions with an "Add question" affordance. The user experiences it as *"I'm making a survey with questions."* The word "group/section" never appears.
- **Two or more sections:** the section layer *appears* (a left rail or section dividers). Now the user sees *"oh, I can organize into sections."* The default section is present and trivially renameable.
- **Reaching for power:** when the user adds a branching "jump to…" rule or makes a section repeatable, *that* is the moment a one-line explanation lands: *"Sections group related questions — that's what lets you skip ahead or repeat a block."* The concept is taught at the moment of relevance, with a benefit.

Net effect: a simple survey never shows the user the word "group"; a complex survey introduces it exactly when it becomes useful.

### Proposed flow

```text
1. Survey Dashboard
        │  click "Add questions"
        ▼
2. Builder   (default section auto-created, invisible)
        │
        ▼
3. Add question 1, 2, 3 …    ← flat list, no "group" concept shown
        │
        ├─ stop here → simple survey, done
        │
        └─ want to organise?
                │  "Add section"
                ▼
            Section layer appears (left rail / dividers)
                │
                ▼
            Drag questions into sections
                │
                ▼
            Sections unlock: branching · repeats · sharing
```

---

## The section model

| State | What the user sees | What the system does |
|---|---|---|
| New survey, 0 questions | Builder with "Add question" focused; no section chrome | A default `QuestionGroup` exists (auto-created) but is not rendered as a header |
| 1 section, N questions | Flat list of questions; a subtle, renameable "Section" label at most | Questions belong to the default group |
| 2+ sections | Section layer visible: left rail (or dividers) listing sections in order, with "Add section" | Each question belongs to exactly one group; reordering groups = reordering sections |
| User adds branching / repeat / publish | A one-line contextual explanation of *why* sections exist | Existing group features, unchanged |

**Default section naming.** Name it neutrally (`General` or `Section 1`) and make it trivially renameable. Because a single-section survey shows no section chrome, the name is rarely seen and never blocks the user.

**Why auto-create a default group is safe.** The model already requires every question to have a group, so a default group is not a new concept — it is simply one that the system creates for the user instead of asking them to. It is always removable/renamable, and for multi-section surveys it is just the first section.

---

## Naming

| Context | Term | Rationale |
|---|---|---|
| User-facing UI (builder, groups page, empty states, tooltips) | **Section** / **Sections** | A word clinicians already understand; matches the docs' own "chapters / sections" metaphor |
| Code, API, data model, docs reference | **Question group** / `QuestionGroup` | Stable technical term; no migration |
| Template library — navbar, dashboard, builder empty state | **Question Bank** (keep) | Friendly, intuitive; a good counterpoint to "Sections" (ready-made vs. your own structure) |
| Template library — page title and `<h1>` | **Question Bank** (adopt consistently) | Today the navbar says "Question Bank" but the page is titled "Question Group Template Library". Align the page title with the navbar label; keep the URL `/surveys/templates/` and the route name `published_templates_list` unchanged |
| Publishing action — button label and modal heading | **Share as template** / **Publish to Question Bank** | Reframes "Publish a Question Group" in user language; the action still creates a `PublishedQuestionGroup` |
| Publishing docs and API reference | **Question Group Template** / `PublishedQuestionGroup` | Stable technical term; matches the API endpoint `/api/question-group-templates/` and the `sync_global_question_group_templates` management command |

This is a low-risk, high-impact change: it is template-string work only. Keep `QuestionGroup` as the internal term everywhere it is load-bearing (API, admin, Outline import, publishing).

---

## Phased delivery

Work is split into three tiers so value can be shipped incrementally. **Tier 1 is the minimum that meaningfully de-confuses the flow** and requires no data-model work.

### Tier 1 — Cheap, high-impact (copy + routing + one small backend change)

| # | Change | Where | Notes |
|---|---|---|---|
| 1.1 | **Auto-create a default `QuestionGroup`** on survey creation (or lazily on first question) | `views.survey_create`, or a helper used by the question-create paths | The single most important change — removes the "name a group first" gate |
| 1.2 | **Fix the dashboard CTA** — rename the "Question Builder" card to **"Add questions"** and point it at a surface where a question can be added immediately | `dashboard.html` (the "Add or edit questions" card grid) | Stop sending users to the Groups page as the "builder" |
| 1.3 | **Reframe "Question Groups" → "Sections"** in user-facing templates | `groups.html`, `group_builder.html`, breadcrumbs, empty states | Templates only; keep the technical term in code/API/docs |
| 1.4 | **Rewrite the empty state** to lead with *"Add your first question"* (default section already exists); keep *"Browse the Question Bank"* as the secondary path | `groups.html` empty state | Drop "Create from scratch → name a group" as the primary action |
| 1.5 | **Add a one-line "why"** to sections at first use | Builder / groups page | Teach the concept at the moment of relevance |

### Tier 2 — The real fix (a unified builder page)

| # | Change | Where | Notes |
|---|---|---|---|
| 2.1 | **Build a master-detail builder**: left rail = sections (in order, with "Add section"), main area = questions in the selected section with "Add question" | New/updated builder view + template | Kills the "create group → navigate in → add question" dance. An unused `builder.html` template (flat "All Questions" list + a "Groups" sidebar) is close to this target and is a useful starting point — it is currently not wired to any route |
| 2.2 | **Hide the section layer for single-section surveys** in the builder | Builder template | Implements the "invisible until needed" mechanic |

### Tier 3 — Progressive disclosure of advanced features ✅ (implemented)

| # | Change | Where | Notes |
|---|---|---|---|
| 3.1 | **Replace builder empty state with question-type signposting** | `builder_empty_state.html` (new) | Replaces generic `how_to_build.html` explainer with relevant signposting |
| 3.2 | **Always render the section rail + add rename/delete to rail items** | `builder_section_rail.html`, `builder-rail.js`, `views.py` | Rail always renders; rename via modal; delete for 2nd+ sections only |
| 3.2a | **Match builder card styling in Outline and AI Assistant views** | `bulk_upload.html` | Consistent `border-l-4 border-primary/secondary` accents across all building surfaces |
| 3.3 | **Rename "Sections" page to "Organise" + replace orientation strip** | `groups.html`, `organise_explainer.html` (new) | Page-specific explainer replaces 3-step orientation strip |
| 3.4 | **Deprecate `group_builder` route** | `groups.html`, `views.py`, `group_builder.html` | Links now point to unified builder; old route kept for bookmarks |
| 3.5 | **Docs update for Tier 3** | Multiple docs files | Reflect Organise rename, group_builder deprecation, builder styling |

**Deferred to a follow-up PR:**

*Completed in the visualise branch:*
- ✅ Extract the Survey Map visualiser to its own route (`/<slug>/survey-map/`)
- ✅ Drag-reorder sections in the builder rail
- ✅ Remove rename/delete from the Organise page (now builder-only)
- ✅ Move single-section "Create repeat" into the builder rail (originally 3.1 in old plan)
- ✅ Reframe Organise as a small advanced page (removed explainer card and info alerts)

*TODO — future PR:*
- [ ] Frame branching targets as sections by friendly name (originally 3.2)
- [ ] Move "Share as template" to per-section action (originally 3.4)

*Completed:*
- ✅ First-run nudge — focus the Add Question form (originally 3.3). The empty-state nudge card is consistent across all swap paths (shared `builder_questions_empty.html` partial), and the Add Question text input is auto-focused when the active section has no questions (`data-autofocus` signal + `focusFirstQuestionInput()` in `builder.js`).

*Stays in Organise by design:*
- Publish as template (can apply to multiple sections)
- Branching (between sections, not within them)
- Multi-section repeat (bulk select)

---

## Affected surfaces (high level)

| Surface | File(s) | Change type |
|---|---|---|
| Survey creation redirect | `checktick_app/surveys/views.py` (`survey_create`) | Create default group (Tier 1.1) |
| Dashboard "Add or edit questions" cards | `checktick_app/surveys/templates/surveys/dashboard.html` | CTA label + destination (Tier 1.2) |
| Groups page (orientation strip, empty state, list, "add group" form) | `checktick_app/surveys/templates/surveys/groups.html` | Reframed to "Sections" (Tier 1), then renamed to "Organise" (Tier 3.3). Orientation strip replaced with `organise_explainer.html` partial. Section row links now point to unified builder. |
| Per-group question builder | `checktick_app/surveys/templates/surveys/group_builder.html` | Reframed (Tier 1); question pane extracted into shared partial `builder_question_pane.html` (Tier 2.1). **Deprecated** in Tier 3.4 — route kept for bookmarked URLs but no longer linked from any template. |
| Unused flat builder | ~~`checktick_app/surveys/templates/surveys/builder.html`~~ | **Removed** in Tier 1 commit 1 (was dead code — no route, no view, no test exercised it). |
| Unified builder | `checktick_app/surveys/templates/surveys/survey_builder.html` (new), `partials/builder_question_pane.html`, `partials/builder_section_rail.html`, `partials/builder_section_swap.html`, `partials/builder_empty_state.html` (new), `static/js/builder-rail.js` (new) | **New** in Tier 2. Master-detail layout with responsive rail/dropdown, HTMX section switching. Tier 3: rail always renders, rename/delete buttons added, empty state replaced with question-type signposting, card styling applied (border-l-4 accents). |
| Routes | `checktick_app/surveys/urls.py` | Added `survey_builder` route at `/<slug>/builder/` (Tier 2.1). `group_builder` route deprecated (Tier 3.4) — kept for bookmarked URLs. |
| Repeat creation | `checktick_app/surveys/views.py` (`survey_groups_repeat_create`), `groups.html` | Relocate/reframe into builder (Tier 3.1) |
| Navbar "Question Bank" entry | `checktick_app/templates/base.html` (desktop + mobile menus) | Label already correct; no change required, but verify it stays "Question Bank" after the Section rename (Tier 1.3) |
| Question Bank / template library page | `checktick_app/surveys/templates/surveys/published_templates_list.html`, `published_template_detail.html` | Align page `<h1>` to "Question Bank"; copy polish only (Tier 1.3). Route `published_templates_list` and URL `/surveys/templates/` unchanged |
| Per-group "Publish" button | `checktick_app/surveys/templates/surveys/groups.html` (per-row), `question_group_publish.html` | Relabel to "Share as template" / "Publish to Question Bank"; relocate to per-section action in the unified builder (Tier 3). View `question_group_publish` and route unchanged |
| Home page "Browse templates" CTA | `checktick_app/core/templates/core/home.html` | Label already says "Browse templates"; verify it still resolves to `published_templates_list` (Tier 1.3) |
| Bulk upload "Browse the template library" link | `checktick_app/surveys/templates/surveys/bulk_upload.html` | Copy polish only; the link target is unchanged (Tier 1.3) |

No changes to `models.py`, the Outline importer, the AI generator, or the API are required for any tier.

---

## Feature preservation: where each Groups View capability goes

[Question Groups](/docs/groups-view/) documents the current Groups View page as the home of several capabilities. This redesign relocates and reframes them; it does not remove any. The mapping:

| Capability (per `groups-view.md`) | Current home | New home in this design | Tier |
|---|---|---|---|
| Reorder groups (drag handle, "Save order") | Groups View list | Section rail in the unified builder (drag to reorder) | 2 |
| Create repeat from selection | Groups View ("Create repeat from selection") | Per-section action in the builder, reframed as "Let respondents fill this section out multiple times" | 3 |
| Nest repeats (one level) | Groups View repeat modal | Same repeat flow; nesting option preserved | 3 |
| Remove group from repeat | Groups View (✕ on repeat badge) | Per-section repeat controls in the builder | 3 |
| Publish as template (org/global, attribution, copyright) | Groups View ("Publish" per group) | Per-section "Share this section as a template" action | unchanged |
| Template library / Question Bank (browse, search, filter, one-click import) | Groups View + Question Bank page | "Browse the Question Bank" stays a first-class entry point (dashboard + builder empty state) | 1 |
| Access control (survey owner, org ADMIN) | Groups View | Same `require_can_edit` / `can_edit_survey` checks on the builder | 1 |
| Security / CSP (external JS, SortableJS) | Groups View | Builder JS follows the same no-inline-script / external-JS constraint | 2 |

Nothing documented in `groups-view.md` is dropped. Repeats, publishing, and the template library all survive; only their location and framing change so they are discovered at the moment of relevance. Whether the standalone Groups View page itself becomes a thin redirect to the unified builder after Tier 2 is an open question (see *Open questions*).

---

## Question-group publication and the Question Bank

CheckTick has a first-class publication workflow for sharing question groups as reusable templates. It is documented in [Publishing Question Groups](/docs/publish-question-groups/) and [Question Group Template Library](/docs/question-group-template-library/), and is reached from several surfaces:

- **Navbar** (desktop + mobile): a top-level **"Question Bank"** entry → `published_templates_list` (`/surveys/templates/`).
- **Groups page**: a **"Browse the Question Bank"** card in the empty state, a footer link, and a per-row **"Publish"** button → `question_group_publish`.
- **Home page**: a **"Browse templates"** CTA → `published_templates_list`.
- **Bulk upload page**: a "Browse the template library" link → `published_templates_list`.

The workflow has two halves:

1. **Browse / import** — any authenticated user can browse the library, filter by level/tags/language, view a template's markdown and attribution, and import it into a survey. Importing creates a complete `QuestionGroup` (with questions, options, attribution) in the target survey in one step.
2. **Publish** — a survey owner (or org ADMIN) can publish a `QuestionGroup` from their survey as a `PublishedQuestionGroup` at Organisation or Global level, with attribution (authors, DOI, PMID, license), tags, and a markdown preview. Rate-limited: 10 publications/day/user, 50 imports/hour/user.

### How this interacts with the redesign

The publication workflow is **largely untouched** by the Sections refactor — and that is intentional. It operates on whole question groups, which is exactly what `QuestionGroup` already is. The changes are confined to labels, entry-point location, and one consistency fix:

| Aspect | Today | After the redesign | Tier |
|---|---|---|---|
| Navbar label | "Question Bank" | "Question Bank" (unchanged) | — |
| Library page `<h1>` / title | "Question Group Template Library" | **"Question Bank"** (align with navbar) | 1.3 |
| Library route / URL | `published_templates_list` / `/surveys/templates/` | Unchanged | — |
| Browse entry from builder | Groups page empty-state card | Builder empty-state card ("Browse the Question Bank") — same target, new location | 1.4 / 2 |
| Publish entry point | Per-row "Publish" button on Groups page | Per-section "Share as template" action in the unified builder | 3 |
| Publish view / form / route | `question_group_publish`, `question_group_publish.html` | Unchanged — same form, same attribution fields, same rate limits | — |
| Import behaviour | Creates a `QuestionGroup` in the target survey | Unchanged — and it already bypasses the "name a group first" gate, so it complements Tier 1.1 naturally | — |
| `PublishedQuestionGroup` model / API | `/api/question-group-templates/` | Unchanged | — |
| Global template sync task | `sync_global_question_group_templates` | Unchanged (admin/ops name stays technical) | — |
| Docs page titles | `publish-question-groups.md`, `question-group-template-library.md` | User-facing prose reframed to "Question Bank" / "Share as template"; technical references stay | 1.3 |

### Why the publication workflow complements the Sections change

- **Import already creates the group for the user.** The import path has never forced the user to name a group first — it creates a complete `QuestionGroup` from the template in one step. Tier 1.1 (auto-create a default group on survey creation) makes the *manual* path match the *import* path. The two changes reinforce each other.
- **"Question Bank" vs. "Sections" is a clean mental split.** The Question Bank is the ready-made library (curated, attributed, validated instruments); Sections are the user's own structure inside their survey. Keeping the Question Bank name preserves that distinction and gives the builder empty state a natural secondary CTA: *"Add your first question, or browse the Question Bank."*
- **Publishing is a per-section power move.** Under the unified builder, "Share as template" lives on a section's context menu — exactly where the feature-preservation table puts it. This is the moment-of-relevance principle applied to publishing: a user who has just finished a clean PHQ-9 section sees "Share as template" right there, rather than having to navigate back to a standalone Groups page.
- **Attribution and clinical validity are unaffected.** The copyright/republishing protections (no republishing of imported templates, attribution preserved on import) are properties of `PublishedQuestionGroup` and the import flow, not of the Groups page UI. They survive unchanged.

### What does *not* change

- The `PublishedQuestionGroup` model, its fields, and its status lifecycle.
- The `/api/question-group-templates/` API endpoints.
- The `question_group_publish` view, its form, attribution fields, rate limits, and the `question_group_publish.html` template's *form structure* (only its heading/labels get the "Share as template" polish).
- The `sync_global_question_group_templates` management command and the `docs/question-group-templates/` curated repository.
- Import semantics: a template still imports as a complete `QuestionGroup`; imported groups still cannot be republished.
- Access control: publishing still requires survey ownership / org ADMIN; importing still requires owning the target survey.

### Open interaction: single-section surveys and publishing

A subtle edge case: under Tier 2.2, a single-section survey hides the section chrome in the builder. But the "Share as template" action is per-section. If the section layer is invisible, where does the publish action live? Two options:

1. Surface "Share as template" as a top-level builder action when there is exactly one section (it implicitly acts on that section).
2. Only surface it once a second section is added.

Option 1 is recommended — publishing a single-section survey (e.g., a standalone PHQ-9) is a common case and should not require the user to add a dummy second section just to access the action. This is added to *Open questions* below.

---

## Edge cases & considerations

- **Existing surveys that already have groups.** They should render under the new model with no migration: N existing groups = N visible sections. A survey with a single existing group shows no section chrome (consistent with new surveys). No data change.
- **Single-section header in the participant view.** Today a group renders as a section header for respondents. For a single-section survey, consider suppressing the redundant header so the participant experience matches the "just questions" mental model. This is a respondent-side polish item and is optional; it does not affect data.
- **Deleting the default section.** If a user deletes the only section that still contains questions, block deletion or reassign — the model requires every question to have a group. Surface a clear message rather than an orphaned state.
- **Internationalisation.** All new user-facing strings ("Add questions", "Add section", "Section", the one-line "why") must go through `{% trans %}` / `{% blocktrans %}` like the existing strings.
- **Accessibility.** The builder must remain WCAG 2.2 AA compliant: the section rail needs a clear heading hierarchy and keyboard-operable "Add section" / reorder controls; the "invisible until needed" behaviour must not remove information from assistive tech (use visually-hidden headings rather than removing structure).
- **Permissions.** The "Add questions" / "Add section" affordances must respect the same `require_can_edit` / `can_edit_survey` checks the Groups page already uses.
- **CSP.** Any new builder JS must follow the existing no-inline-script / external-JS constraint used by the Groups page.

---

## Open questions

1. ~~**Left rail vs. inline dividers**~~ **Resolved:** Left rail (desktop) + dropdown (mobile). Implemented in Tier 2. The rail scales to many sections; the dropdown is compact on mobile. Single-section surveys hide both.
2. ~~**Default section name.**~~ **Resolved:** `Section 1` — ordinal, neutral, rarely seen because single-section surveys hide the section chrome.
3. ~~**Should the dashboard "Add questions" CTA open the unified builder directly, or the current per-group builder**~~ **Resolved:** Tier 1 pointed at the per-group builder; Tier 2 migrated the dashboard CTA to the unified builder (`survey_builder`).
4. ~~**Participant single-section header suppression**~~ **Resolved:** Implemented in Tier 1 (commit 7). The `<fieldset>` structure is preserved for assistive tech; only the visible header is suppressed.
5. ~~**Do we keep the standalone Groups page at all**~~ **Resolved:** Keep it. The Groups page remains the home for bulk reorder, repeats, and publishing. The unified builder links to it for those operations.
6. **Publishing from a single-section survey.** ~~When the section layer is hidden (Tier 2.2), should "Share as template" be a top-level builder action (recommended, so a standalone PHQ-9 can be published without adding a dummy second section), or only surface once a second section exists?~~ **Resolved (Tier 3):** The section rail now always renders (commit 3.2), so the question of hiding the publish action for single-section surveys no longer applies. Publishing from single-section surveys is deferred to a follow-up PR (per-section "Share as template" action in the builder).
7. ~~**Question Bank page title.**~~ **Resolved:** The library page `<h1>` already says "Question Bank" (aligned with navbar). Done in Tier 1.

---

## Related documentation

- [Surveys](/docs/surveys/) — creating and managing surveys
- [Sections](/docs/groups-view/) — managing sections, repeats, publishing
- [Publishing Question Groups](/docs/publish-question-groups/) — publish a section as a reusable template (the "Share as template" workflow)
- [Question Group Template Library](/docs/question-group-template-library/) — the Question Bank: browse and import validated templates
- [Global Question Group Templates](/docs/question-group-templates-index/) — curated global template index
- [Branching Logic & Repeating Questions](/docs/branching-and-repeats/) — conditional logic and repeats
- [Repeats (Nested, repeatable sections)](/docs/collections/) — repeat data model and UI
- [Outline / Import](/docs/import/) — text format for questions and groups
- [AI-Assisted Survey Generator](/docs/ai-survey-generator/) — alternative creation path (out of scope here)

---

## Question-group references across `docs/`

This index lists every place in the `docs/` folder that refers to **question groups**, the **Groups View** page, or the `groups.html` / `group_builder.html` templates. It is here so that any UI/terminology refactor landing from this design doc can be propagated through the docs in one pass. The "Refactor touch?" column flags whether the line is likely to need a copy change under the proposed "Sections" UI label.

Legend:
- **Copy** — user-facing wording that would change if we adopt "Sections" in the UI.
- **Keep** — technical/API/data-model reference; should stay as `QuestionGroup` per the naming table above.
- **Review** — mixed or borderline; needs a judgement call when the refactor lands.

| File | Lines | Context | Refactor touch? |
|---|---|---|---|
| `docs/README.md` | L9 | Product blurb: "prebuilt question groups" | Copy |
| `docs/accessibility.md` | L35, L151 | "Question groups use `<fieldset>`/`<legend>`"; "Group context (when in a question group)" | Review (assistive-tech contract; keep technical, soften prose) |
| `docs/account-tiers-implementation.md` | L119, L121, L136, L137 | Feature matrix rows: "Question Groups", "Repeating Groups", "Question Group Sharing", "Published Question Groups" | Review (tier matrix — likely keep as canonical feature names) |
| `docs/ai-survey-generator.md` | L217, L445 | Outline `# Group Name {group-id}`; "Collections - Repeatable question groups" | Keep (data format) |
| `docs/api.md` | L60, L62, L127, L129, L139, L202 | `/api/question-group-templates/` endpoints and "Question Group Template Library API" section | Keep (API contract) |
| `docs/branching-and-repeats.md` | L7, L28, L46, L122 | "repeating question groups"; "Jump ahead to a specific section"; "Using the Groups View" | Copy |
| `docs/branching-technical.md` | L50 | "Links question groups or child collections to a parent collection" | Keep (data model) |
| `docs/groups-view.md` | whole file | The canonical Groups View doc; heading "Question Groups", "Managing Groups in the Groups View", related-docs links | Copy (primary refactor target) |
| `docs/import.md` | L29, L279 | "removes all existing question groups"; "recreates question groups" | Review (technical description of import behaviour) |
| `docs/languages/COMPLETE_STRINGS_LIST.md` | L63, L117–119, L121, L131, L227 | Source strings: "Question Group Builder", "Question Groups", "Question Group", "Create new question group", "New group name", import warning | Copy (these are the strings Tier 1.3 will change) |
| `docs/languages/arabic.md` | L54–58, L108–116, L122–126, L166–170 | Arabic translations of the above strings | Copy (re-translate after source strings change) |
| `docs/languages/chinese.md` | L54–58, L108–116, L122–126, L166–170 | Chinese translations | Copy |
| `docs/languages/french.md` | L54–58, L108–116, L122–126, L166–170 | French translations | Copy |
| `docs/languages/german.md` | L54–58, L108–116, L122–126, L166–170 | German translations | Copy |
| `docs/languages/hindi.md` | L54–58, L108–116, L122–126, L166–170 | Hindi translations | Copy |
| `docs/languages/italian.md` | L54–58, L108–116, L122–126, L166–170 | Italian translations | Copy |
| `docs/languages/polish.md` | L54–58, L108–116, L122–126, L166–170 | Polish translations | Copy |
| `docs/languages/portuguese.md` | L54–58, L108–116, L122–126, L166–170 | Portuguese translations | Copy |
| `docs/languages/spanish.md` | L54–58, L108–116, L122–126, L166–170 | Spanish translations | Copy |
| `docs/languages/urdu.md` | L54–58, L108–116, L122–126, L166–170 | Urdu translations | Copy |
| `docs/languages/welsh.md` | L54–58, L108–116, L122–126, L166–170 | Welsh translations | Copy |
| `docs/publish-question-groups.md` | whole file | Title, "Publishing a Question Group", "survey's question groups page", "question builder", markdown format `# Question Group Name {group-id}` | Copy (prose: reframe to "Share as template" / "Publish to Question Bank") + Keep (markdown format, `PublishedQuestionGroup` references) |
| `docs/question-group-template-library.md` | L2, L8, L24, L29, L67, L73, L78, L80, L118, L123, L125, L127, L156, L161 | Template library doc; "Browse Question Group Template Library" button, import behaviour, "Specialist templates vs. question group templates" | Copy (page title → "Question Bank"; UI labels) + Keep (data import descriptions, `PublishedQuestionGroup` semantics) |
| `docs/question-group-templates-index.md` | L2, L6, L68 | "Global Question Group Templates" title and heading | Review (page title — keep "Global Question Group Templates" as the technical index name; optionally add "Question Bank" subtitle) |
| `docs/self-hosting-scheduled-tasks.md` | L118, L122, L124 | "Global Question Group Templates Sync" scheduled task | Keep (admin/ops task name) |
| `docs/self-hosting.md` | L761 | "Global Question Group Templates Sync" | Keep (admin/ops task name) |
| `docs/survey-translation.md` | L24, L107 | "Question group names and descriptions" in what gets translated | Review (describes translatable fields — keep field reference, may add UI note) |
| `docs/surveys.md` | L7, L54, L79, L81, L140, L184, L190, L194 | "Question groups vs questions" section; "act like chapters"; "Jump the respondent to another question group"; "Repeats are managed from the Groups page"; Next-steps link | Copy (this is the main user-facing survey doc and already uses the "chapters" metaphor) |
| `docs/testing-api.md` | L132, L271 | "Question and Question Group API Tests", "Testing Question Groups" | Keep (test-suite names map to API) |
| `docs/testing-webapp.md` | L18, L330 | `test_groups_reorder.py`; "Testing Question Groups" section | Review (test file names are code; section heading is copy) |
| `docs/themes.md` | L526, L539, L553, L592, L615 | Breadcrumbs component: "Question group: multiple documents icon", example labels "Question Group Builder", convention note, `{% blocktrans %}Groups for {{ survey.name }}{% endblocktrans %}` | Copy (these are the exact template patterns Tier 1.3 touches) |

Notes for the refactor pass:
- The `docs/languages/` folder mirrors `COMPLETE_STRINGS_LIST.md` one-to-one. When the source strings change under Tier 1.3, every language file in that folder needs its rows 11, 65, 66, 67, 69, 70, 79, 80 (and the import warning at category 3, item 15) updated in lockstep.
- Files marked **Keep** describe the `QuestionGroup` model, API endpoints, scheduled-task names, or test-suite identifiers. The naming table in this doc explicitly keeps `QuestionGroup` as the internal term; these references should not be renamed.
- `docs/groups-view.md` and `docs/surveys.md` are the highest-impact copy edits because they are the primary user-facing surfaces that already use the "chapters / sections" metaphor inconsistently with their headings.
- The publication workflow (`docs/publish-question-groups.md`, `docs/question-group-template-library.md`) is mostly **Keep** on the data/API side and **Copy** on the prose side — reframe user-facing headings to "Question Bank" / "Share as template", but do not touch the markdown format, `PublishedQuestionGroup` references, or the import/publish semantics.
- Template files outside `docs/` that are affected by the publication refactor are listed in the *Affected surfaces* table above (`base.html` navbar, `published_templates_list.html`, `published_template_detail.html`, `question_group_publish.html`, `home.html`, `bulk_upload.html`).
