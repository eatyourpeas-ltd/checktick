{% load i18n %}

## {% trans "Your Data Access is Ready" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "The waiting period for your key recovery request has completed. You can now restore access to your encrypted data." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}

### {% trans "Complete Your Recovery" %}

{% trans "Click the link below to set a new passphrase and restore access to your data:" %}

[**{% trans "Complete Recovery" %}**]({{ recovery_url }})

{% trans "Or copy and paste this URL:" %}

```
{{ recovery_url }}
```

### {% trans "Important Notes" %}

- {% trans "You will need to set a new passphrase" %}
- {% trans "Your previous passphrase will no longer work" %}
- {% trans "Make sure to save your new passphrase securely" %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Team{% endblocktrans %}
