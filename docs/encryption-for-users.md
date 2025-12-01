---
title: Encryption for Users
category: security
priority: 1
---

# Data Encryption: User Guide

CheckTick protects your sensitive survey data with encryption. This guide explains how encryption works for each subscription tier and what happens if you forget your password.

## Quick Overview

| Subscription Tier | Encryption Features | Recovery Options |
|-------------------|---------------------|------------------|
| **Free** | Standard surveys only (no patient data) | N/A - no encryption needed |
| **Individual** | Password + Recovery Phrase + **Platform Key Escrow** | Password OR Recovery Phrase OR **Verified Identity Recovery** |
| **Pro** | Enhanced encryption + Vault backup | Password OR Recovery Phrase OR **Verified Identity Recovery** |
| **Team Small/Medium/Large** | Team-shared keys + Organization master key | Team admin OR Organization admin OR Platform recovery |
| **Organization** | Hierarchical encryption + Admin recovery | Organization admin OR **Platform recovery** |
| **Enterprise** | Custom encryption + Dedicated Vault | Custom recovery procedures + Platform recovery |

## The Important Promise

**🛡️ You will never permanently lose your patient data due to a forgotten password.**

CheckTick implements **ethical key recovery**: if you lose both your password AND recovery phrase, the platform can help you regain access through a secure identity verification process. This ensures patient data remains accessible while maintaining strong security.

---

## Free Tier

### What You Get
- Create up to 3 surveys
- Collect general survey responses
- Export your data
- Basic API access

### When to Use
- Testing CheckTick features
- Non-sensitive surveys and feedback forms
- Learning how the platform works
- General data collection (no patient identifiers)

### Limitations
⚠️ **Patient data collection is not available** on the Free tier

The Patient Details (encrypted) template is a paid feature. To collect patient-identifiable data with encryption, upgrade to Pro (£5/month) or higher.

### Upgrade Path
When you're ready to collect patient data or need more features:
- **Pro (£5/mo)**: Unlimited surveys, encrypted patient data, collaboration
- **Team (from £25/mo)**: Team collaboration, SSO, admin recovery
- **Organization**: Custom pricing, hierarchical management

---

## Individual Tier

### What You Get
- **Password Protection**: Unlock surveys with your password
- **Recovery Phrase**: 12-word backup phrase for account recovery
- **Platform Key Escrow**: Secure backup stored in HashiCorp Vault
- **AES-256-GCM Encryption**: Industry-standard encryption
- **Per-Survey Keys**: Each survey has its own unique encryption key

### How It Works

#### When You Create Your First Survey

1. **Choose a strong password** (12+ characters, mix of letters/numbers/symbols)
2. **Write down your 12-word recovery phrase** (shown once only - very important!)
3. **Confirm you've saved it** ✅
4. Done! Your survey is encrypted

**Behind the scenes:**
- Your survey key is encrypted with your password
- The same key is encrypted with your recovery phrase
- A secure backup is encrypted with a platform key and stored in Vault
- You don't need to do anything for the backup - it's automatic

#### Daily Use

**To unlock your survey:**
- Navigate to your survey
- Enter your password (quickest method)
- Survey stays unlocked for 30 minutes

**If you forget your password:**
- Use your 12-word recovery phrase instead
- Survey unlocked, set a new password

### The Safety Net: Platform Key Recovery

**What if you lose BOTH your password AND recovery phrase?**

Don't panic! CheckTick can help you recover access through a secure verification process:

#### Step 1: Request Recovery
- Contact support: support@checktick.uk
- Explain that you've lost access to your survey
- Provide your account email and survey details

#### Step 2: Identity Verification (24-48 hours)
You'll need to verify your identity:
- **Upload photo ID** (driving license, passport, etc.)
- **Video verification call** (15 minutes with CheckTick admin)
- **Security questions** from your account setup
- **Optional**: Employment verification (if work-related survey)

#### Step 3: Dual Authorization (Security)
- **Primary admin** reviews your verification
- **Secondary admin** independently approves the request
- Both admins document the reason for recovery
- All actions are logged in an immutable audit trail

#### Step 4: Time Delay (24-48 hours)
- After approval, there's a mandatory waiting period
- You'll receive an email when the time delay starts
- This gives you time to object if the request wasn't from you
- Also prevents rushed or impulsive recovery actions

