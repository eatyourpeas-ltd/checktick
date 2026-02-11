---
title: Data Governance Special Cases
category: None
---

This guide covers edge cases and special situations in data governance, including legal holds, ownership transfers, and the data custodian role.

---

## 1. Legal Holds

### 1.1 What is a Legal Hold?

A **legal hold** (also called "litigation hold") prevents automatic deletion of survey data when:
- Legal proceedings are active or anticipated
- Regulatory investigations are underway
- Formal complaints have been filed
- Audit requirements demand data preservation

**Key characteristics:**
- Overrides normal retention periods
- Prevents automatic deletion
- Requires documented justification
- Reviewable and removable when no longer needed

### 1.2 When to Apply a Legal Hold

**Apply a legal hold when:**
- You receive a legal notice requiring data preservation
- Litigation is reasonably anticipated
- Regulatory authority requests data retention
- Employment tribunal proceedings involve the survey
- Subject access request is complex or disputed
- Formal complaint under investigation
- Internal disciplinary proceedings underway

**Do NOT apply for:**
- General "we might need this" concerns
- Convenience (to avoid deletion)
- Bypassing the 24-month retention limit
- Personal preference to keep data

### 1.3 Who Can Apply Legal Holds

**Only Organisation Owners** can apply legal holds.

**Why this restriction:**

- Legal holds have significant data protection implications
- Require understanding of legal obligations
- Need organisational authority
- Accountability and audit trail

**Survey Creators and Data Custodians:**

- Cannot apply legal holds themselves
- Must request through organisation owner
- Provide justification and context

### 1.4 How to Apply a Legal Hold

**Step 1: Assess Need**

Determine if a legal hold is appropriate:

- Is there genuine legal requirement?
- Has legal counsel advised retention?
- Is the data relevant to proceedings?
- What is the expected duration?

**Step 2: Navigate to Survey**

1. Log in as Organisation Owner
2. Go to "Surveys" → Find the survey
3. Click "Data Management" tab
4. Look for "Legal Hold" section

**Step 3: Apply Hold**

Click "Apply Legal Hold" and provide:

**Required Information:**

- **Reason:** Specific legal basis (e.g., "Employment tribunal case ET/12345/2025")
- **Reference:** Case number, investigation ID, or complaint reference
- **Expected Duration:** Estimate how long hold will be needed
- **Requesting Party:** Who requested the hold (e.g., "Legal counsel" or "ICO investigation")
- **Review Date:** When hold should be reviewed (default: 6 months)

**Example:**

```text
Reason: Employment tribunal proceedings
Reference: ET/12345/2025 - Smith v Organisation
Expected Duration: 12-18 months
Requesting Party: Organisation legal counsel (email: legal@org.uk)
Review Date: 2025-12-01
```

**Step 4: Confirm and Notify**

After applying hold:

- Survey data retention is frozen
- Automatic deletion warnings stop
- Legal hold badge appears on survey
- Organisation administrators notified
- Hold logged for audit trail

### 1.5 Effect of Legal Hold

**While a legal hold is active:**

**Data Retention:**

- Automatic deletion is **prevented**
- Retention period is **frozen** (not counting down)
- Data remains accessible for download
- Warnings are **paused**

**Survey Status:**

- Survey remains **closed**
- No new responses can be added
- Survey structure can still be viewed
- Data exports are still possible

**User Access:**

- Existing permissions remain unchanged
- Survey creators can still download their data
- Organisation owners can download
- Data custodians can download (if assigned)

**Visibility:**

- "Legal Hold" badge visible on survey list
- Hold details visible to organisation owners only
- Survey creators see "Retention frozen - Legal hold active"
- Audit log records hold status

### 1.6 Reviewing Legal Holds

**Mandatory Review:**

- Legal holds must be reviewed every **6 months**
- Organisation owner receives reminder
- Must confirm hold is still necessary
- Update expected duration if changed

**Review Process:**

1. Receive review reminder email
2. Check status of legal proceedings/investigation
3. Consult legal counsel if uncertain
4. Either:
   - **Confirm hold** - Extend for another 6 months
   - **Remove hold** - If no longer needed
   - **Update details** - If circumstances changed

**Questions to ask:**

- Are proceedings still active?
- Has the case been resolved?
- Has the authority closed the investigation?
- Is the data still potentially relevant?
- What is legal counsel's advice?

### 1.7 Removing Legal Holds

**When to Remove:**

- Legal proceedings concluded
- Investigation closed
- Complaint resolved
- Legal counsel confirms data no longer needed
- Review determines hold no longer justified

