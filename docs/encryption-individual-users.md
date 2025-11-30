---
title: Encryption for Individual Users
category: security
priority: 4
---

This guide explains how encryption works for CheckTick users who are not part of an organisation.

## Overview

Individual users have different encryption options depending on how they authenticate:

### For Password-Based Users

If you sign in with a username and password, you get **dual-path encryption**:

- **Password Protection**: Unlock surveys with a password you choose
- **Recovery Phrase**: 12-word backup if you forget your password
- **Complete Control**: Only you can access your encrypted data
- **No Dependencies**: Works without organisation membership

### For SSO Users (Google, Azure, etc.)

If you sign in via Single Sign-On (SSO), you have **two options** when publishing an encrypted survey:

**Option A: SSO-Only Encryption** (Recommended for most users)

- ✅ **Fast setup** - no passwords or phrases to remember
- ✅ **Automatic unlock** - surveys open when you're signed in
- ✅ **Simple** - trust your SSO provider completely
- ⚠️ **Dependency** - if you lose access to your SSO account, your data is permanently inaccessible
- 👍 **Best for**: Low-to-medium sensitivity data, trusted SSO provider (e.g., your work Google/Microsoft account)

**Option B: SSO + Recovery Phrase** (Belt and suspenders)

- ✅ **Automatic unlock** via SSO for convenience
- ✅ **Recovery phrase backup** - 12 words you save securely
- ✅ **Maximum safety** - can recover even if you lose SSO access
- ⚠️ **Responsibility** - you must safely store your recovery phrase
- 👍 **Best for**: High-sensitivity data, critical research data, paranoid users

## Choosing Your Encryption Strategy

| Scenario | Authentication | Recommended Option | Why |
|----------|---------------|-------------------|-----|
| Personal research, low sensitivity | SSO (Google/Azure) | **SSO-Only** | Simple, convenient, low risk |
| Work account with stable SSO | SSO (Work account) | **SSO-Only** | Trust your IT department |
| Critical research data | SSO | **SSO + Recovery** | Maximum protection |
| Highly sensitive patient data | SSO | **SSO + Recovery** | Can't afford data loss |
| No SSO available | Username/Password | **Password + Recovery** | Only option (automatic) |
| Personal Gmail might change | SSO (Personal Google) | **SSO + Recovery** | Account changes happen |

## Creating an Encrypted Survey

The process depends on your authentication method:

### For SSO Users: Choose Your Strategy

When you publish a survey for the first time while signed in via SSO, you'll see a choice screen:

#### Option 1: SSO-Only Encryption (Recommended)

1. Navigate to your survey and click **Publish**
2. Select **"SSO-Only Encryption"**
3. Review the warning about SSO dependency
4. Click **"Encrypt with SSO Only"**
5. ✅ Done! Your survey is encrypted and will auto-unlock when you sign in

**What this means:**

- Your survey key is encrypted using your SSO identity (e.g., your Google account)
- No passwords or recovery phrases to remember
- Automatic unlock whenever you're signed in via SSO
- **If you lose access to your SSO account, your data is permanently inaccessible**

**When to choose this:**

- You trust your SSO provider (Google, Microsoft, etc.)
- Your SSO account is stable (work account, primary email)
- The data sensitivity is low-to-medium
- You want simplicity and convenience

#### Option 2: SSO + Recovery Phrase (Maximum Security)

1. Navigate to your survey and click **Publish**
2. Select **"SSO + Recovery Phrase"**
3. **Write down your 12-word recovery phrase** (shown once only)
4. Confirm you've saved it
5. ✅ Done! Your survey has dual protection

**What this means:**

- Your survey key is encrypted TWO ways: with your SSO identity AND a recovery phrase
- Automatic unlock via SSO for convenience
- Recovery phrase backup if you lose SSO access
- **You must keep your recovery phrase safe and secure**

**When to choose this:**

- The data is highly sensitive or critical
- You can't afford any risk of data loss
- You're willing to securely store a recovery phrase
- You want maximum protection

### For Password Users: Dual-Path Encryption (Automatic)

Password-based users always get dual-path encryption - no choice needed:

1. Navigate to **Create Survey** from your dashboard
2. Fill in survey details
3. Click **Create Survey**

When publishing for the first time:

1. Click **Publish** on your survey
2. You'll be prompted to set up encryption:
   - **Choose a strong password** (12+ characters recommended)
   - **Write down your 12-word recovery phrase** (shown once only)
3. Confirm you've saved your recovery information
4. ✅ Survey published with encryption enabled

**Daily use:**

- Unlock with your password (recommended for quick access)
- Or use your recovery phrase if you forget your password

## Creating an Encrypted Survey

### Step 1: Create Your Survey

1. Navigate to **Create Survey** from your dashboard
2. Fill in survey details (name, description, etc.)
3. Click **Create Survey**

### Step 2: Set Up Encryption

When publishing your survey, you'll be prompted to set up encryption:

1. **Choose a strong password**
   - Minimum 12 characters recommended
   - Mix of letters, numbers, and symbols
   - Don't reuse passwords from other accounts