#### Step 5: Recovery Completion
- Platform admin retrieves the offline custodian key component
- Your survey key is recovered from Vault
- You regain access to your survey
- You're prompted to set a new password + recovery phrase

#### Step 6: Notification & Audit
- You receive email confirmation of the recovery
- All actions are logged (who, what, when, why)
- Audit trail is immutable and can't be deleted

### Security Guarantees

✅ **Your data is protected:**
- Admins can't access your data without going through formal recovery
- Every recovery action is logged and auditable
- You're notified by email if your account is recovered
- Time delays prevent hasty or unauthorized access

✅ **Multiple recovery paths:**
1. **Password** (fastest - instant access)
2. **Recovery phrase** (backup - instant access)
3. **Platform recovery** (last resort - requires verification + 48-96 hours)

✅ **Zero-knowledge encryption:**
- CheckTick never sees your password or recovery phrase
- Your data is encrypted before it reaches our servers
- We can only help with recovery, not bypass your encryption

### Best Practices

**Do:**
- ✅ Store your recovery phrase in a password manager (1Password, Bitwarden, etc.)
- ✅ Write it down and keep in a safe place
- ✅ Use a strong, unique password
- ✅ Keep your email address up to date (for recovery notifications)

**Don't:**
- ❌ Store your password and recovery phrase in the same place
- ❌ Share your recovery phrase with anyone
- ❌ Use the same password as other accounts
- ❌ Ignore recovery notification emails (could be unauthorized access)

---

## Pro Tier

### What You Get
Everything in Individual tier, plus:
- **Enhanced Vault Backup**: Redundant storage across multiple Vault nodes
- **Priority Recovery**: Faster identity verification (12-24 hours)
- **Extended Audit Logs**: 2-year retention instead of 1 year
- **Compliance Reports**: GDPR/HIPAA audit trail exports

### Differences from Individual

| Feature | Individual | Pro |
|---------|-----------|-----|
| Basic encryption | ✅ | ✅ |
| Platform recovery | ✅ | ✅ |
| Verification time | 24-48 hours | 12-24 hours |
| Time delay | 24-48 hours | 24 hours (faster) |
| Audit retention | 1 year | 2 years |
| Compliance reports | ❌ | ✅ |
| Dedicated support | ❌ | ✅ |

---

## Team Tiers (Small, Medium, Large)

### What You Get
- **Team-Shared Encryption Keys**: All team members use the same survey key
- **Admin Recovery**: Team admin can recover member surveys
- **Platform Recovery**: Backup if team admin also loses access
- **SSO Support**: Auto-unlock with Google/Azure/Microsoft

### How It Works

Teams can operate in two modes:
1. **Standalone Teams** - Independent teams not part of an organization
2. **Organization Teams** - Teams that belong to a parent organization

#### Standalone Team Key Management

**When your standalone team is created:**

1. Team owner sets up the team encryption key
2. All team surveys are encrypted with this team key
3. Team admin manages access and recovery
4. Platform provides backup recovery as a last resort

**For team members:**

- Sign in with SSO (Google, Azure, etc.)
- Surveys automatically unlock when signed in
- No passwords or recovery phrases to remember!
- Team admin can grant/revoke access

#### Organization Team Key Management

**When your team belongs to an organization:**

1. Organization owner sets up organization master key
2. Team keys are derived from organization key
3. All team surveys encrypted with team key
4. Both team admin and organization admin can manage access

**For team members:**

- Same SSO experience as standalone teams
- Additional recovery path through organization admin
- Hierarchical key management provides extra redundancy

#### SSO and Patient Data Surveys

**Important**: When a survey collects patient data, SSO auto-unlock alone is not sufficient.

Even with SSO, you'll be asked to set a **passphrase** when your survey includes patient demographics (NHS number, date of birth, names, etc.). This adds an extra layer of protection:

- **Why**: Patient data requires explicit intent to access - it shouldn't unlock "automatically" when you log in
- **How**: You set a passphrase the first time you publish a patient data survey
- **Using**: Enter your passphrase to unlock the survey (in addition to being signed in via SSO)

This ensures that even if your SSO session is compromised, patient data remains protected.

#### Whole Survey Encryption

When your survey collects patient data, **the entire response is encrypted**, not just the demographics:

- ✅ Patient identifiers (NHS number, name, DOB)
- ✅ Clinical observations and notes
- ✅ Free-text answers
- ✅ All checkbox/dropdown selections
- ✅ Everything in that survey response

