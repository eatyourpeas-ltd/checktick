---
title: Billing & Subscriptions
category: billing
priority: 1
---

# Billing & Subscriptions

This guide explains how billing works in CheckTick, including subscriptions, payments, upgrades, and cancellations.

## Overview

CheckTick uses a secure payment provider to handle all billing. We offer flexible subscription plans to suit individual users, small teams, and large organisations.

> **Provider note:** The hosted reference deployment ships with one payment-provider integration and related webhook handling. The billing domain model aims to stay as provider-agnostic as practical, but checkout steps, refund capabilities, event names, settlement timing, and customer notification flows may need adjustment if you use a different provider.

> **Note for Self-Hosters:** If you're running CheckTick with `SELF_HOSTED=true` in your environment configuration, billing features are automatically hidden and all users get Enterprise-level features without payment requirements.

## Pricing

All prices are **inclusive of UK VAT at the configured rate** (default 20%).
The base rate is **£20 per seat (ex VAT)**, which yields **£24 per seat (inc VAT)**
when `VAT_RATE=0.20`. Both the per-seat base price and the VAT rate are driven
by environment variables, so changing `VAT_RATE` (or `BASE_SEAT_PRICE_EX_VAT`)
flows through to checkout amounts, invoices, and the public pricing page
without a code deploy.

### Monthly and Annual Billing

Pro and Team tiers support both **monthly** and **annual** billing. Annual
billing applies a configurable discount (default 20%, set via
`ANNUAL_DISCOUNT_PERCENT`) to the equivalent monthly price × 12. VAT is
computed on the discounted annual ex-VAT amount.

At the default `ANNUAL_DISCOUNT_PERCENT=20`, annual subscribers save
approximately 2.4 months' worth of fees compared to monthly billing.

### Default Hosted Prices

Hosted pricing defaults are configured in application settings and used for checkout unless overridden by Platform Admin. The values below assume the default `VAT_RATE=0.20`, `BASE_SEAT_PRICE_EX_VAT=20`, and `ANNUAL_DISCOUNT_PERCENT=20`:

**Monthly billing:**

- **Individual Pro:** £24/month (inc VAT), £20/month (ex VAT)
- **Team Small (5 seats):** £120/month (inc VAT), £100/month (ex VAT)
- **Team Medium (15 seats):** £360/month (inc VAT), £300/month (ex VAT)
- **Team Large (50 seats):** £1,200/month (inc VAT), £1,000/month (ex VAT)

**Annual billing (20% discount):**

- **Individual Pro:** £230.40/year (inc VAT), £192/year (ex VAT) — equivalent to £19.20/month
- **Team Small (5 seats):** £1,152/year (inc VAT), £960/year (ex VAT) — equivalent to £96/month
- **Team Medium (15 seats):** £3,456/year (inc VAT), £2,880/year (ex VAT) — equivalent to £288/month
- **Team Large (50 seats):** £11,520/year (inc VAT), £9,600/year (ex VAT) — equivalent to £960/month

Organisation and Enterprise pricing remain bespoke.

## Available Plans

### Individual Plans

**Individual (Free)**

- £0/month
- Up to 3 active surveys
- Unlimited responses
- Personal encryption
- Basic features

**Individual Pro**

- £24/month (inc VAT) - 1 seat
- Unlimited surveys
- Unlimited responses
- Collaboration features
- Email support

### Team Plans

Teams provide shared billing and collaboration for groups of 5-50 users.

**Team Small**

- £120/month (inc VAT) - 5 seats
- 5 team members
- Unlimited active surveys
- Role-based access (Admin/Creator/Viewer)
- Team encryption management

**Team Medium**

- £360/month (inc VAT) - 15 seats
- 15 team members
- Unlimited active surveys
- All Team Small features

**Team Large**

- £1,200/month (inc VAT) - 50 seats
- 50 team members
- Unlimited active surveys
- All Team Medium features

### Organisation & Enterprise

**Organisation**

- Bespoke per-seat pricing (default £24/seat/month inc VAT)
- Custom number of seats
- Multiple teams within organisation
- Private datasets
- Advanced governance features
- Priority support

**Enterprise**

- Custom pricing (contact sales)
- Includes hosting and support costs
- Self-hosted option
- Custom branding
- SSO/OIDC integration
- Dedicated support
- SLA guarantee

## VAT Information

All prices include UK VAT at the configured rate (default 20%). The VAT rate is
read from the `VAT_RATE` environment variable, and inc-VAT amounts are computed
from the ex-VAT base at runtime via `checktick_app/core/pricing.py`. VAT invoices
are automatically sent on subscription confirmation containing:

- Unique invoice number
- Invoice date
- Amount excluding VAT
- VAT amount
- Total including VAT
- VAT registration number

