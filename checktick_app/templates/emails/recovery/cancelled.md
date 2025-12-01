{% load i18n %}

## {% trans "Key Recovery Request Cancelled" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "Your key recovery request has been cancelled." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}
- **{% trans "Cancelled by" %}:** {{ cancelled_by }}
  {% if reason %}- **{% trans "Reason" %}:** {{ reason }}{% endif %}

### {% trans "Need Help?" %}

{% trans "If you still need to recover access to your data, you can submit a new recovery request." %}

{% trans "If you have questions about why this request was cancelled, please contact your administrator." %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Team{% endblocktrans %}
