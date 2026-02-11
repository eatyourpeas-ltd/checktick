## {{ urgency }}: Survey Data Deletion Warning

Hi **{{ survey.owner.username }}**,

Your survey **"{{ survey.name }}"** will be automatically deleted **{{ timeframe }}**.

### Deletion Details

- **Survey:** {{ survey.name }}
- **Deletion Date:** {{ deletion_date }}
- **Days Remaining:** {{ days_remaining }}
- **Retention Period:** {{ survey.retention_months }} months

### Why is this happening?

This survey was closed on {{ closure_date }} and has reached the end of its {{ survey.retention_months }}-month retention period. As required by data protection regulations, survey data must be deleted when no longer needed.

### What you can do

#### Option 1: Export Your Data

If you still need this data, **download it now** before it's deleted:

1. Go to your [survey dashboard]({{ site_url }}/surveys/{{ survey.slug }}/dashboard/)
2. Click "Download Survey Data"
3. Store the export securely on your local system

**Note:** Downloaded data becomes your responsibility. Store it encrypted and delete it when no longer needed.

#### Option 2: Extend Retention Period

If you have a legitimate business need to keep this data longer, you can extend the retention period:

1. Go to your [survey dashboard]({{ site_url }}/surveys/{{ survey.slug }}/dashboard/)
2. Click "Extend Retention Period"
3. Provide a justification for the extension
4. Maximum total retention: 24 months from closure

**Note:** Extensions require justification and are logged for audit purposes.

#### Option 3: Take No Action

If you no longer need this data, you don't need to do anything. The survey will be automatically deleted on the scheduled date.

### What happens after deletion?

- All survey responses will be permanently deleted
- The survey structure will be preserved (questions, groups)
- This action **cannot be undone**
- A deletion record will be kept for audit purposes

### Need Help?

If you have questions or concerns about this deletion:

- Review our [Data Governance Policy]({{ site_url }}/docs/data-governance-overview/)
- Contact your organisation administrator
- Email support if you believe this is an error

---

**This is an automated notice.** Do not reply to this email.

The {{ brand_title }} Team
