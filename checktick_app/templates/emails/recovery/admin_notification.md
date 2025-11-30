{% load i18n %}

## {% trans "New Key Recovery Request Requires Review" %}

{% blocktrans with name=admin_name %}Hi {{ name }},{% endblocktrans %}

{% trans "A new key recovery request has been submitted and requires your review." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Requester" %}:** {{ requester_name }} ({{ requester_email }})
- **{% trans "Survey" %}:** {{ survey_name }}
- **{% trans "Reason" %}:** {{ reason }}

### {% trans "Action Required" %}

{% trans "Please review this request and take appropriate action:" %}

[**{% trans "Review Request in Dashboard" %}**]({{ dashboard_url }})

{% trans "Or copy and paste this URL:" %}

```
{{ dashboard_url }}
```

### {% trans "Security Reminder" %}

{% trans "Before approving any recovery request:" %}

- {% trans "Verify the requester's identity through an out-of-band channel" %}
- {% trans "Review the stated reason for reasonableness" %}
- {% trans "Check for any suspicious account activity" %}
- {% trans "Document your verification steps" %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Security Team{% endblocktrans %}
