---
title: Encryption for Organisation Users
category: security
priority: 5
---

This guide explains how encryption works for CheckTick users who are members of an organisation, including organisation owners and administrators.

## Overview

Organisation users have streamlined encryption based on their authentication method:

### For Password-Based Organisation Members

If you sign in with a username and password:

- **Individual encryption** with password + recovery phrase (same as individual users)
- **Organisation encryption** automatically added for administrative recovery
- You unlock your surveys using your password or recovery phrase
- Organisation admins can recover access if needed

### For SSO Organisation Members (Google, Azure, Okta, etc.)

If you sign in via Single Sign-On (SSO):

- **SSO-only encryption** - no passwords or recovery phrases needed! 🎉
- **Organisation encryption** automatically added for administrative recovery
- Surveys unlock automatically when you sign in via SSO
- Organisation admins can recover access if needed
- **If you lose SSO access**: your organisation admin can recover the survey, then you regain SSO access

This is the **recommended approach** for organisations using SSO - it's simple, secure, and has built-in recovery through organisation admins.

## Encryption Strategy Comparison

| User Type | Authentication | Encryption Method | What You Remember | Recovery Options |
|-----------|---------------|-------------------|-------------------|------------------|
| **Org Member** | SSO (Google/Azure/Okta) | **SSO + Organisation** | Nothing! Auto-unlock | 1. SSO account<br>2. Organisation admin recovery |
| **Org Member** | Username/Password | **Password + Recovery + Organisation** | Password OR recovery phrase | 1. Password<br>2. Recovery phrase<br>3. Organisation admin recovery |
| **Individual User** | SSO | **SSO-Only** OR **SSO + Recovery** (your choice) | Nothing OR recovery phrase | 1. SSO account<br>2. Recovery phrase (if chosen) |
| **Individual User** | Username/Password | **Password + Recovery** | Password OR recovery phrase | 1. Password<br>2. Recovery phrase |

**Key insight**: Organisation members with SSO get the best of both worlds - no passwords to remember, but still have administrative recovery as a safety net.

## Creating an Encrypted Survey

The process depends on your authentication method:

### For SSO Organisation Members (Recommended)

When you publish a survey for the first time while signed in via SSO:

1. Navigate to your survey and click **Publish**
2. Configure publish settings (visibility, dates, etc.)
3. Click **Publish Survey**
4. **Done!** Encryption is automatic - no setup required

**What happens behind the scenes:**

- Your survey key is encrypted using your SSO identity
- The same key is also encrypted with your organisation's master key
- Your survey will auto-unlock whenever you're signed in via SSO
- Your organisation admin can recover access if you lose SSO
- All of this happens automatically - you don't need to do anything

**This means:**

- No passwords to remember
- No recovery phrases to save
- Automatic unlock when signed in
- Organisation admin can help if needed
- Simple, secure, and convenient

### For Password-Based Organisation Members

When you publish a survey for the first time with password authentication:

1. Navigate to your survey and click **Publish**
2. You'll be prompted to set up encryption:
   - **Choose a strong password** (12+ characters recommended)
   - **Write down your 12-word recovery phrase** (shown once only)
3. Confirm you've saved your recovery information
4. Done! Organisation encryption is automatically added too

**What this means:**

- You can unlock with your password (quick daily access)
- You can unlock with your recovery phrase (if you forget password)
- Your organisation admin can recover access (administrative backup)
- **You must remember your password OR save your recovery phrase**

## Organisation Key Recovery (Owners & Admins)

### When to Use Administrative Recovery

Organisation key recovery should be used when:

- A team member leaves the organisation unexpectedly
- An employee forgets their password and loses their recovery phrase
- An SSO user loses access to their SSO account
- Critical survey data needs to be accessed for business continuity
- Compliance or audit requirements necessitate access

⚠️ **This is an administrative function** - all access is logged and should follow your organisation's policies.

