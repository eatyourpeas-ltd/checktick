---
title: Key Management for Administrators
category: security
priority: 3
---

# Key Management for Administrators

This guide is for **organisation owners** and **team admins** who manage encryption keys and handle recovery requests for their users.

## Overview

As an administrator, you have elevated privileges that come with responsibilities:

| Role | Can Recover | Scope | Audit Requirements |
|------|-------------|-------|-------------------|
| **Team Admin** | Team members | Own team only | All actions logged |
| **Organisation Owner** | Any user in org | Entire organisation | All actions logged + dual auth for platform recovery |
| **Platform Admin** | Any user (with verification) | All users | Dual auth + time delay + SIEM logging |

## Key Management Hierarchy

```
Platform Master Key (split-knowledge)
├── Vault Component (stored in HashiCorp Vault)
└── Custodian Component (Shamir 3-of-4 threshold)
    │
    ├── Share 1 (Admin 1) ← Also has Vault Unseal Key 1
    ├── Share 2 (Admin 2) ← Also has Vault Unseal Key 2
    ├── Share 3 (Physical Safe) ← Also has Vault Unseal Key 3
    └── Share 4 (Cloud Backup) ← Also has Vault Unseal Key 4
    │
    ├── Organisation A Master Key
    │   ├── Team 1 Key → Team 1 Surveys
    │   └── Team 2 Key → Team 2 Surveys
    │
    └── Organisation B Master Key
        └── Team 3 Key → Team 3 Surveys
```

**Key Principle**:
- Higher-level keys can decrypt lower-level keys, but not vice versa
- Custodian shares use same distribution as Vault unseal keys (aligned security model)
- Need any 3 of 4 shares for platform recovery (same threshold as Vault unsealing)

---

## Team Admin Responsibilities

### Managing Team Access

#### Adding Team Members

When you add a member to your team:

1. Navigate to **Settings → Team Management**
2. Click **Invite Member**
3. Enter their email address
4. Choose their role (Member, Editor, Admin)
5. They receive an invitation email
6. Upon accepting, they automatically get access to team surveys

**What happens behind the scenes:**

- Their account is linked to the team
- Team encryption key is made available via their SSO session
- No passwords or recovery phrases needed (SSO handles authentication)

#### Removing Team Members

When someone leaves:

1. Navigate to **Settings → Team Management**
2. Find the member in the list
3. Click **Remove from Team**
4. Confirm the removal

**Important**: Removing a member:

- ✅ Revokes their access to team surveys immediately
- ✅ Logs the removal action for audit
- ❌ Does NOT delete any surveys they created
- ❌ Does NOT affect their personal (non-team) surveys

#### Changing Member Roles

| Role | Permissions |
|------|------------|
| **Member** | View and edit assigned surveys |
| **Editor** | Create surveys, edit all team surveys |
| **Admin** | All above + manage team members + recover team surveys |

To change a role:

1. Navigate to **Settings → Team Management**
2. Click the role dropdown next to the member
3. Select the new role
4. Confirm the change

### Recovering Team Member Surveys

If a team member loses access to their account (SSO issues, left organisation temporarily, etc.):

#### Standard Team Recovery (Instant)

1. Navigate to **Surveys → Team Surveys**
2. Find the affected survey
3. Click **Admin Actions → Recover Access**
4. Select the reason:
   - Member temporarily unavailable
   - SSO account locked
   - Emergency data access
   - Other (specify)
5. Click **Recover**
6. Access is granted immediately

**This creates an audit log entry:**
```json
{
  "timestamp": "2025-11-30T10:00:00Z",
  "action": "team_admin_recovery",
  "admin": "team.admin@nhs.uk",
  "target_user": "dr.jones@nhs.uk",
  "survey": "diabetes-audit-2025",
  "reason": "SSO account temporarily locked"
}
```

#### When to Escalate to Organisation Admin

Escalate if:

- You cannot access the survey (permissions issue)
- The survey involves multiple teams
- The member disputes the recovery
- You're unsure about the appropriate action

