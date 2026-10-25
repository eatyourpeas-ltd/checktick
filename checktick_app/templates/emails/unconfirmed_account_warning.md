{% load i18n %}## {% blocktranslate %}Action needed: confirm your email to keep your account{% endblocktranslate %}

{% blocktranslate %}Hi {{ user.username }},{% endblocktranslate %}

{% blocktranslate with days=days_until_removal %}Your {{ brand_title }} account will be removed in **{{ days }} days** because your email address has not been confirmed.{% endblocktranslate %}

{% blocktranslate %}If you do not confirm your email before then, you will lose access to your account and any data you have created.{% endblocktranslate %}

### {% blocktranslate %}Confirm your email now{% endblocktranslate %}

{% blocktranslate %}To keep your account, sign in and request a new confirmation email from your profile page:{% endblocktranslate %}

- [{% blocktranslate %}Go to your profile{% endblocktranslate %}]({{ profile_url }}) → {% blocktranslate %}Email Notification Preferences → Resend Confirmation Email{% endblocktranslate %}

### {% blocktranslate %}Having trouble?{% endblocktranslate %}

{% blocktranslate %}If you are having difficulty confirming your email or need help with your account, please contact us:{% endblocktranslate %}

- [{% blocktranslate %}Email support{% endblocktranslate %}]({{ support_email }})

---

{% blocktranslate %}The {{ brand_title }} Team{% endblocktranslate %}
