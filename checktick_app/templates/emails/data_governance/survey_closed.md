## Survey Closed Successfully

Hi **{{ survey.owner.username }}**,

Your survey **"{{ survey.name }}"** has been closed successfully.

### Closure Details

- **Survey:** {{ survey.name }}
- **Closed by:** {{ closed_by.username }}
- **Closed at:** {{ closed_time }}
- **Total responses:** {{ response_count }}

### Data Retention

Your survey data will be retained according to the following schedule:

- **Retention period:** {{ survey.retention_months }} months
- **Automatic deletion date:** {{ deletion_date }}
- **Warnings will be sent:** {{ warning_schedule }}

### What happens now?

#### Data Access

- You can still **download survey data** at any time
- Data exports are tracked and logged for audit purposes
- Organisation administrators are notified of all downloads

#### Retention Management

- You can **extend the retention period** if needed (up to 24 months total)
- Extensions require justification and approval
- Legal holds can prevent deletion for ongoing investigations

#### Deletion Warnings

You'll receive email reminders before automatic deletion:

- **1 month** before deletion
- **1 week** before deletion
- **1 day** before deletion

Each reminder will include options to export data or extend retention.

### Quick Actions

- [Download Survey Data]({{ site_url }}/surveys/{{ survey.slug }}/export/create/)
- [Extend Retention Period]({{ site_url }}/surveys/{{ survey.slug }}/retention/extend/)
- [View Survey Dashboard]({{ site_url }}/surveys/{{ survey.slug }}/dashboard/)

### Need Help?

- Review our [Data Governance Policy]({{ site_url }}/docs/data-governance-overview/)
- Contact your organisation administrator
- Email support with questions

---

Thank you for using {{ brand_title }}!

The {{ brand_title }} Team