This provides complete protection - you can't accidentally expose clinical context by encrypting identifiers alone.

#### Recovery Options for Standalone Teams

**If a team member loses access (standalone team):**

**Option 1: Team Admin Recovery** (Instant)

- Team admin can recover member's survey immediately
- Logged for compliance

**Option 2: Platform Recovery** (24-96 hours)

- Same process as Individual tier
- Identity verification + dual authorization + time delay
- Used if team admin is also unavailable
- All actions logged in immutable audit trail

#### Recovery Options for Organization Teams

**If a team member loses access (organization team):**

**Option 1: Team Admin Recovery** (Instant)

- Team admin can recover member's survey immediately
- No identity verification needed (within same organization)
- Logged for compliance

**Option 2: Organization Admin Recovery** (Instant)

- Organization owner can recover any team survey
- Used when team admin is unavailable
- Logged for compliance

**Option 3: Platform Recovery** (Rare - used if organization dissolves)

- Same process as Individual tier
- Identity verification + dual auth + time delay
- Used only if organization no longer exists

### Best Practices for Teams

**Team Admins:**

- Document who has access to team surveys
- Review access quarterly
- Remove access when members leave
- Monitor recovery actions in audit log

**Team Members:**

- Maintain access to your SSO account
- Report lost SSO access immediately
- Don't share SSO credentials
- Understand that team admin can recover your surveys

---

## Organization Tier

### What You Get
- **Hierarchical Encryption**: Platform → Organization → Team → Survey
- **Centralized Key Management**: Organization owner controls master key
- **Flexible Recovery**: Multiple recovery paths for different scenarios
- **Advanced Audit**: Dashboard showing all key operations
- **Compliance Tools**: GDPR/HIPAA/NHS DSPT reports

### How It Works

```
Platform Master Key
├─ Your Organization Master Key
   ├─ Team A Key → Team A Surveys
   ├─ Team B Key → Team B Surveys
   └─ Direct Org Surveys
```

#### Key Management Hierarchy

**Organization Owner:**
- Sets organization-wide encryption passphrase
- Can recover any survey in organization
- Manages team access
- Reviews audit logs

**Team Admins:**
- Can recover surveys within their team
- Cannot access other teams' surveys
- Report to organization owner

**Team Members:**
- Automatic unlock via SSO
- Request admin recovery if needed
- Focus on data collection, not key management

### Recovery Dashboard

Organization owners have access to a recovery management dashboard:

**Features:**
- 📊 View pending recovery requests
- 🔍 Review identity verification submissions
- ✅ Approve/reject recovery requests
- ⏱️ Monitor time delay countdowns
- 📝 View complete audit trail
- 📈 Recovery rate monitoring (alerts if unusual activity)
- 🔐 Dual authorization workflow

**Example dashboard view:**
```
┌─────────────────────────────────────────────────────────┐
│ Recovery Requests                              [Filter] │
├─────────────────────────────────────────────────────────┤
│ Dr. Sarah Jones | diabetes-audit-2025                   │
│ Status: Awaiting Dual Authorization (1 of 2 approvals)  │
│ Submitted: 2025-11-28 | Time Delay: 18h remaining       │
│ [View Details] [Approve] [Reject]                       │
├─────────────────────────────────────────────────────────┤
│ Dr. Michael Brown | patient-satisfaction                │
│ Status: In Time Delay Period                            │
│ Approved: 2025-11-29 | Ready for completion: 24h        │
│ [View Audit Trail]                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Enterprise Tier

### What You Get
- **Dedicated Vault Instance**: Your own HashiCorp Vault cluster
- **Custom Recovery Procedures**: Tailored to your organization's policies
- **Advanced Security**: Custom time delays, multi-party authorization
- **Compliance Integration**: Direct integration with your SIEM
- **White-glove Support**: Dedicated account manager

### Custom Features

Work with CheckTick to design:
- Custom identity verification workflows
- Integration with your existing identity systems
- Custom audit log retention (5+ years)
- Advanced recovery procedures (3+ person authorization)
- Automated compliance reporting
- Dedicated security reviews

---

## Understanding the Recovery Process

### Why Platform Recovery is Ethical

**For patient data custodians**, permanent data loss due to forgotten passwords is unacceptable:

- Clinicians have a duty of care to their patients
- Research data represents significant time and resources
- Patient information may be needed for future care
- Regulatory requirements may mandate data retention

**Platform recovery** balances security with data availability:
- Strong security through verification + dual auth + time delay
- Accountability through immutable audit trails
- User notification prevents unauthorized access
- Compliance with healthcare regulations

### How We Prevent Abuse

**Multiple safeguards:**

1. **Identity Verification**: Photo ID + video call + security questions
2. **Dual Authorization**: Two admins must approve independently
3. **Time Delay**: 24-48 hour waiting period after approval
4. **User Notification**: Email alerts at every stage
5. **Audit Trail**: Immutable logs stored in Vault + SIEM
6. **Recovery Dashboard**: All recoveries visible to organization admins
7. **Rate Monitoring**: Alerts if recovery requests spike (potential attack)
8. **Offline Key Component**: Custodian key not stored in database

### What Gets Logged

Every recovery action creates audit entries:

```json
{
  "timestamp": "2025-11-30T14:30:00Z",
  "action": "recovery_request_submitted",
  "user": "dr.smith@nhs.uk",
  "survey": "diabetes-audit-2025",
  "verification_method": "photo_id_video_call",
  "status": "pending_dual_authorization"
}

