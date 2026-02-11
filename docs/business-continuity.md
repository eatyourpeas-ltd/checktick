---
title: Business Continuity
category: security
priority: 4
---

# Business Continuity and Disaster Recovery

This guide covers disaster recovery procedures for CheckTick's encryption system, ensuring business continuity when things go wrong.

## Overview

CheckTick's encryption system is designed with redundancy and recovery in mind. This document covers:

- Recovery scenarios by subscription tier
- Vault unavailability procedures
- Key personnel changes
- Organisation dissolution
- Data backup and restoration

## Recovery Scenarios by Tier

### Free Tier

**Data Location**: Encrypted in database (all surveys are encrypted)

**Disaster Scenarios:**

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Forgot password | Can't unlock surveys | Use recovery phrase |
| Lost recovery phrase | Backup option unavailable | Use password (still works) |
| Lost both password AND phrase | Can't unlock surveys | Platform recovery (48-96 hours) |

**Note**: All Free tier surveys are encrypted with the same protection as paid tiers. Free tier is limited to 3 surveys and cannot use patient data templates, but data security is equivalent across all tiers.

**Recommendation**: Free tier is suitable for general surveys. Upgrade to Pro or higher for unlimited surveys and access to patient data templates.

### Individual Tier

**Data Location**: Encrypted in database + Vault backup

**Disaster Scenarios:**

| Scenario | Impact | Recovery Path |
|----------|--------|---------------|
| Forgot password | Can't unlock surveys | Use recovery phrase |
| Lost recovery phrase | Backup option unavailable | Use password (still works) |
| Lost both password AND phrase | Can't unlock surveys | Platform recovery (48-96 hours) |
| Account compromised | Potential unauthorized access | Change password immediately |
| Email access lost | Can't receive notifications | Update email via support |

**Recovery Priority Order:**

1. Password (instant)
2. Recovery phrase (instant)
3. Platform recovery (48-96 hours)

### Pro Tier

Same as Individual, with faster recovery:

| Feature | Individual | Pro |
|---------|-----------|-----|
| Verification time | 24-48 hours | 12-24 hours |
| Time delay | 48 hours | 24 hours |
| Total recovery time | 72-96 hours | 36-48 hours |

### Team Tiers

**Data Location**: Encrypted with team key, backed up with organisation key

**Disaster Scenarios:**

| Scenario | Impact | Recovery Path |
|----------|--------|---------------|
| Team member loses SSO | Can't access team surveys | Re-authenticate SSO |
| Team admin unavailable | Can't manage team | Organisation owner takes over |
| Team key corrupted | Team surveys inaccessible | Restore from organisation key |
| Entire team loses access | All team surveys locked | Organisation admin recovery |

**Recovery Hierarchy:**

1. Team admin recovery (instant)
2. Organisation owner recovery (instant)
3. Platform recovery (if organisation also unavailable)

### Organisation Tier

**Data Location**: Hierarchical encryption (platform → org → team → survey)

**Disaster Scenarios:**

| Scenario | Impact | Recovery Path |
|----------|--------|---------------|
| Organisation owner leaves | Management gap | Transfer ownership first |
| Organisation key compromised | All org data at risk | Rotate keys immediately |
| Multiple admins unavailable | Recovery bottleneck | Emergency contact list |
| Organisation dissolves | Orphaned data | See "Organisation Dissolution" section |

### Enterprise Tier

**Data Location**: Dedicated Vault instance + custom backup procedures

**Disaster Scenarios:** Handled per custom agreement. Contact your account manager.

## Vault Unavailability

### Symptoms

- Recovery requests fail
- New surveys can't be created (if using Vault for key storage)
- Audit logs not being written
- Dashboard shows "SIEM Disconnected"

### Immediate Actions

1. **Check Vault status** (for self-hosters):

   ```bash
   # Check Vault health
   curl -s https://your-vault-url/v1/sys/health | jq

   # Expected response for healthy sealed Vault:
   # {"sealed":true,"standby":true}

   # Expected response for healthy unsealed Vault:
   # {"sealed":false,"standby":false,"initialized":true}
   ```

2. **If Vault is sealed**, unseal it:

   ```bash
   # You need 3 of 4 unseal keys
   vault operator unseal <key1>
   vault operator unseal <key2>
   vault operator unseal <key3>
   ```

3. **If Vault is completely down**, see "Vault Recovery" below.

### Vault Recovery Procedures

#### Scenario: Vault Pod/Container Crashed

**For Northflank deployments:**

1. Check Northflank dashboard for service status
2. Review container logs for crash reason
3. Restart the service if needed
4. Unseal Vault after restart (always required after restart)

**For self-hosted deployments:**

1. Check container/pod status:
   ```bash
   docker ps -a | grep vault
   # or
   kubectl get pods -l app=vault
   ```

2. Review logs:
   ```bash
   docker logs vault-container
   # or
   kubectl logs vault-pod
   ```

3. Restart and unseal:
   ```bash
   docker start vault-container
   # Then unseal with keys
   ```

