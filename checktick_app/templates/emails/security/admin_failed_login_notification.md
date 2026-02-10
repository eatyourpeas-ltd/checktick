{% load i18n %}

# 🚨 {% blocktranslate %}Security Alert: Failed {{ access_level }} Login Attempt{% endblocktranslate %}

{% blocktranslate %}Hi {{ admin.first_name|default:admin.username }},{% endblocktranslate %}

{% blocktranslate %}A failed login attempt was detected on a {{ access_level }} account in {{ brand_title }}. As a system administrator, you receive this notification to help monitor for potential security threats.{% endblocktranslate %}

## {% blocktranslate %}Attempt Details{% endblocktranslate %}

- **{% blocktranslate %}Account Targeted:{% endblocktranslate %}** {{ targeted_user.email }} ({{ targeted_user.first_name }} {{ targeted_user.last_name }})
- **{% blocktranslate %}Access Level:{% endblocktranslate %}** {{ access_level }}
- **{% blocktranslate %}Time:{% endblocktranslate %}** {{ timestamp }}
- **{% blocktranslate %}IP Address:{% endblocktranslate %}** {{ ip_address }}
- **{% blocktranslate %}Device/Browser:{% endblocktranslate %}** {{ user_agent }}
- **{% blocktranslate %}Result:{% endblocktranslate %}** ❌ {% blocktranslate %}Login Failed{% endblocktranslate %}

## {% blocktranslate %}What to do{% endblocktranslate %}

{% blocktranslate %}Failed login attempts on privileged accounts may indicate:{% endblocktranslate %}

- {% blocktranslate %}Legitimate user forgot their password{% endblocktranslate %}
- {% blocktranslate %}Brute force attack attempt{% endblocktranslate %}
- {% blocktranslate %}Compromised credentials from another breach{% endblocktranslate %}
- {% blocktranslate %}Internal security testing{% endblocktranslate %}

**{% blocktranslate %}Recommended Actions:{% endblocktranslate %}**

1. {% blocktranslate %}Contact the user to verify if this was them{% endblocktranslate %}
2. {% blocktranslate %}Check audit logs for patterns or repeated attempts{% endblocktranslate %}
3. {% blocktranslate %}Review the IP address for known threats or suspicious location{% endblocktranslate %}
4. {% blocktranslate %}If multiple failures occur, consider temporarily locking the account{% endblocktranslate %}
5. {% blocktranslate %}If attack is confirmed, block the IP address at firewall level{% endblocktranslate %}

## {% blocktranslate %}Automated Protections{% endblocktranslate %}

{% blocktranslate %}The account will be automatically locked after {{ failure_limit|default:"5" }} failed attempts. The user and all administrators are notified of both failed attempts and account lockouts.{% endblocktranslate %}

## {% blocktranslate %}Why am I receiving this?{% endblocktranslate %}

{% blocktranslate %}For healthcare compliance and patient data protection, all access attempts to privileged accounts are monitored. As a superuser, you receive notifications about failed login attempts to help maintain security oversight and respond quickly to potential threats.{% endblocktranslate %}

---

{% blocktranslate %}This is an automated security alert required for healthcare compliance. All access attempts to administrative functions are logged and monitored.{% endblocktranslate %}