---

## Organisation Owner Responsibilities

### Managing Teams

#### Creating Teams

1. Navigate to **Settings → Organisation → Teams**
2. Click **Create Team**
3. Enter team name and description
4. Assign a Team Admin
5. Click **Create**

#### Dissolving Teams

When a team is no longer needed:

1. Navigate to **Settings → Organisation → Teams**
2. Select the team
3. Click **Dissolve Team**
4. Choose what happens to surveys:
   - Move to another team
   - Move to organisation level
   - Archive (read-only)
5. Confirm dissolution

**Warning**: This action cannot be undone. All team members lose access immediately.

### Organisation-Level Recovery

As organisation owner, you can recover any survey in your organisation:

1. Navigate to **Admin → Recovery Dashboard**
2. Click **New Recovery Request**
3. Search for the user or survey
4. Select the recovery reason
5. Click **Initiate Recovery**

For team surveys, recovery is instant. For individual user surveys within your organisation, you may need to follow the platform recovery process.

### Recovery Dashboard

The recovery dashboard shows:

```
┌─────────────────────────────────────────────────────────────────┐
│ Organisation Recovery Dashboard                    [Export CSV] │
├─────────────────────────────────────────────────────────────────┤
│ Summary                                                         │
│ ├── Pending Requests: 2                                         │
│ ├── Completed This Month: 5                                     │
│ ├── Recovery Rate: 0.3% (normal range: <1%)                     │
│ └── Last SIEM Sync: 2 minutes ago ✓                             │
├─────────────────────────────────────────────────────────────────┤
│ Pending Requests                                                │
├─────────────────────────────────────────────────────────────────┤
│ 🟡 Dr. Sarah Jones | diabetes-audit-2025                        │
│    Status: Awaiting Secondary Authorization                     │
│    Primary Approval: admin1@org.uk (2025-11-30 09:00)          │
│    Time Remaining: 23h 15m until time delay completes           │
│    [View Details] [Approve as Secondary] [Reject]               │
├─────────────────────────────────────────────────────────────────┤
│ 🟠 Dr. Michael Brown | patient-feedback                         │
│    Status: Identity Verification In Progress                    │
│    Documents Submitted: Photo ID ✓, Video Call: Scheduled       │
│    [View Verification] [Schedule Call]                          │
├─────────────────────────────────────────────────────────────────┤
│ Recent Completions                                              │
├─────────────────────────────────────────────────────────────────┤
│ ✅ Dr. Emma Wilson | research-study-2025                        │
│    Completed: 2025-11-28 14:30                                  │
│    Recovery Type: Team Admin (instant)                          │
│    [View Audit Trail]                                           │
└─────────────────────────────────────────────────────────────────┘
```

#### Dashboard Features

| Feature | Description |
|---------|-------------|
| **Pending Requests** | All recovery requests awaiting action |
| **Identity Verification** | Review submitted documents, schedule video calls |
| **Dual Authorization** | See primary approval status, provide secondary approval |
| **Time Delay Countdown** | Track mandatory waiting period |
| **Audit Trail Viewer** | Complete history of all recovery actions |
| **Recovery Rate Monitor** | Alerts if recovery rate exceeds normal thresholds |
| **SIEM Status** | Connection status to Elasticsearch/external SIEM |

### Reviewing Audit Logs

Navigate to **Admin → Audit Logs** to view all key management events:

**Filter Options:**

- Date range
- Action type (recovery, access grant, access revoke)
- User
- Admin who performed action
- Survey

**Export Options:**

- CSV (for spreadsheet analysis)
- JSON (for SIEM import)
- PDF (for compliance reports)

---

## Platform Recovery Process

When a user loses both their password AND recovery phrase, platform recovery is required.

### Rate Limiting and Abuse Prevention

To prevent abuse and detect suspicious activity, platform recovery enforces strict rate limits:

| Limit Type | Threshold | Action |
|------------|-----------|--------|
| **Per User** | Max 3 requests per 90 days | 4th request requires executive approval |
| **Per Organisation** | Max 5 requests per day | Excess requests flagged for review |
| **System-wide** | Max 50 requests per day | Admin notification + security review |
| **Identity Verification** | Max 5 attempts per request | Account flagged after excessive failures |
| **Failed Authorizations** | Max 3 rejections per user | Escalate to security team |

**Automated Alerts:**

```
🚨 Recovery Rate Alert
───────────────────────────────────────
Organisation: NHS Trust Example
Recovery requests today: 12 (threshold: 5)
Unusual activity detected

Breakdown:
├─ Same IP address: 8 requests
├─ Same admin approver: 10 requests
└─ Similar justifications: 7 requests

Recommended Action:
1. Review audit logs for pattern
2. Contact organisation admin
3. Verify identity of requesters
4. Consider temporary hold on new requests
```

**DoS Protection:**

- IP-based rate limiting: Max 10 requests per hour per IP
- CAPTCHA required after 3 failed identity verifications
- Exponential backoff for repeated rejections
- Email notification throttling: Max 5 per user per day

### Who Can Initiate Platform Recovery?

- The user themselves (via support request)
- Organisation admin (on behalf of unavailable user)
- Platform admin (for orphaned accounts)

### Platform Recovery Workflow

#### Step 1: Request Submission

**If user initiates:**

1. User contacts support@checktick.uk
2. Support creates recovery ticket
3. User receives confirmation email with ticket ID

**If organisation admin initiates:**

1. Navigate to **Admin → Recovery Dashboard**
2. Click **Request Platform Recovery**
3. Enter user email and survey details
4. Provide justification (user unavailable, emergency, etc.)
5. Submit request

#### Step 2: Identity Verification

The user (or their authorized representative) must verify identity:

**Required Documents:**

- ✅ Government-issued photo ID (passport, driving license)
- ✅ Proof of association (NHS email, employment letter)

**Verification Methods:**

| Method | Description | Time |
|--------|-------------|------|
| **Photo ID Upload** | Upload clear photo of ID document | Instant |
| **Video Verification** | Live video call with CheckTick admin | 15-30 mins |
| **Security Questions** | Answer questions from account setup | Instant |
| **Employment Verification** | HR confirmation (for NHS/organisation users) | 1-2 days |

**Identity Verification Checklist (for admins reviewing):**

```
□ Photo ID matches account name
□ Photo ID is not expired
□ Photo ID shows clear, unaltered image
□ Email domain matches organisation (if applicable)
□ Video call completed (face matches ID)
□ Security questions answered correctly (2 of 3 minimum)
□ No suspicious activity on account
□ User confirms they initiated the request
```

#### Step 3: Dual Authorization

Platform recovery requires **two independent admin approvals**:

**Primary Authorization:**

1. First admin reviews verification documents
2. Confirms identity verification checklist is complete
3. Documents reason for approval
4. Clicks **Approve as Primary**

**Secondary Authorization:**

1. Different admin (cannot be same person) reviews
2. Independently confirms verification
3. Documents their approval reason
4. Clicks **Approve as Secondary**

**Rejection:**

- Either admin can reject with documented reason
- User is notified of rejection
- They can appeal or resubmit with additional documentation

#### Step 4: Time Delay Period

After dual authorization, a mandatory waiting period begins:

| Tier | Time Delay |
|------|-----------|
| Individual | 48 hours |
| Pro | 24 hours |
| Organisation | 24 hours |
| Enterprise | Custom (typically 24 hours) |

**During time delay:**

- User receives email notification with countdown
- User can cancel the recovery if they didn't request it
- Admins cannot bypass the delay
- Timer shown in recovery dashboard

**If user objects during time delay:**

1. Click "I didn't request this" in notification email
2. Recovery is immediately cancelled
3. Account is flagged for security review
4. User is prompted to change password

#### Step 5: Key Recovery Execution

After time delay completes:

1. **Platform admin gathers custodian shares**
   - Contact 3 of 4 share custodians
   - Collect shares (Admin 1, Admin 2, Physical Safe, or Cloud Backup)
   - Shares retrieved digitally from password managers or physically from safe