For VAT-exempt customers (e.g., charities, educational institutions), please contact sales.

## Payment Methods

Available payment methods depend on the payment provider configured for your deployment.

For the hosted reference deployment, recurring billing currently uses the configured bank debit / direct debit provider flow.

For self-hosted or custom hosted deployments:

- available payment methods depend on the provider you integrate
- customer-facing checkout wording may need to be adapted to match that provider
- refund handling and webhook/state mapping may need provider-specific changes

CheckTick does not store complete payment credentials directly in application data.

## Starting a Subscription

### Signing Up with a Paid Plan

1. Go to the [pricing page](/pricing/) or [sign up page](/signup/)
2. Select your desired plan
3. Complete the registration form
4. Click "Create account"
5. You'll be redirected to the configured secure checkout or mandate setup flow
6. Complete the payment authorisation steps requested by that provider
7. Return to CheckTick when the provider confirms setup
8. Your account is activated immediately

### Upgrading from Free to Paid

1. Log in to your CheckTick account
2. Navigate to **Profile** > **Subscription**
3. Click **Upgrade Account**
4. Select your desired plan
5. Complete the checkout process
6. Your new features are available immediately

## Managing Your Subscription

### Viewing Subscription Details

To view your current subscription status:

1. Log in to CheckTick
2. Go to **Profile** > **Subscription**

You'll see:

- Current plan tier
- Next billing date
- Payment provider and current subscription reference where available
- Subscription status (Active/Past Due/Cancelled)

### Updating Payment Method

1. Log in to CheckTick
2. Go to **Profile** > **Subscription**
3. Click **Update Payment Method**
4. You'll be redirected to the provider-managed billing or mandate flow if supported
5. Complete the update steps provided there
6. Changes take effect immediately

### Viewing Payment History

1. Log in to CheckTick
2. Go to **Profile** > **Payment History**

You can:

- View all past invoices
- Review payment dates, amounts, and statuses
- Check payment status

The exact level of customer self-service available here depends on the configured billing provider and what metadata CheckTick stores locally.

## Refunds and Billing Adjustments

For the hosted reference deployment, platform admins can initiate supported refunds from the Platform Admin billing timeline and from the tier account list.

Current behaviour:

- refunds are available only for supported provider-backed payments
- the hosted implementation currently performs full-payment refunds only
- partial refunds are policy-restricted (not automated in the hosted admin flow)
- reason codes are required for operator-initiated refunds for auditability
- refund lifecycle updates are reconciled from provider webhook events
- customers receive a confirmation email when the provider reports the refund as paid

Hosted policy baseline (platform admin):

- supported adjustment action is currently **full refund only**
- reason code should be selected (for example: promotion correction, billing error, duplicate charge, support goodwill, other)
- if **Other** is selected, a free-text explanation should be provided
- manual credits can be tracked and reported as adjustment records, but provider automation for credits is integration-dependent
- adjustment records are visible in the Platform Admin billing adjustment report for reconciliation

For self-hosted or alternative provider integrations, the refund workflow may need changes in:

- provider API calls
- webhook event names and status mapping
- settlement timing assumptions
- customer notification copy and compliance handling

## Platform Admin Pricing Overrides

For hosted deployments, superusers can override default public prices from the Platform Admin panel.

### Access

- Navigate to **Platform Admin** -> **Pricing**
- URL: `/platform-admin/pricing/`
- Access is restricted to superusers

### What It Does

- Overrides **Pro**, **Team Small**, **Team Medium**, and **Team Large** prices
- Stores both **inc VAT** and **ex VAT** amounts
- Uses settings defaults when an override is disabled or blank
- Updates the public pricing page and new checkout pricing without a code deploy

### Scope and Limitations

- Overrides affect new subscriptions and displayed prices
- Existing subscriptions are not retroactively repriced
- Organisation and Enterprise pricing are managed separately as bespoke plans
- Refunds and credits resulting from pricing or promotion changes are handled separately from price overrides

## Upgrading Your Plan

You can upgrade to a higher tier at any time:

1. Go to **Profile** > **Subscription**
2. Click **Upgrade Plan**
3. Select your new plan
4. Complete the checkout

**Prorated Billing:**

- You'll be charged the difference between your current plan and the new plan
- The proration is calculated based on remaining days in your billing cycle
- Your next billing date remains the same

**What Happens:**

- New features are available immediately
- All existing surveys are preserved
- No data loss or downtime
- Survey limits update automatically

## Downgrading Your Plan

To downgrade to a lower tier:

1. Go to **Profile** > **Subscription**
2. Click **Change Plan**
3. Select a lower tier
4. Confirm the change

**Important:**

