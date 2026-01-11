---
title: "Data Subject Request Procedure"
category: dspt-1-confidential-data
---

# Data Subject Request (DSR) Handling Procedure

**Version:** 1.0
**Last Updated:** 4 January 2026
**Owner:** Data Protection Officer
**Review Date:** 4 January 2027

## 1. Purpose

This procedure establishes the workflow for handling data subject requests (DSRs) received by CheckTick, whether submitted by survey respondents directly to the platform or escalated from data controllers (survey creators).

## 2. Scope

This procedure applies to:

- All DSRs from survey respondents
- Access requests (Right of Access - GDPR Article 15)
- Erasure requests (Right to Erasure - GDPR Article 17)
- Rectification requests (Right to Rectification - GDPR Article 16)
- Objection requests (Right to Object - GDPR Article 21)
- Data portability requests (GDPR Article 20)

## 3. Roles and Responsibilities

### 3.1 Survey Creator (Data Controller)

- Primary responsibility for responding to DSRs
- Must respond within 30 days of notification
- Determines lawful basis and any exemptions
- Actions the request (access, erasure, rectification)
- Documents resolution

### 3.2 CheckTick Platform (Data Processor)

- Provides tools for controllers to fulfil DSRs
- Receives and forwards DSRs when respondent contacts us directly
- Monitors deadline compliance
- Escalates and freezes data when controllers fail to respond
- May suspend surveys for persistent non-compliance

### 3.3 Data Protection Officer

- Oversees DSR handling
- Reviews escalations
- Determines platform interventions
- Liaises with ICO if necessary

## 4. DSR Types and Controller Tools

### 4.1 Access Request (SAR)

**What the respondent wants:** A copy of their survey response data.

**Controller actions:**

1. Locate the response using the respondent's receipt token
2. Export the individual response data
3. If demographics are encrypted, decrypt using survey key
4. Provide the data to the respondent in a portable format

**CheckTick tools:**

- Response lookup by receipt token
- Individual response export
- Demographic decryption (requires survey key)

### 4.2 Erasure Request (Right to be Forgotten)

**What the respondent wants:** Their survey response deleted.

**Controller actions:**

1. Verify the request is valid (no overriding legal basis to retain)
2. Locate the response using receipt token
3. Delete the response
4. Confirm deletion to the respondent

**CheckTick tools:**

- Response lookup by receipt token
- Individual response deletion
- Audit log of deletion

**Note:** Erasure may not be possible if:

- Data is needed for legal claims
- Data is required by law (e.g., healthcare records)
- Data is processed for public health purposes

The controller must document any refusal and inform the respondent of their right to complain to the ICO.

### 4.3 Rectification Request

**What the respondent wants:** Correction of inaccurate data.

**Controller actions:**

1. Locate the response using receipt token
2. Review the claimed inaccuracy
3. Update the response data if appropriate
4. Confirm the correction to the respondent

**CheckTick tools:**

- Response lookup by receipt token
- Response editing (for authorised users)

### 4.4 Objection / Restriction Request

**What the respondent wants:** Stop processing their data.

**Controller actions:**

1. Assess whether there are legitimate grounds to override the objection
2. If no override, cease processing (freeze the response)
3. Inform the respondent of the outcome

**CheckTick tools:**

- Response freeze (excludes from exports/analysis)
- Response unfreezing (if objection is resolved)

## 5. Workflow: Controller-Handled DSR

This is the standard flow where the controller receives and handles the DSR directly.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTROLLER-HANDLED DSR                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Respondent ──► Controller                                      │
│      │              │                                           │
│      │              ▼                                           │
│      │         Verify Request                                   │
│      │         (receipt token,                                  │
│      │          identity)                                       │
│      │              │                                           │
│      │              ▼                                           │
│      │         Action Request                                   │
│      │         (using CheckTick                                 │
│      │          tools)                                          │
│      │              │                                           │
│      │              ▼                                           │
│      │         Document &                                       │
│      ◄────────── Respond                                        │
│                                                                 │
│  Timeline: Controller must respond within 30 days               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Workflow: Platform-Escalated DSR

This flow applies when the respondent contacts CheckTick directly because they cannot identify or reach the controller.

