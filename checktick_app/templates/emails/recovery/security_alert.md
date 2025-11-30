{% load i18n %}

## 🚨 {% trans "Security Alert: Key Recovery Request" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "We detected potentially suspicious activity related to a key recovery request on your account." %}

### {% trans "Alert Details" %}

- **{% trans "Alert Type" %}:** {{ alert_type }}
- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}

### {% trans "What Happened" %}

{{ alert_details }}

### {% trans "Take Action" %}

{% trans "If you did not initiate this recovery request, take immediate action:" %}

[**{% trans "Report Unauthorized Access" %}**]({{ action_url }})

{% trans "Or copy and paste this URL:" %}

```
{{ action_url }}
```

### {% trans "If This Was You" %}

{% trans "If you did initiate this request, you can safely ignore this alert. This notification is sent as a security precaution." %}

### {% trans "Contact Support" %}

{% trans "If you have any concerns about your account security, please contact your administrator immediately." %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Security Team{% endblocktrans %}
