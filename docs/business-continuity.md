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

## Decrypting Vault Unseal Keys and Custodian Shares

### Overview

CheckTick uses **YubiKey hardware security keys** to protect the most sensitive cryptographic material:

- **Vault Unseal Keys**: Required to unseal HashiCorp Vault after restart
- **Custodian Component Shares**: Required for emergency platform recovery

**Storage Architecture:**

- **2 shares encrypted with YubiKeys** (requires physical possession + PIN)
- **1 share in physical safe** (plaintext backup)
- **1 share in cold storage** (offsite plaintext backup)

**Recovery Threshold**: Any 3 of 4 shares can unseal Vault or reconstruct the custodian component.

### Prerequisites

Before attempting decryption:

1. **Hardware Required:**
   - YubiKey 1 (Custodian A)
   - YubiKey 2 (Custodian B)
   - Access to physical safe (for share 3)

2. **Software Required:**

```bashmacOS
brew install opensc ykmanUbuntu/Debian
sudo apt install opensc-pkcs11 yubikey-manager
```

1. **Files Required:**
   - Download encrypted shares from Bitwarden:
     - `vault_unseal_share1.enc` + `vault_unseal_share1.key.enc`
     - `vault_unseal_share2.enc` + `vault_unseal_share2.key.enc`
     - `custodian_component_share1.enc` + `custodian_component_share1.key.enc`
     - `custodian_component_share2.enc` + `custodian_component_share2.key.enc`

2. **Credentials Required:**
   - YubiKey 1 PIN (6-8 digits)
   - YubiKey 2 PIN (6-8 digits)
   - Physical safe access

### Scenario 1: Unsealing Vault After Restart

**When Vault Restarts** (planned maintenance, server reboot, or crash), it enters a **sealed state** and requires 3 of 4 unseal keys to become operational.

#### Using the Automated Script

The fastest way to unseal Vault is using the provided script:

```bashNavigate to vault directory
cd vaultRun unsealing script
./unseal_vault.sh
```

**Script Workflow:**

1. **Prompts for YubiKey 1**
   - Insert YubiKey 1
   - Press Enter
   - Enter PIN when prompted
   - Script decrypts vault_unseal_share1

2. **Prompts for YubiKey 2**
   - Remove YubiKey 1
   - Insert YubiKey 2
   - Press Enter
   - Enter PIN when prompted
   - Script decrypts vault_unseal_share2

3. **Prompts for physical safe share**
   - Retrieve share 3 from physical safe
   - Script displays all 3 decrypted shares

4. **Apply shares to Vault**

```bash
# SSH to Vault server
#Unseal with each share
vault operator unseal
Paste share 1vault operator unseal
Paste share 2vault operator unseal
Paste share 3Vault is now unsealed
```

#### Manual Decryption (If Script Unavailable)

If the script is not available, decrypt shares manually:

**Step 1: Decrypt Share 1 with YubiKey 1**

```bash
# Insert YubiKey 1Decrypt the AES key
pkcs11-tool --module /usr/local/lib/libykcs11.dylib
--slot 0 --id 03 --decrypt --mechanism RSA-PKCS
--input vault_unseal_share1.key.enc
--output aes_key1.bin
--login
Enter YubiKey 1 PINDecrypt the share
openssl enc -d -aes-256-cbc -pbkdf2
-in vault_unseal_share1.enc
-pass file:aes_key1.binSave the output, then clean up
shred -u aes_key1.bin
```

**Step 2: Decrypt Share 2 with YubiKey 2**

```bash
# Remove YubiKey 1, insert YubiKey 2Decrypt the AES key
pkcs11-tool --module /usr/local/lib/libykcs11.dylib
--slot 0 --id 03 --decrypt --mechanism RSA-PKCS
--input vault_unseal_share2.key.enc
--output aes_key2.bin
--login
Enter YubiKey 2 PINDecrypt the share
openssl enc -d -aes-256-cbc -pbkdf2
-in vault_unseal_share2.enc
-pass file:aes_key2.binSave the output, then clean up
shred -u aes_key2.bin
```

**Step 3: Retrieve Share 3 from Physical Safe**

- Open physical safe at primary location
- Retrieve `vault_unseal_share3.txt` (plaintext)

**Step 4: Apply to Vault**

```bash
vault operator unseal <share-1>
vault operator unseal <share-2>
vault operator unseal <share-3>
```

#### Vault Unsealing Timeframe

| Step | Duration | Notes |
|------|----------|-------|
| Gather custodians | 15-60 min | Depends on availability |
| Decrypt shares | 5-10 min | Using script |
| Apply to Vault | 2-5 min | Manual entry |
| **Total** | **25-75 min** | Typical: 30-45 min |

### Scenario 2: Platform Emergency Recovery