### How to Recover a Member's Survey

1. **Navigate** to the survey you need to access
2. **Click** "Organisation Key Recovery" (available to owners/admins only)
3. **Review** the warning about administrative access
4. **Type** `recover` to confirm you understand this is an audited action
5. **Access** the survey - it will be unlocked for your session

### Security Checks

The system verifies:

- You are an organisation owner or admin
- The survey belongs to your organisation
- You are not the survey owner (owners use regular unlock)
- You explicitly confirm the recovery action
- All recovery actions are logged

### Audit Trail

Every organisation key recovery creates an audit log entry containing:

- **Who**: Username of the administrator performing recovery
- **What**: Survey name and slug
- **When**: Timestamp of recovery
- **Target**: Survey owner's username
- **Role**: Whether recovered by owner or admin
- **Method**: Organisation master key recovery

These logs are:

- **Immutable**: Cannot be edited or deleted
- **Encrypted**: Stored securely in the database
- **Permanent**: Retained for compliance purposes
- **Accessible**: Available to organisation owners for review

## Organisation Master Key

### What Is It?

The organisation master key is a cryptographic key that:

- Encrypts copies of all survey keys in your organisation
- Is stored securely in the CheckTick database
- Enables administrative recovery without knowing member passwords
- Is never exposed to users or administrators

### How It's Created

When an organisation is created:

1. A random 256-bit master key is generated
2. It's encrypted using AES-256-GCM
3. It's stored in the organisation record
4. Survey keys are automatically encrypted with it during survey creation

### Security Properties

- **Automatic**: No manual key management required
- **Secure**: Uses industry-standard AES-256-GCM encryption
- **Audited**: All uses are logged
- **Restricted**: Only accessible to owners and admins
- **Per-Organisation**: Each organisation has its own unique master key

## Roles and Permissions

### Organisation Owner

The organisation owner:

- Can recover **any survey** in their organisation
- Can view all organisation surveys (even when locked)
- Can edit organisation settings
- Sees admin recovery options on all member surveys

### Organisation Admin

Organisation admins:

- Can recover **any survey** in their organisation
- Can view all organisation surveys (even when locked)
- Have the same recovery powers as owners
- Are identified in audit logs as "admin" role

### Organisation Creator

Regular members with Creator role:

- Can create and publish surveys
- Use SSO auto-unlock OR password/recovery phrase (depending on authentication)
- **Cannot** recover other members' surveys
- Can request admin assistance if they lose access

### Organisation Viewer

Members with Viewer role:

- Can view published surveys (when unlocked by owner)
- **Cannot** create surveys
- **Cannot** perform key recovery
- **Cannot** unlock encrypted surveys

## Best Practices for Organisations

### For Organisation Owners/Admins

 **Do:**

- Document your recovery procedures
- Use recovery only when necessary
- Review audit logs regularly
- Inform users about organisational recovery capabilities
- Follow your organisation's data access policies
- Encourage SSO use for simpler key management

 **Don't:**

- Use recovery for routine survey access
- Access surveys without business justification
- Share recovery capabilities with unauthorized users
- Bypass organisational policies

### For Organisation Members (SSO Users)

**Do:**

- Maintain access to your SSO account
- Contact your admin if you lose SSO access
- Understand that admins can recover your surveys
- Trust your organisation's authentication system

**Don't:**

- Share your SSO credentials
- Assume your data is inaccessible to your organisation
- Create password-based surveys if SSO is available (unnecessarily complex)

### For Organisation Members (Password Users)

**Do:**

- Choose strong passwords for your surveys
- Store your recovery phrase securely
- Understand that admins can recover your surveys
- Contact your admin if you lose access

**Don't:**

- Assume your data is inaccessible to your organisation
- Share passwords with colleagues
- Rely solely on admins for access (use your own credentials)

### Recovery Policy Recommendations

Your organisation should establish policies for:

