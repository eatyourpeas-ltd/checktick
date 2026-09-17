## Your {{ tier_name }} Access Ends Soon

Hi **{{ user.username }}**,

This is a friendly reminder that your {{ tier_name }} access on {{ brand_title }} will end on **{{ expiry_date }}** (in {{ days_until_expiry }} days).

### What Happens When It Ends

- Your account will be downgraded to the Free tier
{% if surveys_to_close > 0 %}
- You currently have {{ survey_count }} surveys, but the Free tier allows a maximum of {{ free_tier_limit }}. Your {{ surveys_to_close }} oldest survey(s) will be automatically closed (read-only). You can still view and export data from closed surveys.
{% else %}
- All your surveys are within the Free tier limit, so none will be closed.
{% endif %}

### Want to Keep Your {{ tier_name }} Features?

You can renew your access at any time before it ends:

- [Renew your subscription]({{ site_url }}/subscription/)
- [View plans]({{ site_url }}/pricing/)

### Need More Time?

If you have questions about your renewal or need to discuss options, please reply to this email or contact our team.

---

The {{ brand_title }} Team