#### Scenario: Vault Data Corrupted

If Vault's storage backend is corrupted:

1. **Stop Vault immediately** to prevent further damage

2. **Restore from backup** (if available):

   ```bash
   # Stop Vault
   docker stop vault-container

   # Restore data directory from backup
   cp -r /backup/vault-data/* /vault/file/

   # Start Vault
   docker start vault-container

   # Unseal
   vault operator unseal <keys>
   ```

3. **If no backup exists**, you'll need to:
   - Re-initialize Vault (generates new keys)
   - Re-run setup script
   - Re-create all escrowed keys (users need to re-encrypt)

#### Scenario: Lost Unseal Keys

**If you've lost unseal keys but Vault is still running (unsealed):**

1. **Generate new unseal keys immediately** using `vault operator rekey`
2. Store new keys securely
3. Document the rotation

**If Vault is sealed and keys are lost:**

⚠️ **Critical**: Without unseal keys, Vault data is unrecoverable by design.

Options:

1. Re-initialize Vault (loses all stored secrets)
2. Users fall back to password/recovery phrase access
3. Contact HashiCorp support (Enterprise only)

**Prevention:**

- Store unseal keys in multiple secure locations
- Use Shamir's Secret Sharing (default) - need 3 of 4 keys
- Document key storage locations securely

### During Vault Outage

While Vault is unavailable:

| Feature | Status | Workaround |
|---------|--------|------------|
| Survey access (with password) | ✅ Works | Users can still access with password |
| Survey access (with recovery phrase) | ✅ Works | Users can still access with phrase |
| Platform recovery | ❌ Blocked | Wait for Vault restoration |
| New survey creation | ⚠️ Depends | Works if not using Vault for key storage |
| Audit logging to Vault | ❌ Blocked | Logs queued locally, sync after recovery |

## Key Personnel Changes

### Team Admin Leaves

**Before they leave:**

1. Transfer admin role to another team member
2. Review their recovery actions in audit log
3. Revoke their team admin access
4. Update emergency contact list

**If they've already left:**

1. Organisation owner assigns new team admin
2. Review audit logs for any concerning activity
3. Consider rotating team encryption key

### Organisation Owner Leaves

**Before they leave:**

1. **Transfer ownership** to designated successor
2. Update Vault access credentials
3. Transfer custodian component responsibility
4. Update emergency contacts
5. Review and document all admin procedures

**If they've already left without handover:**

1. Contact CheckTick support immediately
2. Provide proof of authority (board resolution, HR confirmation)
3. Platform will facilitate emergency ownership transfer
4. Consider this a security incident - review all access

### Platform Admin Changes

**When platform admins change:**

1. Rotate custodian component
2. Update Vault access policies
3. Revoke old admin credentials
4. Update dual authorization list
5. Document handover in audit trail

## Organisation Dissolution

When an organisation ceases to exist:

### Planned Dissolution

1. **Notify all users** (30+ days notice recommended)
2. **Export data** that needs to be retained
3. **Transfer surveys** to individual accounts if needed
4. **Archive** read-only copies for compliance
5. **Delete** organisation and keys after retention period

### Unplanned Dissolution

If organisation disappears suddenly (bankruptcy, etc.):

1. **Users contact CheckTick support**
2. **Verify user identity** (standard verification)
3. **Verify organisation status** (legal documentation)
4. **Platform recovery** for individual user data
5. **Surveys transferred** to individual accounts
6. **Organisation keys** securely destroyed

### Data Retention After Dissolution

| Data Type | Retention | Reason |
|-----------|-----------|--------|
| Patient data | Per original consent | Healthcare regulations |
| Audit logs | 7 years minimum | Compliance |
| Encryption keys | Destroyed after data migrated | Security |
| User accounts | Converted to individual | Continuity |

## Backup Procedures

### What Gets Backed Up

| Component | Backup Frequency | Retention | Location |
|-----------|-----------------|-----------|----------|
| Database (encrypted surveys) | Daily | 30 days | Cloud storage |
| Vault data | Daily | 30 days | Separate cloud storage |
| Unseal keys | N/A (manual) | Permanent | Secure offline storage |
| Custodian component | N/A (manual) | Permanent | Secure offline storage |
| Audit logs | Real-time to SIEM | 2-7 years | SIEM + archive |

### Custodian Component Backup

The custodian component is critical and must be backed up securely:

**Primary Storage:**

- Secure safe or lockbox
- Limited access (2-3 designated people)
- Access logging

**Backup Storage:**

- Different physical location
- Same security requirements
- At least 50 miles from primary (disaster protection)

**Format:**

- Paper printout in sealed envelope
- USB drive (encrypted, in safe)
- Never in email, cloud storage, or databases

### Testing Backups

**Monthly:**

- Verify backup files exist and are readable
- Check backup job logs for errors
- Confirm retention policy is enforced

**Quarterly:**

- Test restore procedure in isolated environment
- Verify Vault backup can be unsealed
- Document any issues found

**Annually:**

- Full disaster recovery drill
- Restore from backup to new infrastructure
- Measure Recovery Time Objective (RTO)
- Update procedures based on findings

