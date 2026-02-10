{% load i18n %}

# 🚨 {% blocktranslate %}Failed Login Attempt to Your {{ access_level }} Account{% endblocktranslate %}

{% blocktranslate %}Hi {{ user.first_name|default:user.username }},{% endblocktranslate %}

{% blocktranslate %}Someone attempted to log in to your {{ access_level }} account on {{ brand_title }} but failed.{% endblocktranslate %}

{% blocktranslate %}Because your account has privileged access to patient data, we immediately notify you of any failed login attempts.{% endblocktranslate %}

## {% blocktranslate %}Attempt Details{% endblocktranslate %}

- **{% blocktranslate %}Account Targeted:{% endblocktranslate %}** {{ user.email }}
- **{% blocktranslate %}Access Level:{% endblocktranslate %}** {{ access_level }}
- **{% blocktranslate %}Time:{% endblocktranslate %}** {{ timestamp }}
- **{% blocktranslate %}IP Address:{% endblocktranslate %}** {{ ip_address }}
- **{% blocktranslate %}Device/Browser:{% endblocktranslate %}** {{ user_agent }}
- **{% blocktranslate %}Result:{% endblocktranslate %}** ❌ {% blocktranslate %}Login Failed{% endblocktranslate %}

## {% blocktranslate %}What to do{% endblocktranslate %}

{% blocktranslate %}If this was you, make sure you're using the correct password and try again.{% endblocktranslate %}

{% blocktranslate %}If this was NOT you, someone may be attempting to access your account. Take immediate action:{% endblocktranslate %}

1. ⚠️ **{% blocktranslate %}Change your password immediately{% endblocktranslate %}**
2. {% blocktranslate %}Review your recent account activity{% endblocktranslate %}
3. {% blocktranslate %}Enable two-factor authentication if not already enabled{% endblocktranslate %}
4. {% blocktranslate %}Check if the IP address or location seems suspicious{% endblocktranslate %}
5. {% blocktranslate %}Contact your system administrator if you suspect unauthorized access{% endblocktranslate %}

## {% blocktranslate %}Security Measures{% endblocktranslate %}

{% blocktranslate %}Your account will be automatically locked after multiple failed login attempts. Other system administrators have also been notified of this event.{% endblocktranslate %}

## {% blocktranslate %}Why am I receiving this?{% endblocktranslate %}

{% blocktranslate %}For healthcare compliance and patient data protection, all access attempts to privileged accounts are monitored and logged. Failed login attempts may indicate a security threat and require immediate attention.{% endblocktranslate %}

---

{% blocktranslate %}This is an automated security alert required for healthcare compliance. All access attempts to administrative functions are logged and monitored.{% endblocktranslate %}
