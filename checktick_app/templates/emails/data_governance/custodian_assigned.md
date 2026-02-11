## Data Custodian Role Assigned

Hi **{{ custodian_user.username }}**,

You have been designated as a **Data Custodian** for survey **"{{ survey.name }}"**.

### Assignment Details

- **Survey:** {{ survey.name }}
- **Granted by:** {{ granted_by.username }} ({{ granted_by.email }})
- **Reason:** {{ reason }}
  {% if expires_at %}- **Access expires:** {{ expiry_date }}{% endif %}

### What is a Data Custodian?

A Data Custodian has permission to:

✅ **Download survey data** for approved purposes
✅ **Receive deletion warning emails** for this survey
✅ **View survey responses** in the dashboard

Data Custodians **cannot**:

❌ Edit the survey structure or questions
❌ Extend the retention period
❌ Delete or modify responses
❌ Grant custodian access to others

### Your Responsibilities

As a Data Custodian, you are responsible for:

#### 1. Data Security

- Store downloaded data in encrypted, secure locations
- Use password protection for all exports
- Delete local copies when no longer needed

#### 2. Data Privacy

- Only access data for the stated purpose
- Do not share data inappropriately
- Follow your organisation's data protection policies

#### 3. Compliance

- Report any data breaches immediately
- Respond to audit requests
- Maintain audit trail of data access

### Accessing the Survey

To access this survey and download data:

1. Log in to {{ brand_title }}
2. Navigate to your [dashboard]({{ site_url }}/dashboard/)
3. Find **"{{ survey.name }}"** in your surveys list
4. Click "Download Survey Data" when needed

### Quick Links

- [View Survey Dashboard]({{ site_url }}/surveys/{{ survey.slug }}/dashboard/)
- [Data Governance Policy]({{ site_url }}/docs/data-governance-overview/)

### Questions?

If you have questions about this role or your responsibilities:

- Contact {{ granted_by.username }} who assigned you this role
- Review the [Data Governance Policy]({{ site_url }}/docs/data-governance-overview/)
- Contact your organisation's data protection officer

---

**This is an automated notification.** Do not reply to this email.

The {{ brand_title }} Team
