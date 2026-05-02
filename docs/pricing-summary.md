---
title: CheckTick Pricing Summary
category: None
priority: 2
---

# CheckTick Pricing Summary

**Date: December 2025**
**Version: 1.1**

---

## Overview

CheckTick is a secure survey platform designed for healthcare and research organisations. We offer tiered pricing to accommodate individuals, teams, and enterprise deployments.

All payments are processed securely through our UK-based payment provider.

---

## Pricing Tiers

### Individual Plans

| Plan | Monthly Price (inc VAT) | Key Features |
|------|--------------------------|--------------|
| **Free** | £0 | Up to 3 active surveys (all encrypted), unlimited responses, no patient data templates |
| **Pro** | £6 | Unlimited encrypted surveys, patient data collection, collaboration, email support |

---

### Team Plans

Fixed-price plans for collaborative teams.

| Plan | Monthly Price (inc VAT) | Members | Surveys |
|------|--------------------------|---------|---------|
| **Team Small** | £30 | 5 | 50 |
| **Team Medium** | £90 | 15 | 50 |
| **Team Large** | £300 | 50 | 50 |

All team plans include: Role-based access (Admin/Creator/Viewer), team encryption management.

---

### Organisation Tier

Per-seat pricing for larger organisations requiring flexible user counts.

| Component | Monthly Price |
|-----------|---------------|
| **Per user (typical hosted rate)** | £6/user (inc VAT) |

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
| 10 | £300 | £3,000 | £600 |
| 25 | £750 | £7,500 | £1,500 |
| 50 | £1,500 | £15,000 | £3,000 |
| 100 | £3,000 | £30,000 | £6,000 |

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
| **Per-seat Licensing** | Per user per year | £300/user/year |
| **Infrastructure** | Cloud hosting, database, vault, backups, monitoring | £3,000 - £15,000/year |
| **Custom Development** | Bespoke features (if required) | Quoted separately |

#### Example Enterprise Pricing

| Deployment | Users | Platform | Seats | Infrastructure | Total Annual |
|------------|-------|----------|-------|----------------|--------------|
| Small NHS Trust | 25 | £5,000 | £7,500 | £5,000 | **£17,500** |
| Medium NHS Trust | 75 | £7,500 | £22,500 | £8,000 | **£38,000** |
| Large NHS Trust | 150 | £10,000 | £45,000 | £12,000 | **£67,000** |
| Academic Institution | 50 | £5,000 | £15,000 | £6,000 | **£26,000** |

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

Document version: 1.2
Last updated: 2 May 2026
