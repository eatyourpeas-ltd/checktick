{% load i18n %}

## {% trans "Identity Verification Required" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "To proceed with your key recovery request, we need to verify your identity." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`

### {% trans "Verification Method" %}

**{{ verification_method }}**

{{ verification_instructions }}

### {% trans "Important" %}

⏰ **{% trans "This verification request expires:" %}** {{ expires_at }}

{% trans "If you do not complete verification by this time, your recovery request will be cancelled and you'll need to submit a new one." %}

⚠️ **{% trans "Security Note" %}:** {% trans "If you did not submit this recovery request, please contact your administrator immediately as someone may be attempting to access your data." %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Security Team{% endblocktrans %}
