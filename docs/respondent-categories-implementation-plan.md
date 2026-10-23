---
title: Respondent Categories — Implementation Plan
category: development
priority: 18
---

Implementation plan for the **respondent categories** feature — a
cross-cutting feature (not a layout) that lets a survey author categorise
respondents along one or more author-defined dimensions (`rater_role`,
`site`, `cohort`, …) within a single published survey, so different
respondents see different subsets of the same survey without cloning it.

This unblocks the **360° / multi-rater assessment** pattern (NHS 360,
clinician appraisal, medical education) and generalises the per-layout
FK pattern the codebase already uses (`assigned_arm` for RCT,
`delphi_round` for Delphi, `access_token` for token visibility).

Once implemented, this document is the source for updating
`docs/survey-layouts.md` and `docs/survey-layouts-technical.md` — the
"Planned layouts" / "Patterns and modes" sections that currently
describe respondent categories as parked will move into live
reference sections, mirroring how the Delphi and Diary sections
graduated.

## Motivation

NHS 360 assessments need multiple rater types (self, peer, supervisor,
patient) rating a single subject, each seeing a different question set,
with results aggregated by subject across raters. Today this requires
cloning the survey per rater role — one survey per role, joined
manually on a subject reference. Respondent categories makes it a
single survey with a `rater_role` dimension driving section visibility
and a `subject` dimension driving cross-rater aggregation in
reporting.

The feature is general: the same mechanism serves multi-site trials
(`site`), cohort studies (`cohort`), and any future "different
respondents see different sections" need without adding more hardcoded
per-layout FKs.

## Scope

### In scope

- Author-defined category **dimensions** (name + allowed values) per
  survey, authored on the Organise page.
- **Resolution** of a category value per participant, from four sources
  in priority order: invite token, self-select question, system
  assignment (reusing the RCT seed allocator), profile field.
- **Item visibility**: `required_categories` rule on `QuestionGroup`
  and `SurveyQuestion` that drops sections/questions whose categories
  don't match the participant's resolved values. This is a static
  pre-step filter on `_resolved_group_order_ids` — no new branching
  action.
- **Bulk-upload / outline grammar**: a `CATEGORIES` block and
  `~ cat:<dim>:<value>` section suffixes, with export round-trip.
- **Publication workflow**: token batches carry `category_values` for
  that batch.
- **Reporting**: results slicable/pivotable by any category dimension.
- **Preview**: `?simulate_category=<dim>:<value>,<dim>:<value>` path.
- **360° question-bank template**: a ready-made 360 instrument
  (rater_role + subject dimensions, pre-tagged sections) ships in the
  question bank once the mechanism exists. No new layout enum value.

### Out of scope (recorded to forestall scope creep)

- **Language / translation.** Language is a content-level variant
  (question text differs), not a visibility-level variant (same
  questions, different subset). Subsuming language into categories
  would require categories to carry per-variant content, not just
  per-variant visibility — a fundamentally bigger model. A survey can
  have both: an English survey with `rater_role` categories and a Welsh
  translation of the same with its own `rater_role` categories. See
  `docs/survey-layouts-technical.md` §Respondent categories for the
  full rationale.
