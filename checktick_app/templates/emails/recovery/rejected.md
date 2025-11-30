{% load i18n %}

## {% trans "Key Recovery Request Rejected" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "Unfortunately, your key recovery request has been rejected." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}
- **{% trans "Reviewed by" %}:** {{ rejected_by }}

### {% trans "Reason for Rejection" %}

{{ reason }}

### {% trans "What You Can Do" %}

{% trans "If you believe this rejection was made in error, you can:" %}

1. {% trans "Contact your organization administrator" %}
2. {% trans "Submit a new recovery request with additional information" %}
3. {% trans "Verify your identity through your organization's IT support" %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Security Team{% endblocktrans %}
