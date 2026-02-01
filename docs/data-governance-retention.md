---
title: Data Retention Policy
category: None
---

This guide explains how long survey data is kept in CheckTick, when it will be deleted, how to extend retention periods, and what happens during deletion.

## Overview

CheckTick follows a **time-limited storage** principle:

- Survey data is **not kept indefinitely**
- Retention periods are **clearly defined** and **enforced automatically**
- Users receive **multiple warnings** before deletion
- Deletion is **permanent and cannot be undone**

This policy balances the need for data access with data protection obligations and storage efficiency.

## Default Retention Period

### When Retention Begins

The retention period starts when a survey is **closed**:

**Before Closure:**

- Responses are being collected
- No retention period applies
- Data is kept until survey is closed
- Survey can be edited and reopened

**After Closure:**
- Survey is locked (no new responses)
- 6-month retention period begins
- Countdown to deletion starts
- Warnings are scheduled

### Standard Period

**Default: 6 months** from survey closure

This is sufficient time for:

- Analyzing results
- Writing reports
- Publishing findings
- Archiving important data elsewhere

**Example timeline:**

- Survey closed: January 1, 2025
- Retention period: 6 months
- First warning: June 1, 2025 (1 month remaining)
- Final warning: June 24, 2025 (1 week remaining)
- Last chance: June 30, 2025 (1 day remaining)
- Automatic deletion: July 1, 2025

## Extended Retention

### Maximum Period

You can extend retention up to **24 months** (2 years) from closure.

**Why the limit?**

- Minimizes data protection risks
- Reduces storage costs
- Encourages timely analysis
- Complies with data minimization principles

### Who Can Extend

**Survey Creators:**

- Can extend retention for **their own surveys**
- Each survey treated separately
- No organization-wide permissions needed

**Organization Owners:**

- Can extend retention for **any survey in the organization**
- Can set organization-wide policies
- Receive warnings for all surveys

**Data Custodians:**

- **Cannot extend retention** - Read-only access
- Must ask survey creator or organization owner

**Editors/Viewers:**

- **Cannot extend retention** - No data access

### How to Extend Retention

**Step 1: Receive Warning**

You'll receive emails at:

- **1 month** before deletion
- **1 week** before deletion
- **1 day** before deletion

Each email contains a link to extend retention.

**Step 2: Navigate to Survey**

1. Go to the survey dashboard
2. Look for the "Data Retention" section
3. Check current expiry date
4. See remaining time

**Step 3: Request Extension**

Click "Extend Retention Period" and choose:

- **3 months** - Short-term extension
- **6 months** - Standard extension
- **12 months** - Long-term extension
- **Custom** - Up to 24 months total

**Step 4: Provide Justification**

You must explain why you need more time:

**Valid reasons:**
- Ongoing analysis
- Publication pending
- Legal proceedings
- Audit requirements
- Research project timeline

**Invalid reasons:**

- "Just in case"
- "Might need it later"
- No specific purpose
- Convenience

**Step 5: Confirm Extension**

- New expiry date is calculated
- Extension is logged for audit trail
- New warning schedule is created
- All relevant users are notified

### Extension Limits

**Per Survey:**

- **Maximum total retention:** 24 months from closure
- **Number of extensions:** Unlimited (within 24-month limit)
- **Minimum extension:** 1 month
- **Maximum single extension:** 12 months

**Example:**

- Survey closed: January 1, 2025
- Initial retention: 6 months (expires July 1, 2025)
- First extension: +6 months (expires January 1, 2026)
- Second extension: +6 months (expires July 1, 2026)
- Third extension: +6 months ❌ **Denied** - Would exceed 24 months
- Maximum possible expiry: January 1, 2027 (24 months from closure)

## Deletion Warnings

### Warning Schedule

You receive automatic warnings at:

#### 1 Month Warning

**Sent:** 30 days before deletion
**Subject:** "Survey data will be deleted in 1 month"
**Contains:**

- Survey name and ID
- Current expiry date
- How to extend retention
- Link to download data

**Action:** Consider if you still need the data. Download now if unsure.

#### 1 Week Warning

**Sent:** 7 days before deletion
**Subject:** "Survey data will be deleted in 1 week"
**Contains:**

- Survey name and ID
- Exact deletion date and time
- Last chance to extend
- Urgent: Download data now

