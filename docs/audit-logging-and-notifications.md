---
title: Audit Logging and Notifications
category: security
priority: 5
---

# Audit Logging, Email Notifications, and SIEM Integration

This document specifies the logging, notification, and SIEM requirements for CheckTick's encryption and recovery system.

For a complete overview of security controls aligned with OWASP Top 10, see [Security Overview](/docs/security-overview/).

## Audit Logging Requirements

### Implementation

CheckTick uses a unified `AuditLog` model for all security-relevant events. The model is located in `checktick_app/surveys/models.py` and supports:

- **Scopes**: Organization, Survey, Security, Account
- **Severity levels**: INFO, WARNING, CRITICAL (auto-detected based on action)
- **Context capture**: IP address, user agent, actor, target user
- **Structured metadata**: JSON field for additional context

#### Logging Security Events

Use the convenience method for security events:

```python
from checktick_app.surveys.models import AuditLog

# Log a security event
AuditLog.log_security_event(
    action=AuditLog.Action.LOGIN_SUCCESS,
    actor=user,
    request=request,  # IP and user-agent extracted automatically
    message="Successful login via password",
)
```

### Events That MUST Be Logged

All key management and recovery events must create immutable audit entries.

#### Authentication Events

| Event | Severity | Required Fields |
|-------|----------|-----------------|
| `login_success` | INFO | user_id, method (password/sso), ip, user_agent |
| `login_failed` | WARNING | email_attempted, reason, ip, user_agent |
| `logout` | INFO | user_id, session_duration |
| `account_locked` | CRITICAL | user_id, ip, failure_count |
| `password_changed` | CRITICAL | user_id, ip |
| `user_created` | INFO | user_id, registration_method |

#### Two-Factor Authentication Events

| Event | Severity | Required Fields |
|-------|----------|-----------------|
| `2fa_enabled` | INFO | user_id, method (totp), ip |
| `2fa_disabled` | CRITICAL | user_id, ip, reason |
| `2fa_verified` | INFO | user_id, method (totp/backup_code), ip |
| `2fa_failed` | WARNING | user_id, ip, failure_reason |
| `backup_codes_generated` | INFO | user_id, code_count, ip |
| `backup_code_used` | WARNING | user_id, remaining_codes, ip |

#### Survey Access Events

| Event | Severity | Required Fields |
|-------|----------|-----------------|
| `survey_unlocked` | INFO | user_id, survey_id, method (password/phrase/sso) |
| `survey_unlock_failed` | WARNING | user_id, survey_id, reason |
| `survey_created` | INFO | user_id, survey_id, encryption_method |
| `survey_deleted` | WARNING | user_id, survey_id, deletion_reason |
| `kek_escrowed` | INFO | user_id, survey_id, vault_path |

#### Recovery Events (HIGH PRIORITY)

| Event | Severity | Required Fields |
|-------|----------|-----------------|
| `recovery_request_submitted` | WARNING | user_id, survey_id, request_id, verification_method |
| `recovery_verification_submitted` | INFO | request_id, verification_type (photo_id/video/questions) |
| `recovery_verification_approved` | INFO | request_id, admin_id, verification_type |
| `recovery_verification_rejected` | WARNING | request_id, admin_id, rejection_reason |
| `recovery_primary_approval` | WARNING | request_id, admin_id, approval_reason |
| `recovery_secondary_approval` | WARNING | request_id, admin_id, approval_reason |
| `recovery_rejected` | INFO | request_id, admin_id, rejection_reason |
| `recovery_time_delay_started` | INFO | request_id, delay_hours, expires_at |
| `recovery_user_objection` | CRITICAL | request_id, user_id, objection_reason |
| `recovery_cancelled` | WARNING | request_id, cancelled_by, cancellation_reason |
| `recovery_executed` | CRITICAL | request_id, admin_id, user_id, survey_id, custodian_used |
| `recovery_completed` | WARNING | request_id, user_id, new_credentials_set |

#### Administrative Events

| Event | Severity | Required Fields |
|-------|----------|-----------------|
| `team_member_added` | INFO | team_id, user_id, added_by, role |
| `team_member_removed` | WARNING | team_id, user_id, removed_by, reason |
| `team_admin_recovery` | WARNING | team_id, admin_id, target_user_id, survey_id |
| `org_admin_recovery` | WARNING | org_id, admin_id, target_user_id, survey_id |
| `custodian_component_accessed` | CRITICAL | admin_id, reason, request_id |
| `vault_key_rotated` | WARNING | key_type, rotated_by |

### Audit Entry Format

All audit entries must follow this structure:

```json
{
  "timestamp": "2025-11-30T14:30:00.000Z",
  "event_type": "recovery_executed",
  "severity": "CRITICAL",
  "request_id": "uuid-here",
  "actor": {
    "type": "admin",
    "id": 123,
    "email": "admin@checktick.uk",
    "ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  },
  "target": {
    "type": "user",
    "id": 456,
    "email": "dr.smith@nhs.uk"
  },
  "resource": {
    "type": "survey",
    "id": 789,
    "name": "diabetes-audit-2025"
  },
  "details": {
    "primary_approver_id": 100,
    "secondary_approver_id": 101,
    "time_delay_hours": 48,
    "verification_methods": ["photo_id", "video_call"],
    "custodian_component_used": true
  },
  "metadata": {
    "session_id": "session-uuid",
    "correlation_id": "correlation-uuid",
    "environment": "production"
  }
}
```

### Retention Requirements

| Log Type | Minimum Retention | Recommended | Regulation |
|----------|------------------|-------------|------------|
| Authentication | 1 year | 2 years | GDPR |
| Survey access | 1 year | 2 years | GDPR |
| Recovery events | 7 years | 10 years | Healthcare compliance |
| Admin actions | 7 years | 10 years | HIPAA/NHS DSPT |

### Immutability Requirements

Audit logs MUST be:

- ✅ Write-once (no modifications after creation)
- ✅ Cryptographically signed (detect tampering)
- ✅ Replicated (survive single-point failures)
- ✅ Accessible for compliance audits
- ✅ Searchable by date, user, event type

Implementation options:

1. **Vault Audit Backend** (recommended): Built-in, compliant
2. **Elasticsearch with ILM**: Index lifecycle management prevents deletion
3. **AWS CloudWatch Logs**: Retention policies enforced by AWS
4. **Blockchain-backed**: For highest assurance (enterprise)

## Email Notification Requirements

### Recovery Workflow Notifications

Users MUST receive email notifications at each stage of the recovery process.

#### When Recovery Request is Submitted

**To**: User whose data is being recovered
**Subject**: `[CheckTick] Recovery request submitted for your account`

```text
Hello Dr. Smith,

A recovery request has been submitted for your CheckTick account.

Survey: Diabetes Audit 2025
Requested: 30 November 2025 at 14:30 UTC
Request ID: ABC-123-XYZ

If you did NOT request this recovery:
→ Click here to cancel immediately: [Cancel Recovery Link]
→ Or reply to this email

If you DID request this recovery:
→ No action needed - we'll update you on progress

The recovery process includes identity verification and a mandatory waiting period for your protection.

Questions? Contact support@checktick.uk

CheckTick Security Team
```

#### When Identity Verification is Approved

**To**: User
**Subject**: `[CheckTick] Identity verification approved - recovery proceeding`

```text
Hello Dr. Smith,

Your identity has been verified for recovery request ABC-123-XYZ.

What happens next:
1. Two administrators must independently approve
2. A 48-hour waiting period will begin
3. You'll receive another email when recovery is ready

If you did NOT request this:
→ Click here to cancel: [Cancel Recovery Link]

CheckTick Security Team
```

#### When Dual Authorization is Complete (Time Delay Starts)

**To**: User
**Subject**: `[CheckTick] Recovery approved - 48-hour waiting period started`

```text
Hello Dr. Smith,

Your recovery request has been approved by two administrators.

Request ID: ABC-123-XYZ
Survey: Diabetes Audit 2025
Approved: 30 November 2025 at 16:30 UTC

⏱️ WAITING PERIOD: 48 hours

Recovery will be available: 2 December 2025 at 16:30 UTC

This waiting period is a security measure to give you time to object if this recovery was not requested by you.

If you did NOT request this recovery:
→ CLICK HERE TO CANCEL IMMEDIATELY: [Cancel Recovery Link]
→ This will cancel the recovery and flag your account for security review

CheckTick Security Team
```

#### When Time Delay is Approaching End (12 hours before)

**To**: User
**Subject**: `[CheckTick] Recovery completing in 12 hours`

```text
Hello Dr. Smith,

Your recovery request ABC-123-XYZ will complete in 12 hours.

Survey: Diabetes Audit 2025
Recovery available: 2 December 2025 at 16:30 UTC

After completion, you'll be able to set a new password and recovery phrase.

Last chance to cancel:
→ [Cancel Recovery Link]

CheckTick Security Team
```

#### When Recovery is Complete

**To**: User
**Subject**: `[CheckTick] Recovery complete - please set new credentials`

```text
Hello Dr. Smith,

Your recovery is complete. You can now access your survey.

Request ID: ABC-123-XYZ
Survey: Diabetes Audit 2025
Completed: 2 December 2025 at 16:31 UTC

IMPORTANT: You must set new credentials:
→ [Set New Password Link]

You'll be asked to:
1. Create a new password
2. Write down a new 12-word recovery phrase
3. Confirm your recovery phrase

For your security, please also:
- Review your account for any unauthorized changes
- Enable two-factor authentication if not already enabled

Questions? Contact support@checktick.uk

CheckTick Security Team
```

