---
title: Account Types & Organizations
category: getting-started
priority: 2
---

This guide explains the account tier system in CheckTick, helping you choose the right option for your needs.

## Account Tiers Overview

CheckTick offers four account tiers: **FREE**, **PRO**, **ORGANIZATION**, and **ENTERPRISE**. Each tier builds on the previous one, adding more features and capacity.

## Quick Comparison

| Feature | FREE | PRO | ORGANIZATION | ENTERPRISE |
| --- | --- | --- | --- | --- |
| **Active Surveys** | 3 | Unlimited | Unlimited | Unlimited |
| **Survey Responses** | Unlimited | Unlimited | Unlimited | Unlimited |
| **Team Collaboration** | ✗ | Editors only | Full (Editors + Viewers) | Full (Editors + Viewers) |
| **Collaborators per Survey** | N/A | 10 | Unlimited | Unlimited |
| **Encryption** | Self-managed keys | Self-managed keys | Organization-managed keys | Organization-managed keys |
| **Role-Based Access** | ✗ | Limited | Full (Admin, Creator, Viewer) | Full (Admin, Creator, Viewer) |
| **Custom Branding** | ✗ | ✗ | ✗ | ✓ (Logo, themes, fonts) |
| **Self-Hosted Option** | ✗ | ✗ | ✗ | ✓ |
| **SSO/OIDC** | ✗ | ✗ | ✗ | ✓ |
| **Best For** | Getting started | Active users | Teams | Institutions |

## 👤 - FREE Tier

**Best for:** Getting started, personal research, occasional survey use

***Survey Limits:***

- **3 active surveys maximum**
- Unlimited responses per survey
- Must close or delete a survey to create a new one

***Features***

- Create and manage your own surveys
- Full control over your data and encryption keys
- Simple setup and management
- Full API access
- Export to CSV, JSON, Excel
- AI-assisted survey generator
- Can be invited to collaborate on other surveys

***Key Characteristics***

- **Data ownership:** You own all surveys and responses
- **Key management:** You manage encryption keys yourself
- **Recovery:** If you lose encryption keys, data cannot be recovered
- **Collaboration:** Cannot invite others to your surveys
- **Cost:** Free

## 💎 - PRO Tier

**Best for:** Active individual users, researchers running multiple studies

***Survey Limits:***

- **Unlimited active surveys**
- Unlimited responses per survey

***Features***

- Everything in FREE, plus:
- **No survey limit** - create as many surveys as you need
- Can add editors to your surveys
- Up to 10 collaborators per survey
- Personal survey management

***Key Characteristics***

- **Data ownership:** You own all surveys and responses
- **Key management:** You manage encryption keys yourself
- **Recovery:** If you lose encryption keys, data cannot be recovered
- **Collaboration:** Limited - can add editors only (not viewers)
- **Cost:** Subscription-based

## 🏢 - ORGANIZATION Tier

**Best for:** Healthcare teams, research institutions, collaborative projects

***Survey Limits:***

- **Unlimited active surveys**
- Unlimited responses per survey
- Unlimited collaborators per survey

***Features***

- Everything in PRO, plus:
- **Full team collaboration** with viewers and editors
- Role-based access control (Admin, Creator, Viewer)
- Organization-level encryption key management
- Key recovery and backup services
- Shared survey groups
- Centralized audit logs

***Key Characteristics***

- **Data ownership:** Organization owns surveys, members can access based on roles
- **Key management:** Organization can recover lost encryption keys
- **Recovery:** Admins can help recover access to encrypted data
- **Collaboration:** Full - add both editors and viewers with unlimited collaborators
- **Audit trail:** All actions are logged for compliance
- **Cost:** Contact sales for team pricing

## 🏆 - ENTERPRISE Tier

**Best for:** Large institutions, self-hosted deployments, custom branding requirements

***Survey Limits:***

- **Unlimited active surveys**
- Unlimited responses per survey
- Unlimited collaborators per survey

***Features***

