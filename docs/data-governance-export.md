---
title: Data Export Guide
category: None
---

This guide explains how to download survey data from CheckTick, including who can download, when downloads are available, and what security measures are in place.

## Prerequisites

Before you can download survey data:

1. **Survey must be closed** - Data export is only available after the survey has been formally closed
2. **You must have appropriate permissions** - See [Access Control](#who-can-download-data) below
3. **Survey must have responses** - Empty surveys cannot be exported

## Who Can Download Data

Access to data exports is strictly controlled based on your role:

### Survey Creators

- Can download data from **their own surveys only**
- Must be the original creator or have had ownership transferred to them
- Can extend retention for their own surveys

### Organisation Owners

- Can download data from **all surveys in their organisation**
- Can extend retention for any survey in the organisation
- Can designate data custodians
- Receive notifications for all data downloads in the organisation

### Data Custodians (Optional Role)

- Can download data from **assigned surveys only**
- Cannot edit the survey
- Cannot extend retention periods
- Useful for delegating data management without giving full edit access

### Editors and Viewers

- **Cannot download data** - No access to exports
- Can only view or edit survey structure (if editor)
- For data access, they must request the survey creator or organisation owner to download on their behalf

## When Can I Download Data?

### After Survey Closure

Data export becomes available when a survey is **closed**:

1. Go to your survey dashboard
2. Click "Close Survey" button
3. Confirm closure (this cannot be undone)
4. The "Download Data" button will appear

**What happens when a survey closes:**

- All responses are locked (no further edits possible)
- Data export functionality is enabled
- 6-month retention period begins
- Automatic deletion warnings are scheduled

### Time Window

Once a survey is closed, data can be downloaded:

- For the **default 6-month retention period**
- Up to **24 months** if retention is extended
- Until **automatic deletion** occurs (after warnings)
- Unless a **legal hold** is placed (prevents deletion)

## How to Download Data

### Step 1: Navigate to Survey

**From Survey List (Organisation Owners):**

1. Go to "Surveys" in the main navigation
2. Find the closed survey in your list
3. Click the "Download Data" button next to the survey

**From Survey Dashboard (Creators/Custodians):**

1. Open your survey
2. Go to the "Data" or "Dashboard" tab
3. Click the "Download Data" button

### Step 2: Accept Disclaimer

Before downloading, you must accept the data responsibility disclaimer:

**You will be asked to confirm:**

- ✓ I will store this data on a secure, encrypted device
- ✓ I will comply with my organisation's data protection policies
- ✓ I understand I am responsible for the security of this data
- ✓ I will delete this data when no longer needed
- ✓ I will report any data breaches immediately

**You must provide:**

- Your full name (for accountability)
- Purpose of download (brief description)
- Confirmation that you have authority to download this data

**Important:** Making false statements in the disclaimer may violate data protection laws and your employment contract.

### Step 3: Receive Download Link

After accepting the disclaimer:

1. A secure download link is generated
2. The link expires in **15 minutes** (for security)
3. The link can be used **only once**
4. An email is sent to all organisation administrators about the download

### Step 4: Download the File

Click the download link to receive a **password-protected ZIP file** containing:

**Files in the ZIP:**

- `survey_data.csv` - The encrypted survey responses
- `metadata.json` - Export information (timestamp, user, version)
- `README.txt` - Instructions for using the data

**File Protection:**

- ZIP file is password-protected
- Password is shown on-screen (not emailed for security)
- CSV inside is also encrypted
- You must save the password securely

### Step 5: Extract and Use Data

1. Extract the ZIP file using the provided password
2. Open `survey_data.csv` in Excel, R, Python, or your preferred tool
3. Review `metadata.json` for export details
4. Read `README.txt` for data dictionary and notes

## Data Format

### CSV Structure

The exported CSV file contains:

**Standard Columns:**

- `response_id` - Unique identifier for this response
- `submitted_at` - Date and time response was submitted
- `user_id` - Anonymized user identifier (if logged in)
- `status` - Response status (complete, partial, etc.)

**Question Columns:**

- Each question becomes a column
- Column names use question slugs (e.g., `patient_age`, `hospital_name`)
- Multi-choice questions may span multiple columns

**Metadata Columns:**

- `ip_address` - Anonymized IP (if collected)
- `user_agent` - Browser information (if collected)
- `completion_time` - Time taken to complete (seconds)

### Data Types

- **Text responses** - Free text as entered
- **Multiple choice** - Selected option text
- **Checkboxes** - Comma-separated list of selected options
- **Dates** - ISO 8601 format (YYYY-MM-DD)
- **Numbers** - Numeric values (no formatting)

### Encrypted Fields

Some fields may be encrypted in the CSV:
- Email addresses
- Phone numbers
- Other personally identifiable information (PII)

**To decrypt:**

- Use the decryption key provided in `metadata.json`
- Or contact your organisation administrator
- Decryption requires appropriate permissions

## Security Measures

### Password Protection

Every download is protected by:

- **ZIP password** - Generated randomly, shown once
- **Encryption** - CSV data encrypted with survey key
- **Time-limited link** - Expires in 15 minutes
- **Single-use link** - Cannot be reused after download

### Audit Logging

Every download is logged with:

- User who downloaded (name, email, user ID)
- Timestamp (date and time)
- IP address
- Survey downloaded
- Purpose stated
- Attestation accepted

### Email Notifications

When data is downloaded:

- **Organisation administrators** receive immediate email
- Email includes: who, what, when, why
- Links to audit log for full details

### Access Tracking

You can view download history:

1. Go to survey dashboard
2. Click "Download History" tab
3. See all past downloads with details

## Download Limits

To prevent abuse:

- **Maximum 5 downloads per survey per day** per user
- **Excessive attempts** are logged and may be blocked
- **Rate limiting** applies to prevent automated downloads

If you need more downloads, contact your organisation administrator.

## Troubleshooting

### "Download Data" Button Not Visible

**Possible causes:**

- Survey is not yet closed → Close the survey first
- You don't have permission → Check your role
- Survey has no responses → Nothing to download
- Survey is deleted → Cannot download from deleted surveys

### Download Link Expired

**If your link expires:**

- Click "Download Data" again to generate a new link
- You must accept the disclaimer again (for audit trail)
- Previous link cannot be extended or reused

### Password Doesn't Work

**If ZIP password fails:**

- Copy and paste carefully (no extra spaces)
- Check for case sensitivity
- Regenerate the download (creates new password)
- Contact support if problem persists

### File Won't Open

**If CSV file won't open:**

- Ensure you extracted the ZIP first
- Try different software (Excel, Google Sheets, etc.)
- Check file encoding (UTF-8)
- Contact your organisation administrator

### "Permission Denied" Error

**You may not have permission because:**

- You're an Editor or Viewer (not Creator/Owner/Custodian)
- You're not the survey creator (and not an org owner)
- You're not in the organisation that owns the survey
- Your account has been deactivated

Contact your organisation owner to request access.

## Best Practices

### Secure Storage

Store downloaded data:

- ✓ On encrypted drives
- ✓ Behind strong passwords
- ✓ On work-managed devices only
- ✓ In access-controlled folders
- ✗ Never on USB drives
- ✗ Never in personal cloud storage (Dropbox, Google Drive, etc.)
- ✗ Never on personal devices
- ✗ Never in unencrypted email attachments

### Data Handling

When working with data:

- Download only what you need
- Delete local copies when analysis is complete
- Don't share with unauthorized people
- Don't re-identify anonymized data
- Follow your organisation's policies
- Use data only for stated purpose

### Retention

Manage downloaded data responsibly:

- Set reminders to delete after analysis
- Don't keep "just in case"
- Securely wipe files when deleting
- Keep audit trail of what you downloaded and when

## Legal and Compliance

### Your Obligations

When you download data, you become a **data controller** or **data processor** and must:

- Comply with GDPR and data protection laws
- Maintain confidentiality
- Prevent unauthorized access
- Report data breaches within 72 hours
- Respect participant privacy

### Data Breaches

**If data is compromised, you must:**

1. Report immediately to your organisation administrator
2. Document what happened
3. Identify what data was affected
4. Assist with breach notification (if required)
5. Take corrective action

**Consequences of not reporting:**

- Legal liability
- Regulatory fines
- Disciplinary action
- Reputational damage

### Sharing Data

You may **only** share downloaded data:

- With people who have legitimate need
- Who have signed appropriate agreements
- Within the scope stated in your attestation
- With appropriate security measures

**Never** share data:

- On social media
- In public forums
- With commercial third parties (without approval)
- For purposes outside the original scope

## Getting Help

**For questions about:**

- **Permissions:** Contact your organisation owner
- **Technical issues:** [GitHub Issues](https://github.com/eatyourpeas/checktick/issues)
- **Data policy:** See [Data Policy](/docs/data-governance-policy/)
- **Security concerns:** Contact your Data Protection Officer immediately

## Related Guides

- [Data Governance Overview](/docs/data-governance-overview/) - Understanding data governance
- [Data Retention Policy](/docs/data-governance-retention/) - How long data is kept
- [Data Security Guide](/docs/data-governance-security/) - Security best practices
- [Data Policy](/docs/data-governance-policy/) - Formal data protection policy
