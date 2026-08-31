---
title: Reporting and Exports
category: features
priority: 8
---

This guide covers the reporting features available for survey administrators: the dashboard response insights, the summary report view, and the CSV export.

## Dashboard Response Insights

The survey dashboard displays response insights with visual distribution charts for chartable question types (Yes/No, single choice, multiple choice, dropdown, Likert). The insights are unlock-gated: when a survey has encrypted responses, you must unlock the survey before the distribution charts render. Counts and the submission sparkline use metadata only and render without unlock.

### Accessing the Dashboard

Navigate to your survey and click "Dashboard" from the survey menu. The dashboard shows:

- **Total responses** - Count of all submitted responses
- **Today's submissions** - Responses received today
- **Last 7 days** - Responses in the past week
- **Sparkline chart** - Visual trend of submissions over time
- **Response Insights** - Answer distribution charts for chartable questions

### Response Insights Features

The Response Insights section displays horizontal bar charts showing how respondents answered each chartable question. This section automatically appears once your survey has responses to chartable questions.

**Supported question types:**

- Yes/No questions (with colour-coded bars)
- Single choice (radio buttons)
- Multiple choice (checkboxes)
- Dropdown selections
- Likert scales

**Accessibility features:**

- Fully keyboard accessible (uses native `<details>` element)
- ARIA attributes on progress bars for screen readers
- Truncated labels show full text on hover
- High contrast colour scheme

**Note:** Text and numeric questions are excluded from the dashboard distribution charts because they contain free-form responses. They are covered by the Summary Report (see below), which collates text responses and computes numeric summary statistics.

### Unlock Gate

When any response in the survey has encrypted answers (`enc_answers` set), the dashboard insights are unlock-gated: you must unlock the survey with your encryption password or recovery phrase before the charts render. This avoids decrypting patient data without authentication. Plaintext-only surveys (draft, legacy, or staff-audience surveys with a recorded encryption opt-out) render the insights without unlock.

---

## Summary Report

The Summary Report is a printable, in-session report covering **every** question in your survey in document order — not just the chartable slice shown on the dashboard. It is the recommended way to hand a stakeholder a single document summarising a survey's responses without exporting the raw data.

### What you see in the UI

Navigate to `Surveys → {your survey} → Summary` (or `/surveys/{slug}/summary/`). The report renders one card per question, in the order respondents see them:

- **Chartable questions** (Yes/No, single choice, multiple choice, dropdown, Likert) — the same horizontal bar charts as the dashboard, plus a **"Copy data"** button per chart that copies the underlying distribution to the clipboard as CSV (label, count, percent). Numeric Likert values are also summarised as a chart.
- **Numeric questions** — a compact summary-statistics table: count, min, max, mean, median, sum, and standard deviation. Non-numeric answers are skipped (not coerced) so a stray text value cannot skew the stats. The stats card also has a "Copy data" button that copies the summary as JSON.
- **Text / textarea questions** — three things stacked vertically:
  1. A **word cloud** — a frequency-weighted visualisation of the most common terms in the responses, rendered client-side from a server-computed JSON payload (case-folded, stop-word filtered, minimum 3 characters). No LLM is involved.
  2. A **collated list** of every response to that question, each truncated to ~500 characters, inside a `<details>` element so the page stays scannable. Expand it to read the verbatim responses.
  3. An opt-in **"Summarise themes"** button (see LLM Theme Analysis below) that paraphrases the recurring themes in the responses.

At the top of the page you'll see the survey name, the total response count, any active date-range filter, and a **"Print / Save as PDF"** button. A date-range filter form (`?from=YYYY-MM-DD&to=YYYY-MM-DD`) lets you scope the whole report — and the LLM theme button — to a window of `submitted_at` timestamps. The `to` bound is inclusive through the end of that day.

### Who can see it, and when

The Summary Report is **only viewable by the survey's creator and the people they have explicitly authorised** — the same access control as the dashboard:

- the survey owner (the person who created it),
- organisation admins for organisation-owned surveys,
- survey members the owner has invited as a viewer, editor, or creator.