**When Required**: User has lost both their password AND recovery phrase and needs emergency access to their encrypted surveys.

**Prerequisites:**

- Vault must be unsealed (see Scenario 1 if needed)
- Recovery request created in Django admin (status: `PENDING_PLATFORM_RECOVERY`)
- Authorization from appropriate administrator

#### Using the Automated Script

```bash
#Navigate to scripts directory
cd s
# Run platform key unsealing script
./unseal-platform-key.sh
```

**Script Workflow:**

1. Decrypts custodian_component_share1 with YubiKey 1
2. Decrypts custodian_component_share2 with YubiKey 2
3. Prompts for share 3 from physical safe
4. Displays all 3 shares for use in recovery command

**Execute Platform Recovery:**

```bash
docker compose exec web python manage.py execute_platform_recovery
--recovery-request-id <id>
--custodian-share "<share-1-from-script>"
--custodian-share "<share-2-from-script>"
--custodian-share "<share-3-from-safe>"
--new-password "TempPassword123!"
--audit-approved-by "admin@example.com"
```

**What Happens:**

1. Reconstructs custodian component from 3 shares (Shamir's Secret Sharing)
2. Retrieves Vault component from HashiCorp Vault
3. XORs components to derive Platform Master Key
4. Decrypts organisation key → team key → survey KEK
5. Re-encrypts survey KEK with user's new temporary password
6. Updates database and creates audit log
7. Notifies user of recovery completion

#### Platform Recovery Timeframe

| Step | Duration | Notes |
|------|----------|-------|
| Verify identity | 24-48 hours | User verification process |
| Time delay | 48 hours | Security cooling-off period |
| Gather custodians | 15-60 min | Coordinate availability |
| Decrypt shares | 5-10 min | Using script |
| Execute recovery | 2-5 min | Run management command |
| **Total** | **3-5 days** | Includes verification + delay |

### Scenario 3: YubiKey Unavailable

If a YubiKey is lost, damaged, or the PIN is locked:

**Option 1: Use Remaining YubiKey + Physical Backups**

```bash
# You still have YubiKey 1 (or 2)
# Use it to decrypt one share
./unseal_vault.sh  # Will work with 1 YubiKeyThen use physical backups for shares 3 and 4:
# - Share 3: Physical safe at primary location
# - Share 4: Cold storage at secondary locationApply 3 shares to Vault
vault operator unseal <share-from-yubikey>
vault operator unseal <share-3-from-safe>
vault operator unseal <share-4-from-cold-storage>
```

**Option 2: Use All Physical Backups**

If both YubiKeys are unavailable:

```bash
# Retrieve shares from physical locations:
# - Share 2: Physical safe (was originally encrypted, now keep plaintext backup)
# - Share 3: Physical safe
# - Share 4: Cold storageApply any 3 shares to Vault
vault operator unseal <share-2>
vault operator unseal <share-3>
vault operator unseal <share-4>
```

**After Recovery:**

1. Order replacement YubiKey(s)
2. Generate new PIV keys on replacement YubiKey
3. Re-encrypt shares with new public keys
4. Update Bitwarden with new encrypted files
5. Test decryption with new YubiKey before destroying old shares

### Scenario 4: Both YubiKeys Compromised

**If YubiKeys are stolen with PINs potentially known:**

**Immediate Actions (within 4 hours):**

1. **Revoke compromised YubiKeys:**

Disable PIV certificates immediately
(Requires physical access to YubiKeys - if stolen, skip to step 2)

1. **Rotate custodian component:**
   - Reconstruct current component from physical backups
   - Generate new component using `vault/setup_vault.py`
   - Split new component with new YubiKeys
   - Re-encrypt all organizational keys

2. **Audit all key access:**

Check audit logs for suspicious activity:

```bash
docker compose exec web python manage.py shell
from checktick_app.core.models import AuditLog
recent_access = AuditLog.objects.filter(
action='KEY_ACCESS',
created_at__gte=timezone.now() - timedelta(days=7)
)
```

1. **Notify affected users:**
   - Email all organization users
   - Recommend password changes
   - Consider rotating survey encryption keys

**Long-term Actions (within 1 week):**

1. Purchase new YubiKeys (2 primary + 2 backup)
2. Generate new PIV keys
3. Re-split custodian component
4. Distribute new shares to custodians
5. Update documentation

### Troubleshooting Decryption Issues

#### YubiKey Not Detected

```bash
# Check YubiKey is recognized
ykman list
```

If not found:

1. Unplug and re-insert YubiKey
2. Try different USB port
3. Check USB-C adapter (if using USB-A YubiKey)
4. Install/update ykman:

```bash
brew install ykman  # macOS
sudo apt install yubikey-manager  # Ubuntu
```

#### PIN Locked (Too Many Wrong Attempts)

Use PUK to reset PIN (have 3 attempts before PUK locks)

```bash
ykman piv access change-pin
--pin <wrong-pin>
--new-pin <new-pin>
--puk <puk-code>
```

If PUK is also locked:

- PIV application is permanently locked on this YubiKey
- Use other YubiKey or physical backup shares
- Order replacement YubiKey and re-encrypt shares

#### Decryption Returns Gibberish

**Possible Causes:**

- Wrong YubiKey used (share 1 requires YubiKey 1, share 2 requires YubiKey 2)
- Corrupted encrypted file
- Wrong encryption format (old vs new)

**Solutions:**

1. Verify you're using correct YubiKey
Check YubiKey serial number:

```bash
ykman info
```

2. Re-download encrypted files from Bitwarden
May have been corrupted during download3. Try other YubiKey
Maybe shares were re-encrypted and documentation not updated4. Use physical backup shares instead
Retrieve from safe or cold storage

#### pkcs11-tool Command Not Found

Install OpenSC package

```bash
brew install openscUbuntu/Debian:
sudo apt install opensc-pkcs11Verify:
pkcs11-tool --version
```

#### Wrong pkcs11 Library Path

The library path differs by system:

macOS Intel:

```bash
--module /usr/local/lib/libykcs11.dylibmacOS Apple Silicon:
--module /opt/homebrew/lib/libykcs11.dylibUbuntu/Debian:
--module /usr/lib/x86_64-linux-gnu/opensc-pkcs11.soFind your path:
find /usr -name "libykcs11." 2>/dev/null
find /opt -name "libykcs11." 2>/dev/null
```

The unsealing scripts auto-detect the correct path.

### Testing Decryption (Quarterly Recommended)

**Test without unsealing production Vault:**

1. Verify YubiKeys work:

```bash
ykman info  # For each YubiKey2. Test decryption of one share
./vault/unseal_vault.sh
```

Stop after seeing first decrypted share
Don't apply to production Vault3. Verify physical backups accessible
Check you can open safe and locate shares4. Document results
Note any issues found
Update emergency contact list if needed

**Full Disaster Recovery Drill (Annually):**

1. Set up isolated test Vault instance
2. Encrypt test shares with production YubiKeys
3. Practice full unsealing procedure
4. Measure time taken
5. Identify any blockers or delays
6. Update procedures based on findings

### Security Best Practices

**YubiKey Storage:**

- Store YubiKey 1 and YubiKey 2 in separate secure locations
- Never store both YubiKeys together
- Keep YubiKeys on person or in locked drawer when not in use

**PIN Security:**

- Use 6-8 digit random PINs (not birthdays or patterns)
- Store PINs separately from YubiKeys (password manager or sealed envelope)
- Never write PIN on YubiKey or store together
- Change PIN if you suspect it was observed

**Physical Backup Storage:**

- Safe at primary location (Share 3)
- Bank safety deposit box or offsite safe (Share 4)
- At least 50 miles apart (disaster protection)
- Access controlled and logged

**Custodian Availability:**

- Maintain 24/7 contact information for both custodians
- Ensure custodians are in different time zones or departments
- Have backup plan if custodian on vacation/sick
- Document handover procedures for custodian changes

**Regular Audits:**

- Quarterly: Verify YubiKeys functional, PINs known
- Quarterly: Check physical backup locations accessible
- Annually: Full disaster recovery drill
- After any custodian change: Re-test entire process

### Emergency Contact Procedure

**If decryption needed urgently:**

1. **Identify scenario** (Vault restart vs platform recovery)
2. **Contact custodians:**
   - Custodian A: [Name] - [Phone] - [Email]
   - Custodian B: [Name] - [Phone] - [Email]
3. **Coordinate meeting** (in-person preferred for security)
4. **Follow appropriate script** (`unseal_vault.sh` or `unseal-platform-key.sh`)
5. **Document in audit log** (who performed decryption, when, why)

**Escalation if custodians unavailable:**

1. Contact backup custodian (if designated)
2. Use physical backup shares (requires accessing safe + cold storage)
3. For life-threatening emergency: Contact CheckTick support for guidance

### Recovery Time Objectives (Updated)

| Scenario | RTO Target | Dependencies |
|----------|-----------|--------------|
| Vault unsealing (custodians available) | 30-60 min | YubiKeys + safe access |
| Vault unsealing (custodians unavailable) | 2-4 hours | Physical backup retrieval |
| Platform recovery (total) | 3-5 days | Includes verification + time delay |
| YubiKey replacement | 1-2 weeks | Hardware shipping time |
| Complete key rotation (compromise) | 4-8 hours | All custodians + admin coordination |

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
