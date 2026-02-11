---
title: Data Security Guide
category: None
---

This guide explains security best practices for handling survey data downloaded from CheckTick, your responsibilities as a data handler, and what to do if something goes wrong.

## Your Responsibility

When you download survey data, **you become responsible** for protecting it. This includes:

- Storing data securely
- Preventing unauthorized access
- Following data protection laws
- Reporting breaches immediately
- Deleting data when no longer needed

**Important:** You can be held personally liable for data breaches if you fail to follow security practices.

## Before You Download

### Check Your Authority

Before downloading data, verify:

- ✓ You have a **legitimate purpose** for accessing the data
- ✓ You have **appropriate permissions** (Creator/Owner/Custodian)
- ✓ Downloading is **necessary** - Can you work with anonymized/aggregated data instead?
- ✓ You have **approval** from your organisation (if required)
- ✓ You understand **your obligations** under data protection laws

### Prepare Your Environment

Ensure your device is secure:

- ✓ **Work device only** - Never use personal computers
- ✓ **Full disk encryption** enabled (FileVault on macOS, BitLocker on Windows)
- ✓ **Strong password** - At least 12 characters, unique
- ✓ **Up-to-date software** - Operating system and security patches current
- ✓ **Antivirus/antimalware** - Running and updated
- ✓ **Firewall** - Enabled and properly configured
- ✓ **Screen lock** - Automatic after 5 minutes of inactivity

### Check Your Network

Download only over secure networks:

- ✓ **Organisational network** - Work VPN or office network
- ✗ **Public WiFi** - Never use coffee shops, airports, hotels
- ✗ **Home network** - Avoid unless it meets organisational security standards
- ✗ **Mobile hotspot** - Avoid unless encrypted and from work device

## During Download

### Secure Download Process

Follow these steps when downloading:

1. **Verify the URL** - Ensure you're on the genuine CheckTick site
2. **Accept disclaimer** - Read and understand your obligations
3. **Save password securely** - Use password manager, never write it down
4. **Download to encrypted location** - Work drive, not Downloads folder
5. **Verify download** - Check file size and integrity
6. **Delete browser history** - Clear download history after saving

### Password Management

The ZIP password is critical:

- ✓ **Use password manager** - LastPass, 1Password, Bitwarden, etc.
- ✓ **Copy carefully** - No typos, no extra spaces
- ✓ **Save immediately** - Before closing the download page
- ✗ **Never email** - Even to yourself
- ✗ **Never write down** - Not on paper, sticky notes, or text files
- ✗ **Never share** - Except with authorized colleagues via secure method

### Immediate Actions

After downloading:

1. **Move to secure location** - Encrypted folder on work drive
2. **Extract the ZIP** - In the same secure location
3. **Delete ZIP file** - Keep only extracted files
4. **Verify contents** - Check all expected files are present
5. **Set file permissions** - Restrict to only yourself
6. **Close download link** - Clear from browser

## Storing Data Securely

### Location Requirements

Store downloaded data:

**Approved Locations:**
- ✓ Encrypted work device hard drive
- ✓ Organisation-managed network drive (if encrypted)
- ✓ Organisation-approved secure cloud (e.g., Azure with encryption)
- ✓ Secure server with access controls

**Prohibited Locations:**
- ✗ USB drives or external hard drives
- ✗ Personal cloud storage (Dropbox, Google Drive, iCloud, OneDrive personal)
- ✗ Personal email attachments
- ✗ Unencrypted network shares
- ✗ Shared drives without access controls
- ✗ Personal devices (laptops, phones, tablets)
- ✗ Physical printouts (unless absolutely necessary and secured)

### File Organisation

Organize files securely:

**Folder Structure:**
```text
/secure_work_folder/
  └── census_data/
      ├── 2025/
      │   ├── survey_12345/
      │   │   ├── survey_data.csv
      │   │   ├── metadata.json
      │   │   └── README.txt
      │   └── survey_67890/
      └── archive/
```

**Best Practices:**
- Use descriptive folder names (but avoid PII in folder names)
- Keep different surveys separate
- Archive old data separately
- Delete entire folder structure when done

### File Permissions

Set strict permissions:

**On Windows:**
1. Right-click file/folder → Properties → Security
2. Remove "Everyone" and "Users" groups
3. Keep only your user account
4. Set to "Full Control" for you only

**On macOS:**
1. Right-click file/folder → Get Info → Sharing & Permissions
2. Remove "everyone" and "staff"
3. Keep only your user account
4. Set to "Read & Write" for you only

**On Linux:**
```bash
chmod 600 survey_data.csv  # Read/write for owner only
chmod 700 census_data/     # Full access for owner only
```

### Encryption

Layer encryption for maximum security:

**Level 1: Full Disk Encryption**

- Already provided by FileVault/BitLocker
- Protects if device is stolen

**Level 2: Folder Encryption**

