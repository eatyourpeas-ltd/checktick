## You're Invited to Join {{ org_name }}

Hi there,

**{{ invited_by_name }}** has invited you to join their organisation on {{ brand_title }}.

### Invitation Details

- **Organisation:** {{ org_name }}
- **Your Role:** {{ role_display }}
- **Invited by:** {{ invited_by_name }} ({{ invited_by_email }})

### Get Started

To accept this invitation and join the organisation, create your account:

[**Create Account**]({{ signup_link }})

Or copy and paste this URL:

```
{{ signup_link }}
```

Once you create your account, you'll automatically be added to the organisation.

### What You'll Be Able to Do

As a **{{ role_display }}**, you'll be able to:
{% if role == "admin" %}- Manage organisation settings, teams, and members{% endif %}
{% if role == "admin" or role == "creator" %}- Create and edit surveys across the organisation{% endif %}
- View organisation surveys and data
- Collaborate with team members

---

If you have any questions, please contact {{ invited_by_email }}.

The {{ brand_title }} Team
