---
title: Reporting and Exports
category: features
priority: 8
---

This guide covers the reporting features available for survey administrators, including the dashboard insights and CSV export functionality.

## Dashboard Response Insights

The survey dashboard displays response insights with visual distribution charts for multiple-choice questions.

### Accessing the Dashboard

Navigate to your survey and click "Dashboard" from the survey menu. The dashboard shows:

- **Total responses** - Count of all submitted responses
- **Today's submissions** - Responses received today
- **Last 7 days** - Responses in the past week
- **Sparkline chart** - Visual trend of submissions over time
- **Response Insights** - Answer distribution charts

### Response Insights Features

The Response Insights section displays horizontal bar charts showing how respondents answered each question. This section automatically appears once your survey has responses.

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

**Note:** Text and numeric questions are excluded from distribution charts as they contain free-form responses that cannot be meaningfully aggregated.

### Future Enhancements

The insights system is designed for easy upgrade to JavaScript charting libraries like Plotly. The template includes data attributes containing chart data in JSON format for future interactive visualisation.

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

**Future enhancement**: Date range filtering is planned to allow exporting subsets of responses for large datasets.

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

### Export Access

The CSV export (`/surveys/{slug}/export.csv`) requires:

- User must be logged in
- User must be the survey owner
- Survey must be unlocked (encryption key in session)

Rate limit: 30 requests per hour per user.

---

## Troubleshooting

### "Unlock survey first" error on export

You need to unlock the survey before exporting. Go to the survey responses page and enter your password or recovery phrase.

### Missing questions in export

Only questions that have been added to the survey will appear. Questions added after responses were submitted will show empty values for earlier responses.

### Response Insights not showing

Response Insights only appear if:

- The survey has at least one response
- The survey has chartable questions (not just text fields)

### Rate limit exceeded

If you see a rate limit error, wait an hour before trying again. If you need more frequent access, consider using the API for read-only data (note: API does not provide decrypted data).