```
┌─────────────────────────────────────────────────────────────────┐
│                   PLATFORM-ESCALATED DSR                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Day 0:  Respondent ──► CheckTick                               │
│              │              │                                   │
│              │              ▼                                   │
│              │         Create DSR                               │
│              │         Record                                   │
│              │              │                                   │
│              │              ▼                                   │
│              │         Notify Controller                        │
│              │         (email with                              │
│              │          30-day deadline)                        │
│              │              │                                   │
│  Day 7:     │              ▼                                   │
│              │         Reminder #1                              │
│              │         (23 days remaining)                      │
│              │              │                                   │
│  Day 28:    │              ▼                                   │
│              │         Reminder #2                              │
│              │         (2 days remaining)                       │
│              │              │                                   │
│  Day 30:    │              ▼                                   │
│              │         If no response:                          │
│              │         ┌─────────────────┐                      │
│              │         │ ESCALATE:       │                      │
│              │         │ • Freeze data   │                      │
│              │         │ • Notify owner  │                      │
│              │         │ • Log action    │                      │
│              │         └─────────────────┘                      │
│              │              │                                   │
│              │              ▼                                   │
│              ◄──────── Inform respondent                        │
│                        of status                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.1 Day 0: Receipt and Notification

1. Respondent contacts CheckTick at dpo@checktick.uk
2. Support creates a `DataSubjectRequest` record
3. System identifies the survey and controller
4. System sends notification email to controller with:
   - Description of the request
   - 30-day deadline
   - Link to tools for handling the request
5. DSR status set to `NOTIFIED`

### 6.2 Day 7: First Reminder

Automated `process_dsr_deadlines` command sends reminder email:
- 23 days remaining
- Link to review the request
- Warning of consequences if not actioned

### 6.3 Day 28: Final Reminder

Automated command sends urgent reminder:
- 2 days remaining
- Explicit warning that data will be frozen
- Contact details for platform support

### 6.4 Day 30+: Escalation

If controller has not responded:

1. DSR status set to `ESCALATED`
2. Response is frozen with `freeze_source=platform`
3. `ResponseFreezeLog` entry created
4. Controller notified that response is frozen
5. Respondent notified of escalation status
6. Survey flagged with `has_pending_dsr=True`

### 6.5 Resolution

When controller finally responds:

1. Controller actions the request
2. Controller contacts CheckTick support
3. Platform admin reviews documentation
4. If satisfied:
   - Response unfrozen (if appropriate)
   - DSR status set to `RESOLVED`
   - Survey DSR flag cleared
5. Respondent notified of resolution

## 7. Response Freezing

### 7.1 What Freezing Does

- Response excluded from all exports
- Response excluded from analytics
- Response data remains in database (not deleted)
- Freeze is logged with reason, source, and timestamp

### 7.2 Freeze Sources

| Source | Who Can Unfreeze | When Used |
|--------|------------------|-----------|
| `controller` | Survey owner, org admin, team admin | Controller is proactively quarantining during DSR handling |
| `platform` | Superuser only | Platform escalated due to deadline breach |

### 7.3 Controller-Initiated Freeze

Controllers may proactively freeze a response while handling a DSR:

- Prevents accidental inclusion in exports during processing
- Controller can unfreeze once resolved

### 7.4 Platform-Initiated Freeze

Platform freezes responses when:

- DSR deadline exceeded (30 days)
- Controller unresponsive despite reminders

Platform freezes can only be lifted by CheckTick support after review.

## 8. Survey Suspension

### 8.1 When Suspension Occurs

A survey may be suspended if the controller:

- Repeatedly fails to respond to DSRs
- Shows a pattern of non-compliance
- Refuses to comply without lawful justification

### 8.2 Effect of Suspension

- Survey set to `SUSPENDED` status
- No new responses can be collected
- Existing responses remain frozen
- Dashboard shows suspension notice

### 8.3 Lifting Suspension

To lift suspension:

1. Controller must resolve all outstanding DSRs
2. Controller must provide evidence of compliance measures
3. Platform admin reviews and approves
4. Suspension lifted, survey can be republished

## 9. Anonymous Surveys

### 9.1 DSRs Not Applicable

For anonymous surveys (public, unlisted without personal tokens):

- No receipt token is issued
- Responses cannot be linked to individuals
- DSRs cannot be fulfilled (no identifiable data subject)
- Respondent is warned before submission

### 9.2 Pre-Submission Notice

Anonymous surveys display:

> **Anonymous Survey Notice**
>
> This survey is anonymous. Your response cannot be linked to your identity.
> After submission, you will not be able to request access to, correction of,
> or deletion of your response because we cannot identify which response is yours.

## 10. Record Keeping

### 10.1 DSR Records

All DSRs are logged with:

- Date received
- Request type
- Receipt token (if provided)
- Controller notification date
- Deadline
- Reminder dates sent
- Resolution date
- Resolution outcome

### 10.2 Freeze Logs

All freeze/unfreeze actions logged with:

- Action (freeze/unfreeze)
- Source (controller/platform)
- Reason
- Performed by
- Timestamp
- Related DSR (if any)

### 10.3 Retention

DSR records retained for 6 years from resolution date for accountability and audit purposes.

## 11. Escalation to DPO

The DPO should be consulted when:

- Controller disputes the validity of a DSR
- Respondent disputes the controller's refusal
- Pattern of non-compliance identified
- ICO inquiry received
- Complex cases involving healthcare/sensitive data

## 12. ICO Complaints

If a respondent complains to the ICO:

1. DPO coordinates response
2. All DSR records provided to ICO
3. Controller notified and involved in response
4. Full cooperation with ICO investigation

## 13. Automation

The `process_dsr_deadlines` management command runs daily and:

- Sends 7-day and 28-day reminder emails
- Escalates and freezes at 30+ days
- Updates survey DSR warning flags
- Clears flags when DSRs are resolved

### 13.1 Running the Command

```bash
# Normal run
python manage.py process_dsr_deadlines

# Dry run (no changes)
python manage.py process_dsr_deadlines --dry-run

# Verbose output
python manage.py process_dsr_deadlines --verbose
```

### 13.2 Scheduling

Add to cron or Northflank scheduled job to run daily:

```
0 8 * * * python manage.py process_dsr_deadlines
```

## 14. Training

All support staff handling DSRs must:

- Complete GDPR awareness training
- Understand the DSR workflow
- Know when to escalate to DPO
- Be familiar with CheckTick DSR tools

## 15. Review

This procedure is reviewed annually or when:

- Significant changes to data protection law
- ICO guidance changes
- After any DSR-related complaint or incident
- Following internal audit findings

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 4 January 2026 | DPO | Initial version |