- Downgrades take effect at the end of your current billing period
- You retain access to current features until the period ends
- If you have more surveys than the new limit allows, excess surveys will be automatically closed
- **Organisation members cannot downgrade** - only individual users can downgrade their accounts

**Survey Auto-Closure:**
If downgrading would exceed survey limits:

- Your oldest surveys are automatically closed (not deleted)
- You'll receive an email notification listing which surveys were closed
- Closed surveys and their responses remain accessible
- You can reopen surveys by upgrading again

## Cancelling Your Subscription

### How to Cancel

1. Log in to CheckTick
2. Go to **Profile** > **Subscription**
3. Click **Cancel Subscription**
4. Confirm your cancellation

**Rate Limiting:** For security, you can only cancel your subscription 5 times per hour.

### What Happens When You Cancel

**Immediate Effects:**

- Your subscription is marked for cancellation
- You receive a confirmation email
- Billing stops at the end of the current period

**Until Period End:**

- You retain full access to paid features
- You can continue using your account normally
- No refunds for partial months

**After Period End:**

- Your account downgrades to Individual (Free)
- If you have more than 3 surveys, excess surveys are automatically closed
- All data is preserved
- You can reactivate by subscribing again

### Reactivating After Cancellation

If you cancel and change your mind before the period ends:

1. Go to **Profile** > **Subscription**
2. Click **Reactivate Subscription**
3. Your subscription continues without interruption

After the period ends, simply sign up for a new subscription to restore paid features.

## Failed Payments & Past Due Accounts

### What Happens with Failed Payments

If a payment fails:

1. **Day 1**: Payment attempt fails
   - You receive an email notification
   - Account remains active
   - Payment retry is attempted automatically

2. **Day 3**: First retry
   - Payment attempt made again
   - Email reminder sent

3. **Day 7**: Second retry
   - Final automatic retry
   - Final warning email

4. **Day 10**: Subscription suspended
   - Account marked as "Past Due"
   - Access to paid features is limited
   - All data remains safe

### Resolving Past Due Status

To fix a past due account:

1. Log in to CheckTick
2. Go to **Profile** > **Subscription**
3. Click **Update Payment Method**
4. Enter valid payment details
5. Payment is processed immediately
6. Access is restored within minutes

## Refunds & Cancellation Policy

### Refund Policy

In accordance with UK Consumer Contracts Regulations:

- **14-day right to cancel** for consumers on initial subscriptions
- **No automatic refunds** on subscription renewals or unused subscription periods
- We may grant refunds at our discretion beyond the 14-day period - contact us to discuss
- **Pro-rated refunds** for annual plans are supported via the platform admin billing view. The refund amount is calculated as `amount × (days_remaining / total_days)`, rounded to the nearest penny. Monthly subscriptions always refund the full amount.

### Requesting a Refund

To request a refund within the 14-day cancellation period:

1. Email us at [support@checktick.uk](mailto:support@checktick.uk)
2. Include your account email and order number
3. Refunds are processed within 14 days of the cancellation request
4. Refunds go back to the original payment method

For more details, see our [Refund Policy](/docs/refund-policy/).

## Team & Organisation Billing

### How Team Billing Works

- **One billing owner**: The team creator owns the subscription
- **Shared features**: All team members get access to team features
- **Per-team pricing**: Each team is billed separately
- **Member changes**: Adding/removing members doesn't affect billing until next renewal

### Organisation Billing

Organisations are billed per user per month, with a choice of monthly or
annual billing cycle set by the platform admin:

- **Base rate**: £24/user/month (inc VAT) at the default `VAT_RATE=0.20`, derived from the `BASE_SEAT_PRICE_EX_VAT` setting (£20 ex VAT)
- **Annual billing**: When the org's billing cycle is set to annual, the annual discount (`ANNUAL_DISCOUNT_PERCENT`, default 20%) is applied to the monthly rate × 12. The platform admin sets this per-organisation in the org form.
- **Minimum commitment**: Contact sales
- **Invoice billing**: Available for organisations

### Switching Billing Cycle

Existing subscribers can switch between monthly and annual billing at any time
from the subscription portal. Because GoCardless doesn't support changing the
`interval_unit` on an existing subscription, switching cancels the current
subscription and creates a new one with the new billing cycle, reusing the
existing Direct Debit mandate (no re-authorisation needed).

- **Monthly → Annual**: The new annual subscription charges the discounted
  annual amount on the next billing date.
- **Annual → Monthly**: The new monthly subscription charges the standard
  monthly amount on the next billing date.
- The old subscription remains active until the end of its current billing
  period; the new subscription starts immediately.

### Managing Team Members

Team admins can:

- Add members (up to team limit)
- Remove members (immediate access revocation)
- Change member roles
- Transfer team ownership

**Billing impact:**

