{% load i18n %}

## {% trans "Key Recovery Request Approved" %}

{% blocktrans with name=user_name %}Hi {{ name }},{% endblocktrans %}

{% trans "Good news! Your key recovery request has been approved." %}

### {% trans "Request Details" %}

- **{% trans "Request ID" %}:** `{{ request_id }}`
- **{% trans "Survey" %}:** {{ survey_name }}
- **{% trans "Approved by" %}:** {{ approved_by }}

### {% trans "Mandatory Waiting Period" %}

{% blocktrans with hours=time_delay_hours %}For security reasons, there is a mandatory **{{ hours }}-hour waiting period** before your access is restored.{% endblocktrans %}

⏰ **{% trans "Access will be available at" %}:** {{ access_available_at }}

{% trans "This delay helps protect against unauthorized access by giving you time to report if this request was not legitimately made by you." %}

### {% trans "What Happens Next" %}

1. {% trans "Wait for the time delay to complete" %}
2. {% trans "You will receive another email when access is ready" %}
3. {% trans "You may then need to set a new passphrase" %}

⚠️ **{% trans "Important" %}:** {% trans "If you did not request this recovery, contact your administrator immediately to cancel the request during this waiting period." %}

---

{% blocktrans with brand=brand_title %}The {{ brand }} Security Team{% endblocktrans %}
