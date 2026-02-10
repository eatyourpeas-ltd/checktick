{% load i18n %}

# {% blocktranslate %}Admin Login Detected{% endblocktranslate %}

{% blocktranslate %}Hi {{ user.first_name|default:user.username }},{% endblocktranslate %}

{% blocktranslate %}Your {{ access_level }} account just logged in to {{ brand_title }}.{% endblocktranslate %}

{% blocktranslate %}Because this is a healthcare application with access to sensitive patient data, we notify you of all privileged account access.{% endblocktranslate %}

## {% blocktranslate %}Login Details{% endblocktranslate %}

- **{% blocktranslate %}Account:{% endblocktranslate %}** {{ user.email }}
- **{% blocktranslate %}Access Level:{% endblocktranslate %}** {{ access_level }}
- **{% blocktranslate %}Time:{% endblocktranslate %}** {{ timestamp }}
- **{% blocktranslate %}IP Address:{% endblocktranslate %}** {{ ip_address }}
- **{% blocktranslate %}Device/Browser:{% endblocktranslate %}** {{ user_agent }}

## {% blocktranslate %}What to do{% endblocktranslate %}

{% blocktranslate %}If this was you, no action is needed. This is just a confirmation for your records.{% endblocktranslate %}

{% blocktranslate %}If this was NOT you, someone may have accessed your account. Take immediate action:{% endblocktranslate %}

1. {% blocktranslate %}Change your password immediately{% endblocktranslate %}
2. {% blocktranslate %}Review your recent account activity{% endblocktranslate %}
3. {% blocktranslate %}Enable two-factor authentication if not already enabled{% endblocktranslate %}
4. {% blocktranslate %}Contact your system administrator{% endblocktranslate %}

## {% blocktranslate %}Why am I receiving this?{% endblocktranslate %}

{% blocktranslate %}For healthcare compliance and patient data protection, all privileged account access is monitored and logged. This notification helps ensure that only authorized personnel access sensitive information.{% endblocktranslate %}

---

{% blocktranslate %}This is an automated security notification required for healthcare compliance. All access to administrative functions is logged and monitored.{% endblocktranslate %}