2. **Write down your recovery phrase**
   - You'll receive a 12-word recovery phrase
   - Write it down on paper (don't store digitally)
   - This is your **only way** to recover access if you forget your password

3. **Store your recovery hint**
   - The first and last words are shown as a hint
   - Keep your full phrase in a safe place

### Step 3: Confirm and Save

✅ Check the box confirming you've saved your recovery information

⚠️ **Important**: After clicking "I have saved my recovery information", you will **never see these keys again**!

## Unlocking Your Survey

### Using Your Password (Recommended)

1. Navigate to your survey
2. Click **Unlock Survey**
3. Enter your password
4. Click **Unlock**

Your survey will remain unlocked for 30 minutes of activity.

### Using Your Recovery Phrase

If you forget your password:

1. Navigate to your survey
2. Click **Unlock Survey**
3. Click **Use Recovery Phrase Instead**
4. Enter all 12 words in order (space-separated)
5. Click **Unlock**

💡 **Tip**: The recovery hint shows the first and last words to help you find the right recovery phrase if you have multiple.

## Single Sign-On (SSO) Users

If you log in using Google or Microsoft Azure:

### Automatic Survey Unlocking

- Surveys are automatically unlocked when you sign in via SSO
- No password or recovery phrase needed
- Your identity provider (Google/Azure) manages authentication

### How It Works

1. Sign in with your Google or Microsoft account
2. CheckTick automatically unlocks your surveys
3. Surveys remain unlocked for your session (30 minutes of inactivity)

### Setting Up Encryption with SSO

When you create a survey using SSO:

1. Create your survey as normal
2. Publish it - encryption is set up automatically
3. No password or recovery phrase to manage
4. Your survey is encrypted with keys tied to your SSO identity

### Recovery Options for SSO Users

⚠️ **Important**: If your SSO account is disabled or deleted:

- You will lose access to your encrypted surveys
- There is no password or recovery phrase
- Contact your organization's IT administrator to restore access to your SSO account

**Best Practice**: For critical surveys, consider:
- Using a personal account (not SSO) for greater control
- Exporting unencrypted data backups regularly
- Documenting your SSO account details with your organization

## Security Best Practices

### Password Management

✅ **Do:**
- Use a unique password for CheckTick (don't reuse)
- Use a password manager (1Password, Bitwarden, LastPass)
- Choose passwords with 12+ characters
- Include uppercase, lowercase, numbers, and symbols

❌ **Don't:**
- Use common words or patterns
- Share your password with others
- Write passwords in digital notes
- Use the same password for multiple services

### Recovery Phrase Management

✅ **Do:**
- Write down your 12-word phrase on paper
- Store it in a secure location (safe, safety deposit box)
- Consider splitting it between two secure locations
- Test your recovery phrase after writing it down

❌ **Don't:**
- Store in emails, notes apps, or cloud storage
- Take a photo with your phone
- Share with anyone else
- Throw away your written copy

### Session Security

Your unlocked survey session:
- Automatically locks after 30 minutes of inactivity
- Locks immediately when you log out
- Locks if you close your browser (depending on settings)

**Best Practice**: Always lock your survey manually when finished by clicking **Lock Survey** or logging out.

## What Gets Encrypted

### Encrypted Data (Protected)

The following fields are encrypted in survey responses:

- First name, Last name
- Date of birth
- NHS number / Health ID
- Address
- Postcode
- Phone numbers
- Email addresses
- Any other personally identifiable information (PII)

### Unencrypted Data (Metadata)

The following information is **not** encrypted:

- Survey name and description
- Question text and structure
- Survey owner
- Creation and modification dates
- Response counts and statistics

This allows you to browse surveys and see basic information without unlocking.

## Frequently Asked Questions

### What happens if I forget both my password and recovery phrase?

Unfortunately, your data **cannot be recovered**. CheckTick uses end-to-end encryption, meaning we don't have access to your encryption keys. This ensures maximum privacy but requires you to manage your own keys.

### Can CheckTick support help me recover my password?

No. CheckTick staff cannot access your encrypted data or reset your encryption password. This is by design to ensure your data privacy.

### How long does a session stay unlocked?

Surveys remain unlocked for **30 minutes of inactivity**. Each time you interact with the survey, the timer resets.

### Can I change my password?

Currently, passwords and recovery phrases cannot be changed after survey creation. This is a planned feature for future releases.

### What encryption algorithm is used?

CheckTick uses **AES-256-GCM** (Advanced Encryption Standard with Galois/Counter Mode), which provides:
- 256-bit encryption keys (extremely secure)
- Authenticated encryption (prevents tampering)
- Industry-standard security used by banks and governments

### How are my keys derived from my password?

CheckTick uses **Scrypt** key derivation with these parameters:
- Work factor: n=2^14 (16,384 iterations)
- Block size: r=8
- Parallelization: p=1

This makes brute-force attacks computationally expensive while keeping unlock times fast for legitimate users.

### Is my password stored?

No. Your password is never stored. We only store:
- A hash of your encryption key (to verify correct password)
- The encrypted version of your survey key
- Salt values for key derivation

### Can I export my encrypted data?

Yes. You can export survey responses while unlocked. The export will be unencrypted, so handle it carefully.

### What about backups?

CheckTick backups include only the encrypted data. Even our backup systems cannot decrypt your surveys without your password or recovery phrase.

## Related Documentation

- [Encryption for Organization Users](encryption-organization-users.md) - If you're part of an organization
- [Authentication and Permissions](authentication-and-permissions.md) - User roles and access control
- [OIDC SSO Setup](oidc-sso-setup.md) - Setting up Google/Azure single sign-on

## Technical Details

For developers and technical users, see:
- [Patient Data Encryption](patient-data-encryption.md) - Complete technical specification
- [API Documentation](api.md) - API access to encrypted surveys
