# You're invited to join CheckTick and complete a survey

Hello,

You've been invited to complete the following survey:

**{{ survey_name }}**

{% if organization_name %}
This survey is being conducted by {{ organization_name }}.
{% endif %}

To access this survey, you'll need to create a free CheckTick account. Click the link below to get started:

[Create Account and Access Survey]({{ signup_link }})

After creating your account, you'll be automatically directed to the survey.

Once logged in, you can also go directly to the survey: <{{ survey_link }}>
{% if qr_code_data_uri %}

You can also scan this QR code with your phone to get started:

![QR Code]({{ qr_code_data_uri }})
{% endif %}

{% if end_date %}
**Please complete by:** {{ end_date }}
{% endif %}

{% if contact_email %}
If you have any questions, please contact {{ contact_email }}.
{% endif %}

Thank you for your participation!