**Action:** Make final decision. Download data if needed. Extend if necessary.

#### 1 Day Warning

**Sent:** 24 hours before deletion
**Subject:** "URGENT: Survey data will be deleted tomorrow"
**Contains:**

- Survey name and ID
- Deletion happens in 24 hours
- This is your final warning
- Cannot be recovered after deletion

**Action:** **Final opportunity** to download or extend.

### Who Receives Warnings

**Survey Creators:**

- Warnings for their own surveys
- One email per survey

**Organization Owners:**

- Warnings for all surveys in organization
- Daily digest (not per-survey emails)
- Summary of upcoming deletions

**Data Custodians:**

- Warnings for assigned surveys only

**Administrators:**

- Weekly summary of all upcoming deletions
- Organization-wide statistics

### Snoozing Warnings

You **cannot** snooze or dismiss warnings.

**Why?**

- Deletion is permanent
- Multiple reminders prevent accidents
- Ensuring informed decisions

**Too many emails?**

- Set email filters
- Unsubscribe from specific surveys (if you're not responsible)
- Ask organization owner to reassign data custodian

## Deletion Process

### Soft Deletion (30-Day Grace Period)

When the retention period expires:

**Day 0 (Deletion Date):**

- Survey data is **soft deleted**
- No longer accessible in the UI
- Marked for permanent deletion
- 30-day grace period begins

**Grace Period (Days 1-30):**

- Data still exists in database
- **Can be recovered** by administrators
- Not visible to users
- Backups still include the data

**Purpose of Grace Period:**

- Protects against accidental deletion
- Allows for "oops" moments
- Organization owner can restore if needed

### Recovery During Grace Period

**Who Can Recover:**

- **Organization owners** only
- System administrators (on request)

**How to Recover:**

1. Contact your organization owner
2. Explain why recovery is needed
3. Organization owner accesses "Deleted Surveys"
4. Clicks "Restore" next to the survey
5. Survey data is restored with new retention period
6. Must provide justification for audit trail

**Limitations:**

- **Must be within 30 days** of soft deletion
- **Cannot exceed 24-month total limit** from original closure
- **Recovery is logged** and reported

### Hard Deletion (Permanent)

**After 30 days:**

- Survey data is **hard deleted**
- **Completely removed** from database
- **Backups are purged**
- **Cannot be recovered** by anyone
- **Deletion is logged** for compliance

**Cryptographic Key Erasure** (for encrypted surveys):

For surveys with patient data encryption, hard deletion includes **cryptographic key erasure** to ensure GDPR compliance:

1. **All encryption keys are overwritten** with cryptographically secure random data:
   - Password-encrypted survey key
   - Recovery phrase-encrypted survey key
   - OIDC-encrypted survey key (if using SSO)
   - Organization-encrypted survey key (if applicable)

2. **Keys are purged** from HashiCorp Vault (if platform key escrow is enabled)

3. **Why this matters**: Even if database backups exist somewhere, the encrypted patient data cannot be recovered because the encryption keys have been cryptographically erased

4. **Audit trail**: Key erasure is logged before deletion, recording:
   - Which keys were overwritten
   - Timestamp of erasure
   - User who initiated deletion
   - Survey ID and metadata

**What is Deleted:**

- All survey responses (including encrypted patient data)
- Personally identifiable information (PII)
- Export history (summary retained for audit)
- Attachments and uploaded files
- Associated metadata
- **All encryption keys** (overwritten with random data first)

**What is Retained:**

- Survey structure (questions, groups)
- Audit log summary (who, when, not data content)
- Aggregated statistics (if anonymized)
- Download history (who downloaded, when, not data)
- Key erasure audit records (proves compliance)

**Security Properties:**

- **Irreversible**: Once keys are overwritten, encrypted data cannot be recovered
- **GDPR Compliant**: Meets Article 17 (Right to Erasure) requirements
- **Auditable**: Complete trail of deletion and key erasure
- **Defense in Depth**: Multiple layers (key erasure + data deletion + backup purge)

## Special Cases

### Legal Holds

**What is a Legal Hold?**

- Prevents automatic deletion
- Used during legal proceedings, investigations, or audits
- Overrides retention period
- Requires documented reason

**Who Can Place Legal Holds:**

- **Organization owners only**
- Must provide justification
- Cannot be applied retroactively to hard-deleted data

**Effect:**

- Deletion warnings stop
- Retention period frozen
- Data export still available
- Survey remains closed

**Removing Legal Holds:**
- Organization owner must remove explicitly
- New retention period begins after removal
- Standard warning schedule resumes

**See:** [Special Cases Guide](/docs/data-governance-special-cases/) for details

### Ownership Transfer

**What happens when survey creator leaves?**

If the creator is removed from the organization:

- **Ownership transfers** to organization owner
- Retention settings **remain unchanged**
- Organization owner receives future warnings
- Data custodians remain assigned (if any)

**See:** [Special Cases Guide](/docs/data-governance-special-cases/) for details

### Organization Deletion

**What happens when an organization is deleted?**

- All surveys in the organization are **immediately soft deleted**
- **30-day grace period** applies
- Organization owner receives final email
- After 30 days: **All data hard deleted**

## Retention Best Practices

### Plan Ahead

- **Download early** - Don't wait for warnings
- **Set calendar reminders** - Track important expiry dates
- **Archive externally** - Move data to long-term storage if needed
- **Extend proactively** - Don't rely on last-minute extensions

### Be Realistic

- **Don't over-extend** - Only keep data you actually need
- **Justify extensions** - Have clear, specific reasons
- **Review periodically** - Reassess if you still need the data
- **Delete when done** - Reduce risk and storage costs

### Follow Policy

- **Respect the 24-month limit** - It exists for good reasons
- **Provide honest justifications** - Don't make up reasons
- **Don't hoard data** - "Just in case" is not sufficient
- **Document your decisions** - Keep notes on why you extended

### Security

- **Download before deletion** - Export critical data
- **Encrypt downloads** - Use password-protected files
- **Delete local copies** - When no longer needed
- **Follow data policy** - See [Data Policy](/docs/data-governance-policy/)

## Troubleshooting

### Didn't Receive Warnings

**Check:**

- Email address is correct in your profile
- Warnings not in spam folder
- You have appropriate role (Creator/Owner/Custodian)
- Email notifications enabled in settings

**Fix:**

- Update your email address
- Check spam filters
- Contact organization owner
- Enable notifications

### Warning Says "Cannot Extend"

**Possible reasons:**

- Already at 24-month maximum
- Survey has legal hold (cannot extend, already protected)
- You don't have permission (not Creator or Owner)
- Survey already deleted

### Accidentally Deleted

**Within 30 days:**

- Contact organization owner immediately
- Request recovery
- Explain situation
- Provide justification

**After 30 days:**

- **Cannot be recovered**
- Data is permanently gone
- Learn from the experience
- Improve processes to prevent recurrence

### Extension Request Rejected

**Organization policies may:**

- Limit maximum retention
- Require approval for extensions over certain length
- Prohibit extensions without strong justification
- Require data protection impact assessment

**Contact your organization owner** to understand policy.

## Compliance and Legal

### Data Minimization

This policy implements the **data minimization principle** (GDPR Article 5):

- Data kept only as long as necessary
- Automatic deletion reduces risk
- Clear retention periods
- Justification required for extensions

### Right to Erasure

Participants may request deletion under "right to be forgotten" (GDPR Article 17):

- Deletion supersedes retention policy
- Must be actioned within 30 days
- Survey responses are removed immediately
- Audit trail retained (anonymized)

### Accountability

This policy ensures **accountability** (GDPR Article 5):

- All retention decisions are logged
- Justifications required and retained
- Audit trail for compliance demonstration
- Regular review of retention practices

## Getting Help

**For questions about:**

- **Extending retention:** Contact your organization owner
- **Warnings not received:** Check your profile email settings
- **Recovery:** Contact organization owner (within 30 days only)
- **Policy questions:** See [Data Policy](/docs/data-governance-policy/)

## Related Guides

- [Data Governance Overview](/docs/data-governance-overview/) - Understanding data governance
- [Data Export Guide](/docs/data-governance-export/) - How to download data
- [Data Security Guide](/docs/data-governance-security/) - Security best practices
- [Special Cases Guide](/docs/data-governance-special-cases/) - Legal holds, ownership transfer
- [Data Policy](/docs/data-governance-policy/) - Formal data protection policy
