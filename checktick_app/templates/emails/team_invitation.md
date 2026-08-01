## You're Invited to Join {{ team_name }}

Hi there,

**{{ invited_by_name }}** has invited you to join their team on {{ brand_title }}.

### Invitation Details

- **Team:** {{ team_name }}
- **Your Role:** {{ role_display }}
- **Invited by:** {{ invited_by_name }} ({{ invited_by_email }})

{% if organization_name %}This team is part of **{{ organization_name }}**.{% endif %}

### Get Started

To accept this invitation and join the team, create your account:

[**Create Account**]({{ signup_link }})

Or copy and paste this URL:

```
{{ signup_link }}
```

Once you create your account, you'll automatically be added to the team.

### What You'll Be Able to Do

As a **{{ role_display }}**, you'll be able to:
{% if role == "admin" %}- Manage team settings and members{% endif %}
{% if role == "admin" or role == "creator" %}- Create and edit surveys{% endif %}
- View team surveys and data

---

If you have any questions, please contact {{ invited_by_email }}.

The {{ brand_title }} Team
