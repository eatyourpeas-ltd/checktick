---
title: Billing & Subscriptions
category: billing
priority: 1
---

# Billing & Subscriptions

This guide explains how billing works in CheckTick, including subscriptions, payments, upgrades, and cancellations.

## Overview

CheckTick uses Paddle as our payment processor to handle all billing securely. We offer flexible subscription plans to suit individual users, small teams, and large organizations.

> **Note for Self-Hosters:** If you're running CheckTick with `SELF_HOSTED=true` in your environment configuration, billing features are automatically hidden and all users get Enterprise-level features without payment requirements.

## Available Plans

### Individual Plans

**Individual (Free)**
- £0/month
- Up to 3 active surveys
- Unlimited responses
- Personal encryption
- Basic features

**Individual Pro**
- £5/month
- Unlimited surveys
- Unlimited responses
- Collaboration features
- Email support

### Team Plans

Teams provide shared billing and collaboration for groups of 5-20 users.

**Team Small**
- £25/month
- 5 team members
- 50 active surveys
- Role-based access (Admin/Creator/Viewer)
- Team encryption management

**Team Medium**
- £50/month
- 10 team members
- 50 active surveys
- All Team Small features

**Team Large**
- £100/month
- 20 team members
- 50 active surveys
- All Team Medium features

### Organization & Enterprise

**Organisation**
- £30/user/month (contact sales)
- Unlimited members and surveys
- Multiple teams within organization
- Private datasets
- Advanced governance features
- Priority support

**Enterprise**
- Custom pricing (contact sales)
- Self-hosted option
- Custom branding
- SSO/OIDC integration
- Dedicated support
- SLA guarantee

## Payment Methods

CheckTick accepts the following payment methods through Paddle:

- Credit cards (Visa, Mastercard, American Express)
- Debit cards
- PayPal
- Google Pay
- Apple Pay

All payments are processed securely by Paddle, our payment partner. CheckTick never stores your complete payment information.

## Starting a Subscription

### Signing Up with a Paid Plan

1. Go to the [pricing page](/pricing/) or [sign up page](/signup/)
2. Select your desired plan
3. Complete the registration form
4. Click "Create account"
5. You'll be redirected to Paddle's secure checkout
6. Enter your payment details
7. Complete the payment
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
- Payment method (last 4 digits)
- Subscription status (Active/Past Due/Cancelled)

### Updating Payment Method

1. Log in to CheckTick
2. Go to **Profile** > **Subscription**
3. Click **Update Payment Method**
4. You'll be redirected to Paddle's secure portal
5. Update your payment details
6. Changes take effect immediately

### Viewing Payment History

1. Log in to CheckTick
2. Go to **Profile** > **Payment History**

You can:
- View all past invoices
- Download invoice PDFs
- See payment dates and amounts
- Check payment status

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
- **Organization members cannot downgrade** - only individual users can downgrade their accounts

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
   - Paddle retries payment automatically

2. **Day 3**: First retry
   - Paddle attempts payment again
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

- **7-day money-back guarantee** for new subscriptions
- **Prorated refunds** for annual plans cancelled early (contact support)
- **No refunds** for partial months on monthly plans
- **Downgrade credits** applied to future billing when downgrading

### Requesting a Refund

To request a refund within the 7-day guarantee period:

1. Email support at [support@checktick.uk](mailto:support@checktick.uk)
2. Include your account email and reason for refund
3. We'll process the refund within 5-7 business days
4. Refunds go back to the original payment method

For more details, see our [Refund Policy](/docs/refund-policy/).

## Team & Organization Billing

### How Team Billing Works

- **One billing owner**: The team creator owns the subscription
- **Shared features**: All team members get access to team features
- **Per-team pricing**: Each team is billed separately
- **Member changes**: Adding/removing members doesn't affect billing until next renewal

### Organization Billing

Organizations are billed per user per month:

- **Base rate**: £30/user/month
- **Minimum commitment**: Contact sales
- **Annual discounts**: Available for yearly contracts
- **Invoice billing**: Available for organizations

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

- All payments processed by **Paddle**, a PCI-compliant payment provider
- CheckTick never stores complete payment card details
- SSL/TLS encryption for all payment pages
- 3D Secure authentication for card payments

### Data Protection

- Your subscription data is encrypted
- Payment history is secure and private
- Billing emails use encrypted connections
- GDPR compliant data handling

### Rate Limiting

For security, billing operations are rate-limited:

- **Subscription cancellation**: 5 attempts per hour
- **Payment updates**: 10 attempts per minute
- **Webhook callbacks**: 10 per minute per IP
- **Checkout sessions**: 100 per minute per IP

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

### VAT for EU Customers

- VAT is automatically calculated based on your location
- UK VAT (20%) applies for UK customers
- EU VAT rates apply for EU customers
- Reverse charge available for businesses with valid VAT numbers

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
- Organization members cannot self-cancel
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

**For ORGANIZATION and ENTERPRISE users:**
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

For Organization or Enterprise plans:

- **Email**: [sales@checktick.uk](mailto:sales@checktick.uk)
- **Custom quotes**: Volume discounts available
- **Annual contracts**: Significant savings on yearly billing
- **Invoice billing**: Available for large organizations

## Next Steps

- [Compare all plans and pricing](/pricing/)
- [Create a free account](/signup/)
- [Read the Getting Started Guide](/docs/getting-started/)
- [Learn about Account Types](/docs/getting-started-account-types/)
