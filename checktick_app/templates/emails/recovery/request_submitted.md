{% load i18n %}

## {% trans "Key Recovery Request Submitted" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "Your request to recover access to your encrypted survey data has been submitted and is pending review." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}
- **{% trans "Reason" %}:** {{ reason }}

### {% trans "What Happens Next" %}

1. {% trans "A platform administrator will review your request" %}
2. {% trans "You may be asked to verify your identity" %}
3. {% trans "Once approved, there will be a mandatory waiting period before access is restored" %}

**{% trans "Estimated review time" %}:** {{ estimated_review_time }}

⚠️ **{% trans "Important" %}:** {% trans "If you did not submit this request, please contact your administrator immediately." %}

---

{% trans "Thank you for your patience." %}

{% blocktrans with brand=brand_title %}The {{ brand }} Team{% endblocktrans %}
