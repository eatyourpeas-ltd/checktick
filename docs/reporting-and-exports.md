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

The Summary Report is a printable, in-session report covering every question in document order — not just the chartable slice shown on the dashboard. It is the recommended way to hand a stakeholder a single document summarising a survey's responses.

### Accessing the Summary Report

Navigate to `Surveys → {your survey} → Summary` (or `/surveys/{slug}/summary/`). The Summary Report shows:

- **Chartable questions** — the same horizontal bar charts as the dashboard, with a "Copy data" button per chart that serialises the underlying distribution to CSV on the clipboard.
- **Numeric questions** — a summary statistics table (count, min, max, mean, median, sum, standard deviation).
- **Text / textarea questions** — a collated list of responses (each truncated to ~500 characters), a client-side word cloud (frequency-weighted, no LLM), and an opt-in "Summarise themes" button that uses the self-hosted RCPCH Ollama instance to paraphrase the recurring themes (see below).

### Date Range

The Summary Report accepts `?from=YYYY-MM-DD&to=YYYY-MM-DD` query parameters, applied to `submitted_at`. The `to` bound is inclusive through the end of that day. The same date range is forwarded to the LLM theme endpoint when you click "Summarise themes", so the theme summary covers the same responses you see on screen.

### Print / Save as PDF

The Summary Report is designed to be printed or saved as PDF directly from the browser. Click "Print / Save as PDF" to open the browser print dialog. The print stylesheet hides the on-screen chrome (date filter, copy buttons, theme buttons) and keeps one question per section so the printed document is keyboard-navigable and screen-reader-friendly before printing. No server-side PDF library is involved.

### Copy Data

Each chart card and the numeric summary card have a "Copy data" button that copies the underlying data to the clipboard as CSV (charts) or JSON (numeric summary). This uses `navigator.clipboard.writeText` with a legacy `execCommand` fallback — no third-party library.

### Word Cloud

The word cloud is a frequency-weighted visualisation computed server-side as a `Counter` over tokenised free text (case-folded, stop-word filtered, minimum length 3 characters) and shipped to the template as a JSON payload. It is rendered client-side by `summary-charts.js`. No LLM is involved.

### LLM Theme Analysis (opt-in, per question)

Free-text theme summarisation uses the self-hosted RCPCH Ollama instance documented in `docs/llm-security.md`. It is:

- **Opt-in**: a "Summarise themes" button per text question, never automatic.
- **Unlock-gated**: only decrypted content is sent to the LLM, and only to authorised users (the same access control as the dashboard).
- **Per-question**: bounded token volume, one question at a time.
- **Non-persistent alongside patient data**: theme output is session-scoped. It is never written back into `enc_answers`.
- **Sanitised**: the LLM output is passed through the existing `sanitize_markdown()` pipeline before being rendered, and the client renders it as preformatted text (no `innerHTML` of raw markdown).
- **Separately rate-limited**: 20 requests per hour per user (LLM calls are expensive); the summary view itself is 100/h.
- **Audited with metadata only**: the audit log entry records the question id, response count, token count, model name, duration, and success/failure. It never records the free-text input or the LLM output verbatim, per the medical-app logging rules in `AGENTS.md`.
- **Graceful degradation**: if Ollama is unavailable or LLM features are disabled on the instance, the button returns a clear message and the plain collation + word cloud still work.

**Residual risk — identifiable content:** Even surveys without a `patient_details_encrypted` group can collect free-text responses that contain names, postcodes, or clinician identifiers ("I see Dr X at…"). The unlock gate handles authorisation but not content safety. A brief warning is shown above the theme buttons: *"Responses may contain identifiable content — review the summary before sharing it."* Automated redaction is explicitly out of scope for v1 (unreliable). See `docs/reporting-planning.md` §6 for the full risk discussion.

### Access Control

The Summary Report (`/surveys/{slug}/summary/`) requires:

- User must be logged in
- User must have view permission for the survey:
  - Survey owner
  - Organisation admin
  - Survey member (viewer, editor, or creator role)
- Unlock required when any response has `enc_answers` set

Rate limit: 100 requests per hour per user (view); 20 requests per hour per user (theme analysis).

### Out of Scope (v1)

The following are intentionally not in the first iteration of the Summary Report:

- **Cross-survey aggregation** — the summary is per-survey.
- **Demographics / IMD / professional fields** — those stay in the CSV export only, as today. The Summary Report never surfaces demographic fields even for surveys with `patient_details_encrypted`.
- **Server-side PDF generation** — print CSS only.
- **Automated redaction** of free text before LLM summarisation — a user-facing warning is used instead.
- **Persisted LLM theme artefacts** — theme summaries are session-scoped only for v1.

See `docs/reporting-planning.md` for the full planning record and design rationale.

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