2. **Execute recovery via management command**
   - SSH into production server
   - Run: `python manage.py execute_platform_recovery <request_id> --custodian-share-1=<share1> --custodian-share-2=<share2> --custodian-share-3=<share3>`
   - Custodian component reconstructed in memory (never persisted)
   - Command validates all checks passed

3. **Platform master key reconstructed**
   - Vault component retrieved from Vault automatically
   - Custodian component reconstructed from 3 shares
   - XOR combination happens in memory only
   - Full platform key exists briefly, then cleared

3. **User's KEK retrieved from Vault**
   - Platform key decrypts the escrowed key
   - Key is made available to user's session

4. **User regains access**
   - Survey unlocks with recovered key
   - User prompted to set new password + recovery phrase
   - New key escrow created automatically

5. **Notification sent**
   - User receives confirmation email
   - Organisation admin notified (if applicable)
   - Audit entry created

### Custodian Component Management

The custodian component is the offline portion of the platform master key, split into 4 shares using Shamir's Secret Sharing.

#### Storage Requirements

**Custodian shares are distributed across 4 locations:**
- ✅ Admin 1's password manager (Share 1)
- ✅ Admin 2's password manager (Share 2)
- ✅ Physical safe - fireproof, waterproof (Share 3)
- ✅ Encrypted cloud backup (Share 4 - spare)

**Security model:**
- Need any 3 of 4 shares to reconstruct custodian component
- Same distribution as Vault unseal keys (aligned security)
- No single point of failure
- Shares never stored in application environment

#### Initial Setup: Splitting the Custodian Component

When setting up CheckTick for the first time, split the custodian component from `vault/setup_vault.py`:

```bash
# After running vault/setup_vault.py, you get a custodian component
# Split it into 4 shares:
python manage.py split_custodian_component \
  --custodian-component=<64-byte-hex-from-setup>

# Output:
# Share 1: 801-abc123def456...
# Share 2: 802-xyz789ghi012...
# Share 3: 803-jkl345mno678...
# Share 4: 804-pqr901stu234...
```

Securely distribute shares to designated custodians and **remove the original custodian component from your .env file**.

#### Retrieval Procedure for Recovery

When executing platform recovery:

1. **Verify authorization**: Confirm dual-authorized recovery request exists
2. **Gather shares**: Obtain 3 of 4 shares from custodians
3. **Execute recovery**: Run management command with shares
4. **Reconstruct temporarily**: Shares combine in memory only
5. **Complete recovery**: User regains access, shares cleared from memory
6. **Return to storage**: Shares remain with custodians (not returned to physical safe)

**Example recovery execution:**

```bash
# Retrieve 3 shares from custodians
# Share 1 from Admin 1, Share 2 from Admin 2, Share 3 from physical safe

python manage.py execute_platform_recovery ABC-123-XYZ \
  --custodian-share-1="801-abc123def456..." \
  --custodian-share-2="802-xyz789ghi012..." \
  --custodian-share-3="803-jkl345mno678..." \
  --executor=admin@checktick.uk

# Custodian component reconstructed in memory
# Recovery executed
# Memory cleared immediately
```

**Security features:**
- Shares only in memory during execution
- Never persisted to disk or logs
- Automatic memory clearing after use
- Full audit trail of share usage
- Alerts sent to all admins when shares are used

#### Rotation Schedule

Rotate the custodian shares:

- After any suspected compromise
- Annually (as part of security review)
- When designated custodians change

**Rotation Process:**

1. Generate new platform master key (via `vault/setup_vault.py`)
2. Split new custodian component into 4 shares (`split_custodian_component`)
3. Re-encrypt all escrowed keys with new platform key (migration script)
4. Distribute new shares to custodians
5. Securely destroy old shares (all 4 shares + any backups)
6. Update Vault with new vault component
7. Test recovery with new shares

---

## Key Rotation Policy