**How to Remove:**

1. Go to survey → "Data Management" → "Legal Hold"
2. Click "Remove Legal Hold"
3. Provide reason for removal
4. Confirm removal

**Effect of Removal:**

**Immediate:**

- Legal hold badge removed
- Retention period **resumes** from where it was frozen
- New deletion warnings calculated
- Organisation administrators notified

**Example:**

- Survey closed: January 1, 2025
- Legal hold applied: March 1, 2025 (60 days after closure)
- Time elapsed before hold: 60 days
- Legal hold active: 12 months (365 days)
- Legal hold removed: March 1, 2026
- Retention resumes with: 180 - 60 = 120 days remaining
- New deletion date: July 1, 2026 (120 days from March 1, 2026)

**If retention already expired:**

- Survey data **not automatically deleted**
- Organisation owner must decide: extend retention or delete
- Must act within 30 days

### 1.8 Legal Hold Audit Trail

All legal hold actions are logged:

**Recorded Information:**

- Who applied the hold (name, email, timestamp)
- Reason and reference provided
- Expected duration
- Review dates and outcomes
- Who removed the hold (name, email, timestamp)
- Reason for removal
- Total duration of hold

**Access to audit trail:**

- Organisation owners: Full access
- Data Protection Officer: Full access
- System administrators: Full access
- Survey creators: Summary only ("Legal hold was active from [date] to [date]")

---

## 2. Ownership Transfer

### 2.1 What is Ownership Transfer?

**Ownership transfer** occurs when the survey creator leaves the organisation or can no longer fulfill their responsibilities. Ownership automatically or manually transfers to ensure:

- Continued data governance
- Compliance with retention policies
- Access for legitimate purposes
- Accountability

### 2.2 When Ownership Transfers

**Automatic Transfer:**

- Survey creator's account is **deactivated**
- Survey creator leaves the organisation
- Survey creator's access is **revoked**

**Manual Transfer:**

- Survey creator requests transfer (e.g., changing roles)
- Organisation reorganisation
- Project reassignment
- Data custodian promoted to owner

### 2.3 Automatic Transfer Process

**Trigger Event:**

- User account deactivation
- Organisation membership removal
- Account deletion

**Automatic Actions:**

1. **Identify affected surveys** - All surveys where user is creator
2. **Determine new owner** - Default: Organisation owner
3. **Transfer ownership** - Update database records
4. **Notify parties:**
   - New owner (email notification)
   - Organisation administrators
   - Data custodians (if assigned)
5. **Update audit log** - Record transfer details

**Data Preservation:**

- All survey data remains intact
- Retention settings **unchanged**
- Legal holds remain active
- Data custodians remain assigned

**Example Timeline:**

```text
Day 0: Alice (survey creator) leaves organisation
  → Account deactivated
  → System identifies 5 surveys owned by Alice
  → Ownership transfers to Bob (organisation owner)

Day 0: Bob receives email:
  "You are now the owner of 5 surveys previously owned by Alice.
   Please review retention settings and download any needed data."

Day 1-30: Bob reviews surveys
  → Survey A: Downloads data, extends retention 6 months
  → Survey B: Already has legal hold, no action needed
  → Survey C: No longer needed, allows deletion
  → Survey D: Assigns data custodian (Carol)
  → Survey E: Keeps existing settings
```

### 2.4 Manual Transfer Process

**Step 1: Requester Initiates**

**Survey Creator (current owner):**

1. Go to survey → "Settings" → "Ownership"
2. Click "Transfer Ownership"
3. Select new owner (must be organisation member)
4. Provide reason for transfer
5. Click "Request Transfer"

**Organisation Owner (forced transfer):**

1. Go to "Surveys" → Find survey
2. Click "..." menu → "Transfer Ownership"
3. Select new owner
4. Provide reason
5. Click "Transfer Now" (no approval needed)

**Step 2: New Owner Accepts (if requested by creator)**

New owner receives email:

1. Click "Review Transfer Request"
2. See survey details and reason
3. Click "Accept" or "Decline"
4. If accepted, ownership transfers immediately

**Step 3: Completion**

- Ownership changes
- Old owner loses download access (unless also org owner)
- New owner receives full creator permissions
- Audit log updated

### 2.5 Post-Transfer Responsibilities

**New Owner Must:**

- Review survey data and purpose
- Check retention expiry date
- Decide if extension needed
- Review data custodian assignments
- Download data if needed
- Ensure compliance with data policy