- **Dynamic branching on category** ("if rater_role=supervisor AND
  answer to Q3=yes, jump to Q7"). This would need a new condition
  source type on `SurveyQuestionCondition`. Most cross-cut cases can be
  expressed as static visibility by splitting the survey into
  per-category sections. Defer until a clear use case emerges that
  static visibility cannot cover.
- **A `MultiRaterMenu` model or `360` layout enum value.** The docs
  explicitly argue against this; 360 is a pattern on categories, not a
  layout.

## Data model

```python
class RespondentCategory(models.Model):
    """One category dimension per survey (e.g. rater_role, site, cohort).

    Dimensions are author-defined; there is no fixed enum. The name is
    the key used in required_categories rules and category_values maps.
    """
    survey = models.ForeignKey(
        Survey, related_name="respondent_categories", on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
        help_text="Dimension key, e.g. 'rater_role', 'site'. Slug-like.",
    )
    label = models.CharField(
        max_length=100, blank=True,
        help_text="Human label for the Organise page (defaults to name).",
    )
    allowed_values = models.JSONField(
        default=list,
        help_text="List of allowed values, e.g. ['self', 'peer', 'supervisor'].",
    )
    resolution_source = models.CharField(
        max_length=20,
        choices=[
            ("token", "Invite token"),
            ("self_select", "Self-select question"),
            ("system", "System assignment (RCT allocator)"),
            ("profile", "Profile field"),
        ],
        default="token",
    )
    # For resolution_source = "self_select": the question whose answer
    # populates this dimension. For "profile": the profile field key.
    source_question = models.ForeignKey(
        "SurveyQuestion", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_categories",
        help_text="For self_select resolution: the question whose answer sets this dimension.",
    )
    profile_field = models.CharField(
        max_length=100, blank=True,
        help_text="For profile resolution: the UserProfile/Org field key.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("survey", "name")
        ordering = ["order", "id"]


class RespondentAssignment(models.Model):
    """The resolved category value for one participant × dimension.

    Resolved once at first access and preserved on resume — same
    lifecycle as assigned_arm (RCT) and delphi_round (Delphi).
    """
    progress = models.ForeignKey(
        SurveyProgress, related_name="category_assignments", on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        RespondentCategory, on_delete=models.CASCADE,
        related_name="assignments",
    )
    value = models.CharField(max_length=100)

    class Meta:
        unique_together = ("progress", "category")


class SurveyAccessToken(models.Model):
    ...
    # New: the category values for this token's batch. e.g.
    # {"rater_role": "peer"} means every participant using this token
    # resolves rater_role=peer. Blank = no token-borne values; the
    # dimension falls back to its next resolution source.
    category_values = models.JSONField(
        default=dict, blank=True,
        help_text="Category values carried by this token batch (dim -> value).",
    )


class QuestionGroup(models.Model):
    ...
    # New: sections absent from a participant's resolved categories are
    # dropped before _resolved_group_order_ids. e.g.
    # {"rater_role": ["peer", "supervisor"]} = show this section only
    # to peer and supervisor raters. Empty/absent = visible to all.
    required_categories = models.JSONField(
        default=dict, blank=True,
        help_text="Category rules gating this section (dim -> [allowed values]).",
    )


class SurveyQuestion(models.Model):
    ...
    # New: same shape as QuestionGroup.required_categories, at question
    # granularity. A question is shown only if its group is visible AND
    # its own required_categories match.
    required_categories = models.JSONField(
        default=dict, blank=True,
        help_text="Category rules gating this question (dim -> [allowed values]).",
    )
```

A `linear` survey with no `RespondentCategory` rows behaves exactly as
before — `required_categories` defaults to `{}` and the filter is a
no-op.

**Migration:** `0071_respondent_categories` (adds `RespondentCategory`,
`RespondentAssignment`, and the three new JSONFields on
`SurveyAccessToken`, `QuestionGroup`, `SurveyQuestion`).

## Resolution

`_resolve_categories_for_progress(progress)` is a standalone function
in `views.py` (next to `_assign_arm_for_progress`), called on first
access when the survey has `RespondentCategory` rows and the progress
record has no `RespondentAssignment` rows yet. For each dimension, in
priority order:

1. **Invite token** — if `progress.access_token` is set and its
   `category_values` contains the dimension, use that value. This is
   the 360 rater-invite pattern: each token batch carries the role for
   that batch.
2. **Self-select question** — if the dimension's `source_question` is
   set, read the participant's answer to that question. Works for
   public/unlisted visibility where there is no token.
3. **System assignment** — reuses the RCT seed allocator
   (`_assign_arm_for_progress` logic). This is "RCT arm as a category
   dimension" — the dimension is marked `system_assigned` and the
   allocator picks a value from `allowed_values` using
   `progress.randomisation_seed` (set on first access if absent, same
   as RCT).
4. **Profile field** — if `profile_field` is set, read it from
   `progress.user.userprofile` (or org membership). Useful for
   authenticated-visibility surveys.

The resolved values are stored as `RespondentAssignment` rows and
preserved on resume. If no source resolves a value, the dimension is
left unset and `required_categories` rules referencing it evaluate to
"not shown" (a section requiring `rater_role=peer` is hidden if
`rater_role` is unresolved).

## Runtime hook

Category-based visibility is a **static pre-step filter**, not a
branching rule — the same argument as
`docs/survey-layouts-technical.md` §Runtime — why no new branching
action is needed. In `_handle_participant_submission`, after category
resolution and before `_resolved_group_order_ids`:

1. Resolve category values for the progress record (if not already
   resolved).
2. Build a set of "visible" group IDs by dropping any `QuestionGroup`
   whose `required_categories` don't match the resolved values.
3. Intersect with `selected_group_ids` (if set by section_menu / RCT /
   matrix) so the two filters compose.
4. Pass the filtered set to `_resolved_group_order_ids` as usual.
5. Drop any `SurveyQuestion` whose `required_categories` don't match
   (question-level filter, applied after the group filter).

Questions filtered out by category are simply absent from the rendered
list, so any `jump_to` / `show` / `hide` conditions targeting them are
never triggered. No new branching action or condition source is needed.

**Composition with existing layouts:** respondent categories composes
with every shipped layout. A section_menu + categories survey shows
the picker first, then walks the chosen sections filtered by category.
An RCT + categories survey resolves the arm (system-assigned
dimension) and the token-borne dimensions independently. This is the
"orthogonal dimensions" property the `assigned_arm` docstring and the
`0061` migration comment already describe.

## Outline grammar (bulk upload)

The `CATEGORIES` block sits at the top of the outline (analogous to
`RANDOMISED`, `STAGED`, `MATRIX`) and `~ cat:<dim>:<value>` suffixes
mark which sections belong to which category values:

```text
CATEGORIES
  rater_role:
    values: self, peer, supervisor, patient
    source: token
  subject:
    values: self
    source: self_select
    question: {subject-id}

# Demographics {demographics}    ~ cat:rater_role:self, cat:rater_role:peer, cat:rater_role:supervisor, cat:rater_role:patient
## Name {name}
(text)

# Peer rating {peer-rating}    ~ cat:rater_role:peer
## Clinical knowledge {clinical-knowledge}
(likert number)
min: 1
max: 5

# Self-reflection {self-reflection}    ~ cat:rater_role:self
## What went well {went-well}
(long_text)
```

- Each dimension is a `key:` block with `values:` (comma-separated) and
  `source:` (`token`, `self_select`, `system`, `profile`).
- For `self_select`, add `question: {question-id}` pointing at the
  self-select question in the outline.
- `~ cat:<dim>:<value>` may repeat on a section (a section visible to
  multiple values of a dimension). Sections with no `~ cat:` suffix are
  visible to all (category filter is a no-op for them).
- A blank line ends the config block.

The export side emits the `CATEGORIES` block and `~ cat:` suffixes,
and the config survives export → import round-trips — same contract as
the RCT `RANDOMISED` block and `~ arm:` suffixes.

## Publication workflow

Category **dimensions** are defined at design time (Organise page).
Category **values** are assigned at publication time:

- **Token-borne values:** when generating a token batch, the author
  specifies the category values for that batch ("this batch of 50
  tokens is for `rater_role=peer`"). The values are written to
  `SurveyAccessToken.category_values` for each token in the batch.
- **Self-select:** no publication-time action; the value is resolved
  from the participant's answer at take time.
- **System assignment:** no publication-time action; the allocator
  picks at first access.

## Reporting

Results can be sliced/pivoted by any category dimension. This is the
cross-rater aggregation 360 needs (group responses by `subject`, break
down by `rater_role`), but it is also what every observational study
wants ("break down by recruitment site"). The CSV export
(`PaymentAdmin.export_to_csv` / survey response export) gains a column
per category dimension; the response analytics view gains a
group-by dropdown.

## Preview

`?simulate_category=<dim>:<value>,<dim>:<value>` on the preview path,
e.g. `?simulate_category=rater_role:peer,subject:self`. When present,
the category filter uses the simulated values instead of resolving
from token/question/profile. A "Simulate category" panel on
`detail.html` (preview mode only) provides a dropdown per dimension.

## Atomic commit plan

Each commit is self-contained: model/code + tests + the doc section it
implements. Commits are ordered so each builds on the previous.

### Commit 1 — Migration + models

- `checktick_app/surveys/migrations/0071_respondent_categories.py`
- `RespondentCategory`, `RespondentAssignment` models in `models.py`
- `category_values` on `SurveyAccessToken`
- `required_categories` on `QuestionGroup` and `SurveyQuestion`
- Tests: `checktick_app/surveys/tests/test_respondent_categories_models.py`
  — model creation, defaults, `unique_together`, cascade behaviour.
- Docs: add this file (`docs/respondent-categories-implementation-plan.md`).

### Commit 2 — Resolution logic

- `_resolve_categories_for_progress(progress)` in `views.py`
- Four resolution sources (token, self_select, system, profile) in
  priority order.
- `RespondentAssignment` rows created on first access, preserved on
  resume.
- Tests: `test_respondent_categories_resolution.py` — each source,
  fallback order, unresolved dimension, resume preserves assignment.

### Commit 3 — Runtime hook (visibility filter)

- Category filter in `_handle_participant_submission` before
  `_resolved_group_order_ids`.
- Group-level `required_categories` filtering (question-level field
  exists on the model but is not enforced by the runtime hook in this
  release — see §Resolved decisions 4).
- Composition with `selected_group_ids` (section_menu / RCT / matrix).
- Tests: `test_respondent_categories_runtime.py` — section hidden by
  category, composition with section_menu, composition with RCT, resume
  preserves filtered set.

### Commit 4 — Organise page UI

- Dimension authoring (add/edit/remove categories, set allowed values,
  resolution source).
- `required_categories` tagging on groups and questions in the
  organise page.
- `_sync_respondent_categories(survey)` (analogous to
  `_sync_section_menu_items`) called on organise page visit.
- Tests: `test_respondent_categories_organise_ui.py` — create/edit/
  remove dimensions, tag a section, tag a question, sync on visit.

### Commit 5 — Preview + Survey Map

- `?simulate_category=` preview path.
- Survey Map shows category dimensions and `~ cat:` annotations.
- Tests: `test_respondent_categories_preview_map.py` — simulate
  parameter, map shows dimensions, map shows cat annotations.

### Commit 6 — Outline / bulk-upload grammar

- `CATEGORIES` block parsing in the outline importer.
- `~ cat:<dim>:<value>` section suffixes.
- Export side emits the block + suffixes.
- Tests: `test_outline_respondent_categories.py` — parse block, parse
  suffixes, round-trip export, missing dimension warning, blank
  config block.
- Extend `test_bulk_upload_branching.py` if needed for interaction
  with branching suffixes.

### Commit 7 — Publication workflow (token batches)

- Token batch generation accepts `category_values` per batch.
- `SurveyAccessToken.category_values` populated on batch creation.
- Tests: extend publish/token tests — batch with category values,
  token resolves dimension, token without values falls back.

### Commit 8 — Reporting (CSV export + analytics)

- CSV export gains a column per category dimension.
- Response analytics group-by dropdown.
- Tests: extend `test_csv_export.py` and `test_response_analytics.py`
  — category columns in export, group-by dimension in analytics.

### Commit 9 — 360° question-bank template

- A ready-made 360 instrument template (rater_role + subject
  dimensions, pre-tagged sections) in the question bank.
- Tests: `test_respondent_categories_360_template.py` — template
  loads, dimensions resolve, sections filter correctly per role.

### Commit 10 — Docs + version bump

- Move respondent categories from "Planned layouts" / "Patterns and
  modes" into live reference sections in
  `docs/survey-layouts-technical.md` and `docs/survey-layouts.md`.
- Update `docs/import.md` with the `CATEGORIES` block grammar.
- Update `docs/README.md` index if needed.
- Bump `pyproject.toml` version: `0.19.10` → `0.20.0` (minor).
- Run `s/lint`.

## Version

Minor bump (`0.19.10` → `0.20.0`). Respondent categories is a new
feature (new models, new outline grammar, new reporting columns) but
is backward-compatible — existing surveys with no `RespondentCategory`
rows behave exactly as before. Per `docs/versioning-and-deployment.md`,
merging the version bump to `main` triggers the container publish
workflow with versioned tags.

## UI surfacing

Based on the existing layout patterns (RCT arms panel, Delphi rounds
panel, section_menu picker):

- **Organise page:** a "Categories" panel (like the RCT arms panel)
  where the author adds dimensions (free-text name + label), types
  allowed values as a comma-separated list, and picks a resolution
  source per dimension. For `self_select`, points at the question
  whose answer populates the dimension.
- **Section tagging:** on each group card in the organise page, a
  "Visible to" control per dimension (multi-select of allowed values,
  or "everyone"). Groups with no tag are visible to all. This is the
  `required_categories` authoring surface.
- **Token batch generation:** when creating a batch, a "Category values
  for this batch" field (e.g. `rater_role = peer`). Written to
  `SurveyAccessToken.category_values` for every token in the batch.
- **Take page:** the participant sees nothing category-related — they
  just get their filtered question set. No picker (unlike
  section_menu). If resolution is `self_select`, the self-select
  question is a normal question they answer; the filter applies from
  the next page render onward.
- **Preview:** a "Simulate category" panel (like "Simulate section
  selection") with a dropdown per dimension.
- **Survey Map:** shows dimensions and `~ cat:` annotations on
  sections.
- **Reporting/analytics:** a "Group by" dropdown listing each
  dimension; CSV export gains a column per dimension.

## Resolved decisions

1. **`allowed_values` UX — free-text.** The author types allowed
   values as a comma-separated list. No preset library for the first
   release; add presets later if adoption data warrants it. The model
   stays author-defined either way.
2. **`subject` dimension — category dimension, not a dedicated
   field.** The 360 template uses a `subject` `RespondentCategory`
   dimension (values resolved from a self-select question or token).
   This keeps cross-rater aggregation in the existing reporting
   mechanism (group-by dimension) rather than a single-purpose
   `subject_ref` field. Revisit if reporting ergonomics need a
   dedicated field.
3. **Race window on system assignment — accepted for first PR.**
   The RCT allocator (`_assign_arm_for_progress`) counts existing
   assignments (`allocation_count`) to pick the next value, then
   writes the assignment. If two participants hit first-access
   simultaneously, both read the same count before either writes, so
   both can be assigned the same value — breaking a balanced block.
   `system`-resolved categories inherit this because they reuse the
   same allocator. This is a known limitation the RCT docs already
   flag as acceptable for the first PR; a follow-up can serialise
   allocation under `select_for_update` or a per-survey allocation
   counter. Not a new problem — just the same one inherited from the
   allocator being reused.
4. **Question-level `required_categories` — group-level first.** The
   model includes `required_categories` on both `QuestionGroup` and
   `SurveyQuestion` (per the docs), but the runtime hook initially
   only filters at group level. Most use cases (including 360) are
   section-level; question-level filtering adds complexity for little
   gain. Add question-level runtime filtering only if a concrete need
   emerges.
5. **Language — independent axis via the translation model, not a
   category dimension.** The NHS 360 use case needs multiple languages
   *per rater type* (a peer may be English or Welsh; a patient may be
   English or Welsh), with language independent of rater role. This
   is **not** the content-variant problem (rater_role=peer → English
   text, rater_role=patient → Welsh text within one Survey row).
   The questions are the same; only the text is translated — which is
   exactly what the translation model already does. So language stays
   on `translation_group` (content) and `rater_role` lives on
   categories (visibility); the two are orthogonal and compose:
   an English 360 + a Welsh 360, each with its own `rater_role`
   categories, linked by `translation_group`. No `content_variants`,
   no survey variant layer.
   - **Take-time language routing** is the one gap. Today each
     translation is a separate `Survey` with its own URL. Two options:
     1. Per-language token batches (zero new code): English peer
        tokens → English survey URL; Welsh patient tokens → Welsh
        survey URL. Works today but the organiser manages language
        per batch.
     2. Take-time language picker (small addition): one token for the
        360; the participant picks language; the take view redirects
        to the right `translation_group` Survey row, preserving
        token/category context. Cleaner for the "patient may speak
        either language" case.
     Suggest option 1 for the first release, option 2 as a small
     follow-up if per-language token overhead is a pain point.
   - **Cross-language `subject` aggregation** is the real cost: a 360
     report for one subject rated by English-speaking peers and
     Welsh-speaking patients joins across `translation_group` Survey
     rows. Reporting concern (join on subject ref across the group),
     not a data model blocker. Report per-language for the first
     release; add cross-language aggregation when the use case lands.

## Open questions

1. **Take-time language picker vs per-language token batches** —
   whether the first release ships the picker or relies on
   per-language token batches. Suggest per-language batches first
   (no new code), picker as a follow-up.
2. **Cross-language `subject` aggregation** — join across
   `translation_group` Survey rows for a unified 360 report. Not
   needed for the first release (report per-language); revisit when
   an international 360 use case lands.

## Related documentation

- [Survey Layouts (Technical)](survey-layouts-technical.md) — §Planned
  layouts / §Patterns and modes (to be updated in commit 10).
- [Survey Layouts](survey-layouts.md) — §Planned layouts / §Patterns
  and modes (to be updated in commit 10).
- [Outline (import)](import.md) — bulk-upload grammar (to be updated
  in commit 10).
- [Versioning and Deployment](versioning-and-deployment.md) —
  version bump and publish policy.