- Use VeraCrypt or similar to create encrypted container
- Protects even if device is accessed while running

**Level 3: File Encryption**

- CSV files can be encrypted with tools like GPG
- Protects if file is copied elsewhere

**Recommended:** At minimum, use Levels 1 and 2.

## Using Data Securely

### Working with Data

When analyzing data:

- ✓ **Close door/curtains** - Prevent shoulder surfing
- ✓ **Privacy screen filter** - On your monitor
- ✓ **Lock screen** - When leaving desk, even briefly
- ✓ **Minimize windows** - When not actively using
- ✓ **Use secure viewer** - Excel/R/Python with data at rest encryption
- ✗ **Never screen share** - Without ensuring no sensitive data visible
- ✗ **Never present** - With raw data on screen in public spaces

### Sharing Within Your Organisation

If you must share data with colleagues:

**Approved Methods:**

- ✓ Secure file share (organisation-approved)
- ✓ Encrypted email (if organisation supports it)
- ✓ Hand delivery on encrypted USB (if policy allows)
- ✓ Through CheckTick itself (add them as data custodian)

**Prohibited Methods:**

- ✗ Unencrypted email
- ✗ Personal email (Gmail, Yahoo, etc.)
- ✗ Cloud sharing links (Dropbox, Google Drive, WeTransfer, etc.)
- ✗ Instant messaging (Slack, Teams, WhatsApp, etc.)
- ✗ Social media
- ✗ Physical printouts left unsecured

**Before Sharing:**

1. Verify recipient has legitimate need
2. Confirm they have appropriate permissions
3. Use password-protected ZIP (new password, shared separately)
4. Notify via separate channel (e.g., phone call)
5. Log the share in your own records

### Sharing Outside Your Organisation

**Generally prohibited** without specific approval.

**If absolutely necessary:**

1. Get written approval from organisation owner
2. Ensure data sharing agreement is signed
3. Anonymize/pseudonymize data if possible
4. Use secure transfer method
5. Log the transfer
6. Audit recipient's security practices

## Deleting Data Securely

### When to Delete

Delete data when:

- ✓ Analysis is complete
- ✓ Report is published
- ✓ No longer needed for stated purpose
- ✓ Retention period expires
- ✓ Participant requests deletion (right to erasure)
- ✓ You leave the organisation
- ✓ Project is cancelled

**Don't keep data "just in case"** - This violates data minimization principles.

### Secure Deletion Methods

**Simple Delete (Not Sufficient):**

- Moving to Trash/Recycle Bin does not delete
- Standard "Empty Trash" can be recovered
- Not acceptable for sensitive data

**Secure File Deletion:**

**On Windows:**

- Use SDelete from Microsoft Sysinternals
- Or: `cipher /w:C:\folder` (built-in)

**On macOS:**

- Use `srm` command (if available)
- Or: Disk Utility → Erase Free Space → "Most Secure"

**On Linux:**

- Use `shred -vfz -n 10 survey_data.csv`
- Or: `wipe -rfq census_data/`

**In Python (for programmatic deletion):**

```python
import os
import random

def secure_delete(file_path, passes=7):
    with open(file_path, "ba+") as f:
        length = f.tell()
        for _ in range(passes):
            f.seek(0)
            f.write(os.urandom(length))
    os.remove(file_path)
```

### Verify Deletion

After secure deletion:

1. **Check Trash/Recycle Bin** - Should be empty
2. **Search for file** - Should not be found
3. **Check backups** - Ensure backups are also purged (if you control them)
4. **Document deletion** - Log date and method in your records

### Cloud Storage Deletion

If data was stored in cloud:

1. Delete from cloud storage
2. Empty cloud trash/recycle bin
3. Check "version history" - Delete all versions
4. Verify deletion in cloud provider's audit log
5. Contact provider if permanent deletion needed (some providers retain deleted data)

## Data Breach Response

### What Counts as a Breach?

A data breach includes:

- Unauthorized access to data
- Accidental email to wrong person
- Lost or stolen device containing data
- Ransomware/malware infection on device with data
- Unauthorized copying or sharing
- Data left unattended in public space
- Improper disposal (e.g., not securely deleted)

**Even small breaches must be reported.**

### Immediate Actions (Within Minutes)

If you suspect a breach:

1. **Stop** - Don't make it worse (e.g., don't forward the email again)
2. **Contain** - Disconnect device from network if infected
3. **Preserve evidence** - Don't delete logs or emails
4. **Notify immediately** - Contact organisation owner and Data Protection Officer

**Call, don't email** - Breaches are urgent.

### Reporting Requirements

**Within 1 hour:**
- Notify your organisation owner
- Notify Data Protection Officer (if your organisation has one)
- Notify IT security team

**Within 24 hours:**
- Provide written incident report:
  - What happened
  - When it happened
  - What data was affected (how many records, what type)
  - Who may have accessed the data
  - What you've done to contain it

