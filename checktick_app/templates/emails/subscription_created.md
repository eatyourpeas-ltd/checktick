## Welcome to {{ tier_name }}!

Hi **{{ user.username }}**,

Thank you for subscribing to {{ brand_title }} {{ tier_name }}! 🎉

Your subscription is now active and you have access to all {{ tier_name }} features.

### What's Included

{% if tier == 'pro' %}

- **Unlimited surveys** - Create as many surveys as you need
- **Advanced question types** - Access all survey features
- **Priority support** - Get help when you need it
- **Enhanced analytics** - Deeper insights into your data
  {% elif tier == 'enterprise' %}
- **Everything in Pro** plus:
- **Custom branding** - White-label your surveys
- **SSO integration** - Single sign-on for your organization
- **Dedicated support** - Direct access to our team
- **SLA guarantees** - Uptime and support commitments
  {% endif %}

---

## VAT Invoice

|                    |                                        |
| ------------------ | -------------------------------------- |
| **Invoice Number** | {{ invoice_number }}                   |
| **Invoice Date**   | {{ invoice_date }}                     |
| **Customer**       | {{ user.username }} ({{ user.email }}) |

### Invoice Details

| Description                                        |                   Amount |
| -------------------------------------------------- | -----------------------: |
| {{ tier_name }} Subscription ({{ billing_cycle }}) |      {{ amount_ex_vat }} |
| VAT @ {{ vat_rate }}                               |         {{ vat_amount }} |
| **Total (inc. VAT)**                               | **{{ amount_inc_vat }}** |

{% if vat_number %}
**VAT Registration Number**: GB {{ vat_number }}
{% endif %}

**Supplier**: {{ company_name }}{% if company_address %}
{{ company_address }}{% endif %}

---

### Quick Links

- [Manage Subscription]({{ site_url }}/subscription/) - View plan details and billing
- [View Plans]({{ site_url }}/pricing/) - Compare features
- [Payment History]({{ site_url }}/subscription/payment-history/) - Access invoices

### Billing Information

- **Plan**: {{ tier_name }}
- **Status**: Active
- **Billing Cycle**: {{ billing_cycle|default:"Monthly" }}

Your subscription will automatically renew at the end of each billing period. You can manage or cancel your subscription at any time from your account settings.

### Need Help?

If you have any questions about your subscription, please visit your [subscription portal]({{ site_url }}/subscription/) or contact support.

---

Thank you for your business!
The {{ brand_title }} Team
