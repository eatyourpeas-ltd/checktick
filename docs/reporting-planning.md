---
title: Reporting and Summary Feature Planning
category: features
priority: 8
status: planning
---

# Reporting and Summary Feature Planning

This document is a planning record for the reporting work. It captures the
current state of reporting in CheckTick, the gap, the agreed scope for the
first iteration, and the design decisions behind it (including the LLM theme
analysis feature).

It is intended to be consumed alongside:

- `docs/reporting-and-exports.md` — the existing user-facing reporting doc
  (which will be rewritten as part of this work; see §8).
- `docs/llm-security.md` — the LLM security posture that governs the theme
  analysis feature.
- the encrypt-all-responses security upgrade (now implemented — see
  `docs/encryption-technical-reference.md`).

## 1. Current state

Reporting today consists of two things:

1. **Dashboard response counts** — total, today, last 7 days, a 14-day
   sparkline. Rendered on the survey dashboard.
2. **CSV export** — full per-response export, re-encrypted with a
   user-provided password, time-limited download link, audit-logged. See
   `docs/reporting-and-exports.md` and `docs/data-governance-export.md`.

There is also a **`response_analytics.py` service** that computes
`AnswerDistribution` (count + percentage per option) for chartable question
types (`mc_single`, `mc_multi`, `yesno`, `likert`, `dropdown`). The service
is called from `survey_dashboard` and the result is placed in the template
context as `analytics`.

**Important: the analytics rendering layer does not exist.** No template
under `checktick_app/surveys/templates/` references `analytics`,
`distribution`, `insights`, or `options_json`. The "Response Insights"
section of `docs/reporting-and-exports.md` describes a UI (bar charts, ARIA
attributes, hover truncation) that is not present in the codebase. The
service is sound; the template was never written.

## 2. The gap

- **Free-text responses** are never summarised in-product; users must export
  to see them.
- **Numeric questions** have no summary statistics (mean/median/min/max/n).
- **Chartable question distributions** are computed but not rendered.
- There is no **shareable / printable summary** — the dashboard is
  interactive but not a "report" you can hand to a stakeholder.
- There is no **date-range scoping** on any analytics or export (the docs
  flag this as a planned enhancement for exports).

## 3. Design principles

These principles are non-negotiable for the first iteration.

### 3.1 Encryption posture

The summary must work for **both** plaintext and encrypted surveys by
calling `SurveyResponse.load_answers(survey_key)`, which already falls back
to the plaintext `answers` field when `enc_answers` is not set.

The summary view is **unlock-gated whenever any response in the survey has
`enc_answers` set**. With the encrypt-all-responses upgrade implemented
(see `docs/encryption-technical-reference.md`), this means
unlock-gated for:

- all patient-data surveys (existing behaviour, unchanged);
- all patient / public audience surveys (new — audience-based);
- all SSO-owned surveys (new — default-on for SSO).

The only surveys that remain plaintext under the upgraded posture are
staff-audience, password-user surveys without patient identifiers, where
the creator has made an explicit logged opt-out declaration. For those
surveys only, the summary is available without unlock, matching the
existing `load_answers` fallback behaviour.

For surveys with no encrypted responses (draft / legacy / opted-out
surveys), the summary is available without unlock. This avoids a hard
failure on test data and preserves the narrow opt-out path.

### 3.2 No new download / re-encryption flow

The summary is **view-only, in-session, behind unlock**. There is no
re-encrypted-download artefact like the CSV export. Users who want to take
data away use:

- **Print → Save as PDF** (print CSS, no server-side PDF library).
- **Copy data to clipboard** per chart (CSV/TSV of the underlying numbers).
- The existing **CSV export** for the raw responses.

This keeps the security surface area unchanged: no new encrypted blobs, no
new download tokens, no new expiry logic.

### 3.3 LLM theme analysis is opt-in, per-question, gated

Free-text theme summarisation uses the self-hosted RCPCH Ollama instance
documented in `docs/llm-security.md` §6. It is:

- **Opt-in**: a "Summarise themes" button per text question, never
  automatic.
- **Unlock-gated**: only decrypted content is ever sent to the LLM, and
  only to authorised users.
- **Per-question**: bounded token volume, one question at a time.
- **Non-persistent alongside patient data**: theme output is session-scoped
  or stored as a short derived text blob, never written back into
  `enc_answers`.
- **Sanitised** through the existing `sanitize_markdown()` pipeline before
  rendering.
- **Separately rate-limited** from the view rate limit (LLM calls are
  expensive).
- **Audited** with metadata only (question id, token count, success /
  failure) — never the free-text input or the LLM output verbatim, per the
  medical-app logging rules in `AGENTS.md`.
- **Graceful degradation**: if Ollama is unavailable or the user's tier does
  not include LLM features, plain collation + word cloud still work.

### 3.4 Word cloud is client-side, no LLM

