# Survey Deletion Cancelled

Good news! The scheduled deletion for survey **"{{ survey.name }}"** has been cancelled.

## Restoration Details

- **Survey:** {{ survey.name }}
- **Cancelled by:** {{ cancelled_by.username }} ({{ cancelled_by.email }})
- **Original deletion date:** {{ deletion_date }}
- **Cancellation date:** {{ cancellation_date }}
- **Action:** Survey restored from soft deletion

## What This Means

Your survey has been restored and is now accessible again. The scheduled deletion has been cancelled.

### Current Status

**Survey is active** - All response data is accessible
**Data exports enabled** - You can download survey data
**No deletion scheduled** - Survey will follow normal retention period

### Important: Retention Period Still Active

{% if survey.deletion_date %}
**Note:** This survey was closed on {{ closure_date }} and has a retention period of {{ survey.retention_months }} months.

- **New deletion date:** {{ survey.deletion_date }}
- **Retention ends:** {{ survey.deletion_date|date:"Y-m-d" }}

You'll receive deletion warnings at the appropriate times (30 days, 7 days, 1 day before deletion).

If you need to keep this data longer, you can extend the retention period from your survey dashboard.
{% else %}
This survey is not currently closed, so no deletion is scheduled.
{% endif %}

## What You Should Do

1. **Review your data needs:** Determine if you still need this survey data
2. **Export if needed:** Download the data if you want a local backup
3. **Consider retention:** If you need longer retention, extend the period now
4. **Document the reason:** Keep records of why deletion was cancelled (for audit purposes)

## Need to Extend Retention?

If you need to keep this data for longer:

1. Go to your [survey dashboard]({{ site_url }}/surveys/{{ survey.slug }}/dashboard/)
2. Click "Extend Retention Period"
3. Provide justification for the extension
4. Maximum total retention: 24 months from closure date

---

## Compliance Reminder

This cancellation has been logged for audit purposes. Ensure you:

- Have a legitimate reason for retaining the data
- Comply with data protection regulations
- Delete data when no longer needed
- Keep records of data retention decisions

For questions about data governance, contact your data protection officer or administrator.

---

**{{ brand_title }}**
{{ site_url }}