Different keys in CheckTick's security architecture have different rotation requirements. This section clarifies which keys need regular rotation and which don't.

### Keys That Require Regular Rotation

#### 1. VAULT_SECRET_ID (Every 90 Days) ⏰

**What It Is**: AppRole secret ID used by the Django webapp to authenticate to Vault.

**Why Rotate**: Limits exposure window if webapp credentials are compromised.

**How To Rotate**:

```bash
# 1. Generate new secret ID in Vault
vault write -f auth/approle/role/checktick-app/secret-id

# 2. Update .env file with new VAULT_SECRET_ID
# 3. Restart webapp: docker compose restart web
```

**Frequency**: Every 90 days (set calendar reminder)

**Priority**: **HIGH** - This is your most important regular rotation

---

#### 2. Custodian Component Shares (Annually or After Compromise) 🔐

**What It Is**: The 4 Shamir shares that reconstruct the custodian component (part of platform master key).

**Why Rotate**:
- After any suspected compromise
- When designated custodians change
- Annual security review requirement

**How To Rotate**: See [Rotation Schedule](#rotation-schedule) above for full 7-step process.

**Frequency**:
- **Mandatory**: After compromise or custodian changes
- **Recommended**: Annually as part of security audit

**Priority**: **MEDIUM** - Important but less frequent than VAULT_SECRET_ID

---

#### 3. Vault's Internal Encryption Key (Optional - Annually) 🔄

**What It Is**: Vault's "barrier key" that encrypts all data at rest within Vault itself.

**Why Rotate**: Compliance requirements, annual security reviews.

**How To Rotate**:

```bash
# Vault handles re-encryption automatically
vault operator rotate
```

**Requirements**:
- Vault must be unsealed
- No impact on application - Vault handles everything internally
- Does NOT require re-encrypting application data
- Does NOT require new unseal keys

**Frequency**: Annually (optional, for compliance)

**Priority**: **LOW** - Nice to have for compliance, but Vault handles it transparently

---

### Keys That Rarely Need Rotation

#### 4. Vault Unseal Keys (Only After Major Security Events) ⚠️

**What They Are**: The 4 Shamir-split keys needed to unseal Vault after restart (3 of 4 required).

**When To Rotate**:
- Custodian leaves organization without proper handover
- Multiple unseal keys suspected compromised
- Changing threshold requirements (e.g., 3-of-4 to 4-of-6)
- Major security incident affecting infrastructure

**How To Rotate**:

```bash
# REQUIRES ALL CURRENT UNSEAL KEYS
vault operator rekey
```

⚠️ **WARNING**: This is disruptive - generates entirely new unseal keys and invalidates all existing ones.

**Frequency**: Only after major security events

**Priority**: **CRITICAL** (when needed) - But rarely needed

---

### Keys That Generally Don't Need Rotation

#### 5. Organization Master Keys ❌ (No Routine Rotation)

**What They Are**: Per-organization encryption keys that encrypt team keys.

**Why Not Rotate**:
- Encrypted with platform master key (which uses custodian shares)
- Rotation requires re-encrypting all team keys
- Only rotate if specific compromise suspected

**Exception**: Rotate only when:
- Organization key specifically compromised
- Compliance requires it (rare)
- Organization security incident

---

#### 6. Team Keys ❌ (No Routine Rotation)

**What They Are**: Team-shared encryption keys for team surveys.

**Why Not Rotate**:
- SSO-based access control (revoke access by removing from team)
- Rotation requires re-encrypting all team surveys
- Operationally disruptive for active teams

**Exception**: Rotate only when:
- Team member with key access leaves under suspicious circumstances
- Team-specific security incident
- Compliance audit requires it

**Alternative**: Instead of rotating, remove compromised user from team (instant revocation).

---

#### 7. Survey KEKs (Key Encryption Keys) ❌ (No Routine Rotation)

**What They Are**: Per-survey encryption keys that encrypt patient data.

**Why Not Rotate**:
- Each survey already has unique key (isolation by design)
- Password/recovery phrase protect access
- Rotation requires re-encrypting all survey responses

**Exception**: Rotate only when:
- Specific survey's KEK known to be compromised
- User reports unauthorized access to specific survey

**Alternative**: For unauthorized access concerns, audit logs + investigate rather than blanket rotation.

---

### Summary: Rotation Schedule

| Key Type | Frequency | Method | Priority |
|----------|-----------|--------|----------|
| **VAULT_SECRET_ID** | **Every 90 days** | `vault write` + restart | **HIGH** |
| **Custodian shares** | **Annually** or after compromise | Full re-initialization | **MEDIUM** |
| **Vault encryption key** | Annually (optional) | `vault operator rotate` | **LOW** |
| **Vault unseal keys** | Only after major incident | `vault operator rekey` | **CRITICAL*** |
| Organization keys | Only if compromised | Re-encrypt hierarchy | N/A |
| Team keys | Only if compromised | Re-encrypt team data | N/A |
| Survey KEKs | Only if compromised | Re-encrypt survey | N/A |

\* Priority is CRITICAL when needed, but it's rarely needed.

---

### Automation and Reminders

Set up calendar reminders for routine rotations:

- **Every 90 days**: Rotate VAULT_SECRET_ID
- **Annually (same date each year)**:
  - Rotate custodian shares
  - Optionally rotate Vault encryption key
  - Test custodian share reconstruction
  - Audit custodian access logs

**Recommended Annual Date**: Choose your organization's security audit date or fiscal year-end.

---

### Rotation Best Practices

1. **Document All Rotations**: Record date, who performed it, and reason in audit log
2. **Test Before and After**: Always verify functionality after rotation
3. **Dual Authorization**: Require two administrators for custodian share rotation
4. **Secure Disposal**: Use cryptographic erasure for old secrets (not just deletion)
5. **Update Documentation**: Keep custodian lists and distribution records current
6. **Communication**: Notify relevant administrators before scheduled rotations
7. **Rollback Plan**: Document how to roll back if rotation causes issues

---

## SIEM Integration

Security Information and Event Management (SIEM) integration provides centralized logging and alerting.

### Supported SIEM Systems

| System | Integration Method |
|--------|-------------------|
| **Elasticsearch** (self-hosted) | Direct API integration |
| **Splunk** | HTTP Event Collector (HEC) |
| **Microsoft Sentinel** | Log Analytics workspace |
| **AWS CloudWatch** | CloudWatch Logs agent |

### Events Forwarded to SIEM

All key management events are forwarded:

```json
{
  "timestamp": "2025-11-30T14:30:00Z",
  "event_type": "key_management",
  "action": "platform_recovery_completed",
  "severity": "high",
  "details": {
    "user": "dr.smith@nhs.uk",
    "survey_id": "uuid-here",
    "primary_approver": "admin1@checktick.uk",
    "secondary_approver": "admin2@checktick.uk",
    "time_delay_hours": 48,
    "verification_methods": ["photo_id", "video_call", "security_questions"]
  }
}
```

### Alert Thresholds

Configure alerts for unusual activity:

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| Recovery requests per day | > 5 | > 10 |
| Recovery rate (% of users) | > 1% | > 2% |
| Failed verification attempts | > 3 per user | > 5 per user |
| Time delay bypass attempts | Any | Any |

### Setting Up Elasticsearch (Self-Hosted)

For self-hosted SIEM on Northflank:

1. Deploy Elasticsearch addon (see [Vault Setup Guide](/docs/vault/))
2. Configure Vault audit backend to forward logs
3. Set up Kibana for visualization
4. Create alert rules for thresholds above

---

## Compliance Reporting

### GDPR Requirements

For GDPR compliance, maintain records of:

- ✅ All data access (who accessed what, when)
- ✅ Recovery requests and outcomes
- ✅ Consent for identity verification
- ✅ Data retention periods

**Export GDPR Report:**

1. Navigate to **Admin → Compliance → GDPR Report**
2. Select date range
3. Click **Generate Report**
4. Download PDF or JSON

### NHS DSPT Requirements

For NHS Data Security and Protection Toolkit:

- ✅ Encryption of personal data at rest
- ✅ Access controls and audit logging
- ✅ Incident response procedures
- ✅ Staff training records

**Export DSPT Evidence:**

1. Navigate to **Admin → Compliance → DSPT Export**
2. Select evidence categories needed
3. Click **Generate Evidence Pack**
4. Download ZIP with all documentation

### HIPAA Requirements (if applicable)

For HIPAA compliance:

- ✅ Access controls (role-based)
- ✅ Audit controls (all access logged)
- ✅ Transmission security (TLS 1.3)
- ✅ Encryption (AES-256-GCM)

---

## Best Practices

### For Team Admins

1. **Review access quarterly**: Remove members who no longer need access
2. **Document recovery reasons**: Always provide clear justification
3. **Monitor audit logs**: Check weekly for unusual activity
4. **Train team members**: Ensure they understand encryption basics
5. **Escalate when unsure**: Better to ask organisation admin than make mistakes

### For Organisation Owners

1. **Establish clear policies**: Document when recovery is appropriate
2. **Designate backup admins**: At least 2 people who can authorize
3. **Review recovery dashboard daily**: Catch issues early
4. **Test recovery process annually**: Ensure it works when needed
5. **Maintain SIEM integration**: Don't let alerts go unmonitored
6. **Secure custodian component**: Follow storage and retrieval procedures

### For Platform Admins

1. **Never bypass security controls**: Follow all procedures even in emergencies
2. **Always require dual authorization**: No exceptions for recovery
3. **Use management commands**: Never store custodian shares in webapp environment
4. **Verify identity thoroughly**: When in doubt, request more evidence
5. **Log everything**: Actions not logged didn't happen (legally)
6. **Rotate custodian shares**: Follow rotation schedule (annually or after compromise)
7. **Monitor recovery rates**: Investigate unusual patterns (>1% of users)
8. **Test recovery process**: Annual dry-run ensures shares work when needed
9. **Distribute shares wisely**: Align with Vault unseal key custodians
10. **Clear memory**: Shares should never persist after recovery completes

---

## Troubleshooting

### User Can't Access Survey After SSO Login

1. Check team membership is active
2. Verify SSO provider is configured correctly
3. Check team encryption key is available
4. Review error logs for specific issue

### Recovery Request Stuck in Pending

1. Check if dual authorization is complete
2. Verify time delay hasn't been bypassed
3. Check if user objected to the recovery
4. Review audit logs for rejection

### Audit Logs Not Appearing in SIEM

1. Verify SIEM connection is active (check dashboard)
2. Check Elasticsearch/SIEM is running
3. Verify audit backend configuration in Vault
4. Check network connectivity between services

### Custodian Shares Not Working

1. Verify shares are complete and unmodified
2. Ensure using exactly 3 shares (not 2 or 4)
3. Check shares match current generation (not rotated)
4. Confirm using correct share format (starts with 80X-)
5. Test with `--dry-run` flag first
6. Contact CheckTick support if issues persist

### Recovery Command Fails

1. Check SSH access to production server
2. Verify Django application is running
3. Ensure Vault is unsealed and accessible
4. Confirm recovery request exists and is approved
5. Check all 3 shares are provided correctly
6. Review error logs: `docker logs checktick-web`

---

## Related Documentation

- [Encryption for Users](/docs/encryption-for-users/) - End-user encryption guide
- [Business Continuity](/docs/business-continuity/) - Disaster recovery procedures
- [Vault Integration](/docs/vault/) - Deploying HashiCorp Vault (includes developer API reference)

---

## Getting Help

**For urgent recovery issues:**

- Email: support@checktick.uk
- Include: Organisation name, user email, survey ID, ticket number

**For security concerns:**

- Email: security@checktick.uk
- Report any suspected unauthorized access immediately

**For compliance questions:**

- Email: compliance@checktick.uk
- Include: Specific regulation and evidence needed