## Recovery Rate Monitoring

### Normal vs Abnormal Recovery Rates

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Recovery requests/day | 0-2 | 3-5 | 5+ |
| Recovery rate (% users) | <0.5% | 0.5-1% | >1% |
| Failed verifications | 0-1 | 2-3 | 4+ |

### Alerting Configuration

Configure alerts in your SIEM or monitoring system:

```yaml
alerts:
  - name: high_recovery_rate
    condition: recovery_requests_per_day > 5
    severity: warning
    notify: security@organisation.uk

  - name: critical_recovery_rate
    condition: recovery_requests_per_day > 10
    severity: critical
    notify:
      - security@organisation.uk
      - cto@organisation.uk

  - name: verification_failures
    condition: failed_verifications_per_user > 3
    severity: warning
    notify: security@organisation.uk
```

### Investigating Unusual Activity

If recovery rates spike:

1. **Check for legitimate causes:**
   - Password policy change forcing resets
   - SSO outage affecting users
   - New user onboarding batch

2. **Check for malicious activity:**
   - Review source IPs of requests
   - Check for patterns (same user, same time)
   - Look for social engineering indicators

3. **Take action if needed:**
   - Temporarily disable platform recovery
   - Require additional verification
   - Contact affected users directly

## Emergency Contacts

Maintain an emergency contact list:

```markdown
## CheckTick Emergency Contacts

### Platform Support
- Email: support@checktick.uk
- Emergency: emergency@checktick.uk

### Internal Contacts
- Primary Admin: [name] - [phone] - [email]
- Secondary Admin: [name] - [phone] - [email]
- Custodian Key Holder 1: [name] - [phone]
- Custodian Key Holder 2: [name] - [phone]

### External Contacts
- HashiCorp Support: [if Enterprise]
- Northflank Support: [if using Northflank]
- Legal/Compliance: [name] - [email]
```

## Recovery Time Objectives

### Target Recovery Times

| Scenario | RTO Target | RPO Target |
|----------|-----------|-----------|
| Vault temporary outage | 1 hour | 0 (no data loss) |
| Vault data corruption | 4 hours | 24 hours (daily backup) |
| Complete infrastructure loss | 24 hours | 24 hours |
| Key personnel unavailable | 4 hours | N/A |
| Organisation dissolution | 30 days | N/A |

### Achieving RTO/RPO

**To meet these targets:**

1. **Automated monitoring** with immediate alerts
2. **Documented procedures** that anyone can follow
3. **Regular testing** of recovery procedures
4. **Multiple backup locations** geographically distributed
5. **Redundant personnel** (no single points of failure)

## Quarterly Compliance Reviews

Regular log reviews are essential for DPST compliance and early detection of security issues.

### Review Schedule

| Review | Frequency | Participants | Focus Areas |
|--------|-----------|--------------|-------------|
| Log Review | Quarterly | CTO, DPO | Security events, access patterns |
| Access Audit | Quarterly | CTO, DPO | User permissions, admin actions |
| Disaster Recovery Test | Annually | IT Team | Backup restoration, failover |

### Quarterly Log Review Process

1. **Preparation** (1 week before)
   - Export log summaries from Platform Admin Logs dashboard
   - Identify any CRITICAL events requiring discussion
   - Prepare trend analysis from previous quarter

2. **Review Session** (CTO + DPO)
   - Access Platform Admin Logs at `/platform-admin/logs/`
   - Review Application Logs: Focus on CRITICAL and WARNING events
   - Review Infrastructure Logs: Focus on ERROR events and anomalies
   - Document findings and action items

3. **Post-Review Actions**
   - Update security policies if needed
   - Address any identified vulnerabilities
   - File documentation for DPST evidence
   - Schedule follow-up for action items

### Using Platform Admin Logs Dashboard

The Platform Admin Logs dashboard (`/platform-admin/logs/`) provides:

- **Application Logs Tab**: Structured audit events (logins, admin actions, data access)
- **Infrastructure Logs Tab**: Container/pod logs from hosting provider
- **Filtering**: By severity level and pagination for large datasets
- **Statistics**: Quick overview cards showing event counts

This interface consolidates logs that would otherwise require:
- Direct database queries for audit logs
- Hosting provider dashboard access for infrastructure logs
- Manual correlation between application and infrastructure events

See [Audit Logging and Notifications](audit-logging-and-notifications.md) for detailed dashboard documentation.

## Related Documentation

- [Encryption for Users](/docs/encryption-for-users/) - End-user guide
- [Key Management for Administrators](/docs/key-management-for-administrators/) - Admin procedures
- [Vault Setup](/docs/vault/) - Deploying Vault
- [Self-Hosting Backup](/docs/self-hosting-backup/) - Backup procedures

## Getting Help

**For business continuity planning:**

- Email: support@checktick.uk

**For active incidents:**

- Email: emergency@checktick.uk
- Include: Incident description, impact, urgency

**For compliance questions:**

- Email: compliance@checktick.uk
