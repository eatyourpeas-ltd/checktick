{% load i18n %}

# {% blocktranslate %}Admin Access Monitoring: {{ access_level }} Login{% endblocktranslate %}

{% blocktranslate %}Hi {{ admin.first_name|default:admin.username }},{% endblocktranslate %}

{% blocktranslate %}A {{ access_level }} account has logged in to {{ brand_title }}. As a system administrator, you receive this notification for security monitoring purposes.{% endblocktranslate %}

## {% blocktranslate %}Login Details{% endblocktranslate %}

- **{% blocktranslate %}User:{% endblocktranslate %}** {{ logged_in_user.email }} ({{ logged_in_user.first_name }} {{ logged_in_user.last_name }})
- **{% blocktranslate %}Access Level:{% endblocktranslate %}** {{ access_level }}
- **{% blocktranslate %}Time:{% endblocktranslate %}** {{ timestamp }}
- **{% blocktranslate %}IP Address:{% endblocktranslate %}** {{ ip_address }}
- **{% blocktranslate %}Device/Browser:{% endblocktranslate %}** {{ user_agent }}

## {% blocktranslate %}What to do{% endblocktranslate %}

{% blocktranslate %}If this access is expected, no action is needed. This is a routine security monitoring notification.{% endblocktranslate %}

{% blocktranslate %}If this access seems suspicious or unexpected:{% endblocktranslate %}

1. {% blocktranslate %}Contact the user to verify this was them{% endblocktranslate %}
2. {% blocktranslate %}Review recent account activity logs{% endblocktranslate %}
3. {% blocktranslate %}Check for any unusual data access patterns{% endblocktranslate %}
4. {% blocktranslate %}If unauthorized, immediately disable the account and investigate{% endblocktranslate %}

## {% blocktranslate %}Why am I receiving this?{% endblocktranslate %}

{% blocktranslate %}For healthcare compliance and patient data protection, all privileged account access is monitored. As a superuser, you receive notifications about all administrative logins to help maintain security oversight.{% endblocktranslate %}

---

{% blocktranslate %}This is an automated security notification required for healthcare compliance. All access to administrative functions is logged and monitored.{% endblocktranslate %}
