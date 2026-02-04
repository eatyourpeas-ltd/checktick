---
title: Key Management for Administrators
category: security
priority: 3
---

# Key Management for Administrators

This guide is for **organization owners** and **team admins** who manage encryption keys and handle recovery requests for their users.

## Overview

As an administrator, you have elevated privileges that come with responsibilities:

| Role | Can Recover | Scope | Audit Requirements |
|------|-------------|-------|-------------------|
| **Team Admin** | Team members | Own team only | All actions logged |
| **Organization Owner** | Any user in org | Entire organization | All actions logged + dual auth for platform recovery |
| **Platform Admin** | Any user (with verification) | All users | Dual auth + time delay + SIEM logging |

## Key Management Hierarchy

```
Platform Master Key (split-knowledge)
├── Vault Component (stored in HashiCorp Vault)
└── Custodian Component (offline storage)
    │
    ├── Organization A Master Key
    │   ├── Team 1 Key → Team 1 Surveys
    │   └── Team 2 Key → Team 2 Surveys
    │
    └── Organization B Master Key
        └── Team 3 Key → Team 3 Surveys
```

**Key Principle**: Higher-level keys can decrypt lower-level keys, but not vice versa.

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

If a team member loses access to their account (SSO issues, left organization temporarily, etc.):

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

#### When to Escalate to Organization Admin

Escalate if:

- You cannot access the survey (permissions issue)
- The survey involves multiple teams
- The member disputes the recovery
- You're unsure about the appropriate action

---

## Organization Owner Responsibilities

### Managing Teams

#### Creating Teams

1. Navigate to **Settings → Organization → Teams**
2. Click **Create Team**
3. Enter team name and description
4. Assign a Team Admin
5. Click **Create**

#### Dissolving Teams

When a team is no longer needed:

1. Navigate to **Settings → Organization → Teams**
2. Select the team
3. Click **Dissolve Team**
4. Choose what happens to surveys:
   - Move to another team
   - Move to organization level
   - Archive (read-only)
5. Confirm dissolution

**Warning**: This action cannot be undone. All team members lose access immediately.

### Organization-Level Recovery

As organization owner, you can recover any survey in your organization:

1. Navigate to **Admin → Recovery Dashboard**
2. Click **New Recovery Request**
3. Search for the user or survey
4. Select the recovery reason
5. Click **Initiate Recovery**

For team surveys, recovery is instant. For individual user surveys within your organization, you may need to follow the platform recovery process.

### Recovery Dashboard

The recovery dashboard shows:

```
┌─────────────────────────────────────────────────────────────────┐
│ Organization Recovery Dashboard                    [Export CSV] │
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

### Who Can Initiate Platform Recovery?

- The user themselves (via support request)
- Organization admin (on behalf of unavailable user)
- Platform admin (for orphaned accounts)

### Platform Recovery Workflow

#### Step 1: Request Submission

**If user initiates:**

1. User contacts support@checktick.uk
2. Support creates recovery ticket
3. User receives confirmation email with ticket ID

**If organization admin initiates:**

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
| **Employment Verification** | HR confirmation (for NHS/organization users) | 1-2 days |

**Identity Verification Checklist (for admins reviewing):**

```
□ Photo ID matches account name
□ Photo ID is not expired
□ Photo ID shows clear, unaltered image
□ Email domain matches organization (if applicable)
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
| Organization | 24 hours |
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

1. **Platform admin retrieves custodian component**
   - Stored in secure offline location
   - Requires physical access (not in database/environment)
   - Two-person retrieval recommended

2. **Platform master key reconstructed**
   - Vault component + Custodian component = Platform key
   - Happens in memory only, never persisted

3. **User's KEK retrieved from Vault**
   - Platform key decrypts the escrowed key
   - Key is made available to user's session

4. **User regains access**
   - Survey unlocks with recovered key
   - User prompted to set new password + recovery phrase
   - New key escrow created automatically

5. **Notification sent**
   - User receives confirmation email
   - Organization admin notified (if applicable)
   - Audit entry created

### Custodian Component Management

The custodian component is the offline portion of the platform master key.

#### Storage Requirements

- ✅ Secure physical location (safe, lockbox)
- ✅ Fireproof and waterproof storage
- ✅ Limited access (2-3 designated individuals maximum)
- ✅ Access log maintained
- ✅ Backup copy in separate secure location

#### Retrieval Procedure

1. **Verify authorization**: Confirm dual-authorized recovery request
2. **Two-person rule**: Two designated individuals retrieve together
3. **Log access**: Record date, time, individuals, recovery ticket ID
4. **Use immediately**: Don't store in digital systems
5. **Return to storage**: Immediately after use

#### Rotation Schedule

Rotate the custodian component:

- After any suspected compromise
- Annually (as part of security review)
- When designated custodians change

**Rotation Process:**

1. Generate new platform master key
2. Re-encrypt all escrowed keys with new platform key
3. Securely destroy old custodian component
4. Store new custodian component in secure location
5. Update Vault with new vault component

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
5. **Escalate when unsure**: Better to ask organization admin than make mistakes

### For Organization Owners

1. **Establish clear policies**: Document when recovery is appropriate
2. **Designate backup admins**: At least 2 people who can authorize
3. **Review recovery dashboard daily**: Catch issues early
4. **Test recovery process annually**: Ensure it works when needed
5. **Maintain SIEM integration**: Don't let alerts go unmonitored
6. **Secure custodian component**: Follow storage and retrieval procedures

### For Platform Admins

1. **Never bypass time delays**: Even in emergencies
2. **Always require dual authorization**: No exceptions
3. **Verify identity thoroughly**: When in doubt, request more evidence
4. **Log everything**: Actions not logged didn't happen (legally)
5. **Rotate custodian component**: Follow rotation schedule
6. **Monitor recovery rates**: Investigate unusual patterns

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

### Custodian Component Not Working

1. Verify component hasn't been rotated
2. Check component matches current vault component
3. Ensure correct format (64-byte hex string)
4. Contact CheckTick support if issues persist

---

## Related Documentation

- [Encryption for Users](/docs/encryption-for-users/) - End-user encryption guide
- [Business Continuity](/docs/business-continuity/) - Disaster recovery procedures
- [Vault Integration](/docs/vault/) - Deploying HashiCorp Vault (includes developer API reference)

---

## Getting Help

**For urgent recovery issues:**

- Email: support@checktick.uk
- Include: Organization name, user email, survey ID, ticket number

**For security concerns:**

- Email: security@checktick.uk
- Report any suspected unauthorized access immediately

**For compliance questions:**

- Email: compliance@checktick.uk
- Include: Specific regulation and evidence needed
