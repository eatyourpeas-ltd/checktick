{% load i18n %}

# {% blocktranslate %}Account Temporarily Locked{% endblocktranslate %}

{% blocktranslate %}Hi {{ user.first_name|default:user.username }},{% endblocktranslate %}

{% blocktranslate %}We've detected multiple unsuccessful login attempts to your {{ brand_title }} account.{% endblocktranslate %}

{% blocktranslate %}For your security, your account has been temporarily locked.{% endblocktranslate %}

## {% blocktranslate %}Details{% endblocktranslate %}

- **{% blocktranslate %}Failed attempts:{% endblocktranslate %}** {{ failure_limit }}
- **{% blocktranslate %}IP Address:{% endblocktranslate %}** {{ ip_address }}
- **{% blocktranslate %}Lock duration:{% endblocktranslate %}** {{ cooloff_hours }} {% blocktranslate %}hour(s){% endblocktranslate %}

## {% blocktranslate %}What to do{% endblocktranslate %}

{% blocktranslate %}If this was you, please wait and try again later. Make sure you're using the correct password.{% endblocktranslate %}

{% blocktranslate %}If this was NOT you, someone may be trying to access your account. We recommend:{% endblocktranslate %}

1. {% blocktranslate %}Wait for the lockout to expire{% endblocktranslate %}
2. {% blocktranslate %}Log in and change your password immediately{% endblocktranslate %}
3. {% blocktranslate %}Enable two-factor authentication if not already enabled{% endblocktranslate %}
4. {% blocktranslate %}Review your recent account activity{% endblocktranslate %}

## {% blocktranslate %}Need help?{% endblocktranslate %}

{% blocktranslate %}If you're having trouble accessing your account, please contact our support team.{% endblocktranslate %}

---

{% blocktranslate %}This is an automated security notification. You cannot reply to this email.{% endblocktranslate %}
