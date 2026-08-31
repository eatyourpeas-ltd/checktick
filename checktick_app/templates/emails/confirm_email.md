{% load i18n %}## {% blocktranslate %}Confirm your email address{% endblocktranslate %}

{% blocktranslate %}Hi {{ user.first_name|default:user.username }},{% endblocktranslate %}

{% blocktranslate %}Thank you for signing up for {{ brand_title }}! To complete your registration and activate your account, please confirm your email address.{% endblocktranslate %}

[{% blocktranslate %}Confirm Email Address{% endblocktranslate %}]({{ confirmation_url }})

**{% blocktranslate %}Note:{% endblocktranslate %}** {% blocktranslate %}This link will expire at {{ expires_at }}.{% endblocktranslate %}

{% blocktranslate %}If you did not create an account with us, please ignore this email.{% endblocktranslate %}

---

{% blocktranslate %}Best regards,{% endblocktranslate %}
{% blocktranslate %}The {{ brand_title }} Team{% endblocktranslate %}