{
  "timestamp": "2025-11-30T16:00:00Z",
  "action": "recovery_approved_primary",
  "admin": "admin1@checktick.uk",
  "user": "dr.smith@nhs.uk",
  "survey": "diabetes-audit-2025",
  "reason": "User forgot password and recovery phrase. ID verified."
}

{
  "timestamp": "2025-11-30T16:30:00Z",
  "action": "recovery_approved_secondary",
  "admin": "admin2@checktick.uk",
  "user": "dr.smith@nhs.uk",
  "survey": "diabetes-audit-2025",
  "time_delay_until": "2025-12-02T16:30:00Z"
}

{
  "timestamp": "2025-12-02T16:31:00Z",
  "action": "recovery_completed",
  "admin": "admin1@checktick.uk",
  "user": "dr.smith@nhs.uk",
  "survey": "diabetes-audit-2025",
  "custodian_component_used": true
}
```

These logs:
- Cannot be deleted or modified
- Are stored in Vault's audit backend
- Can be forwarded to external SIEM
- Are available for compliance audits
- Include who, what, when, why for every action

---

## Frequently Asked Questions

### General Questions

**Q: Do I really need encryption?**

A: If you're collecting:
- Patient names, NHS numbers, or dates of birth
- Sensitive health information
- Personal identifiers
- Data covered by GDPR special categories

Then **yes**, you should use encryption. CheckTick makes it easy.

**Important**: When your survey collects patient data, **the entire survey response is encrypted** - not just the patient demographics. This means all answers (clinical observations, notes, outcomes, etc.) are protected together with the patient identifiers. This approach provides complete protection for the entire clinical encounter.

**Q: What if I just use strong passwords on my CheckTick account?**

A: Account passwords protect access to CheckTick, but encryption protects the data itself. Even if someone gained access to the database, encrypted data would be unreadable.

**Q: Is encryption hard to use?**

A: No! For most users (Teams/Organizations with SSO), it's automatic. For individual users, it's just:
1. Choose a password when creating your first survey
2. Write down your 12-word recovery phrase
3. Done!

### Recovery Questions

**Q: How long does platform recovery take?**

A:
- **Identity verification**: 12-48 hours (depending on tier)
- **Dual authorization**: Usually within 24 hours
- **Time delay**: 24-48 hours after approval
- **Total**: 60-96 hours (2.5-4 days) typically

**Q: Can I speed up recovery if it's urgent?**

A: Pro/Enterprise tiers have faster verification (12-24 hours), but time delays can't be bypassed - they're a critical security measure.

**Q: What if the recovery request wasn't from me?**

A: You'll receive email notifications at each stage. If you didn't request recovery:
1. Click "Report Unauthorized Access" in the email
2. Recovery is immediately cancelled
3. Your account is flagged for security review
4. You're prompted to change your password

**Q: Will admins read my survey data during recovery?**

A: No. Recovery gives **you** access back. Admins retrieve your encryption key but don't decrypt your data. You unlock the survey yourself after recovery is complete.

**Q: What happens to my data if I lose access permanently?**

A: With platform recovery, you can't lose access permanently (as long as you can verify your identity). That's the whole point!

### Security Questions

**Q: Can CheckTick admins access my data without my knowledge?**

A: No. Recovery requires:
- Your request (or your organization admin's request)
- Identity verification
- Dual authorization
- Time delay
- Immutable audit logs
- User notification emails

Silent access is not possible.

**Q: What if my recovery phrase is stolen?**

A: If someone has your recovery phrase, they can access your surveys. This is why:
- Store it securely (password manager + physical backup)
- Don't share it with anyone
- Treat it like cash or credit card details

**Q: Is platform recovery less secure than no recovery?**

A: No! Platform recovery is **more secure** than users writing passwords on sticky notes or reusing weak passwords because they're afraid of forgetting them. The verification + dual auth + time delay + audit trail make it robust.

### Team/Organization Questions

**Q: Can my organization admin access my surveys without asking?**

A: For organization users:
- **Team surveys**: Yes, team admin has access (this is by design for collaboration)
- **Personal surveys within org**: Only through recovery process (requires your request or verification you're unavailable)
- All admin access is logged for audit

**Q: What if my organization admin loses their password?**

A: Organization admins can use platform recovery (same process as individual users). This is why the custodian component is stored offline - as a last resort for organization-level key recovery.

### Technical Questions

**Q: What encryption does CheckTick use?**

A: AES-256-GCM (Galois/Counter Mode) with authenticated encryption. This is the same encryption used by:
- Signal (secure messaging)
- WhatsApp (end-to-end encryption)
- 1Password (password manager)
- US Government (classified information)

**Q: Where are my encryption keys stored?**

A:
- **Your password/recovery phrase**: Never stored (you remember it)
- **Encrypted survey keys**: In the database (can only be decrypted with your password/phrase)
- **Recovery backup keys**: In HashiCorp Vault (encrypted with platform key)
- **Platform custodian component**: Offline storage (not in database or environment variables)

**Q: What's HashiCorp Vault?**

A: Vault is industry-leading secrets management software used by:
- Fortune 500 companies
- Major healthcare organizations
- Government agencies
- Financial institutions

It provides hardened, audited, compliant key storage.

**Q: Can I see the audit logs for my surveys?**

A:
- **Individual users**: Via support request
- **Organization admins**: Via recovery dashboard
- **Enterprise**: Direct SIEM integration

---

## Summary

### Key Takeaways

1. **All paid tiers have strong encryption** using industry-standard AES-256-GCM

2. **Multiple recovery options** mean you won't lose your data:
   - Password (instant)
   - Recovery phrase (instant)
   - Platform recovery (2-4 days, requires verification)

3. **Security measures prevent abuse**:
   - Identity verification
   - Dual authorization
   - Time delays
   - Immutable audit logs
   - User notifications
   - Recovery dashboard

4. **SSO users have the easiest experience** (Teams/Organizations):
   - Automatic unlock
   - No passwords to remember
   - Admin recovery if needed

5. **Platform recovery is ethical and secure**:
   - Prevents permanent data loss
   - Multiple safeguards
   - Full accountability
   - Healthcare-compliant

### Choosing Your Tier

**Choose Individual if:**
- Solo practitioner
- Personal research
- Want full control
- Don't mind managing password + recovery phrase

**Choose Pro if:**
- Need faster recovery
- Want extended audit logs
- Need compliance reports
- High-value data

**Choose Team if:**
- Working in a team
- Want SSO convenience
- Need admin recovery
- Collaborative surveys

**Choose Organization if:**
- Multiple teams
- Need centralized management
- Want recovery dashboard
- Compliance requirements

**Choose Enterprise if:**
- Large organization
- Custom security requirements
- Need dedicated Vault
- Want white-glove support

---

## Getting Help

**For encryption questions:**
- See: [Key Management for Administrators](key-management-for-administrators.md)
- See: [Business Continuity Guide](business-continuity.md)

**For recovery requests:**
- Email: support@checktick.uk
- Include: Account email, survey name, verification method preference

**For security concerns:**
- Email: security@checktick.uk
- Report unauthorized recovery attempts immediately

**For technical details:**
- See: [Patient Data Encryption (Technical Spec)](patient-data-encryption.md)
- See: [Vault Integration](vault.md)

---

**Remember**: Encryption protects your data, but YOU are the first line of defense. Use strong passwords, store recovery phrases securely, and stay vigilant about recovery notification emails.

🛡️ **Your data. Your keys. Your control. Our ethical backup.**
