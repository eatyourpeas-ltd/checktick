## Data Export Notification

Hi **{{ recipient_name }}**,

A data export has been created for survey **"{{ survey.name }}"**.

### Export Details

- **Survey:** {{ survey.name }}
- **Exported by:** {{ export_user.username }} ({{ export_user.email }})
- **Export time:** {{ export_time }}
- **Response count:** {{ export.response_count }}
- **Download expires:** {{ expiry_time }}

### Audit Information

- **Export ID:** {{ export.id }}
- **User IP:** {% if export.downloaded_from_ip %}{{ export.downloaded_from_ip }}{% else %}Not yet downloaded{% endif %}
- **Password protected:** {% if export.is_encrypted %}Yes{% else %}No{% endif %}

### Why am I receiving this?

As an organisation administrator, you receive notifications for all data exports to maintain oversight and ensure compliance with data protection policies.

### What to do

This is an informational notice. No action is required unless:

- You don't recognize the user who exported the data
- The export was unexpected or unauthorized
- You have concerns about data security

If you have concerns, contact your organisation's data protection officer or the user who created the export.

### Data Protection Reminders

Users who download data are responsible for:

- Storing exports securely (encrypted, password-protected)
- Not sharing data inappropriately
- Deleting local copies when no longer needed
- Reporting any data breaches

### Quick Links

- [View Survey Dashboard]({{ site_url }}/surveys/{{ survey.slug }}/dashboard/)
- [Data Governance Policy]({{ site_url }}/docs/data-governance-overview/)

---

**This is an automated audit notification.** Do not reply to this email.

The {{ brand_title }} Team