**New Owner Should:**

- Understand original survey purpose
- Maintain continuity of data governance
- Honor original consent/privacy notices
- Continue compliance obligations

**New Owner Must NOT:**

- Use data for purposes incompatible with original intent
- Share data beyond original scope
- Re-identify anonymized data
- Violate participant expectations

### 2.6 Multiple Transfers

**Scenario:** Ownership transferred multiple times.

**Tracking:**

- Audit log records all transfers
- Each transfer timestamped
- Reasons documented
- Chain of custody maintained

**Example:**

```text
Survey #12345 Ownership History:
1. Created by: Alice (Jan 1, 2025)
2. Transferred to: Bob (Mar 15, 2025) - "Alice left organisation"
3. Transferred to: Carol (Jun 1, 2025) - "Project reassignment"
4. Current owner: Carol
```

**Data Protection Considerations:**

- Original consent/privacy notice still applies
- Purpose limitation must be respected
- If purpose changes significantly, may need new consent

---

## 3. Data Custodian Role

### 3.1 What is a Data Custodian?

A **data custodian** is a user who:

- Has **download access** to specific survey data
- **Cannot edit** the survey
- **Cannot extend** retention periods
- Acts as a **trusted delegate** for data management

**Purpose:**

- Delegate data access without full ownership
- Separate survey editing from data access
- Support collaborative research/analysis
- Maintain accountability

### 3.2 When to Use Data Custodians

**Appropriate Uses:**

**Scenario 1: Collaborative Research**

- Survey creator (Principal Investigator)
- Data custodian (Research Assistant)
- Custodian analyzes data, creator manages survey

**Scenario 2: IT/Data Team**

- Survey creator (Clinical Team)
- Data custodian (Data Analyst)
- Custodian produces reports, creator owns data

**Scenario 3: Organisational Handover**

- Survey creator (Departing Staff)
- Data custodian (Incoming Staff)
- Custodian learns during handover, then becomes owner

**Scenario 4: Backup/Contingency**

- Survey creator (Primary Researcher)
- Data custodian (Backup Person)
- Custodian can download if creator unavailable

