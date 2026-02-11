# Legal Hold Removed

The legal hold on survey **"{{ survey.name }}"** has been removed.

## Removal Details

- **Survey:** {{ survey.name }}
- **Removed by:** {{ removed_by.username }} ({{ removed_by.email }})
- **Date removed:** {{ removed_date }}
- **Original hold placed:** {{ hold_placed_date }}
- **Duration:** {{ hold_duration }}

## Reason for Removal

{{ reason }}

## What This Means

✅ **Normal data governance has resumed**

The survey is no longer subject to legal preservation requirements:

- Automatic deletion schedule has resumed
- Normal retention policies apply
- You can manage data per usual procedures
- Deletion warnings will be sent as scheduled

## Updated Deletion Schedule

{% if survey.deletion_date %}
**New scheduled deletion date:** {{ new_deletion_date }}

You will receive deletion warning emails:

- 30 days before deletion
- 7 days before deletion
- 1 day before deletion

{% else %}
The survey is still open. Once closed, data will be retained for {{ survey.retention_months }} months before deletion.
{% endif %}

## What You Should Do

### Review Data Needs

Now that the legal hold is lifted, assess whether you still need this data:

1. **Do you still need the data?**
   - If yes: Take no action, wait for deletion warnings
   - If no: Consider exporting and then deleting the survey

2. **Does retention period need adjustment?**
   - Current retention: {{ survey.retention_months }} months
   - You can extend up to 24 months total if needed
   - Provide justification for extensions

### Manage Local Copies

If you have local copies of this survey data:

- **Review security**: Ensure exports are still stored securely
- **Assess need**: Do you still need these local copies?
- **Delete if done**: Securely delete local copies if no longer needed
- **Document retention**: If keeping data, document why

### Update Access

Review and update data access as needed:

- Remove custodian access for anyone who no longer needs it
- Update permissions to reflect current requirements
- Ensure only authorized users can access the data

## Return to Normal Governance

With the legal hold removed, you are back to normal data governance:

✅ **Retention limits apply**: Maximum 24 months from closure
✅ **Justification required**: Extensions need documented reasons
✅ **Automatic deletion**: Survey will be deleted at end of retention
✅ **Audit logging**: All actions are logged for compliance

## Your Ongoing Responsibilities

Continue to:

- **Protect the data**: Maintain appropriate security measures
- **Minimize retention**: Don't keep data longer than necessary
- **Respond to warnings**: Act on deletion warning emails
- **Stay compliant**: Follow data protection regulations
- **Document decisions**: Keep records of retention extensions

## Accessing Your Data

To download survey data or manage settings:

[Go to Survey Dashboard]({{ site_url }}/surveys/{{ survey.slug }}/)

Features available:

- Download survey data
- Extend retention period
- Grant/revoke custodian access
- View audit logs

## Questions?

For questions about the legal hold removal:

- Contact {{ removed_by.username }} who removed the hold
- Review the [Data Governance Overview](/docs/data-governance-overview/)
- Contact your organisation's legal counsel
- Contact your organisation administrator

## Important Reminder

Even though the legal hold is removed:

⚠️ **Do not discuss the legal matter** that led to the hold
⚠️ **Maintain confidentiality** about privileged information
⚠️ **Consult legal counsel** if you have questions about the case

---

_This is an automated notification from {{ brand_title }}._