**Within 72 hours (if required by law):**
- Your organisation must report to regulatory authority (ICO in UK, etc.)
- You must cooperate fully with investigation

### What NOT to Do

During a breach:

- ✗ **Don't hide it** - Covering up makes legal consequences worse
- ✗ **Don't try to "fix" it yourself** - You may destroy evidence
- ✗ **Don't contact affected individuals** - Organisation will handle this
- ✗ **Don't discuss publicly** - Including social media
- ✗ **Don't delete anything** - Even if you think it helps

### Consequences

Data breaches can result in:

- **Personal liability** - Fines up to £17 million or 4% of organisational turnover (GDPR)
- **Disciplinary action** - Up to and including termination
- **Criminal prosecution** - In serious cases
- **Professional sanctions** - Loss of licenses/certifications
- **Civil lawsuits** - From affected individuals
- **Reputational damage** - Both personal and organisational

**This is serious.** Follow security practices carefully.

## Security Checklist

### Daily Practices

- [ ] Lock screen when leaving desk (even briefly)
- [ ] Close data files when not actively using
- [ ] Use privacy screen on monitor
- [ ] Keep work area clear of printouts
- [ ] Shut down or lock computer at end of day

### Weekly Practices

- [ ] Check for software updates (OS, antivirus, etc.)
- [ ] Review who has access to shared files
- [ ] Clean up old data no longer needed
- [ ] Verify backups are encrypted
- [ ] Review password manager for weak passwords

### Monthly Practices

- [ ] Review all downloaded data - still needed?
- [ ] Securely delete old data
- [ ] Check retention periods in CheckTick
- [ ] Audit file permissions
- [ ] Review organisational security policies

## Getting Help

### Security Questions

**For questions about:**
- Security best practices → Contact IT security team
- Data protection law → Contact Data Protection Officer
- Organisational policy → Contact organisation owner
- CheckTick security features → See [Data Policy](/docs/data-governance-policy/)

### Reporting Issues

**Report immediately if:**
- You suspect a breach
- You receive suspicious emails about CheckTick
- You notice unauthorized access to data
- You're unsure if something is a security issue

**Contact:**
- Organisation owner: [Set in organisation settings]
- Data Protection Officer: [Set in organisation settings]
- IT Security: [Your organisation's IT security contact]

### Emergency Contacts

**Outside Business Hours:**
- Critical breach: Call organisation emergency number
- Device lost/stolen: Call IT security hotline
- Ransomware: Disconnect device, call IT security

## Training and Awareness

### Required Training

Before downloading data, ensure you have completed:

- [ ] Data protection awareness training
- [ ] Information security training
- [ ] Your organisation's data handling training
- [ ] CheckTick-specific training (if provided)

### Ongoing Learning

Stay informed about:

- Changes to data protection laws
- New security threats (phishing, ransomware, etc.)
- Organisational policy updates
- CheckTick feature updates

### Testing Your Knowledge

Regularly test yourself:

- Would you recognize a phishing email?
- Do you know how to report a breach?
- Can you securely delete a file?
- Do you understand your legal obligations?

## Legal and Compliance

### GDPR Obligations

Under GDPR, you must:

- **Lawful basis** - Have legal grounds for processing (usually "legitimate interest" or "consent")
- **Data minimization** - Only download data you need
- **Purpose limitation** - Use data only for stated purpose
- **Accuracy** - Ensure data is correct
- **Storage limitation** - Delete when no longer needed
- **Integrity and confidentiality** - Keep data secure (this guide)
- **Accountability** - Document your compliance

### UK Data Protection Act 2018

Additional UK requirements:

- Comply with Data Protection Principles
- Respect individual rights (access, rectification, erasure)
- Report breaches to ICO within 72 hours (if required)
- Appoint Data Protection Officer (if required)

### NHS Data Security and Protection Toolkit

If handling NHS data:

- Complete annual DSP Toolkit assessment
- Meet all mandatory standards
- Implement role-based access control
- Audit all data access
- Encrypt data at rest and in transit

### Caldicott Principles

For health and social care data:

1. **Justify purpose** - Legitimate basis for using confidential information
2. **Don't use unless absolutely necessary**
3. **Use minimum necessary**
4. **Access on strict need-to-know basis**
5. **Everyone must understand their responsibilities**
6. **Understand and comply with the law**
7. **Duty to share information can be as important as duty to protect confidentiality**

## Related Guides

- [Data Governance Overview](/docs/data-governance-overview/) - Understanding data governance
- [Data Export Guide](/docs/data-governance-export/) - How to download data
- [Data Retention Policy](/docs/data-governance-retention/) - How long data is kept
- [Data Policy](/docs/data-governance-policy/) - Formal data protection policy

## Remember

**Security is not just about technology - it's about behavior.**

- Be vigilant
- Think before you click
- When in doubt, ask
- Report incidents immediately
- You are responsible for protecting the data you download

**If you can't follow these security practices, don't download the data.**
