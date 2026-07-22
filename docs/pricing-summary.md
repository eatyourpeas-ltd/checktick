---
title: CheckTick Pricing Summary
category: None
priority: 2
---

# CheckTick Pricing Summary

**Date: July 2026**
**Version: 2.0**

---

## Overview

CheckTick is a secure survey platform designed for healthcare and research organisations. We offer tiered pricing to accommodate individuals, teams, and enterprise deployments.

All payments are processed securely through our UK-based payment provider.

All prices below assume the default `VAT_RATE=0.20` (20% UK VAT) and `BASE_SEAT_PRICE_EX_VAT=20` (£20 per seat ex VAT). Both are environment variables; changing them updates checkout amounts, invoices, and the public pricing page without a code deploy.

---

## Pricing Tiers

### Individual Plans

| Plan | Monthly (inc VAT) | Annual (inc VAT) | Key Features |
|------|-------------------|------------------|--------------|
| **Free** | £0 | £0 | Up to 3 active surveys (all encrypted), unlimited responses, no patient data templates |
| **Pro** | £24/month | £230.40/year (£19.20/mo equiv) | Unlimited encrypted surveys, patient data collection, collaboration, email support |

---

### Team Plans

Fixed-price plans for collaborative teams. Annual billing includes a 20% discount.

| Plan | Monthly (inc VAT) | Annual (inc VAT) | Members | Surveys |
|------|-------------------|------------------|---------|---------|
| **Team Small** | £120/month | £1,152/year (£96/mo equiv) | 5 | 50 |
| **Team Medium** | £360/month | £3,456/year (£288/mo equiv) | 15 | 50 |
| **Team Large** | £1,200/month | £11,520/year (£960/mo equiv) | 50 | 50 |

All team plans include: Role-based access (Admin/Creator/Viewer), team encryption management.

---

### Organisation Tier

Per-seat pricing for larger organisations requiring flexible user counts.

| Component | Monthly Price |
|-----------|---------------|
| **Per user (typical hosted rate)** | £24/user (inc VAT) |

#### Included Features

- Unlimited members (based on seats purchased)
- Unlimited surveys
- Multiple teams within organisation
- Private datasets
- Advanced data governance features
- Priority email support
- Hosted on CheckTick shared infrastructure

#### Example Organisation Pricing

| Users | Monthly | Annual | Annual Saving |
|-------|---------|--------|---------------|
| 10 | £1,200 | £12,000 | £2,400 |
| 25 | £3,000 | £30,000 | £6,000 |
| 50 | £6,000 | £60,000 | £12,000 |
| 100 | £12,000 | £120,000 | £24,000 |

---

### Enterprise Tier

Bespoke pricing for dedicated, independently hosted deployments.

Enterprise tier provides a fully independent deployment of the CheckTick platform, including dedicated infrastructure, database, and secrets management—all managed by our team on the customer's behalf.

#### What's Included (vs Organisation)

| Component | Organisation | Enterprise |
|-----------|--------------|------------|
| Hosting | Shared infrastructure | Dedicated infrastructure |
| Database | Shared PostgreSQL | Dedicated PostgreSQL instance |
| Secrets Management | Shared | Dedicated HashiCorp Vault |
| Custom Branding | Logo only | Full white-label (logo, colours, domain) |
| SSO/OIDC | Not included | Included |
| Support | Priority email | Named account manager |
| SLA | Best effort | 99.9% uptime guarantee |
| Data Residency | UK/EU | Customer choice of region |

#### Enterprise Pricing Components

| Component | Description | Typical Cost |
|-----------|-------------|--------------|
| **Base Platform Fee** | Annual licence and support | £5,000 - £10,000/year |
| **Per-seat Licensing** | Per user per year (based on £20/seat/month ex VAT) | £288/user/year (inc VAT at 20%) |
| **Infrastructure** | Cloud hosting, database, vault, backups, monitoring | £3,000 - £15,000/year |
| **Custom Development** | Bespoke features (if required) | Quoted separately |

#### Example Enterprise Pricing

| Deployment | Users | Platform | Seats | Infrastructure | Total Annual |
|------------|-------|----------|-------|----------------|--------------|
| Small NHS Trust | 25 | £5,000 | £7,200 | £5,000 | **£17,200** |
| Medium NHS Trust | 75 | £7,500 | £21,600 | £8,000 | **£37,100** |
| Large NHS Trust | 150 | £10,000 | £43,200 | £12,000 | **£65,200** |
| Academic Institution | 50 | £5,000 | £14,400 | £6,000 | **£25,400** |

*Infrastructure costs vary by: hosting region, redundancy requirements, backup frequency, and compliance needs.*

---

## Billing Information

### Payment Processing

- **Currency:** GBP (£)
- **Billing Cycles:** Monthly (default for hosted tiers)
- **Payment Methods:** Direct Debit (UK bank accounts), Credit/Debit cards
- **UK Only:** CheckTick is currently available to UK customers only

## Platform Admin Pricing Overrides

Hosted deployments can override Pro/Team prices in the Platform Admin panel without a code release.

- **Path:** `/platform-admin/pricing/`
- **Access:** Superuser only
- **Behavior:** Active overrides change public pricing display and new checkout amounts
- **Fallback:** Disabling an override reverts to settings defaults
- **Note:** Existing subscriptions are not retroactively repriced

### Refund Policy

In accordance with UK Consumer Contracts Regulations:

- **14-day right to cancel** for consumers on initial subscriptions
- Refunds may be granted at our discretion beyond 14 days
- No automatic refunds on subscription renewals
- See full [Refund Policy](/docs/refund-policy/) for details

---

## Contact

For Organisation and Enterprise pricing enquiries:

- **Email:** [sales@checktick.com](mailto:sales@checktick.com)
- **Support:** [support@checktick.com](mailto:support@checktick.com)

---

## Self-Hosted Option

Organisations may also choose to self-host CheckTick on their own infrastructure using our open-source codebase (AGPL-3.0 licence). Self-hosted deployments include all Enterprise features but require the customer to manage their own infrastructure.

Optional paid support contracts are available for self-hosted customers.

---

**CheckTick**
*Secure surveys for healthcare and research*

Document version: 2.0
Last updated: 21 July 2026