Nobody else can reach the report. Anonymous visitors are redirected to log in; non-members get a 403.

**When responses are encrypted** (which is the default for any survey collecting patient data, any patient- or public-audience survey, and any survey owned by an SSO user — see `docs/encryption-technical-reference.md`), the report is **unlock-gated**: you must unlock the survey with your encryption password or recovery phrase before any answer content is decrypted and shown. SSO users unlock automatically with their identity. The server holds no key that can decrypt your responses without you — the unlock re-derives the key from your credentials on each request, and it expires after 30 minutes. Until you unlock, the report shows a single "Responses are encrypted" panel with an unlock button and no answer content at all.

For the small set of plaintext-only surveys (draft surveys, legacy surveys, or staff-audience surveys where the creator has made an explicit, audit-logged opt-out declaration), the report renders without unlock — matching the existing `load_answers` behaviour.

### Is it safe for patient data?

Yes — by design. The Summary Report never creates a new copy of your data and never widens who can see it:

- **Same access as the dashboard.** The report uses the exact same permission check (`require_can_view`) and the exact same unlock gate (`get_survey_key_from_session`) as the dashboard you already use. No new role, no new share link, no new download token.
- **In-session only.** The report is rendered on the page; there is no server-side artefact to leak. "Print / Save as PDF" uses the browser's native print dialog and a print stylesheet — no PDF library, no temp file on the server.
- **No demographics in the report.** Even for surveys with a `patient_details_encrypted` group, the Summary Report never surfaces first name, surname, NHS number, date of birth, address, IMD, or professional fields. Those stay in the CSV export only. The report shows answer content only.
- **Copy-data is your data.** The "Copy data" button copies the chart's underlying numbers (labels and counts) to your clipboard — the same numbers rendered in the bars. It does not copy raw response rows.
- **Audit-logged.** Every view of the report is recorded in the audit log with metadata only (survey id, total response count, date range, whether responses were encrypted, whether you unlocked). No answer content is logged, per the medical-app logging rules in `AGENTS.md`.

### Print / Save as PDF

Click "Print / Save as PDF" to open the browser print dialog. The print stylesheet hides the on-screen chrome (date filter, copy buttons, theme buttons, back-to-dashboard link) and keeps one question per section so the printed document is keyboard-navigable and screen-reader-friendly before printing. No server-side PDF library is involved — the output is whatever your browser produces from the print DOM.

### Copy Data

Each chart card and the numeric summary card have a "Copy data" button that copies the underlying data to the clipboard as CSV (charts) or JSON (numeric summary). This uses `navigator.clipboard.writeText` with a legacy `execCommand` fallback for older browsers — no third-party library, no network call.

### Word Cloud

The word cloud is a frequency-weighted visualisation computed **server-side** as a `Counter` over tokenised free text (case-folded, stop-word filtered, minimum length 3 characters, capped at 60 terms) and shipped to the template as a JSON payload. It is rendered client-side by `summary-charts.js`. **No LLM is involved** — the cloud is pure word frequency, so it is safe to compute over decrypted patient free text exactly as the rest of the report is. The terms never leave the server except as the rendered cloud; they are not sent to any external service.

### LLM Theme Analysis (opt-in, per question)

Free-text theme summarisation uses the **self-hosted RCPCH Ollama instance** documented in `docs/llm-security.md` §6. It is the same Ollama instance used for survey generation and translation. The security posture for patient data is:

- **Self-hosted, on RCPCH infrastructure.** The model runs on RCPCH servers. No data is sent to any third-party commercial AI service, and the model is not used for training. See `docs/llm-security.md` §6 for the full data-provenance statement.
- **Only decrypted content is sent, and only to authorised users.** The "Summarise themes" button is unlock-gated exactly like the rest of the report: if the survey is encrypted, the button fails closed with "Unlock the survey first" until you enter your password or recovery phrase (or your SSO identity unlocks it). A non-member or a locked session cannot trigger the LLM call.
- **Per-question, opt-in, never automatic.** You click the button for one text question at a time. The report never sends all free text in one batch; each click is one bounded request for one question's responses.
- **Non-persistent alongside patient data.** The theme summary is session-scoped — it is rendered into the page and never written back into `enc_answers` or any other table. Refreshing the page clears it.
- **Sanitised before render.** The model's output is passed through the existing `sanitize_markdown()` pipeline (strips HTML, script tags, dangerous patterns), and the client renders it as preformatted text — never as `innerHTML` of raw markdown.
- **Separately rate-limited.** The view is 100 requests/hour per user; the theme endpoint is 20 requests/hour per user, because LLM calls are expensive.
- **Audited with metadata only.** The audit log entry records the question id, response count, token count, model name, duration, and success/failure. **It never records the free-text input or the LLM output verbatim**, per the medical-app logging rules in `AGENTS.md`.
- **Graceful degradation.** If Ollama is unavailable, or LLM features are disabled on the instance, the button returns a clear message and the plain collation + word cloud still work — the report is still useful without the LLM.

In short: for a patient-data survey, the LLM theme summary can only be requested by the creator (or an authorised member) who has unlocked the survey with their password or SSO identity, the request goes to a self-hosted model that is not used for training, the output is sanitised and never persisted, and the audit log records only that the call happened — never what was in it.

**Residual risk — identifiable content in free text:** Even surveys without a `patient_details_encrypted` group can collect free-text responses that contain names, postcodes, or clinician identifiers ("I see Dr X at…"). The unlock gate handles authorisation but not content safety: the LLM receives the decrypted free text and may paraphrase identifiable content. A brief warning is shown above the theme buttons: *"Responses may contain identifiable content — review the summary before sharing it."* Automated redaction is explicitly out of scope for v1 (unreliable). Review the generated summary before sharing it onward. See `docs/llm-security.md` §6 for the self-hosted Ollama data-provenance statement that underpins this risk acceptance.

### Access Control

The Summary Report (`/surveys/{slug}/summary/`) requires:

- User must be logged in
- User must have view permission for the survey (owner, organisation admin, or an invited viewer/editor/creator member)
- Unlock required when any response has `enc_answers` set (password, recovery phrase, or SSO identity)

Rate limit: 100 requests per hour per user (view); 20 requests per hour per user (LLM theme analysis).

### Out of Scope (v1)

The following are intentionally not in the first iteration of the Summary Report:

- **Cross-survey aggregation** — the summary is per-survey.
- **Demographics / IMD / professional fields** — those stay in the CSV export only, as today. The Summary Report never surfaces demographic fields even for surveys with `patient_details_encrypted`.
- **Server-side PDF generation** — print CSS only.
- **Automated redaction** of free text before LLM summarisation — a user-facing warning is used instead (unreliable).
- **Persisted LLM theme artefacts** — theme summaries are session-scoped only for v1.

---

## CSV Export

Export your survey responses to CSV format for analysis in spreadsheet applications or statistical software like Excel, Power BI, or SPSS.

### Exporting Responses

1. Navigate to your survey dashboard
2. Click the "Export" button
3. The CSV file will download automatically

### Export Requirements

- **Authentication**: You must be logged in
- **Ownership**: Only the survey owner can export responses
- **Unlock required**: Survey must be unlocked with your password or recovery phrase

This ensures that only authorised users with encryption credentials can access decrypted response data.

### How Encryption Affects Exports

For surveys with patient data encryption enabled, the export process handles encrypted data securely:

**During Export Creation:**