1. **When** administrative recovery is permitted
2. **Who** can authorize recovery requests
3. **How** recovery actions are documented
4. **What** notification requirements exist
5. **Where** audit logs are reviewed

**Example Policy**:
 Organisation key recovery may only be used when:

> - The survey owner has left the organisation, OR
> - The owner has exhausted all personal recovery methods, AND
> - A department head approves the access in writing, AND
> - The recovery is documented in our compliance log"

## Compliance and Regulations

### GDPR Considerations

Organisation key recovery supports GDPR compliance:

- **Audit Trail**: All recovery actions are logged
- **Justification**: Recovery should be documented with business need
- **Data Subject Rights**: Organisations can fulfill access requests
- **Breach Response**: Admins can secure data if accounts are compromised

### Healthcare Compliance (HIPAA, etc.)

For healthcare organisations:

- **Break-Glass Access**: Administrative recovery serves as emergency access
- **Audit Logging**: Meets requirements for access monitoring
- **Business Continuity**: Ensures patient data availability
- **Role-Based Access**: Restricts recovery to authorized administrators

### Data Retention

Consider:

- How long audit logs are retained
- Who has access to audit records
- How recovery actions are reported
- When recovered data should be re-encrypted

## Frequently Asked Questions

### Can organisation admins see my password?

No. Admins can unlock your survey using the organisation master key, but they never see your personal password or recovery phrase (if you're using password-based authentication).

### Will I know if an admin recovers my survey?

Currently, there is no automatic notification to survey owners. However, all recovery actions are logged and your organisation can establish notification procedures.

### Can I opt out of organisation encryption?

No. All surveys created within an organisation automatically include organisation-level encryption to ensure business continuity.

### What happens if the organisation master key is lost?

The organisation master key is securely stored in the CheckTick database and backed up with all other CheckTick data. There is no scenario where it can be "lost" under normal operations.

### Can I transfer a survey to a different organisation?

Survey transfer capabilities depend on your CheckTick version. Contact your organisation owner or CheckTick support for assistance.

### As an owner, can I see all member passwords?

No. Organisation owners can recover surveys but cannot see member passwords or recovery phrases. Each member's credentials remain private.

### What's the difference between recovery and unlocking?

- **Unlocking**: Using your own SSO account, password, or recovery phrase (member action)
- **Recovery**: Using organisation master key (admin action, audited)

### Can members see who has recovered their surveys?

Currently, audit logs are only accessible to organisation owners. Your organisation should establish procedures for transparency about recovery actions.

### Does recovery create a permanent unlock?

No. Organisation recovery unlocks the survey for a 30-minute session only. After the session expires, the survey is locked again.

### Can I recover surveys from different organisations?

No. You can only recover surveys within organisations where you are an owner or admin.

### Why don't SSO users need passwords or recovery phrases?

SSO users rely on their organisation's authentication system (Google, Microsoft, etc.) and organisation administrative recovery. This provides:

- Simpler user experience (no passwords to remember)
- Stronger authentication (SSO providers typically enforce MFA)
- Organisational control (admins can manage access)
- Backup recovery (organisation admin can recover if SSO fails)

If you lose access to your SSO account, contact your organisation admin for survey recovery, then work with your IT department to regain SSO access.

## Related Documentation

- [Encryption for Individual Users](encryption-individual-users.md) - Personal survey encryption options
- [Authentication and Permissions](authentication-and-permissions.md) - User roles and access control
- [User Management](user-management.md) - Managing organisation members
- [Patient Data Encryption](patient-data-encryption.md) - Complete technical specification
- [OIDC SSO Setup](oidc-sso-setup.md) - Setting up Single Sign-On

## Audit Log Review

Organisation owners should regularly review audit logs to:

- Monitor administrative access patterns
- Verify recovery actions were authorized
- Detect potential security issues
- Meet compliance requirements

Access audit logs through your organisation dashboard (feature availability may vary by CheckTick version).