- Adding members: No immediate charge, reflected in next renewal
- Removing members: Access ends immediately, credit applied to next billing
- Over limit: Must upgrade team size or remove members

## Security & Privacy

### Payment Security

- All payments processed by a **PCI-compliant payment provider**
- CheckTick never stores complete payment card or bank details
- SSL/TLS encryption for all payment pages
- Strong Customer Authentication (SCA) for card payments

### Data Protection

- Your subscription data is encrypted
- Payment history is secure and private
- Billing emails use encrypted connections
- GDPR compliant data handling

### Rate Limiting

For security, billing operations are rate-limited:

- **Subscription cancellation**: 5 attempts per hour
- **Checkout start**: 10 attempts per hour per user
- **Webhook callbacks**: 100 per minute per IP
- **Platform-admin refund action**: 20 attempts per hour per superuser

Webhook callbacks are accepted only when the provider signature is valid and a webhook secret is configured. Each event is deduplicated by its provider event id (recorded in the `WebhookEvent` table) so a replayed webhook cannot re-run handlers or duplicate payment records (F14).

## Invoices & Receipts

### Accessing Invoices

1. Log in to CheckTick
2. Go to **Profile** > **Payment History**
3. Click **Download Invoice** next to any payment

### Invoice Details

Each invoice includes:

- Invoice number
- Billing date
- Payment amount
- VAT/Tax details (if applicable)
- Payment method
- Subscription period

### VAT for UK Customers

- UK VAT at the configured `VAT_RATE` (default 20%) applies to all customers
- VAT is automatically computed from the ex-VAT base at checkout
- VAT invoices are available for download

## Troubleshooting

### Common Issues

**"Payment failed" error:**

- Check payment details are correct
- Ensure sufficient funds available
- Try a different payment method
- Contact your bank to authorize the payment

**"Subscription not updating" issue:**

- Wait 5 minutes for webhook processing
- Refresh the page
- Clear browser cache
- Contact support if persists

**"Cannot cancel subscription" error:**

- You may have hit the rate limit (5 per hour)
- Wait an hour and try again
- Organisation members cannot self-cancel
- Contact support for assistance

**"Survey limit exceeded" after downgrade:**

- This is expected behavior
- Oldest surveys are auto-closed
- Check your email for the list of closed surveys
- Upgrade again to reopen surveys

### Getting Help

If you encounter billing issues:

**For FREE and PRO users:**

- Check the [FAQ section](/docs/getting-started/#frequently-asked-questions)
- Visit [Community Discussions](https://github.com/eatyourpeas/checktick/discussions)
- Email support: [support@checktick.uk](mailto:support@checktick.uk)

**For ORganisaTION and ENTERPRISE users:**

- Priority support email: [enterprise@checktick.uk](mailto:enterprise@checktick.uk)
- Phone support (if applicable to your plan)
- Dedicated account manager (Enterprise only)

## Self-Hosted Deployments

If you're running CheckTick in self-hosted mode:

### Configuration

Set in your `.env` file:
```bash
SELF_HOSTED=true
```

### What This Means

- **No billing integration**: Payment features are completely disabled
- **Enterprise features**: All users get Enterprise-tier features automatically
- **No subscription required**: Unlimited surveys, members, and features
- **No payment UI**: Billing pages and upgrade prompts are hidden
- **Full control**: You manage your own infrastructure and costs

### Self-Hosted Costs

- **Software**: Free and open source
- **Infrastructure**: Your responsibility (servers, databases, storage)
- **Support**: Community support via GitHub Discussions
- **Updates**: Manage your own version updates

For self-hosting setup instructions, see the [Self-Hosting Guide](/docs/self-hosting/).

## Legal & Terms

### Terms of Service

By subscribing to CheckTick, you agree to:

- Our [Terms of Service](/docs/terms-of-service/)
- Our [Privacy Notice](/docs/privacy-notice/)
- Our [Refund Policy](/docs/refund-policy/)

### Data Retention

- **Active subscriptions**: All data retained indefinitely
- **Cancelled subscriptions**: Data retained for 90 days on Free tier
- **Closed surveys**: Retained indefinitely unless manually deleted
- **Deleted accounts**: Data removed after 30-day grace period

For more details, see our [Data Governance](/docs/data-governance/) documentation.

## Contact Sales

For Organisation or Enterprise plans:

- **Email**: [sales@checktick.uk](mailto:sales@checktick.uk)
- **Custom quotes**: Volume discounts available
- **Annual contracts**: Significant savings on yearly billing
- **Invoice billing**: Available for large organisations

## Next Steps

- [Compare all plans and pricing](/pricing/)
- [Create a free account](/signup/)
- [Read the Getting Started Guide](/docs/getting-started/)
- [Learn about Account Types](/docs/getting-started-account-types/)
