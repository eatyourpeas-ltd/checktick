{% load i18n %}

## 🎉 {% trans "Recovery Complete - Access Restored" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "Great news! Your key recovery request has been successfully completed. You can now access your encrypted survey data using your new password." %}

### {% trans "Recovery Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}
- **{% trans "Status" %}:** ✅ {% trans "Completed" %}

### {% trans "Access Your Survey" %}

{% trans "Your data is now accessible. Click below to open your survey:" %}

[**{% trans "Open Survey" %}**]({{ survey_url }})

{% trans "Or copy and paste this URL:" %}

```
{{ survey_url }}
```

### {% trans "Important Security Reminders" %}

- **{% trans "Remember your new password" %}** - {% trans "Store it securely" %}
- **{% trans "Consider setting up a recovery phrase" %}** - {% trans "This helps prevent future lockouts" %}
- **{% trans "Enable 2FA" %}** {% trans "if you haven't already" %}

### {% trans "What Happened" %}

{% trans "Your encryption keys have been recovered from our secure key escrow and re-encrypted with your new password. The original escrowed keys remain protected for future recovery needs." %}

### {% trans "Need Help?" %}

{% trans "If you experience any issues accessing your data, please contact your administrator." %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Team{% endblocktrans %}