The word cloud is a frequency-weighted visualisation computed server-side
as a `Counter` over tokenised text (case-folded, stop-word filtered,
min-length threshold) and shipped to the template as JSON. Rendered
client-side via the existing CDN asset pipeline. No LLM involved.

### 3.5 Accessibility

The summary view targets **WCAG 2.2 AA**, consistent with the rest of the
application (see `docs/accessibility.md`). Charts use the existing ARIA
progress-bar pattern; the print layout must remain keyboard-navigable and
screen-reader-friendly before printing.

## 4. Scope — first iteration

### 4.1 Service layer (`response_analytics.py`)

Keep the existing `AnswerDistribution` for chartable types. Add:

- **`TextCollation`** — for `text` / `textarea` questions:
  - list of responses (truncated to ~500 chars each)
  - answered count, skipped count
  - tokenised word-frequency list for the word cloud
- **`NumericSummary`** — for `number` questions:
  - count, min, max, mean, median, sum, stdev
  - pure Python, no patient data leaves the DB layer
- **`LLMThemeSummary`** — lazy; only populated when the user requests it
  per question (separate endpoint, see §4.2).

All compute functions accept a `responses` queryset so date-range filtering
is applied upstream.

### 4.2 View layer (`views.py`)

- **`survey_summary`** — `GET /surveys/{slug}/summary/`
  - Access: owner / organisation admin / view-permission members (same as
    dashboard).
  - Unlock-gated when any response has `enc_answers` set.
  - Date-range query params `?from=&to=` (ISO date; applied to
    `submitted_at`).
  - Rate limit: 100 requests per hour per user (view).
  - Audit-logged.
- **`survey_summary_themes`** — `POST /surveys/{slug}/summary/themes/`
  - Per-question LLM theme summarisation.
  - Same access + unlock gate.
  - Separate rate limit (e.g. 20 requests per hour per user).
  - Audit-logged with metadata only.
  - Returns sanitised markdown.

The existing `survey_dashboard` analytics call should also be updated to
accept the date-range queryset, for consistency. The dashboard insights
template (currently missing — see §5) should be backfilled as part of this
work since it shares the rendering primitives with the summary view.

### 4.3 Template layer

- **`surveys/summary.html`** — renders all question types in document
  order (not just the chartable slice of 10):
  - chartable: bar chart (reuse the missing dashboard insights component)
  - numeric: summary stats table
  - text: collated list + word cloud + "Summarise themes" button
  - printable via `@media print` stylesheet (one question per page,
    chrome hidden)
- **Chart cards** with "Copy data" buttons — small JS module in
  `checktick_app/static/js/` using `navigator.clipboard.writeText` to
  serialise a chart's underlying data to CSV/TSV. No library.
- **Word cloud** — client-side render from JSON payload.
- **`surveys/_insights.html`** — the missing dashboard insights partial
  that renders the existing `analytics` context variable. Shared between
  dashboard and summary.

### 4.4 Out of scope (first iteration)

- **Cross-survey aggregation** — keep per-survey.
- **Demographics / IMD / professional fields in the summary** — those stay
  in the CSV export only, as today.
- **Server-side PDF generation** — print CSS only.
- **Automated redaction** of free text before LLM summarisation —
  unreliable; a user-facing warning is used instead (see §6).
- **Persisted LLM theme artefacts** — session-scoped only for v1.

## 5. Dashboard insights dead code

The existing `compute_response_analytics` call in `survey_dashboard`
places `analytics` in the context, but no template consumes it. As part of
this work we will backfill `surveys/_insights.html` and include it from
the dashboard template. This is in scope because:

- It shares the rendering primitives with the summary view.
- The service is already written and tested.
- Leaving dead code in the context variable is worse than either shipping
  it or removing it; shipping is the lower-risk option.

If, on review, the dashboard insights are deemed out of scope for this PR,
the alternative is to **remove** the `analytics` context variable and the
"Response Insights" doc section until they ship together. Do not leave the
dead context variable in place.

## 6. LLM theme analysis — residual risks

The self-hosted Ollama posture in `docs/llm-security.md` §6 addresses the
main privacy objections (no third-party commercial AI, NHS data protection
standards, not used for training). Two residual risks remain:

1. **Incidental identifiable content in non-patient surveys.** Even
   surveys without a `patient_details_encrypted` group can collect
   free-text responses that contain names, postcodes, or clinician
   identifiers ("I see Dr X at…"). The unlock gate handles authorisation
   but not content safety. Mitigation: a brief user-facing warning on the
   "Summarise themes" button — *"Responses may contain identifiable
   content — review the summary before sharing it."* Automated redaction
   is explicitly out of scope for v1 (unreliable).

2. **LLM output logging.** The medical-app logging rules in `AGENTS.md`
   prohibit logging patient data or decrypted survey objects. LLM inputs
   are decrypted free text; LLM outputs may paraphrase identifiable
   content. Both must be treated as sensitive. Audit log entries record
   metadata only: question id, response count, token count, model name,
   success / failure, duration. Never the input or output text.