#### When User Objects to Recovery

**To**: User
**Subject**: `[CheckTick] URGENT: Recovery cancelled - security review initiated`

```text
Hello Dr. Smith,

You reported that recovery request ABC-123-XYZ was NOT initiated by you.

The recovery has been IMMEDIATELY CANCELLED.

What we're doing:
1. Your account has been flagged for security review
2. We're investigating how the request was submitted
3. A security analyst will contact you within 24 hours

What you should do:
1. Change your password immediately: [Change Password Link]
2. Review recent account activity
3. Check your email for any suspicious password reset requests
4. Contact us if you notice anything unusual

Emergency contact: security@checktick.uk

CheckTick Security Team
```

### Administrative Notifications

#### To Primary Approver When Request Awaits

**To**: Admin users with recovery approval permissions
**Subject**: `[CheckTick Admin] Recovery request awaiting approval`

```text
A recovery request requires your review.

Request ID: ABC-123-XYZ
User: dr.smith@nhs.uk
Survey: Diabetes Audit 2025
Submitted: 30 November 2025 at 14:30 UTC

Identity Verification Status:
✅ Photo ID verified
✅ Video call completed
✅ Security questions: 3/3 correct

Action required:
→ [Review and Approve/Reject]

This request requires dual authorization (two admin approvals).

CheckTick Admin System
```

#### To Organization Admin on Recovery Completion

**To**: Organization owners
**Subject**: `[CheckTick Admin] Recovery completed in your organisation`

```text
A platform recovery was completed for a user in your organisation.

User: dr.smith@nhs.uk
Survey: Diabetes Audit 2025
Request ID: ABC-123-XYZ

Timeline:
- Submitted: 30 Nov 2025 14:30
- Verification: 30 Nov 2025 15:00
- Primary Approval: admin1@checktick.uk (30 Nov 2025 16:00)
- Secondary Approval: admin2@checktick.uk (30 Nov 2025 16:30)
- Time Delay: 48 hours
- Completed: 2 Dec 2025 16:31

View audit trail:
→ [View in Recovery Dashboard]

CheckTick Admin System
```

### Email Technical Requirements

| Requirement | Specification |
|-------------|---------------|
| Sender | noreply@checktick.uk |
| Reply-to | support@checktick.uk |
| SPF/DKIM/DMARC | Required for deliverability |
| TLS | Required for transmission |
| HTML + Plain text | Both versions required |
| Links | Must use HTTPS, expire after 7 days |
| Tracking | No open/click tracking (privacy) |

## SIEM Integration

### Supported SIEM Platforms

| Platform | Integration Method | Configuration |
|----------|-------------------|---------------|
| **Elasticsearch** (self-hosted) | Direct API | HTTP POST to `/_bulk` |
| **Splunk** | HTTP Event Collector | HEC token + endpoint |
| **Microsoft Sentinel** | Log Analytics Workspace | Workspace ID + key |
| **AWS CloudWatch** | CloudWatch Logs API | IAM credentials |
| **Datadog** | Log API | API key |
| **Graylog** | GELF | UDP/TCP endpoint |

### Elasticsearch Configuration (Recommended for Self-Hosted)

#### Index Template

```json
{
  "index_patterns": ["checktick-audit-*"],
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "index.lifecycle.name": "checktick-audit-policy",
    "index.lifecycle.rollover_alias": "checktick-audit"
  },
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "event_type": { "type": "keyword" },
      "severity": { "type": "keyword" },
      "actor.id": { "type": "integer" },
      "actor.email": { "type": "keyword" },
      "actor.ip": { "type": "ip" },
      "target.id": { "type": "integer" },
      "target.email": { "type": "keyword" },
      "resource.type": { "type": "keyword" },
      "resource.id": { "type": "integer" },
      "details": { "type": "object", "enabled": true }
    }
  }
}
```

#### Index Lifecycle Policy

```json
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "10GB",
            "max_age": "7d"
          }
        }
      },
      "warm": {
        "min_age": "30d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 }
        }
      },
      "cold": {
        "min_age": "90d",
        "actions": {
          "freeze": {}
        }
      },
      "delete": {
        "min_age": "2555d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

Note: 2555 days = 7 years (compliance retention)

### Alert Rules

Configure these alerts in your SIEM:

#### Critical Alerts (Immediate Response)

```yaml
alerts:
  - name: recovery_user_objection
    description: User reported unauthorized recovery attempt
    condition: event_type == "recovery_user_objection"
    severity: critical
    action:
      - page_on_call
      - create_incident
      - freeze_account

  - name: custodian_component_accessed
    description: Offline custodian component was used
    condition: event_type == "custodian_component_accessed"
    severity: critical
    action:
      - notify_security_team
      - log_to_compliance

  - name: high_recovery_rate
    description: Unusual number of recovery requests
    condition: count(event_type == "recovery_request_submitted") > 10 in 24h
    severity: critical
    action:
      - investigate
      - consider_disabling_recovery
