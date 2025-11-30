## Subscription Cancelled

Hi **{{ user.username }}**,

We're sorry to see you go. Your {{ tier_name }} subscription has been cancelled as requested.

### What Happens Next

- **Retain Access**: You'll continue to have access to all {{ tier_name }} features until {{ access_until_date }}
- **Automatic Downgrade**: After {{ access_until_date }}, your account will be downgraded to the Free tier
  {% if surveys_to_close > 0 %}
- **Survey Limits**: You currently have {{ survey_count }} surveys, but the Free tier allows {{ free_tier_limit }}. Your {{ surveys_to_close }} oldest survey(s) will be automatically closed (read-only) when your subscription ends. You can still view and export data from closed surveys.
  {% endif %}

### Free Tier Includes

- **{{ free_tier_limit }} surveys** - Perfect for small projects
- **Core features** - All essential survey functionality
- **Data export** - Download your survey data anytime

### Changed Your Mind?

You can reactivate your subscription at any time before {{ access_until_date }} by visiting your [subscription portal]({{ site_url }}/subscription/).

### Keep Your Data

Even on the Free tier, all your survey data remains accessible. You can:

- View all responses
- Export data anytime
- Upgrade again whenever needed

### Quick Links

- [Subscription Portal]({{ site_url }}/subscription/) - Manage your account
- [View Plans]({{ site_url }}/pricing/) - See what you'll miss
- [Export Data]({{ site_url }}/surveys/) - Download your surveys

### We'd Love Your Feedback

If you have a moment, we'd appreciate knowing why you cancelled. Your feedback helps us improve {{ brand_title }} for everyone.

---

We hope to see you again soon!
The {{ brand_title }} Team
