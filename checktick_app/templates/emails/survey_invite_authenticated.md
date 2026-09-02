# You're invited to complete a survey

Hello,

You've been invited to complete the following survey:

**{{ survey_name }}**

{% if organization_name %}
This survey is being conducted by {{ organization_name }}.
{% endif %}

As an invited participant, please log in to your CheckTick account to access the survey:

[Complete Survey]({{ survey_link }})

Or copy and paste this link into your browser: <{{ survey_link }}>
{% if qr_code_data_uri %}

You can also scan this QR code with your phone:

![QR Code]({{ qr_code_data_uri }})
{% endif %}

{% if end_date %}
**Please complete by:** {{ end_date }}
{% endif %}

{% if contact_email %}
If you have any questions, please contact {{ contact_email }}.
{% endif %}

Thank you for your participation!