**Inappropriate Uses:**
- As a workaround for editors to see data (violates access control)
- To bypass retention limits (custodians can't extend)
- For non-essential "nice to have" access

### 3.3 Assigning Data Custodians

**Who Can Assign:**

- Survey creators (their own surveys)
- Organisation owners (any survey in organisation)

**How to Assign:**

1. Go to survey → "Settings" → "Data Access"
2. Click "Add Data Custodian"
3. Search for user (must be organisation member)
4. Select user
5. Provide **justification** (required):
   - Why does this person need data access?
   - What will they do with the data?
   - How long will they need access?
6. Click "Add"

**Example Justification:**

```text
Dr. Sarah Jones is the data analyst for this project. She will:
- Produce quarterly statistical reports
- Conduct regression analysis
- Create visualizations for publication
Access needed for duration of project (estimated 18 months).
```

**Notification:**

- Data custodian receives email
- Must acknowledge responsibilities
- Access granted after acknowledgment

### 3.4 Data Custodian Permissions

**Can Do:**

- ✓ Download survey data (same process as creators)
- ✓ View survey structure and questions
- ✓ See download history (their own downloads)
- ✓ View retention expiry date

**Cannot Do:**

- ✗ Edit survey structure
- ✗ Close or reopen survey
- ✗ Extend retention periods
- ✗ Apply legal holds
- ✗ Assign other data custodians
- ✗ Transfer ownership
- ✗ Delete survey

### 3.5 Data Custodian Responsibilities

**Data Custodians Must:**

- Follow all data security best practices
- Use data only for stated purpose
- Store data securely
- Delete data when no longer needed
- Report data breaches immediately
- Respect participant privacy
- Comply with data protection laws

**See:** [Data Security Guide](/docs/data-governance-security/)

**Data Custodians are personally liable** for data breaches caused by their actions.

### 3.6 Removing Data Custodians

**When to Remove:**

- Access no longer needed
- Project completed
- Custodian changes roles
- Custodian leaves organisation
- Data breach or policy violation

**Who Can Remove:**

- Survey creators (their own surveys)
- Organisation owners (any survey)
- Automatic removal if custodian account deactivated

**How to Remove:**

1. Go to survey → "Settings" → "Data Access"
2. Find data custodian in list
3. Click "Remove" next to their name
4. Confirm removal

**Effect:**

- Immediate loss of download access
- Custodian notified by email
- Must delete any downloaded data (unless org owner approves retention)
- Audit log updated

### 3.7 Data Custodian Audit Trail

All custodian actions are logged:

**Recorded:**

- Assignment (who, when, why)
- Downloads (what, when, purpose stated)
- Removal (who removed, when, why)

**Accessible to:**

- Survey creators: Full audit trail
- Organisation owners: Full audit trail
- Data custodians: Their own actions only

---

## 4. Other Special Cases

### 4.1 Survey Creator Becomes Data Custodian

**Scenario:** Survey ownership transferred, but original creator still needs data access.

**Solution:**

1. Transfer ownership to new person
2. Assign original creator as data custodian
3. Original creator retains download access
4. New owner controls retention and governance

**Example:**

- Alice creates survey, collects data
- Alice promoted, Bob takes over project
- Ownership transfers to Bob
- Alice assigned as data custodian
- Alice can still download data for ongoing analysis
- Bob manages retention and compliance

### 4.2 Multiple Data Custodians

**Allowed:** Yes, surveys can have multiple data custodians.

**Best Practices:**

- Clearly define each custodian's role
- Document who is responsible for what
- Avoid unnecessary duplication of access
- Review custodian list regularly

**Example:**

- Survey: Patient Satisfaction Survey
- Creator: Dr. Smith (Clinical Lead)
- Custodian 1: Dr. Jones (Data Analyst) - Statistical analysis
- Custodian 2: Sarah Brown (Quality Manager) - Regulatory reporting
- Custodian 3: IT Team (Database Manager) - Technical support

### 4.3 Organisation Deletion

**Scenario:** Entire organisation is deleted.

**Effect:**

- All surveys **soft deleted immediately**
- 30-day grace period for organisation owner
- Organisation owner receives final notification
- After 30 days: **All data hard deleted**

**Recovery:**

- Contact system administrators within 30 days
- Provide justification
- May require new organisation creation
- Data restored if within grace period

### 4.4 Data Subject Deletion Request

**Scenario:** Participant requests deletion under "right to be forgotten."

**Process:**

1. Participant contacts organisation
2. Organisation owner verifies identity
3. Locate participant's response(s)
4. Assess if deletion is required (legal grounds)
5. Delete response immediately (overrides retention)
6. Notify participant within 30 days
7. Log deletion for audit trail

**Exception:** If legal hold or legal obligation requires retention, deletion may be refused with explanation.

### 4.5 Retention Extension Beyond 24 Months

**Generally not allowed** - 24-month maximum is strict.

**Rare Exceptions:**

- Legal hold (data preserved as long as needed)
- Regulatory requirement (documented legal obligation)
- Approved research ethics extension (with appropriate safeguards)

**Approval Required:**

- Data Protection Officer
- Organisation owner
- System administrator (technical implementation)
- Documented justification and legal basis

### 4.6 Restoring After Soft Deletion

**Scenario:** Survey data soft deleted, but needed within 30 days.

**Who Can Restore:**

- Organisation owner only

**How to Restore:**

1. Go to "Deleted Surveys"
2. Find survey in list
3. Click "Restore"
4. Provide justification
5. Choose new retention period
6. Confirm restoration

**Limitations:**

- Must be within 30 days of soft deletion
- Total retention (original + new) cannot exceed 24 months from original closure
- Restoration is logged and reported

**After Restoration:**

- Survey data accessible again
- New retention period begins
- Standard warnings resume
- All stakeholders notified

---

## 5. Getting Help

### Questions About Special Cases

**Legal Holds:**

- Consult legal counsel before applying
- Contact organisation owner if you think one is needed
- DPO can advise on data protection implications

**Ownership Transfer:**

- Contact organisation owner for assistance
- Review with IT/admin if technical issues
- Consult DPO if data protection concerns

**Data Custodians:**

- Survey creators can assign (their own surveys)
- Organisation owners can assign (any survey)
- Contact organisation owner if unclear

### Related Documentation

- [Data Governance Overview](/docs/data-governance-overview/)
- [Data Export Guide](/docs/data-governance-export/)
- [Data Retention Policy](/docs/data-governance-retention/)
- [Data Security Guide](/docs/data-governance-security/)
- [Data Policy](/docs/data-governance-policy/)

---

## Remember

**Special cases are exceptional, not routine.**

- Use legal holds sparingly and appropriately
- Transfer ownership only when necessary
- Assign data custodians based on genuine need
- Document all special case actions
- Review regularly to ensure ongoing justification

**When in doubt, ask your organisation owner or Data Protection Officer.**
