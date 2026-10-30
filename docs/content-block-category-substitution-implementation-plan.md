---
title: Content Block Category Substitution — Implementation Plan
category: development
priority: 19
---

Implementation plan for **`{{<dimension>}}` placeholder substitution in content
blocks** (#349): an author writes `heading: 360° feedback for {{subject}}` and
each participant sees the heading with their resolved category values
substituted at render time. First consumer is the 360° pattern; the mechanism
is generic (`{{site}}`, `{{cohort}}`, `{{rater_role}}` all work).

Builds entirely on respondent categories (v0.20,
[respondent-categories-implementation-plan.md](respondent-categories-implementation-plan.md)).
**No schema change** — substitution happens in
`_annotate_question_render_sequence`, which already annotates
`content_block_heading` / `content_block_subtitle` / `content_block_html`.

## Resolved decisions (issue #349 §Design decisions)

1. **Roster select, not free text (release 1).** The batch form's existing
   `<select>` over the dimension's `allowed_values` (`tokens.html`, fed by
   `survey_tokens` POST reading `category_<dim>`) is the roster — zero backend
   change. Free text would let a typo silently split a subject into two
   reporting groups. A "free-text dimension" flag for large rotating rosters
   is a follow-up issue.
2. **Batch-level subject.** Matches how 360s are run (cohorts invited per
   subject) and the shipped model: `survey_tokens` writes one
   `category_values` dict per batch. A per-token override needs a token-edit
   surface — defer.
3. **Retention / DSR: category values are response metadata.** Subject names
   are staff data, not patient data, but still personal data. They persist in
   `SurveyAccessToken.category_values` (survey-scoped; swept by survey
   deletion / retention), `RespondentAssignment` (cascades with
   `SurveyProgress` — covered by `test_respondent_categories_models`), and
   the `category_*` columns of the response and token CSV exports. Add a line
   to `docs/compliance/data-subject-request-procedure.md` noting: (a) these
   columns are included in access exports, (b) a rater's erasure removes the
   response and its assignments, but token-borne values remain on the token
   row until the survey's retention sweep — the DSR doc must say so.
4. **Thank-you page: echo yes.** The resolved values are the rater's own
   context. Stash them in the session at submission
   (`category_values_<slug>`, same one-time pattern as
   `receipt_token_<slug>`), pop in `survey_thank_you`, render as small badges
   next to the receipt token, auto-escaped.

## Edge cases (from the #349 design conversation)

1. **Delphi inter-round feedback.** Substitution applies to author-written
   text only — `heading` / `subtitle` / authored `body_md`. The
   system-generated feedback body (`is_delphi_feedback` branch of the
   annotator, `_render_delphi_feedback_summary`) is **not** substituted; it is
   already context-specific.
2. **Outline export/import round-trip.** `{{subject}}` in `body_md` /
   `heading:` must survive export → import as literal text. Add a round-trip
   test next to `test_export_content_block_round_trip`
   (`test_content_block.py`). Placeholders belong in the `heading:` /
   `subtitle:` config lines and the body — not the internal label, where
   `## Name {slug}` braces could be misparsed as a slug.
3. **Anonymous / no-progress renders.** No `SurveyProgress` → no
   `RespondentAssignment` rows → placeholders render **empty** on the live
   path (same semantics as visibility rules: unresolved = not shown). The
   preview path uses the `?simulate_category=` values; the Simulate category
   panel is the documented way to see substituted values. Add a one-line
   hint to the panel when any content block contains a placeholder, so the
   author is never shown a bare `{{subject}}` with no explanation.

## Substitution contract

- **Syntax:** `{{<dimension>}}` in `options.heading`, `options.subtitle`,
  `options.body_md` of `content_block` questions. Nothing else substitutes
  (link labels, consent statements, `question.text` — follow-ups if asked
  for).
- **Resolution per path:**
  - Live (`_handle_participant_submission`): the map already computed by
    `_resolve_categories_for_progress` (hoist the local so the annotator
    sees it); `{}` when there is no progress or no categories.
  - Preview (`survey_preview`): the parsed `?simulate_category=` values
    (`sim_values`); `{}` when absent.
  - Builder detail (`survey_detail`): no substitution — the author sees the
    raw placeholder, exactly as typed.
- **Rules:**
  - Unknown dimension (not defined on the survey): left literal —
    `{{subjekt}}` renders visibly so the author catches it in preview,
    `|default:` segment included (the fallback never masks a typo).
  - Known but unresolved: the optional `{{dim|default:<text>}}`
    fallback when present (issue #351), else an empty string.
  - Escaping: `heading` / `subtitle` substitute as plain strings and rely on
    template auto-escaping (`detail.html` emits them unmarked). `body_md`
    substitutes **after** `render_content_block_markdown`, inserting
    `html.escape(value, quote=True)` into the sanitised HTML — never through
    `|safe` unescaped. Post-sanitisation insertion is safe because the
    inserted text is entity-escaped and cannot form tags or attributes.
  - Placeholders inside code spans / link labels also substitute (harmless,
    escaped).
- **Plumbing:** new optional kwarg —
  `_annotate_question_render_sequence(survey, questions, category_values=None)`.
  `None` = no substitution (builder); a dict = substitute. New pure helper
  `_substitute_category_placeholders(text, category_values, known_dims, *,
  escape_values)` next to the annotator, unit-tested in isolation. Known
  dimension names come from `survey.respondent_categories` (fetched once per
  annotator call when a content block is present).

  The `|default:` fallback (issue #351) is authored source text, not
  participant data: it substitutes as typed on the plain-text fields
  (template auto-escaping applies) and as-rendered on the `body_md` path —
  markdown has already escaped and sanitised it with the body, so it is
  never re-escaped. `_CATEGORY_PLACEHOLDER_RE` captures the optional
  `|default:...` segment (no `}` allowed in the fallback text).

## Commit plan

Each commit is self-contained: code + tests + the doc line it implements.

1. **Helper + annotator + live path.** The kwarg, the helper, hoisting
   `resolved` in `_handle_participant_submission`. Tests
   (`test_content_block_substitution.py`): walkthrough (author defines
   roster → content block with `{{subject}}` → token batch → take → heading
   contains the name); unresolved → empty; unknown placeholder left
   literal; value with `<`, `>`, `&`, `"` escaped in output; Delphi feedback
   body not substituted; outline round-trip with `{{subject}}` (added next
   to `test_export_content_block_round_trip`).
2. **Preview path.** Pass `sim_values` to the annotator; hint line in the
   Simulate category panel when a content block contains a placeholder.
   Tests: simulate shows the substituted heading; without simulate → empty;
   hint present.
3. **Thank-you echo.** Session snapshot + badges next to the receipt token.
   Tests: echoed after submit; absent on direct GET; auto-escaped.
4. **Docs + version bump.** `survey-layouts-technical.md` §Content blocks
   (this contract) and §360 pattern; `publish-and-collection.md` token-batch
   category step; the DSR procedure line (decision 3); mark this plan's
   decisions resolved. Bump `0.20.2` → `0.21.0` (minor — new
   participant-facing feature, backward-compatible). Run `s/lint`.

## Out of scope (follow-ups)

- ~~Per-block default text for unresolved dimensions
  (e.g. `{{subject|default:your colleague}}`)~~ — shipped in issue #351
  (`_CATEGORY_PLACEHOLDER_RE` captures the optional `|default:` segment;
  see §Substitution contract).
- Substitution in link labels and consent statements.
- Free-text dimension values (large rotating rosters).
- Token-level subject override; "Generate full 360 set for a subject" batch
  action; Tokens page grouping by subject (already parked in #349).
