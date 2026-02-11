---
title: Data Governance
category: data-governance
priority: 1
---

CheckTick takes data protection and governance seriously. This comprehensive guide explains how we handle your survey data, who can access it, compliance requirements, and your responsibilities as a data custodian.

## Table of Contents

- [Overview](#overview) - Understanding data governance principles
- [Data Policy](#data-policy) - Formal policy and legal framework
- [Access Control & Roles](#access-control--roles) - Who can access what
- [Data Export](#data-export) - How to download survey data
- [Retention Policy](#retention-policy) - How long data is kept
- [Security Best Practices](#security-best-practices) - Protecting downloaded data
- [Special Cases](#special-cases) - Legal holds, transfers, exceptions
- [Implementation](#implementation) - Technical details for developers

---

## Overview

### What is Data Governance?

Data governance is the framework that ensures survey data is:

- **Secure** - Protected from unauthorized access
- **Compliant** - Meets legal and regulatory requirements
- **Controlled** - Only accessible to authorized people
- **Time-limited** - Not kept longer than necessary
- **Audited** - All access is logged and traceable

### Why Does It Matter?

When you collect survey data, especially in healthcare, you may be handling sensitive or personal information. Good data governance protects:

- **Participants** - Their privacy and confidentiality
- **Your organisation** - From data breaches and compliance violations
- **You** - From legal liability and reputational damage

### Key Principles

#### 1. Access Control

Not everyone can access survey data. Access is strictly controlled based on roles:

| Role | Can View Responses | Can Download Data | Can Extend Retention |
|------|-------------------|-------------------|---------------------|
| **Survey Creator** | ✅ Own surveys | ✅ Own surveys | ✅ Own surveys |
| **Organisation Owner** | ✅ All org surveys | ✅ All org surveys | ✅ All org surveys |
| **Data Custodian*** | ❌ No | ✅ Assigned surveys | ❌ No |
| **Editor** | ❌ No | ❌ No | ❌ No |
| **Viewer** | ❌ No | ❌ No | ❌ No |

\* *Optional role - can be assigned per survey for data management delegation*

#### 2. Survey Closure

Data can only be downloaded after a survey has been formally **closed**. Closing a survey:

- Locks all responses (no further edits)
- Enables data export functionality
- Starts the retention countdown
- Triggers automatic deletion warnings

This ensures data is only extracted when collection is complete.

#### 3. Time-Limited Storage

Survey data is **not kept indefinitely**. By default:

- Data is kept for **6 months** after survey closure
- You receive warnings at **1 month**, **1 week**, and **1 day** before deletion
- Data is automatically deleted unless you extend retention
- Maximum retention period is **24 months**

#### 4. Audit Trail

Every data access is logged:

- Who downloaded data
- When they downloaded it
- What survey data was downloaded
- Their stated purpose
- Their IP address

Organisation administrators receive email notifications for all data downloads.

#### 5. User Responsibility

When you download data, you become responsible for:

- Storing it securely (encrypted, password-protected location)
- Not sharing it inappropriately
- Deleting it when no longer needed
- Reporting any data breaches
- Complying with your organisation's data policies

### Data Lifecycle

```
┌─────────────────┐
│ Survey Created  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Collect Data    │ ← Responses locked in database (encrypted)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Survey Closed   │ ← Retention period starts (6 months default)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Data Available  │ ← Can be downloaded by authorized users
│  for Export     │   All downloads logged and audited
└────────┬────────┘
         │
         ├─────────► Can extend retention (up to 24 months)
         │
         ▼
┌─────────────────┐
│ Deletion        │ ← Warnings sent at 1 month, 1 week, 1 day
│   Warnings      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Auto-Deletion   │ ← Data removed from database and backups
└─────────────────┘   Permanent and irreversible
```

---

## Data Policy

### Formal Data Protection Policy

This section outlines the formal data protection policy for CheckTick deployments.

### Purpose

This policy ensures that survey data collected through CheckTick is:

1. Handled lawfully and ethically
2. Protected against unauthorized access
3. Retained only as long as necessary
4. Used only for its stated purpose
5. Managed with appropriate technical and organisational measures

### Scope

This policy applies to:

- All survey data collected through CheckTick
- All users with access to survey data (creators, owners, custodians)
- All data exports from the system
- All backup and archive processes

### Legal Basis

CheckTick processes survey data under the following legal bases (where applicable):

- **Consent** - Explicit consent from survey participants
- **Contract** - Necessary for service delivery
- **Legal obligation** - Compliance with applicable laws
- **Legitimate interests** - Research, quality improvement, service evaluation

Organisations using CheckTick are responsible for ensuring they have appropriate legal basis for their specific use cases.

### Data Controller Responsibilities

The **organisation owner** acts as the data controller and is responsible for:

1. Determining the lawful basis for data collection
2. Ensuring participants are informed about data use
3. Implementing appropriate security measures
4. Responding to data subject access requests
5. Reporting data breaches within 72 hours
6. Maintaining records of processing activities
7. Conducting data protection impact assessments when required

### Data Processor Obligations

CheckTick (as platform provider) acts as a data processor and commits to:

1. Processing data only on documented instructions
2. Ensuring confidentiality of personnel
3. Implementing appropriate technical and organisational measures
4. Assisting with data subject rights requests
5. Assisting with security breaches and impact assessments
6. Deleting or returning data when instructed
7. Making available information for audits

### Compliance Standards

CheckTick supports compliance with:

- **GDPR** (General Data Protection Regulation)
- **UK Data Protection Act 2018**
- **NHS Data Security and Protection Toolkit**
- **Caldicott Principles** (for health and social care)
- **ISO 27001** security standards
- Research ethics committee requirements

---

## Access Control & Roles

### User Roles and Permissions

CheckTick implements a hierarchical permission system with clearly defined roles:

#### Survey Creator

**Who**: The user who created the survey

**Permissions**:

- View all responses to their survey
- Download data exports
- Close the survey
- Extend retention period
- Assign additional users (editors, viewers, custodians)
- Delete the survey (before closure)
- Manage survey settings

**Restrictions**:

- Cannot access other users' surveys (unless also an org owner)
- Cannot bypass retention limits

#### Organisation Owner

**Who**: The owner of an organisation account

**Permissions**:

- All permissions of Survey Creator for ALL organisation surveys
- Assign data custodians
- Place legal holds
- Transfer survey ownership
- View audit logs for all organisation surveys
- Manage organisation members

**Restrictions**:

- Cannot access surveys from other organisations
- Subject to same retention limits (except legal holds)

#### Data Custodian

**Who**: A designated user assigned to specific surveys

**Permissions**:

- Download data exports for assigned surveys
- View audit logs for assigned surveys
- Receive deletion warning emails

**Restrictions**:

- Cannot view responses in the UI
- Cannot edit survey settings
- Cannot extend retention
- Cannot assign additional users

**Use Case**: Delegate data management to a specific person (e.g., research data manager) without giving full edit permissions.

#### Editor

**Who**: Users with edit permission on specific surveys

**Permissions**:

- Edit survey structure (add/remove questions)
- Modify survey settings
- View survey dashboard
- Manage question groups

**Restrictions**:

- **Cannot** view responses
- **Cannot** download data
- **Cannot** close the survey
- **Cannot** delete the survey

#### Viewer

**Who**: Users with read-only permission

**Permissions**:

- View survey structure
- View survey settings
- Preview the survey

**Restrictions**:

- Cannot edit anything
- Cannot view responses
- Cannot download data

### Permission Hierarchy

```
Organisation Owner
    ├── Full access to all org surveys
    ├── Can assign any role
    └── Can place legal holds

Survey Creator
    ├── Full access to own surveys
    ├── Can assign Editor, Viewer, Custodian
    └── Can extend retention

Data Custodian
    ├── Can download data (assigned surveys only)
    └── Receives deletion warnings

Editor
    ├── Can edit survey structure
    └── Cannot access data

Viewer
    └── Read-only access to survey structure
```

---

## Data Export

### How to Download Survey Data

Data can only be exported after a survey has been **closed**. This ensures all responses are finalized before extraction.

### Step 1: Close the Survey

1. Navigate to your survey dashboard
2. Click "Close Survey" button
3. Confirm the closure (this action is permanent)
4. The survey is now locked - no further responses accepted

### Step 2: Request Data Export

1. Click the "Export Data" button on the closed survey dashboard
2. Select your export format:
   - **CSV** - Spreadsheet format, one row per response
   - **JSON** - Structured format for programmatic use
   - **Excel** - Formatted workbook with multiple sheets
3. Enter a **purpose statement** (required):
   - Example: "Annual report analysis"
   - Example: "Research paper dataset"
   - Example: "Quality improvement review"

### Step 3: Confirm Download

1. Review the data governance checklist:
   - ☐ I have a legitimate need to download this data
   - ☐ I will store this data securely
   - ☐ I will not share this data inappropriately
   - ☐ I will delete this data when no longer needed
2. Check all boxes to proceed
3. Click "Download"

### Step 4: Secure Storage

After downloading:

1. **Immediately encrypt** the file (password-protected ZIP or encrypted drive)
2. Store in a secure location:
   - Encrypted fileserver
   - Password-protected cloud storage
   - Locked, encrypted laptop
3. **Do not** store on:
   - Unencrypted USB drives
   - Public cloud storage (Dropbox, Google Drive without encryption)
   - Shared network drives without access controls
4. **Delete** from your downloads folder after securing

### Export Formats

#### CSV Format

- One row per survey response
- Columns for each question
- Includes metadata (timestamp, user ID, IP address if available)
- Compatible with Excel, R, Python pandas, SPSS

**Example**:
```csv
response_id,timestamp,user_id,q1_name,q1_age,q2_diagnosis
uuid-1,2025-01-15 14:30,user123,John,45,Type 2
uuid-2,2025-01-16 09:15,user456,Jane,38,Type 1
```

#### JSON Format

- Nested structure preserving question groups
- Full metadata included
- Ideal for programmatic processing
- Preserves data types

**Example**:
```json
{
  "survey": {
    "id": "uuid",
    "name": "Diabetes Survey",
    "closed_at": "2025-01-20T10:00:00Z"
  },
  "responses": [
    {
      "id": "response-uuid",
      "timestamp": "2025-01-15T14:30:00Z",
      "user_id": "user123",
      "data": {
        "demographics": {
          "name": "John",
          "age": 45
        },
        "clinical": {
          "diagnosis": "Type 2"
        }
      }
    }
  ]
}
```

#### Excel Format

- Multiple sheets:
  - Sheet 1: Responses (one row per response)
  - Sheet 2: Questions (data dictionary)
  - Sheet 3: Metadata (survey info, export timestamp)
- Formatted with headers and data types
- Suitable for non-technical users

### Audit Trail

Every data export creates an audit log entry with:

- **Who** - User ID and name
- **When** - Exact timestamp
- **What** - Survey ID and name
- **Why** - Purpose statement
- **Where** - IP address
- **How** - Export format

Organisation owners receive email notifications for all data exports:

```
Subject: Data Export: Diabetes Survey

User: john.smith@example.com
Survey: Diabetes Survey
Time: 2025-01-20 10:30:00 GMT
Purpose: Annual report analysis
Format: CSV
IP: 192.0.2.1

View full audit log: [link]
```

### Re-Downloading Data

You can download data multiple times:

- No limit on number of exports
- Each export creates a new audit log entry
- Must provide a purpose statement each time
- Organisation owners notified for each download

This allows:

- Correcting failed downloads
- Sharing with additional authorized colleagues
- Regenerating exports after data updates (if survey reopened)

### Data Deletion After Export

Exporting data does **not** prevent automatic deletion:

- Retention countdown continues after export
- Downloaded files are **your responsibility**
- System will still auto-delete at scheduled time
- To keep data longer, extend retention period (see Retention Policy)

---

## Retention Policy

### Default Retention Period

Survey data is kept for **6 months** after survey closure.

```
Survey Closed → [6 months] → Automatic Deletion
```

### Retention Timeline

| Time After Closure | Action |
|-------------------|--------|
| **Day 0** | Survey closed, retention countdown begins |
| **5 months** | First warning email sent (1 month remaining) |
| **5 months 3 weeks** | Second warning (1 week remaining) |
| **5 months 29 days** | Final warning (1 day remaining) |
| **6 months** | **Automatic deletion** - permanent and irreversible |

### Warning Emails

At each warning milestone, emails are sent to:

- Survey creator
- Organisation owner
- All assigned data custodians

**Email content**:
```
Subject: WARNING: Survey data will be deleted in 1 month

Survey: Diabetes Patient Feedback
Responses: 234
Deletion date: 2025-07-20

Options:
1. Download data now (if not already done)
2. Extend retention (up to 24 months total)
3. Allow deletion to proceed

[Download Data] [Extend Retention]
```

### Extending Retention

You can extend retention up to a **maximum of 24 months** total.

#### How to Extend

1. Go to survey dashboard
2. Click "Extend Retention"
3. Select new retention period:
   - 12 months
   - 18 months
   - 24 months
4. Provide justification (required):
   - Example: "Ongoing research study, manuscript in preparation"
   - Example: "Legal requirement for 2-year record retention"
   - Example: "Audit pending, data required for evidence"
5. Click "Extend"

#### Justification Requirements

Extensions must be justified because:

- Data minimization principle (GDPR)
- Storage costs
- Security risk (older data, more exposure)
- Compliance requirements

Poor justifications (will be rejected):

- "Just in case"
- "Might need it later"
- "No specific reason"

Good justifications:

- "Longitudinal study, 2-year follow-up planned"
- "Regulatory requirement for clinical trial data"
- "Awaiting ethics committee review"

#### Extension Limits

- Can extend multiple times (up to 24 months total)
- Each extension requires new justification
- Organisation owners can review all extensions
- Audit log records all extension requests

### Maximum Retention Period

Data **cannot** be kept longer than 24 months except:

1. **Legal hold** (see Special Cases)
2. **Legal obligation** (e.g., clinical trial regulations)

After 24 months:

- Must download data if needed
- System will force deletion
- No further extensions allowed

### Automatic Deletion Process

When the retention period expires:

1. **Database deletion**:
   - All survey responses removed
   - Participant data deleted
   - Question group data retained (for survey structure)

2. **Backup deletion**:
   - Data removed from all backups within 30 days
   - Follows backup rotation schedule

3. **Audit log retention**:
   - Audit logs kept for 7 years (compliance requirement)
   - Personal data redacted
   - Metadata retained (who, when, what action)

4. **Confirmation email**:
   ```
   Subject: Survey data deleted: Diabetes Survey

   The survey "Diabetes Survey" has been automatically deleted.

   - Responses deleted: 234
   - Deletion date: 2025-07-20
   - Reason: Retention period expired

   This action is permanent and cannot be undone.
   ```

### Early Deletion

Survey creators can delete data **before** the retention period expires:

1. Go to survey dashboard
2. Click "Delete Survey Data"
3. Confirm deletion (requires typing survey name)
4. Data immediately removed

This is useful for:

- Accidentally closed surveys
- Completed analysis, data no longer needed
- Participant withdrawal requests

### Retention Policy Override

Only **organisation owners** can place a **legal hold** to prevent automatic deletion (see Special Cases section).

---

## Security Best Practices

### Protecting Downloaded Data

When you export survey data, you become the **data controller**. This section explains how to protect that data.

### Storage Security

#### Recommended Storage Locations

✅ **Secure Options**:

- Institutional encrypted file server
- Password-protected encrypted cloud storage (OneDrive for Business, Google Workspace with encryption)
- Encrypted external hard drive in locked cabinet
- Password-protected laptop with full-disk encryption
- Secure research data management system (e.g., REDCap, institutional repository)

❌ **Insecure Options**:

- Unencrypted USB drives
- Personal Dropbox/Google Drive (without encryption)
- Email attachments
- Shared network drives without access controls
- Unencrypted laptop
- Cloud storage with weak passwords

#### Encryption Requirements

**All exported data must be encrypted.**

##### Option 1: Password-Protected ZIP (Easy)

```bash
# macOS/Linux
zip -er survey_data.zip survey_data.csv

# Windows (use 7-Zip)
7z a -p -mhe=on survey_data.7z survey_data.csv
```

Use a **strong password**:

- Minimum 16 characters
- Mix of letters, numbers, symbols
- Not related to survey content
- Store password in password manager (not with the file)

##### Option 2: Full-Disk Encryption (Better)

- **macOS**: FileVault
- **Windows**: BitLocker
- **Linux**: LUKS

This encrypts your entire hard drive, protecting all files automatically.

##### Option 3: Encrypted Folder (Best for Shared Systems)

- **macOS**: Create encrypted disk image (Disk Utility)
- **Windows**: Use VeraCrypt
- **Linux**: Use eCryptfs or VeraCrypt

### Access Controls

#### Who Should Have Access?

Only people with a **legitimate need** should access the data:

✅ **Appropriate**:

- Research team members listed on ethics approval
- Quality improvement team members
- Audit committee members (if auditing the service)
- Data analyst assigned to the project

❌ **Inappropriate**:

- Colleagues not involved in the project
- Students not listed on ethics approval
- External collaborators without data sharing agreement
- IT support staff (unless specifically authorized)

#### Sharing Data Securely

If you need to share data with authorized colleagues:

1. **Verify authorization**: Ensure they're listed on ethics approval/data sharing agreement
2. **Use secure transfer**:
   - Institutional file sharing with access controls
   - Encrypted email (S/MIME or PGP)
   - Secure file transfer service (e.g., institutional Dropbox alternative)
3. **Log the transfer**: Document who, what, when, why
4. **Remind recipient** of their data protection obligations

**Never**:

- Send unencrypted email attachments
- Upload to public file sharing sites
- Share passwords in the same message as encrypted files
- Post in Slack/Teams without encryption

### Data Processing Security

When analyzing data:

1. **Use secure computing environments**:
   - Password-protected computer
   - Private workspace (not public café)
   - Screen privacy filter if working in shared spaces
   - Lock computer when stepping away

2. **Minimize data copies**:
   - Work with data in one location
   - Delete temporary files
   - Clear clipboard after copying sensitive data
   - Don't save to Downloads folder

3. **Anonymize early**:
   - Remove names, email addresses, IP addresses as soon as possible
   - Replace with participant IDs
   - Store linking file separately (encrypted)

4. **Version control**:
   - Use clear file naming (diabetes_survey_v1.csv)
   - Document changes (data_cleaning_log.txt)
   - Don't keep unnecessary old versions

### Data Destruction

When you no longer need the data:

1. **Verify retention requirements**: Check ethics approval, institutional policy, legal obligations
2. **Delete all copies**:
   - Original export file
   - Working copies
   - Analysis files
   - Temporary files
   - Backup copies
3. **Secure deletion**:
   - Empty Trash/Recycle Bin
   - Use secure delete tools (macOS: `srm`, Windows: `cipher`, Linux: `shred`)
   - If on encrypted drive, deletion is sufficient
4. **Document destruction**:
   - Record date of deletion
   - Record who deleted it
   - Keep destruction log for audit

### Physical Security

Protect physical access to devices:

- **Lock computer** when leaving desk (even briefly)
- **Secure laptops** in locked cabinet when not in use
- **Encrypt portable drives** before transporting
- **Report lost/stolen devices** immediately
- **Use privacy screens** in public spaces
- **Shred printed data** (cross-cut shredder)

### Incident Response

If data is lost, stolen, or accessed by unauthorized person:

1. **Immediate actions** (within minutes):
   - Disconnect affected device from network
   - Change passwords
   - Notify organisation IT security team

2. **Within 24 hours**:
   - Document incident (what, when, how)
   - Notify organisation data protection officer
   - Notify survey participants if required
   - Notify regulatory bodies if required (e.g., ICO for UK)

3. **Investigation**:
   - Determine scope of breach
   - Identify affected individuals
   - Assess risk to participants
   - Implement additional security measures

4. **Legal requirements**:
   - GDPR requires breach notification within 72 hours
   - Must notify affected individuals if high risk to their rights
   - Maintain breach register

### Compliance Checklist

Before downloading data, ensure:

- [ ] You have a legitimate need to download this data
- [ ] You have appropriate authorization (ethics approval, data sharing agreement)
- [ ] You have secure storage available (encrypted location)
- [ ] You understand your data protection responsibilities
- [ ] You know your organisation's data security policies
- [ ] You have access to secure analysis environment
- [ ] You know who to contact in case of security incident
- [ ] You understand retention and destruction requirements

After downloading data, ensure:

- [ ] File is immediately encrypted
- [ ] File is stored in secure location
- [ ] Download folder copy is deleted
- [ ] Access is restricted to authorized users only
- [ ] Sharing is logged and justified
- [ ] Backup copies are encrypted
- [ ] Destruction plan is documented

---

## Special Cases

### Legal Holds

A **legal hold** is a mechanism to prevent automatic deletion of survey data when there is a legal or regulatory requirement to preserve evidence.

#### When to Use Legal Holds

Legal holds should only be used in specific circumstances:

✅ **Appropriate use cases**:

- Active litigation involving the survey data
- Regulatory investigation (e.g., ICO, Care Quality Commission)
- Freedom of Information request
- Subject Access Request requiring complex data retrieval
- Criminal investigation
- Parliamentary inquiry
- Serious incident investigation

❌ **Inappropriate use cases**:

- "Just in case we need it later"
- Avoiding normal retention policies
- Ongoing research (use retention extension instead)
- General audit purposes (use retention extension)

#### Who Can Place a Legal Hold?

Only **organisation owners** can place legal holds.

**Why this restriction?**

- Legal holds override normal data minimization principles
- Require documented legal justification
- Subject to audit and review
- Potential compliance implications

#### How to Place a Legal Hold

1. Navigate to survey dashboard
2. Click "Place Legal Hold" (only visible to org owners)
3. Provide detailed justification:
   - Legal basis (litigation, investigation, etc.)
   - Case reference number
   - Expected duration
   - Contact information for legal counsel
4. Attach supporting documentation (optional but recommended)
5. Click "Confirm Legal Hold"

**Example justification**:
```
Case: Smith v. NHS Trust (Case No. 2025-1234)
Basis: Active litigation
Solicitor: Jane Doe, ABC Law Firm (jane@abclaw.com)
Expected duration: 18 months (trial scheduled July 2026)
Notes: Survey responses may be required as evidence.
```

#### Legal Hold Effects

When a legal hold is active:
- **Automatic deletion suspended** - data will not be deleted
- **Warnings suppressed** - no deletion warning emails sent
- **No retention limit** - can be held indefinitely
- **Audit trail updated** - all holds logged
- **Organisation notified** - org owner receives confirmation email

#### Reviewing and Lifting Legal Holds

Legal holds should be reviewed regularly:

1. **Monthly review**: Organisation owner checks all active holds
2. **Verify continued need**: Contact legal counsel to confirm hold still required
3. **Lift hold when appropriate**:
   - Navigate to survey dashboard
   - Click "Lift Legal Hold"
   - Provide reason for lifting
   - Data immediately subject to normal retention policy

After lifting:

- Retention countdown resumes from where it left off
- Deletion warnings sent if close to deadline
- Can be placed again if needed

#### Legal Hold Audit Trail

All legal hold actions are logged:

- Who placed the hold
- When it was placed
- Justification provided
- When it was lifted (if applicable)
- Reason for lifting

Organisation owners can view legal hold reports showing:

- All active legal holds
- Hold duration
- Surveys affected
- Estimated data volume

### Ownership Transfer

When a survey creator leaves the organisation or changes roles, survey ownership may need to be transferred.

#### Automatic Transfer

Surveys automatically transfer to the **organisation owner** when:

- Survey creator's account is deactivated
- Survey creator leaves the organisation (membership revoked)
- Survey creator requests transfer

**Automatic transfer process**:

1. System detects creator account deactivation
2. Ownership transfers to organisation owner
3. Both parties notified via email (if possible)
4. Audit log records transfer
5. All permissions preserved

**Email notification**:
```
Subject: Survey ownership transferred

The survey "Diabetes Survey" has been transferred to you.

Previous owner: john.smith@example.com (deactivated)
New owner: you@example.com
Transfer date: 2025-02-01

You now have full control over this survey.
```

#### Manual Transfer

Survey creators can manually transfer ownership:

1. Navigate to survey dashboard
2. Click "Transfer Ownership"
3. Select new owner (must be organisation member)
4. Provide reason for transfer
5. New owner receives notification and must accept

**Transfer confirmation**:

- New owner must explicitly accept
- All data access permissions retained
- Original creator loses owner permissions (becomes Editor)
- Cannot be reversed without another transfer

#### Transfer Implications

**For the new owner**:

- Full survey control
- Data download permission
- Retention management
- All future emails (warnings, exports, etc.)

**For the previous owner**:

- Automatically becomes Editor (can modify survey structure)
- Loses data access
- No longer receives deletion warnings
- Can be removed entirely by new owner

#### Organisation Dissolution

If an organisation is deleted:

- All surveys automatically transfer to individual survey creators
- Organisation-level encryption removed (if applicable)
- Each creator becomes independent owner
- All creators notified

### Data Custodian Role

The **Data Custodian** role allows delegation of data management without granting full survey control.

#### When to Use Data Custodians

✅ **Appropriate use cases**:

- Research data manager responsible for data exports
- Quality improvement lead who analyzes data
- Audit committee member who reviews data
- Delegate who handles data while you're on leave

❌ **Not appropriate for**:

- Survey editors (use Editor role)
- People who should view responses in UI (use organisation membership)
- General collaborators (use Viewer role)

#### Assigning a Data Custodian

1. Navigate to survey dashboard
2. Click "Manage Users"
3. Click "Assign Data Custodian"
4. Enter email address or select from organisation members
5. Optionally provide note explaining why
6. Click "Assign"

**Custodian receives email**:
```
Subject: You've been assigned as Data Custodian

Survey: Diabetes Survey
Organisation: NHS Trust Research
Assigned by: john.smith@example.com

As Data Custodian, you can:
- Download data exports
- View audit logs
- Receive deletion warnings

You cannot:
- View responses in the UI
- Edit the survey
- Extend retention
- Manage other users
```

#### Data Custodian Permissions

**Can do**:

- Download exports (CSV, JSON, Excel)
- Provide purpose statements
- View audit logs for this survey
- Receive deletion warning emails

**Cannot do**:

- View responses in the web interface
- Edit survey questions or settings
- Close or reopen survey
- Extend retention period
- Assign or remove other users
- Delete the survey
- Place legal holds

#### Removing Data Custodians

Survey creators or organisation owners can remove custodians:

1. Navigate to survey dashboard
2. Click "Manage Users"
3. Find custodian in list
4. Click "Remove"
5. Confirm removal

**Removal email**:
```
Subject: Data Custodian access removed

You no longer have Data Custodian access to:

Survey: Diabetes Survey
Organisation: NHS Trust Research
Removed by: john.smith@example.com
Date: 2025-02-01
```

### Emergency Data Access

In rare circumstances, organisation owners may need emergency access to survey data.

#### Emergency Access Scenarios

- Survey creator suddenly unavailable (illness, emergency)
- Critical incident requiring immediate data review
- Data breach investigation
- Safeguarding concern

#### Emergency Access Procedure

1. **Organisation owner** can access any organisation survey
2. Emergency access automatically logged
3. Survey creator notified (if possible)
4. Requires documented justification post-access

**Emergency access audit entry**:
```
Emergency data access
User: admin@example.com (Organisation Owner)
Survey: Diabetes Survey
Time: 2025-02-01 15:30:00
Reason: Creator unavailable, urgent data needed for incident investigation
Notification: Survey creator notified via email
```

### Participant Withdrawal

If a survey participant requests their data be removed:

#### Right to Erasure (GDPR)

Participants have the right to request deletion of their data if:

- They withdraw consent
- Data no longer necessary for original purpose
- They object to processing
- Data processed unlawfully

#### Withdrawal Process

1. Participant contacts survey creator/organisation
2. Verify identity (ensure request is genuine)
3. Locate response (using timestamp, email, or other identifier)
4. Delete specific response:
   - Navigate to survey responses
   - Find participant's response
   - Click "Delete Response"
   - Document reason: "Participant withdrawal request"
5. Confirm deletion to participant

#### Deletion Limitations

Cannot delete if:

- Data already anonymized (cannot identify individual response)
- Legal obligation to retain (e.g., clinical trial regulations)
- Public interest (e.g., public health research)
- Exercise/defense of legal claims

If deletion not possible, must inform participant and explain why.

#### Partial Deletion

Participant can request:

- Deletion of specific questions
- Anonymization instead of deletion
- Restricted processing (mark as "do not use")

Document all requests and actions taken.

---

## Implementation

This section provides technical details for developers implementing data governance features.

### Database Schema

#### Survey Model

```python
class Survey(models.Model):
    # Core fields
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    organisation = models.ForeignKey(Organisation, null=True, on_delete=models.SET_NULL)

    # Lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    # choices: 'draft', 'published', 'closed', 'archived'

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Retention
    retention_period_months = models.IntegerField(default=6)
    deletion_scheduled_at = models.DateTimeField(null=True, blank=True)
    legal_hold = models.BooleanField(default=False)
    legal_hold_reason = models.TextField(blank=True)
    legal_hold_placed_at = models.DateTimeField(null=True, blank=True)
    legal_hold_placed_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='legal_holds_placed')
```

#### Data Export Log

```python
class DataExportLog(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    exported_at = models.DateTimeField(auto_now_add=True)
    export_format = models.CharField(max_length=10)  # 'csv', 'json', 'xlsx'
    purpose = models.TextField()

    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()

    # Compliance
    governance_acknowledged = models.BooleanField(default=False)
    terms_version = models.CharField(max_length=20)
```

#### Retention Extension Log

```python
class RetentionExtension(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    extended_at = models.DateTimeField(auto_now_add=True)
    previous_deletion_date = models.DateTimeField()
    new_deletion_date = models.DateTimeField()

    justification = models.TextField()
    approved = models.BooleanField(default=True)
    approved_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='retention_approvals')
```

### Permission Checks

#### View Decorator

```python
from functools import wraps
from django.core.exceptions import PermissionDenied

def require_data_access(view_func):
    """Require user has data download permission for survey."""
    @wraps(view_func)
    def wrapper(request, survey_slug, *args, **kwargs):
        survey = get_object_or_404(Survey, slug=survey_slug)

        # Check permissions
        if not (
            request.user == survey.owner or
            request.user == survey.organisation.owner or
            survey.data_custodians.filter(user=request.user).exists()
        ):
            raise PermissionDenied("You do not have data access permission.")

        # Check survey is closed
        if survey.status != 'closed':
            raise PermissionDenied("Survey must be closed before data export.")

        return view_func(request, survey_slug, *args, **kwargs)

    return wrapper
```

#### Permission Helper Methods

```python
class Survey(models.Model):
    # ... fields ...

    def can_download_data(self, user):
        """Check if user has permission to download data."""
        if not self.is_closed():
            return False

        return (
            user == self.owner or
            user == self.organisation.owner or
            self.data_custodians.filter(user=user).exists()
        )

    def can_extend_retention(self, user):
        """Check if user can extend retention period."""
        return (
            user == self.owner or
            user == self.organisation.owner
        )

    def can_place_legal_hold(self, user):
        """Check if user can place legal hold."""
        return (
            self.organisation and
            user == self.organisation.owner
        )
```

### Scheduled Tasks

#### Deletion Warnings

```python
# celery tasks (schedule with celery beat)
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail

@celery.task
def send_deletion_warnings():
    """Send deletion warning emails at 1 month, 1 week, 1 day."""
    now = timezone.now()

    # Surveys to be deleted in 1 month
    one_month_surveys = Survey.objects.filter(
        deletion_scheduled_at__gte=now + timedelta(days=29),
        deletion_scheduled_at__lt=now + timedelta(days=31),
        legal_hold=False
    )

    for survey in one_month_surveys:
        send_deletion_warning(survey, days_remaining=30)

    # Surveys to be deleted in 1 week
    one_week_surveys = Survey.objects.filter(
        deletion_scheduled_at__gte=now + timedelta(days=6),
        deletion_scheduled_at__lt=now + timedelta(days=8),
        legal_hold=False
    )

    for survey in one_week_surveys:
        send_deletion_warning(survey, days_remaining=7)

    # Surveys to be deleted in 1 day
    one_day_surveys = Survey.objects.filter(
        deletion_scheduled_at__gte=now + timedelta(hours=22),
        deletion_scheduled_at__lt=now + timedelta(hours=26),
        legal_hold=False
    )

    for survey in one_day_surveys:
        send_deletion_warning(survey, days_remaining=1)

def send_deletion_warning(survey, days_remaining):
    """Send warning email to survey owner, org owner, and custodians."""
    recipients = [survey.owner.email]

    if survey.organisation:
        recipients.append(survey.organisation.owner.email)

    for custodian in survey.data_custodians.all():
        recipients.append(custodian.user.email)

    send_mail(
        subject=f'WARNING: Survey data will be deleted in {days_remaining} day(s)',
        message=f'Survey "{survey.name}" is scheduled for deletion.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=list(set(recipients)),  # Remove duplicates
    )
```

#### Automatic Deletion

```python
@celery.task
def delete_expired_surveys():
    """Delete surveys whose retention period has expired."""
    now = timezone.now()

    expired_surveys = Survey.objects.filter(
        deletion_scheduled_at__lt=now,
        legal_hold=False
    )

    for survey in expired_surveys:
        delete_survey_data(survey)

def delete_survey_data(survey):
    """Permanently delete all survey responses."""
    # Delete all responses
    response_count = survey.responses.count()
    survey.responses.all().delete()

    # Log deletion
    DeletionLog.objects.create(
        survey=survey,
        deleted_at=timezone.now(),
        response_count=response_count,
        reason='retention_expired'
    )

    # Send confirmation email
    send_mail(
        subject=f'Survey data deleted: {survey.name}',
        message=f'{response_count} responses have been permanently deleted.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[survey.owner.email],
    )

    # Update survey status
    survey.status = 'archived'
    survey.save()
```

### Export Views

#### CSV Export

```python
import csv
from django.http import HttpResponse

@require_data_access
def export_csv(request, survey_slug):
    survey = get_object_or_404(Survey, slug=survey_slug)

    # Get purpose from form
    purpose = request.POST.get('purpose', '')
    if not purpose:
        return JsonResponse({'error': 'Purpose required'}, status=400)

    # Log export
    DataExportLog.objects.create(
        survey=survey,
        user=request.user,
        export_format='csv',
        purpose=purpose,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        governance_acknowledged=True
    )

    # Send notification to org owner
    if survey.organisation:
        notify_data_export(survey, request.user, 'csv', purpose)

    # Generate CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{survey.slug}_export.csv"'

    writer = csv.writer(response)

    # Write headers
    headers = ['response_id', 'timestamp', 'user_id']
    for question in survey.questions.all():
        headers.append(question.key)
    writer.writerow(headers)

    # Write data
    for response_obj in survey.responses.all():
        row = [
            response_obj.id,
            response_obj.created_at,
            response_obj.user_id or ''
        ]
        for question in survey.questions.all():
            value = response_obj.data.get(question.key, '')
            row.append(value)
        writer.writerow(row)

    return response
```

### Audit Trail

#### Audit Log Model

```python
class AuditLog(models.Model):
    # Who
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    # What
    action = models.CharField(max_length=50)
    # choices: 'data_export', 'retention_extension', 'legal_hold_placed',
    #          'legal_hold_lifted', 'survey_closed', 'ownership_transferred'

    # Where
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)

    # When
    timestamp = models.DateTimeField(auto_now_add=True)

    # Why
    reason = models.TextField(blank=True)

    # How
    ip_address = models.GenericIPAddressField()
    metadata = models.JSONField(default=dict)
```

#### Audit Logging

```python
def log_audit_event(user, survey, action, reason='', metadata=None):
    """Create audit log entry."""
    AuditLog.objects.create(
        user=user,
        action=action,
        survey=survey,
        reason=reason,
        ip_address=get_client_ip(request),
        metadata=metadata or {}
    )
```

### Email Notifications

#### Data Export Notification

```python
def notify_data_export(survey, user, format, purpose):
    """Notify org owner of data export."""
    if not survey.organisation:
        return

    send_mail(
        subject=f'Data Export: {survey.name}',
        message=f'''
User: {user.email}
Survey: {survey.name}
Time: {timezone.now()}
Purpose: {purpose}
Format: {format.upper()}
IP: {get_client_ip(request)}

View full audit log: {settings.SITE_URL}/surveys/{survey.slug}/audit/
        ''',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[survey.organisation.owner.email],
    )
```

### Settings Configuration

```python
# settings.py

# Data governance
DATA_RETENTION_DEFAULT_MONTHS = 6
DATA_RETENTION_MAX_MONTHS = 24

DELETION_WARNING_INTERVALS = [
    30,  # 1 month
    7,   # 1 week
    1,   # 1 day
]

# Email notifications
DATA_EXPORT_NOTIFICATIONS = True
DELETION_WARNING_EMAILS = True

# Audit log retention (years)
AUDIT_LOG_RETENTION_YEARS = 7
```

---

## Your Responsibilities

### As a Survey Creator

- Close surveys promptly when data collection is complete
- Download data only when necessary
- Store downloaded data securely
- Delete local copies when no longer needed
- Respond to deletion warnings before deadlines
- Justify any retention extensions

### As an Organisation Owner

- Set clear data policies for your organisation
- Monitor data downloads across all surveys
- Review retention extensions
- Ensure appropriate access controls
- Designate data custodians when appropriate
- Respond to legal hold requests

### As a Data Custodian

- Download data only when authorized
- Follow your organisation's data handling procedures
- Store exports securely
- Report any security concerns immediately
- Maintain confidentiality

---

## Getting Help

If you have questions about data governance:

1. **Contact your organisation's data protection officer** (if designated)
2. **For technical issues:** [GitHub Issues](https://github.com/eatyourpeas/checktick/issues)
3. **For security concerns:** Contact your organisation administrator immediately

---

## Compliance

CheckTick is designed to support compliance with:

- **GDPR** (General Data Protection Regulation)
- **UK Data Protection Act 2018**
- **NHS Data Security and Protection Toolkit**
- **Caldicott Principles**
- Research ethics requirements

However, **you are responsible** for ensuring your specific use case complies with applicable regulations. CheckTick provides the tools - you provide the governance.
