# Retention Period Extended

The retention period for survey **"{{ survey.name }}"** has been extended.

## Extension Details

- **Survey:** {{ survey.name }}
- **Extended by:** {{ extended_by.username }} ({{ extended_by.email }})
- **Previous deletion date:** {{ old_deletion_date }}
- **New deletion date:** {{ new_deletion_date }}
- **Months added:** {{ months_added }}
- **New total retention:** {{ survey.retention_months }} months from closure
- **Extension date:** {{ extension_date }}

## Justification

{{ reason }}

## What This Means

Your survey data will now be retained until **{{ new_deletion_date }}** instead of the original deletion date.

### Updated Timeline

1. **Now - {{ new_deletion_date }}**: Survey data is retained and accessible
   - You can download survey data at any time
   - Data custodians can access responses
   - Further extensions possible (up to 24 months total)

2. **Deletion Warnings**: You'll receive new email notifications
   - 30 days before the new deletion date
   - 7 days before the new deletion date
   - 1 day before the new deletion date

3. **After {{ new_deletion_date }}**: All response data will be permanently deleted
   - Survey structure (questions) will be preserved
   - This action cannot be undone

## Compliance Note

Retention extensions are logged for audit and compliance purposes. Make sure you have:

✅ A legitimate business need for the extension
✅ Documented justification for retaining the data
✅ Approval from appropriate stakeholders (if required)
✅ Compliance with data protection regulations

## Maximum Retention Limit

{% if survey.retention_months >= 24 %}
⚠️ **You have reached the maximum retention period of 24 months.**

You cannot extend retention further. If you need to keep data beyond this period:

1. Export the data before the deletion date
2. Store it securely with appropriate safeguards
3. Take personal responsibility for the data
4. Delete it when no longer needed
   {% else %}
   You can extend retention up to **{{ max_retention_months }}** total months from survey closure.

If you need to extend retention again:

1. Go to your survey dashboard
2. Click "Extend Retention Period"
3. Provide clear justification
4. Maximum total retention: 24 months
   {% endif %}

## Your Responsibilities

Extended retention means extended responsibilities:

- **Justify the need**: Ensure there's a legitimate reason to keep the data
- **Secure the data**: Continue protecting survey responses appropriately
- **Monitor deletions**: Respond to deletion warnings when they arrive
- **Delete when done**: Don't keep data longer than necessary
- **Stay compliant**: Follow all data protection regulations

## Accessing Your Data

To download survey data:

1. [Go to Survey Dashboard]({{ site_url }}/surveys/{{ survey.slug }}/)
2. Click "Download Survey Data"
3. Confirm you're authorized to export data
4. Optionally add password protection
5. Download link expires in 7 days

## Questions?

For questions about retention extensions:

- Review the [Data Governance Overview](/docs/data-governance-overview/)
- Contact {{ extended_by.username }} who extended the retention
- Contact your organisation administrator
- Review your organisation's data retention policy

---

_This is an automated notification from {{ brand_title }}._