```

#### Warning Alerts

```yaml
alerts:
  - name: elevated_recovery_rate
    description: Above-normal recovery requests
    condition: count(event_type == "recovery_request_submitted") > 5 in 24h
    severity: warning
    action:
      - notify_admins

  - name: failed_verification_attempts
    description: Multiple failed identity verifications
    condition: count(event_type == "recovery_verification_rejected" AND target.id == $user_id) > 2 in 24h
    severity: warning
    action:
      - flag_for_review

  - name: admin_recovery_spike
    description: High number of admin-initiated recoveries
    condition: count(event_type IN ["team_admin_recovery", "org_admin_recovery"]) > 20 in 24h
    severity: warning
    action:
      - review_admin_activity
```

### Dashboard Requirements

#### Platform Admin Logs Dashboard

The Platform Admin Logs dashboard (`/platform-admin/logs/`) provides superusers with a unified interface for viewing both application audit logs and infrastructure logs. This interface is essential for:

- **DPST Compliance**: Quarterly log reviews with the Data Protection Officer (DPO)
- **Security Monitoring**: Real-time visibility into authentication events and admin actions
- **Incident Investigation**: Correlating application events with infrastructure logs

**Application Logs Tab:**
| Column | Description |
|--------|-------------|
| Timestamp | When the event occurred |
| Action | Event type (login, logout, admin action, etc.) |
| User | Who performed the action |
| Details | Additional context |
| Severity | INFO, WARNING, CRITICAL |

**Infrastructure Logs Tab:**
| Column | Description |
|--------|-------------|
| Timestamp | When the log was generated |
| Level | Log level (debug, info, warn, error) |
| Instance | Container/pod identifier |
| Message | Log message content |

Both tabs support filtering by severity and pagination for large result sets. The dashboard displays summary statistics at the top for quick overview.

**Access Control:** Only platform superusers can access this dashboard. All access is logged.

**Quarterly Review Process:**
1. CTO and DPO schedule quarterly review session
2. Review CRITICAL and WARNING events in Application Logs
3. Review ERROR events in Infrastructure Logs
4. Document findings and any required actions
5. Update security policies as needed

#### SIEM Integration (Optional)

Create these dashboards in your SIEM for additional monitoring:

#### Recovery Operations Dashboard

| Widget | Type | Data |
|--------|------|------|
| Recovery requests (24h) | Counter | Count of `recovery_request_submitted` |
| Recovery rate trend | Line chart | Daily recovery requests over 30 days |
| Pending requests | Table | Open requests with status |
| Time to completion | Histogram | Duration from request to completion |
| Verification methods | Pie chart | Breakdown by verification type |
| Recovery by tier | Bar chart | Individual vs Team vs Org |

#### Security Monitoring Dashboard

| Widget | Type | Data |
|--------|------|------|
| Failed logins (24h) | Counter | `user_login_failed` events |
| User objections | Alert | `recovery_user_objection` events |
| Admin actions | Table | All admin recovery actions |
| Custodian access | Timeline | `custodian_component_accessed` events |
| Geographic anomalies | Map | Login locations by IP |
| Authentication methods | Pie chart | Password vs SSO vs MFA |

## Implementation Checklist

### Audit Logging

- [ ] All required events generate audit entries
- [ ] Audit entries follow standard format
- [ ] Entries are written to Vault audit backend
- [ ] Entries are forwarded to SIEM (if configured)
- [ ] Retention policies are enforced
- [ ] Audit entries cannot be modified or deleted

### Email Notifications

- [ ] All recovery workflow emails implemented
- [ ] Email templates reviewed for clarity
- [ ] Cancel links work correctly
- [ ] SPF/DKIM/DMARC configured
- [ ] Plain text and HTML versions provided
- [ ] Links expire appropriately
- [ ] Admin notifications implemented

### SIEM Integration

- [ ] Index template created
- [ ] Lifecycle policy configured
- [ ] Real-time forwarding working
- [ ] Critical alerts configured
- [ ] Warning alerts configured
- [ ] Dashboards created
- [ ] Alert routing tested

## Related Documentation

- [Key Management for Administrators](/docs/key-management-for-administrators/) - Admin procedures
- [Recovery Dashboard](/docs/recovery-dashboard/) - Dashboard specifications
- [Business Continuity](/docs/business-continuity/) - Disaster recovery and quarterly log reviews
- [Vault Setup](/docs/vault/) - SIEM deployment
- [Logging Policy](/compliance/logging-policy/) - Compliance requirements and review schedules