- Everything in ORGANIZATION, plus:
- **Custom branding** - configure logo, themes, and fonts
- **Self-hosted option** - run on your own infrastructure
- **SSO/OIDC integration** - enterprise authentication
- Complete data control
- Professional support available
- Platform-level branding customization

***Key Characteristics***

- **Data ownership:** Organization owns all data (or self-hosted)
- **Key management:** Organization-managed or self-hosted
- **Recovery:** Full administrative controls
- **Collaboration:** Full team features with unlimited scale
- **Branding:** Web UI at `/branding/` or CLI via `python manage.py configure_branding`
- **Deployment:** Self-hosted on your own servers
- **Cost:** Self-hosted (open source) or contact for hosted enterprise

## Self-Hosted Mode

When running CheckTick in self-hosted mode (with `SELF_HOSTED=true` in settings):

- All users automatically get **Enterprise tier features**
- No payment integration required
- Superusers can configure platform branding via:
  - Web UI: Navigate to `/branding/`
  - CLI: `python manage.py configure_branding --theme nord --logo path/to/logo.png`
- Full control over infrastructure and data
- Suitable for institutions requiring on-premises deployment

## Choosing the Right Tier

### Choose FREE Tier If

- You're just getting started with CheckTick
- You need 3 or fewer active surveys at a time
- You work independently
- You don't need collaboration features
- You want to try CheckTick with no cost

**Example use cases:**

- Learning to use CheckTick
- Small personal projects
- Occasional survey needs
- Testing before upgrading

### Choose PRO Tier If

- You need more than 3 active surveys
- You work independently but at scale
- You want to add editors to your surveys
- You need unlimited survey capacity
- You're comfortable managing your own keys

**Example use cases:**

- Active researchers running multiple studies
- Independent consultants with many clients
- Personal health tracking at scale
- Individual clinicians managing patient surveys

### Choose ORGANIZATION Tier If

- You work as part of a team
- Multiple people need access to surveys
- You need viewer roles (read-only access)
- You need institutional oversight
- Data recovery is important for compliance
- You need audit trails for regulations

**Example use cases:**

- Hospital departments
- Research institutions
- Healthcare teams
- University research groups
- Multi-clinician practices

### Choose ENTERPRISE Tier If

- You need custom branding (logos, themes, fonts)
- You require self-hosted deployment
- You need SSO/OIDC integration
- Complete data control is essential
- You have institutional infrastructure requirements

**Example use cases:**

- Large healthcare systems
- Government institutions
- Organizations with strict data residency requirements
- Institutions requiring custom branding
- Self-hosted deployments

## Organization Roles Explained

Organizations (ORGANIZATION and ENTERPRISE tiers) support role-based access control:

### Admin

- **Full control** over the organization
- Can add/remove members and change their roles
- Can access all organization surveys
- Can manage organization settings
- Can recover encryption keys for the organization

### Creator

- Can create and manage their own surveys
- Can be granted access to specific surveys by admins
- Cannot manage organization members
- Can collaborate on surveys they're invited to

### Viewer

- Read-only access to surveys they're invited to (ORGANIZATION/ENTERPRISE tiers only)
- Can view survey results and responses
- Cannot create or edit surveys
- Cannot manage organization members
- **Note:** Viewer role is not available in FREE or PRO tiers

## Security and Encryption Differences

### Individual Tier Security (FREE/PRO)

**Encryption Model:**

- You generate and manage all encryption keys
- Keys are derived from passwords you create
- Recovery phrases provided for key backup
- **No external recovery options**

> **Risk Considerations:**
>
> - ⚠️ Lost passwords + recovery phrases = permanent data loss
> - ⚠️ No administrative support for key recovery
> - ⚠️ All security responsibility on individual user
>

### Organization Tier Security (ORGANIZATION/ENTERPRISE)

**Encryption Model:**

- Organization manages master encryption keys
- Individual survey keys derived from organization keys
- Administrative key escrow and recovery
- **Organization can recover lost access**

**Enhanced Security Features:**

- Professional key management
- Administrative oversight
- Audit logging for compliance
- Backup and recovery procedures
- Role-based access controls

## Upgrading Your Tier

You can upgrade from one tier to another as your needs grow:

### FREE → PRO

- Removes the 3 survey limit
- Enables basic collaboration (editors only)
- All existing surveys are preserved
- Keys remain self-managed

### PRO → ORGANIZATION

- Enables full team collaboration with viewer roles
- Unlimited collaborators per survey
- Organization-managed encryption keys
- Administrative key recovery options
- All existing surveys transfer to organization

### ORGANIZATION → ENTERPRISE

- Available for self-hosted deployments
- Adds custom branding capabilities
- SSO/OIDC integration
- Contact sales for hosted enterprise options

### Upgrade Process

1. **Go to your Profile page**
2. **Click "Upgrade Account"** (or contact sales for ORGANIZATION/ENTERPRISE)
3. **Choose your new tier**
4. **Your existing surveys are preserved**
5. **New features become available immediately**

### What Happens During Upgrade

**Your surveys:**

- All existing surveys are preserved
- Survey data and responses remain intact
- You maintain full access
- Encryption keys are migrated if moving to ORGANIZATION tier

**Your access:**

- New tier features become available immediately
- You can start using collaboration features (if applicable)
- You can invite team members (ORGANIZATION/ENTERPRISE)
- You get administrative key recovery options (ORGANIZATION/ENTERPRISE)

**Team building (ORGANIZATION/ENTERPRISE):**

- Invite colleagues via email
- Assign appropriate roles (Admin, Creator, Viewer)
- Share existing surveys with team members
- Collaborate on new surveys

### Important Notes About Upgrading

- ⚠️ **Some upgrades are permanent** - moving to ORGANIZATION tier changes key management
- **No data loss** - all your surveys and responses are preserved
- **Enhanced security** - organization key management is more robust (ORGANIZATION/ENTERPRISE)
- **Better compliance** - audit trails and administrative oversight (ORGANIZATION/ENTERPRISE)
- **FREE → PRO is reversible** if you reduce your survey count to 3 or fewer

## Getting Help

### For FREE and PRO Tiers

- Use the in-app help system
- Check the [User Documentation](./getting-started.md)
- Join the [Community Discussions](https://github.com/eatyourpeas/checktick/discussions)

### For ORGANIZATION and ENTERPRISE Tiers

- All FREE/PRO resources, plus:
- Organization admin training materials
- [User Management Guide](./user-management.md)
- [Authentication Setup](./authentication-and-permissions.md)
- [Branding Configuration Guide](./branding-and-theme-settings.md) (ENTERPRISE only)
- Priority support for compliance questions

## Compliance Considerations

### FREE and PRO Tiers

- **HIPAA/GDPR:** User is responsible for compliance
- **Data retention:** User manages all data lifecycle
- **Audit trails:** Limited to basic system logs
- **Key management:** No institutional oversight

### ORGANIZATION and ENTERPRISE Tiers

- **HIPAA/GDPR:** Organization-level compliance support
- **Data retention:** Administrative controls and policies
- **Audit trails:** Comprehensive logging for all actions
- **Key management:** Professional-grade key escrow and recovery

## Next Steps

### Ready to Get Started?

**For FREE Tier:**

1. Complete the signup process
2. Read the [Getting Started Guide](./getting-started.md)
3. Create your first survey (up to 3)

**For PRO Tier:**

1. Sign up for FREE first
2. Upgrade to PRO from your Profile page
3. Create unlimited surveys

**For ORGANIZATION Tier:**

1. Contact sales or upgrade from PRO
2. Set up your organization name
3. Read the [User Management Guide](./user-management.md)
4. Invite your team members
5. Create collaborative surveys

**For ENTERPRISE Tier (Self-Hosted):**

1. Follow the [Self-Hosting Guide](./self-hosting.md)
2. Configure branding via `/branding/` or CLI
3. Set up SSO/OIDC if needed
4. Read the [Branding Configuration Guide](./branding-and-theme-settings.md)

### Questions?

Visit our [Community Discussions](https://github.com/eatyourpeas/checktick/discussions) or check the [FAQ section](./getting-started.md#frequently-asked-questions) for common questions about account types.