These risks are accepted for v1 given the self-hosted posture and the
opt-in / per-question / gated design. They should be revisited if the LLM
provider ever changes from self-hosted Ollama to a third party.

## 7. Testing

Tests in `checktick_app/surveys/tests/`:

- **Unlock gate**: summary view requires unlock when any response has
  `enc_answers`; accessible without unlock for plaintext-only surveys.
- **Access control matrix**: owner / org admin / viewer / editor / non-member.
- **Text collation**: truncation at 500 chars; skipped count; word
  frequency correctness (case-fold, stop words, min length).
- **Numeric stats**: mean / median / stdev correctness against known
  inputs; empty-answer handling; non-numeric input rejection.
- **Date-range filter**: `?from=` / `?to=` applied to `submitted_at`;
  boundary inclusivity; invalid date format handling.
- **LLM theme endpoint**: mocked Ollama client; sanitisation applied to
  output; rate limit enforced; audit log entry contains metadata only
  (assert no input/output text in log); unlock required; graceful
  degradation when Ollama is unreachable.
- **Copy-data endpoint / JS**: clipboard payload is valid CSV; chart data
  matches the rendered distribution.
- **Print layout**: smoke test that the print stylesheet does not hide
  content required for accessibility (axe-core against the print DOM is
  out of scope; manual review documented in the PR).
- **Demographics never appear** in the summary output (assert against a
  survey with `patient_details_encrypted`).

Accessibility tests (`tests/test_accessibility.py`) should cover the
summary view with the `wcag22aa` tag set.

## 8. Documentation changes

As part of this work:

- **Rewrite `docs/reporting-and-exports.md`** to reflect reality:
  - Remove the false claim that dashboard insights are already rendered.
  - Add a "Summary Report" section covering the new view, date ranges,
    print/PDF, copy-data, word cloud, and LLM theme analysis.
  - Document the LLM theme feature with its guardrails and the
    self-hosted Ollama dependency, cross-linking `docs/llm-security.md`.
- **Do not** change the encryption wording in `docs/security-overview.md`
  or `docs/reporting-and-exports.md` as part of this PR. The
  encrypt-all-responses change is already implemented (see
  `docs/encryption-technical-reference.md`); the
  reporting docs assume whatever posture is current at merge time and
  describe the unlock gate in terms of "when any response is encrypted".

## 9. Ordering

The reporting PR depends on the security-upgrade PR being merged first,
because:

- The unlock-gate logic is simpler to reason about once the encryption
  predicate (Option C: schema OR audience OR SSO) is in place. The
  reporting view's unlock check is "any response has `enc_answers`", which
  is correct regardless of posture, but the LLM theme feature's security
  argument is stronger once patient / public audience surveys are
  universally encrypted.
- The LLM theme feature sends decrypted free text to Ollama; doing this
  before the audience-based encryption predicate lands would create a
  window where patient-facing free-text surveys (no patient-identifier
  group, anonymous-by-design) are decrypted in-session for LLM analysis
  but stored in plaintext at rest — an inconsistent posture for exactly
  the surveys the audience field is designed to protect.

If the security-upgrade PR is delayed, the reporting PR can proceed with
the conditional unlock gate (§3.1) and be merged independently, but the
LLM theme feature should be feature-flagged off until the security-upgrade
PR lands, specifically until the `respondent_audience` field and the
Option C predicate are in place.

## 10. Open questions

- **LLM feature tiering**: is the LLM theme feature available to all
  tiers, or gated to Pro / Team / Organisation? The existing LLM features
  (survey generation, translation) are tier-gated; theme analysis should
  follow the same policy. Confirm with billing.
- **Word cloud library**: ship a small vendored JS lib via the CDN asset
  pipeline (`checktick_app/cdn_assets.json`), or implement in pure
  inline SVG / CSS? The latter avoids a new dependency but is more
  rendering work. Recommend vendoring a small, SRI-pinned lib for v1.
- **Theme summary persistence**: v1 is session-scoped. Is there a future
  need to persist theme summaries as a derived artefact (e.g. for
  comparison across date ranges)? If so, design the storage now to avoid
  a migration later. Recommend deferring — v1 session-scoped.
- **LLM on opted-out surveys**: the LLM theme feature requires unlock
  (decrypted free text). For staff-audience password-user surveys that
  have opted out of encryption (plaintext at rest), should the LLM theme
  feature still be available? The data is already plaintext, so sending
  it to Ollama is not a new exposure — but it is a new egress path for
  data that the creator declared non-identifying. Recommend allowing it
  (the creator declared the data non-identifying; the LLM is
  self-hosted), but with the same per-question opt-in and metadata-only
  audit logging as encrypted surveys. Confirm.