1. Survey must be unlocked (you've entered your password or recovery phrase)
2. The system decrypts survey responses using your unlocked encryption key
3. Decrypted data is written to a CSV file
4. The CSV file itself is then re-encrypted with a download password you provide
5. The encrypted export file is stored temporarily (7 days)

**Security Properties:**

- **Double encryption**: Survey data encrypted → decrypted → re-encrypted for download
- **Separate keys**: Export encryption uses a different password than survey encryption
- **Time-limited access**: Export links expire after 7 days
- **Download protection**: Recipients need the download password to access the CSV
- **Audit trail**: All exports are logged with user, timestamp, and encryption status

**What Gets Decrypted:**

- Patient demographics (first name, last name, NHS number, date of birth, address)
- Survey response answers
- Professional details (if collected)
- Any other encrypted fields in the survey

**What Stays Encrypted:**

- The export file itself remains encrypted until downloaded
- You provide a download password during export creation
- Recipients must have this password to open the CSV file

**Best Practices:**

- Use a strong, unique password for each export
- Share the download password separately from the download link
- Delete exports after downloading if no longer needed
- Don't reuse your survey encryption password for exports

### CSV Structure

The export includes the following columns:

| Column | Description |
|--------|-------------|
| `response_id` | Unique identifier for each response |
| `submitted_at` | Timestamp when the response was submitted |
| `submitter_email` | Email of authenticated submitter (if applicable) |
| Demographics fields | Patient/user demographic data (if configured) |
| IMD data | Index of Multiple Deprivation (if enabled) |
| Professional fields | Professional details (if configured) |
| Question columns | One column per survey question |

### Question Column Format

Questions appear as separate columns with their text as the header (truncated if very long). Answer formats:

| Question Type | Export Format |
|---------------|---------------|
| Text | Plain text answer |
| Yes/No | "yes" or "no" |
| Single choice | Selected option text |
| Multiple choice | Options separated by semicolons (`;`) |
| Orderable | Items in ranked order, separated by semicolons |
| Likert | Numeric value (1-5) |
| Template (patient) | Field names selected |
| Template (professional) | Field names selected |

### Security Considerations

- **No API access for encrypted data**: For security, decrypted response data is only available via the dashboard CSV export, not through the API
- **Rate limited**: Export endpoint is rate-limited to 30 requests per hour to prevent abuse
- **Audit logged**: All exports are recorded in the audit log

### Large Datasets

For surveys with many responses (1,000+), the export uses streaming to avoid memory issues. The download may take longer for very large datasets.

**Future enhancement**: Date range filtering is planned to allow exporting subsets of responses for large datasets. The Summary Report already supports date-range filtering for in-session review.

---

## Access Control

Both the dashboard and export features have comprehensive access controls:

### Dashboard Access

The dashboard (`/surveys/{slug}/dashboard/`) requires:

- User must be logged in
- User must have view permission for the survey:
  - Survey owner
  - Organisation admin
  - Survey member (viewer, editor, or creator role)

Rate limit: 100 requests per hour per user.

### Summary Report Access

The summary report (`/surveys/{slug}/summary/`) requires the same access as the dashboard, plus unlock when any response is encrypted. See the Summary Report section above.

Rate limit: 100 requests per hour per user (view); 20 requests per hour per user (LLM theme analysis).

### Export Access

The CSV export (`/surveys/{slug}/export.csv`) requires:

- User must be logged in
- User must be the survey owner
- Survey must be unlocked (encryption key in session)

Rate limit: 30 requests per hour per user.

---

## Troubleshooting

### "Unlock survey first" error on export or summary

You need to unlock the survey before exporting or viewing the summary report for encrypted surveys. Go to the survey responses page and enter your password or recovery phrase.

### Missing questions in export

Only questions that have been added to the survey will appear. Questions added after responses were submitted will show empty values for earlier responses.

### Response Insights not showing

Response Insights only appear if:

- The survey has at least one response
- The survey has chartable questions (Yes/No, single choice, multiple choice, dropdown, Likert)
- The survey is unlocked (when responses are encrypted)

### Summary Report shows "Responses are encrypted"

The Summary Report is unlock-gated when any response has `enc_answers` set. Unlock the survey with your encryption password or recovery phrase to view the report. Plaintext-only surveys (draft, legacy, or staff-audience surveys with a recorded encryption opt-out) render the summary without unlock.

### Rate limit exceeded

If you see a rate limit error, wait an hour before trying again. The summary view is 100/h; the LLM theme endpoint is 20/h; the CSV export is 30/h. If you need more frequent access to the raw data, use the CSV export.
