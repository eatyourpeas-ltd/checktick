---
title: Data Encryption
category: security
priority: 2
---

CheckTick supports encryption of sensitive patient data at rest. This guide explains how encryption works, when to use it, and how to configure it for different account types.

## Table of Contents

- [Quick Reference](#quick-reference) - Choose your encryption option
- [Individual Account Encryption](#individual-account-encryption) - For personal accounts
- [Organisation Account Encryption](#Organisation-account-encryption) - For team accounts

---

## Quick Reference

### Which Encryption Option Should I Use?

| Your Account Type | Recommended Encryption | When to Use | Setup Difficulty |
|------------------|----------------------|-------------|------------------|
| **Individual** (personal account) | **Passphrase encryption** | Collecting sensitive data (e.g., patient information, medical data) | Easy - set once in account settings |
| **Organisation** (team account) | **Organisation-level encryption** | All Organisation surveys automatically encrypted | Medium - requires org owner setup |
| **Organisation** (need individual control) | **Individual passphrase** (in addition to org encryption) | Extra security layer for specific surveys | Easy - works alongside org encryption |

### Encryption Summary Table

| Feature | Individual Passphrase | Organisation Encryption |
|---------|---------------------|------------------------|
| **Who sets it up** | Individual user | Organisation owner |
| **Applies to** | User's own surveys only | All Organisation surveys |
| **Passphrase storage** | Never stored - you must remember it | Never stored - org owner must remember it |
| **Data export** | Requires passphrase to decrypt | Requires org passphrase to decrypt |
| **Lost passphrase** | ⚠️ Data is **permanently** unrecoverable | ⚠️ All org data **permanently** unrecoverable |
| **Setup location** | Account Settings → Security | Organisation Settings → Encryption |
| **Can be changed** | Yes, but requires old passphrase | Yes, but requires old passphrase |
| **Optional** | Yes | Yes |

### Do I Need Encryption?

**You should enable encryption if**:

- Collecting patient names, NHS numbers, or medical identifiers
- Storing sensitive clinical information
- Required by your data protection impact assessment (DPIA)
- Required by your ethics committee
- Handling data covered by GDPR special categories
- Working with vulnerable populations
- Required by organizational policy

**Encryption may not be necessary if**:

- Collecting fully anonymous data
- No identifiable information collected
- Only aggregate/statistical data
- Public surveys with non-sensitive questions

### Quick Start

**For individual accounts**:

1. Go to Account Settings → Security
2. Click "Enable Encryption"
3. Create strong passphrase (min 16 characters)
4. **Write down your passphrase** (you cannot recover it)
5. All future surveys automatically encrypted

**For Organisation accounts**:

1. Organisation owner goes to Organisation Settings → Encryption
2. Click "Enable Organisation Encryption"
3. Create strong passphrase (min 20 characters recommended)
4. **Securely share passphrase** with authorized data managers
5. All Organisation surveys automatically encrypted

---

## Individual Account Encryption

### Overview

Individual account encryption allows you to encrypt survey data using a personal passphrase. This is ideal for:

- Solo researchers
- Individual practitioners
- Personal projects
- When you want exclusive control over data encryption

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User sets passphrase in account settings                 │
│    (never stored on server)                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Survey responses encrypted automatically                  │
│    using AES-256-GCM encryption                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Encrypted data stored in database                        │
│    (unreadable without passphrase)                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. To view/export data, user enters passphrase              │
│    Data decrypted in browser, never on server               │
└─────────────────────────────────────────────────────────────┘
```

### Setting Up Encryption

#### Step 1: Enable Encryption

1. Log in to CheckTick
2. Click your username (top right)
3. Select "Account Settings"
4. Navigate to "Security" tab
5. Find "Data Encryption" section
6. Click "Enable Encryption"

#### Step 2: Create Passphrase

You'll be prompted to create a passphrase:

**Passphrase Requirements**:

- Minimum 16 characters
- Mix of uppercase, lowercase, numbers, symbols recommended
- Should be memorable but not guessable
- Not your login password

**Good passphrases** (examples of pattern, not actual passphrases to use):

- `CorrectHorseBatteryStaple2025!` (random words + year + symbol)
- `MyDog$SpotLoves2Run!` (personal phrase with modifications)
- `PurpleElephants#Dance@Midnight` (memorable sentence)

**Bad passphrases**:

- `password123` (too simple)
- `admin` (too short)
- Your actual login password (creates single point of failure)
- Anything you've used elsewhere

#### Step 3: Confirm and Save

1. Enter your passphrase
2. Re-enter to confirm (ensures no typos)
3. **IMPORTANT**: Check the acknowledgment:
   - ☐ I understand this passphrase is never stored on the server
   - ☐ I understand if I lose this passphrase, my data is permanently unrecoverable
   - ☐ I have written down this passphrase in a secure location
4. Click "Enable Encryption"

#### Step 4: Securely Store Passphrase

**Recommended storage methods**:

- Password manager (1Password, LastPass, Bitwarden)
- Encrypted note in secure location
- Physical written copy in locked safe

**DO NOT**:

- Store in plain text email
- Store in unencrypted cloud notes (e.g., Apple Notes, Google Keep)
- Share via unencrypted messaging
- Tell anyone who doesn't need data access

### Using Encryption

Once encryption is enabled, it works automatically:

#### Creating Encrypted Surveys

1. Create survey as normal
2. If encryption is enabled, you'll see: 🔒 "Encryption enabled" indicator
3. All responses automatically encrypted when submitted
4. No additional action needed

#### Viewing Encrypted Data

When viewing survey responses or exporting data:

1. Navigate to survey dashboard
2. Click "View Responses" or "Export Data"
3. **Passphrase prompt appears**: "Enter your encryption passphrase to decrypt data"
4. Enter your passphrase
5. Data is decrypted **in your browser** (never sent to server)
6. View or download decrypted data

**Session behavior**:

- Passphrase cached for current browser session
- Automatically cleared when you log out
- Cleared if browser closed
- Not stored permanently

#### Exporting Encrypted Data

When you export data:

1. Click "Export Data"
2. Enter encryption passphrase
3. Choose export format (CSV, JSON, Excel)
4. Data is decrypted and downloaded

**Important**: Downloaded data is **no longer encrypted**. You must:

- Encrypt the downloaded file (password-protected ZIP)
- Store in secure location
- Follow data security best practices (see Data Governance guide)

### Changing Your Passphrase

You can change your encryption passphrase:

1. Go to Account Settings → Security
2. Click "Change Encryption Passphrase"
3. Enter **old passphrase** (to decrypt existing data)
4. Enter **new passphrase**
5. All data re-encrypted with new passphrase

**Requirements**:

- Must have old passphrase
- Cannot change if passphrase lost
- Re-encryption happens in background (may take time for large datasets)

### Disabling Encryption

⚠️ **Warning**: Disabling encryption will **decrypt all your survey data**.

To disable:

1. Go to Account Settings → Security
2. Click "Disable Encryption"
3. Enter current passphrase
4. Confirm: "I understand this will decrypt all my survey data"
5. All data decrypted and stored unencrypted

**When you might disable**:

- Data is no longer sensitive (e.g., fully anonymized)
- Moving to Organisation encryption instead
- Decommissioning account

**After disabling**:

- Data remains in database (now unencrypted)
- Can re-enable encryption later (will use new passphrase)

### Lost Passphrase Recovery

**There is no recovery mechanism.**

If you lose your passphrase:

- Your data is **permanently** unrecoverable
- CheckTick support **cannot** help (passphrase never stored)
- You **cannot** decrypt existing data
- You **cannot** change the passphrase without knowing the old one

**Your only options**:

1. If you have unencrypted backups/exports from before, use those
2. Disable encryption and lose access to encrypted data
3. Start fresh with new surveys

**Prevention**:

- Store passphrase in password manager
- Keep physical backup in secure location
- Document passphrase location in organizational procedures
- Consider Organisation encryption for shared responsibility

### Encryption and Data Governance

Encryption works alongside data governance:

| Feature | Without Encryption | With Encryption |
|---------|-------------------|-----------------|
| **Retention period** | Still applies | Still applies |
| **Automatic deletion** | Still happens | Still happens (encrypted data deleted) |
| **Data export** | Immediate | Requires passphrase |
| **Audit logging** | Enabled | Enabled |
| **Legal holds** | Available | Available (data remains encrypted) |
| **Data custodian access** | If authorized | If authorized **and** has passphrase |

**Key point**: Encryption protects data **at rest** (in database). Retention policies and access controls are separate security layers.

### Technical Details

**Encryption algorithm**: AES-256-GCM (Galois/Counter Mode)
**Key derivation**: PBKDF2 with 100,000 iterations
**Passphrase hashing**: SHA-256
**Encryption location**: Client-side (browser) before sending to server
**Decryption location**: Client-side (browser) when viewing data

**What is encrypted**:

- Survey response data (answers to questions)
- Free-text fields
- Uploaded files (if file upload questions used)

**What is NOT encrypted**:

- Survey structure (questions, titles, options)
- Metadata (timestamps, user IDs)
- Audit logs (who accessed what, when)
- Survey settings

**Why metadata is not encrypted**: Allows retention management, audit trails, and access control to function without passphrase.

---

## Organisation Account Encryption

### Overview

Organisation-level encryption applies to **all surveys** created within an Organisation. This is ideal for:

- Healthcare organizations
- Research teams
- Clinical trials
- Any team needing consistent encryption policy

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Organisation owner sets org-wide passphrase              │
│    (never stored on server)                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ALL Organisation surveys automatically encrypted          │
│    (applies to existing and future surveys)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Authorized users enter passphrase to access data         │
│    (org owner controls who has passphrase)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Data encrypted at rest, decrypted client-side            │
│    (same technical implementation as individual)             │
└─────────────────────────────────────────────────────────────┘
```

### Setting Up Organisation Encryption

#### Prerequisites

- You must be the **Organisation owner**
- Organisation account must be active
- Recommend coordinating with team before enabling (will affect all users)

#### Step 1: Enable Organisation Encryption

1. Log in as Organisation owner
2. Navigate to Organisation Settings
3. Select "Encryption" tab
4. Click "Enable Organisation Encryption"

#### Step 2: Create Organisation Passphrase

**Passphrase requirements** (stricter than individual):
- Minimum 20 characters recommended
- Mix of character types
- Not easily guessable
- Not used elsewhere
- Memorable for authorized personnel

**Example patterns**:
- `NHSTrust2025$DiabetesStudy!Secure` (org name + year + project + security)
- `SecureHealthData#TeamAlpha@2025` (descriptive phrase)

#### Step 3: Acknowledge Responsibility

Satisfy each of the following:

- I understand this passphrase encrypts ALL Organisation surveys
- I understand if this passphrase is lost, ALL Organisation data is unrecoverable
- I will securely share this passphrase only with authorized data managers
- I have documented this passphrase in our Organisation's secure records
- I understand I am responsible for passphrase management

#### Step 4: Secure Passphrase Management

**Recommended practices**:

1. **Store in organizational password manager** (e.g., 1Password Teams, LastPass Enterprise)
2. **Document access procedures** (who can access, how to request access)
3. **Create physical backup** in organizational safe
4. **Include in business continuity plan** (what if owner leaves?)
5. **Limit access** to authorized personnel only

**Share passphrase securely**:

- Use encrypted communication (S/MIME email, encrypted messaging)
- Share in person when possible
- Use password manager sharing features
- **Never** send via plain email, Slack, or SMS

### Managing Organisation Encryption

#### Granting Access to Encrypted Data

Organisation encryption creates two levels of access control:

**Level 1: Survey access** (managed in CheckTick)

- Organisation owner assigns users to surveys
- Users can see survey structure
- Users can create/edit surveys

**Level 2: Data access** (managed outside CheckTick)

- Organisation owner shares encryption passphrase with authorized data managers
- Only those with passphrase can decrypt data
- Passphrase sharing is your responsibility

**Example access matrix**:

| User | Survey Access | Has Passphrase | Can View Data |
|------|--------------|----------------|---------------|
| Research Lead | ✅ Owner | ✅ Yes | ✅ Yes |
| Data Manager | ✅ Editor | ✅ Yes | ✅ Yes |
| Clinician | ✅ Editor | ❌ No | ❌ No |
| Research Assistant | ✅ Viewer | ❌ No | ❌ No |

#### Changing Organisation Passphrase

Organisation owner can change the passphrase:

1. Go to Organisation Settings → Encryption
2. Click "Change Organisation Passphrase"
3. Enter **old passphrase**
4. Enter **new passphrase**
5. All surveys re-encrypted with new passphrase

**When to change passphrase**:

- Scheduled rotation (e.g., annually)
- Personnel change (data manager leaves Organisation)
- Security incident or suspected compromise
- Organizational policy requirement

**After changing**:

- Notify all users with old passphrase
- Securely share new passphrase
- Update organizational records
- Old passphrase no longer works

#### Audit Trail

Organisation encryption creates additional audit entries:

- Encryption enabled (timestamp, by whom)
- Passphrase changed (timestamp, by whom)
- Data export attempts (successful and failed)
- Users entering passphrase (successful decryption events)

Organisation owner can view encryption audit log:

1. Organisation Settings → Encryption
2. Click "View Encryption Audit Log"
3. See all encryption-related events

### Organisation + Individual Encryption

You can use **both** Organisation and individual encryption:

```
┌──────────────────────────────────────────┐
│ Organisation Encryption (Layer 1)        │
│  └── All org surveys encrypted           │
│      with org passphrase                 │
│                                          │
│      ┌────────────────────────────────┐ │
│      │ Individual Encryption (Layer 2)│ │
│      │  └── User's surveys get        │ │
│      │      additional encryption     │ │
│      │      with personal passphrase  │ │
│      └────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

**How it works**:

1. User enables individual encryption (in addition to org encryption)
2. User's surveys are **double-encrypted**:
   - First with org passphrase
   - Then with individual passphrase
3. To decrypt data, need **both** passphrases

**When to use double encryption**:

- Extra sensitive data (e.g., HIV status, mental health)
- Principal investigator wants personal control
- Regulatory requirement for dual control
- Separation of duties needed

**To view double-encrypted data**:

1. Enter Organisation passphrase (first layer)
2. Enter individual passphrase (second layer)
3. Data decrypted

**Caution**: If **either** passphrase is lost, data is unrecoverable.

### Disabling Organisation Encryption

⚠️ **Major impact** - affects all Organisation surveys.

To disable:

1. Organisation owner goes to Organisation Settings → Encryption
2. Click "Disable Organisation Encryption"
3. Enter current passphrase
4. Confirm: "I understand this will decrypt ALL Organisation survey data"
5. **All Organisation surveys** decrypted

**Before disabling**:

- Notify all Organisation members
- Confirm data no longer needs encryption
- Export encrypted backups if needed
- Document reason for disabling

### Encryption and Team Workflows

#### Scenario 1: Research Team

**Setup**:

- Organisation owner: Principal Investigator (PI)
- Data managers: 2 research assistants
- Survey creators: 5 clinicians

**Workflow**:

1. PI enables Organisation encryption
2. PI shares passphrase with 2 data managers (via password manager)
3. Clinicians create surveys (automatically encrypted)
4. Clinicians **cannot** view response data (don't have passphrase)
5. Data managers export data for analysis (enter passphrase)

**Benefit**: Separation of duties - clinicians collect data, data managers analyze it.

#### Scenario 2: Clinical Audit Team

**Setup**:

- Organisation owner: Audit Lead
- Encryption access: Audit Lead + Deputy
- Survey access: All clinical staff

**Workflow**:

1. Audit Lead enables encryption
2. Passphrase shared only with Deputy (succession planning)
3. Clinical staff create audit surveys
4. Clinical staff view aggregate results (no passphrase needed for non-identifiable summaries)
5. Audit Lead/Deputy export identifiable data when needed

**Benefit**: Central control of sensitive data access.

#### Scenario 3: Multi-Site Trial

**Setup**:

- Organisation: Trial Coordinating Center
- Sub-organizations: 5 hospital sites
- Encryption: Organisation-level

**Workflow**:

1. Coordinating Center enables Organisation encryption
2. Passphrase shared with lead researcher at each site
3. Each site creates own surveys (within main Organisation)
4. All data encrypted with same organizational passphrase
5. Central data manager can access all site data for analysis

**Benefit**: Consistent encryption across all sites.

### Lost Organisation Passphrase

❌ **Critical situation** - affects entire Organisation.

If Organisation passphrase is lost:

- **All** Organisation survey data is unrecoverable
- Affects all Organisation members
- No recovery mechanism exists
- CheckTick support cannot help

**Prevention measures**:

1. **Multiple secure storage locations**:
   - Organizational password manager (primary)
   - Physical copy in organizational safe (backup)
   - Escrow service (for critical organizations)

2. **Succession planning**:
   - Deputy with passphrase access
   - Documented in business continuity plan
   - Clear handover procedures

3. **Regular verification**:
   - Quarterly passphrase test (attempt to decrypt test survey)
   - Annual review of storage locations
   - Verify backup copies accessible

4. **Documentation**:
   - Who has access to passphrase
   - Where passphrase is stored
   - How to access in emergency
   - Contact information for key personnel

**If lost**:

1. Accept that encrypted data is unrecoverable
2. Disable Organisation encryption (old data lost, new data unencrypted)
3. Use any unencrypted exports previously created
4. Implement stronger passphrase management for future
5. Report to data protection officer if required

### Compliance and Encryption

Organisation encryption supports compliance with:

**GDPR**:

- Article 32: Security of processing (encryption as technical measure)
- Reduces risk in event of data breach
- Demonstrates "appropriate technical measures"

**NHS Data Security and Protection Toolkit**:

- Encryption of personal data at rest
- Access control via passphrase

**Research ethics**:

- Additional protection for sensitive data
- Separation of identifiable data access

**Caldicott Principles**:

- Principle 2: Don't use personal data unless necessary (encryption limits access)
- Principle 6: Use minimum necessary (passphrase access control)

**Important**: Encryption is **one** security measure. Must be combined with:

- Access controls
- Audit trails
- Data retention policies
- Staff training
- Incident response procedures

---

## Best Practices Summary

### Passphrase Management

**Do**:

- Use password manager
- Create long, unique passphrases
- Store backup in secure physical location
- Document who has access
- Share via encrypted channels only
- Rotate passphrases periodically

**Don't**:

- Reuse passphrases from other services
- Share via email/Slack/SMS
- Store in plain text
- Share with unauthorized personnel
- Forget to create backups

### Individual Encryption

**Best for**:

- Solo practitioners
- Personal research projects
- When you want exclusive control

**Key considerations**:

- You are solely responsible for passphrase
- Data unrecoverable if passphrase lost
- Must enter passphrase each session

### Organisation Encryption

**Best for**:

- Teams and organizations
- Consistent security policy
- Shared data responsibility

**Key considerations**:

- Affects all Organisation surveys
- Requires passphrase management procedures
- Must plan for owner succession
- Consider business continuity

### Encryption + Other Security

Encryption is **part** of comprehensive security:

| Security Layer | Purpose | Encryption Role |
|---------------|---------|-----------------|
| **Authentication** | Verify user identity | Complements (who can log in) |
| **Authorization** | Control survey access | Complements (who can see surveys) |
| **Encryption** | Protect data at rest | **Primary** (who can read data) |
| **Audit logging** | Track data access | Complements (monitor usage) |
| **Retention policy** | Delete old data | Independent (applies to encrypted data too) |
| **Backup encryption** | Protect backups | Extension (backups also encrypted) |

---

## Troubleshooting

### Common Issues

**Issue**: "Incorrect passphrase" error when trying to view data

**Solutions**:

- Verify caps lock off
- Check for extra spaces
- Retrieve passphrase from password manager
- If using Organisation encryption, verify you have current passphrase (may have been changed)

---

**Issue**: Forgot passphrase

**Solutions**:

- Check password manager
- Check physical backup location
- For organizations: Contact Organisation owner
- **If truly lost**: Data is unrecoverable - consider disabling encryption (loses access to encrypted data)

---

**Issue**: Passphrase prompt not appearing

**Solutions**:

- Ensure encryption is actually enabled (check Account/Org Settings)
- Clear browser cache/cookies
- Try different browser
- Log out and log back in

---

**Issue**: Want to share data with colleague but they don't have passphrase

**Solutions**:

- **Individual encryption**: Cannot share passphrase (your personal encryption)
  - Export data, re-encrypt with shared password, send encrypted file
  - Disable encryption (if appropriate)
  - Set up Organisation encryption instead

- **Organisation encryption**:
  - Contact Organisation owner to share passphrase with colleague
  - Ensure colleague is authorized to access data
  - Use secure sharing method

---

**Issue**: Slow performance when accessing encrypted surveys

**Solutions**:

- Encryption/decryption happens in browser (CPU-intensive)
- Use modern browser (Chrome, Firefox, Safari)
- Reduce number of responses loaded at once
- Consider exporting data for offline analysis

---

## Getting Help

For encryption issues:

1. **Check this guide** - covers most common scenarios
2. **Contact Organisation owner** (for org encryption issues)
3. **GitHub Issues** - [Report technical issues](https://github.com/eatyourpeas/checktick/issues)
4. **Security incidents** - Contact your Organisation's security team immediately

---

## Summary

**Encryption protects your survey data at rest**:

- Choose individual or Organisation encryption (or both)
- Never lose your passphrase - data is unrecoverable
- Store passphrase in password manager + secure backup
- Encryption complements (not replaces) other security measures
- Plan for passphrase management and succession

**Questions to ask before enabling encryption**:

1. Do I really need encryption? (Is data sensitive enough?)
2. Can I securely manage a passphrase long-term?
3. Individual or Organisation encryption? (Solo vs. team?)
4. Who else needs access to encrypted data?
5. What happens if I lose the passphrase? (Business continuity)
6. How will I share passphrase securely?

**Encryption is a powerful security tool** - use it wisely, manage passphrases carefully, and combine with other security best practices.
