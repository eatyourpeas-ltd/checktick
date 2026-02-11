# Ownership Transfer Notice

{% if is_new_owner %}
You have been assigned as the new owner of survey **"{{ survey.name }}"**.
{% else %}
Your survey **"{{ survey.name }}"** has been transferred to a new owner.
{% endif %}

## Transfer Details

- **Survey:** {{ survey.name }}
- **Previous owner:** {{ old_owner.username }} ({{ old_owner.email }})
- **New owner:** {{ new_owner.username }} ({{ new_owner.email }})
- **Transfer date:** {{ transfer_date }}
- **Reason:** {{ reason }}

## What This Means

{% if is_new_owner %}

### Your New Responsibilities

As the new owner, you now have:

✅ **Full control** over the survey and its data
✅ **Ownership of all responses** and associated data
✅ **Responsibility** for data protection and compliance
✅ **Authority** to extend retention, export data, and grant custodian access

You are now responsible for:

- Managing data access and permissions
- Ensuring compliance with data protection regulations
- Responding to deletion warnings
- Making decisions about data retention
- Maintaining appropriate data security

### Important Information

- **Retention period:** {{ survey.retention_months }} months
  {% if survey.deletion_date %}
- **Scheduled deletion:** {{ deletion_date }}
- You will receive deletion warnings at 30, 7, and 1 day before deletion
  {% endif %}
  {% if survey.is_closed %}
- **Survey status:** Closed (no longer accepting responses)
  {% else %}
- **Survey status:** Open (still accepting responses)
  {% endif %}

### Your Next Steps

1. **Review the survey** in your dashboard
2. **Check data governance settings** (retention period, custodians)
3. **Review access permissions** and update as needed
4. **Familiarize yourself** with [Data Governance Policies](/docs/data-governance-overview/)

[Go to Survey Dashboard]({{ site_url }}/surveys/{{ survey.slug }}/)

{% else %}

### Your Status

You are no longer the owner of this survey. This means:

❌ You can no longer manage survey settings
❌ You cannot extend retention or modify data governance
❌ You will not receive deletion warnings
❌ You cannot grant or revoke custodian access

### If You Still Need Access

If you need continued access to this survey's data:

1. Contact the new owner ({{ new_owner.username }})
2. Request **Data Custodian** access
3. Provide a clear justification for why you need access
4. The new owner can grant you custodian permissions

Data Custodians can:

- Download survey data for approved purposes
- Receive deletion warning emails
- View survey responses

{% endif %}

## Questions?

For questions about this ownership transfer:

{% if is_new_owner %}

- Contact {{ old_owner.username }} for context and background
  {% else %}
- Contact {{ new_owner.username }} if you need access to the data
  {% endif %}
- Review the [Data Governance Overview](/docs/data-governance-overview/)
- Contact your organisation administrator

---

_This is an automated notification from {{ brand_title }}._
