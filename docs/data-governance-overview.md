---
title: Data Governance Overview
category: None
---

CheckTick takes data protection and governance seriously. This guide explains how we handle your survey data, who can access it, and your responsibilities as a data custodian.

## What is Data Governance?

Data governance is the framework that ensures survey data is:

- **Secure** - Protected from unauthorized access
- **Compliant** - Meets legal and regulatory requirements
- **Controlled** - Only accessible to authorized people
- **Time-limited** - Not kept longer than necessary
- **Audited** - All access is logged and traceable

## Why Does It Matter?

When you collect survey data, especially in healthcare, you may be handling sensitive or personal information. Good data governance protects:

- **Participants** - Their privacy and confidentiality
- **Your organization** - From data breaches and compliance violations
- **You** - From legal liability and reputational damage

## Key Principles

### 1. Access Control

Not everyone can access survey data. Access is strictly controlled based on roles:

| Role | Can View Responses | Can Download Data | Can Extend Retention |
|------|-------------------|-------------------|---------------------|
| **Survey Creator** | ✅ Own surveys | ✅ Own surveys | ✅ Own surveys |
| **Organization Owner** | ✅ All org surveys | ✅ All org surveys | ✅ All org surveys |
| **Data Custodian*** | ❌ No | ✅ Assigned surveys | ❌ No |
| **Editor** | ❌ No | ❌ No | ❌ No |
| **Viewer** | ❌ No | ❌ No | ❌ No |

\* *Optional role - can be assigned per survey for data management delegation*

**Organization Administrative Authority**
To ensure accountability, every CheckTick Organization must have at least one designated Owner.

*Provisioning*:

Owners have the exclusive right to invite new members and assign roles (Editor, Viewer, Data Custodian).

*Deprovisioning*:

Owners are responsible for removing users who no longer require access (e.g., staff who have left the Trust).

*CheckTick Support:*

CheckTick staff will only intervene in account management upon a verified request from the registered Organization Owner or via a formal legal instruction.

### 2. Survey Closure

Data can only be downloaded after a survey has been formally **closed**. Closing a survey:

- Locks all responses (no further edits)
- Enables data export functionality
- Starts the retention countdown
- Triggers automatic deletion warnings

This ensures data is only extracted when collection is complete.

### 3. Time-Limited Storage

Survey data is **not kept indefinitely**. By default:

- Data is kept for **6 months** after survey closure
- You receive warnings at **1 month**, **1 week**, and **1 day** before deletion
- Data is automatically deleted unless you extend retention
- Maximum retention period is **24 months**

### 4. Audit Trail

Every data access is logged:

- Who downloaded data
- When they downloaded it
- What survey data was downloaded
- Their stated purpose
- Their IP address

Organization administrators receive email notifications for all data downloads.

### 5. User Responsibility

When you download data, you become responsible for:

- Storing it securely (encrypted, password-protected location)
- Not sharing it inappropriately
- Deleting it when no longer needed
- Reporting any data breaches
- Complying with your organization's data policies

## Data Lifecycle

```
┌─────────────────┐
│ Survey Created  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Collect Data    │ ← Responses locked in database (encrypted)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Survey Closed   │ ← Retention period starts (6 months default)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Data Available  │ ← Can be downloaded by authorized users
│  for Export     │   All downloads logged and audited
└────────┬────────┘
         │
         ├─────────► Can extend retention (up to 24 months)
         │
         ▼
┌─────────────────┐
│ Deletion        │ ← Warnings sent at 1 month, 1 week, 1 day
│   Warnings      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Auto-Deletion   │ ← Data removed from database and backups
└─────────────────┘   Permanent and irreversible
```

## Special Cases

### Legal Holds

In rare cases, a **legal hold** may be placed on survey data:

- Prevents automatic deletion
- Applied by organization owners or administrators
- Requires a documented reason
- Used when data is subject to legal proceedings or investigations
- All legal holds are logged and audited

### Ownership Transfer

If a survey creator leaves the organization:

- Survey ownership automatically transfers to the organization owner
- All permissions and access rights are maintained
- Both parties are notified via email
- Audit trail records the transfer

### Data Custodian Role

Organizations can designate a **Data Custodian** for specific surveys:

- Can download data but cannot edit the survey
- Useful for delegating data management
- Receives deletion warning emails
- Does not have permission to extend retention
- Optional - not required for every survey

## Your Responsibilities

### As a Survey Creator

- Close surveys promptly when data collection is complete
- Download data only when necessary
- Store downloaded data securely
- Delete local copies when no longer needed
- Respond to deletion warnings before deadlines
- Justify any retention extensions

### As an Organization Owner

- Set clear data policies for your organization
- Monitor data downloads across all surveys
- Review retention extensions
- Ensure appropriate access controls
- Designate data custodians when appropriate
- Respond to legal hold requests

### As a Data Custodian

- Download data only when authorized
- Follow your organization's data handling procedures
- Store exports securely
- Report any security concerns immediately
- Maintain confidentiality

## Getting Help

If you have questions about data governance:

1. **Review the detailed guides:**
   - [Data Export](/docs/data-governance-export/) - How to download data
   - [Data Retention](/docs/data-governance-retention/) - Retention policies and deadlines
   - [Data Security](/docs/data-governance-security/) - Security best practices
   - [Data Policy](/docs/data-governance-policy/) - Formal data policy

2. **Contact your organization's data protection officer** (if designated)

3. **For technical issues:** [GitHub Issues](https://github.com/eatyourpeas/checktick/issues)

4. **For security concerns:** Contact your organization administrator immediately

## Compliance

CheckTick is designed to support compliance with:

- **GDPR** (General Data Protection Regulation)
- **UK Data Protection Act 2018**
- **NHS Data Security and Protection Toolkit**
- **Caldicott Principles**
- Research ethics requirements

However, **you are responsible** for ensuring your specific use case complies with applicable regulations. CheckTick provides the tools - you provide the governance.

## Next Steps

- Read the [Data Export Guide](/docs/data-governance-export/) to learn how to download data
- Review the [Data Retention Policy](/docs/data-governance-retention/) to understand timelines
- Check the [Data Security Guide](/docs/data-governance-security/) for best practices
- Read the formal [Data Policy](/docs/data-governance-policy/) for legal details
