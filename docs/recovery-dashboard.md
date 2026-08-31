---
title: Recovery Dashboard
category: security
priority: 6
---

# Recovery Dashboard Specifications

This document provides detailed specifications for the in-app recovery management dashboard used by organisation owners and platform administrators.

## Overview

The Recovery Dashboard is an administrative interface for managing encryption key recovery requests. It provides:

- Real-time view of pending recovery requests
- Identity verification document review
- Dual authorization workflow management
- Time delay monitoring
- Complete audit trail viewing
- Recovery rate monitoring and alerting
- SIEM integration status

Recovery flows recover the survey's **private key** (the per-survey X25519 keypair whose public key encrypts every response at submission time). The private key is escrowed using the same Vault mechanisms and audit trails as before; recovering it grants the ability to decrypt all responses encrypted with the survey's public key. Participants never provide any key material, and the server itself cannot decrypt responses without a recovered private key.

## User Roles and Access

| Role | Dashboard Access | Capabilities |
|------|-----------------|--------------|
| **Team Member** | None | Cannot access dashboard |
| **Team Admin** | Limited | View own team's recoveries (read-only) |
| **Organisation Owner** | Full (org scope) | Manage all org recovery requests |
| **Platform Admin** | Full (all) | Manage all recovery requests + system settings |

## Dashboard Views

### 1. Recovery Requests Overview

**URL**: `/admin/recovery/`

**Purpose**: Main dashboard showing all recovery requests

#### Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Recovery Dashboard                                    [Export] [Refresh]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │    2     │  │    1     │  │    3     │  │    5     │  │   0.3%   │  │
│  │ Pending  │  │ Awaiting │  │ In Time  │  │ Completed│  │ Recovery │  │
│  │ Requests │  │ Approval │  │  Delay   │  │ (30 days)│  │   Rate   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Filters: [Status ▼] [Date Range ▼] [User ▼] [Team ▼] [Search...]       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🟡 AWAITING SECONDARY APPROVAL                                   │   │
│  │ Dr. Sarah Jones (s.jones@nhs.uk)                                │   │
│  │ Survey: Diabetes Audit 2025                                      │   │
│  │ Submitted: 30 Nov 2025, 14:30 • Request ID: ABC-123-XYZ         │   │
│  │                                                                   │   │
│  │ Verification: ✅ Photo ID  ✅ Video Call  ✅ Security Questions   │   │
│  │ Primary Approval: admin1@org.uk (30 Nov 16:00)                  │   │
│  │                                                                   │   │
│  │ [View Details] [Approve as Secondary] [Reject]                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🟠 IDENTITY VERIFICATION IN PROGRESS                            │   │
│  │ Dr. Michael Brown (m.brown@hospital.uk)                         │   │
│  │ Survey: Patient Feedback Q4                                      │   │
│  │ Submitted: 30 Nov 2025, 10:15 • Request ID: DEF-456-UVW         │   │
│  │                                                                   │   │
│  │ Verification: ✅ Photo ID  ⏳ Video Call (scheduled 1 Dec 10:00) │   │
│  │                                                                   │   │
│  │ [View Details] [View Documents] [Schedule/Reschedule Call]       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🟢 IN TIME DELAY                                                 │   │
│  │ Dr. Emma Wilson (e.wilson@clinic.uk)                            │   │
│  │ Survey: Research Study 2025                                      │   │
│  │ Approved: 29 Nov 2025, 16:30 • Request ID: GHI-789-RST          │   │
│  │                                                                   │   │
│  │ ⏱️ Time Remaining: 18h 45m                                       │   │
│  │ Recovery Available: 1 Dec 2025, 16:30                           │   │
│  │                                                                   │   │
│  │ [View Details] [View Audit Trail]                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Status Indicators

| Status | Color | Icon | Description |
|--------|-------|------|-------------|
| Pending Verification | Orange | 🟠 | Identity verification in progress |
| Awaiting Primary | Yellow | 🟡 | Needs first admin approval |
| Awaiting Secondary | Yellow | 🟡 | Needs second admin approval |
| In Time Delay | Green | 🟢 | Approved, waiting period active |
| Ready for Execution | Blue | 🔵 | Time delay complete, ready to execute |
| Completed | Gray | ✅ | Recovery finished |
| Rejected | Red | ❌ | Request rejected |
| Cancelled | Red | ⛔ | Cancelled by user or admin |

### 2. Request Detail View

**URL**: `/admin/recovery/<request_id>/`

**Purpose**: Full details of a single recovery request

#### Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ← Back to Dashboard                                                     │
│                                                                         │
│ Recovery Request: ABC-123-XYZ                                           │
│ Status: 🟡 AWAITING SECONDARY APPROVAL                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ USER INFORMATION                                                        │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Name:        Dr. Sarah Jones                                        ││
│ │ Email:       s.jones@nhs.uk                                         ││
│ │ Account:     Created 15 Jan 2024                                    ││
│ │ Tier:        Individual                                             ││
│ │ Organisation: NHS Trust West (if applicable)                        ││
│ │ Last Login:  28 Nov 2025, 09:15                                     ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ SURVEY INFORMATION                                                      │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Survey:      Diabetes Audit 2025                                    ││
│ │ Created:     10 Oct 2025                                            ││
│ │ Last Access: 25 Nov 2025, 14:00                                     ││
│ │ Records:     156 patient records                                    ││
│ │ Encryption:  Hybrid X25519 + AES-256-GCM (per-survey keypair)       ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ IDENTITY VERIFICATION                                                   │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ ✅ Photo ID                                                         ││
│ │    Document: UK Driving Licence                                     ││
│ │    Submitted: 30 Nov 2025, 14:45                                    ││
│ │    Verified by: admin1@org.uk (30 Nov 15:00)                        ││
│ │    [View Document]                                                  ││
│ │                                                                     ││
│ │ ✅ Video Verification Call                                          ││
│ │    Completed: 30 Nov 2025, 15:30                                    ││
│ │    Duration: 12 minutes                                             ││
│ │    Conducted by: admin1@org.uk                                      ││
│ │    Notes: "Face matches ID. Confirmed employment details."          ││
│ │    [View Recording] (if enabled)                                    ││
│ │                                                                     ││
│ │ ✅ Security Questions                                               ││
│ │    Answered: 30 Nov 2025, 14:50                                     ││
│ │    Result: 3/3 correct                                              ││
│ │    [View Questions & Answers]                                       ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ AUTHORIZATION STATUS                                                    │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ ✅ Primary Authorization                                            ││
│ │    Approved by: admin1@org.uk                                       ││
│ │    Date: 30 Nov 2025, 16:00                                         ││
│ │    Reason: "Identity verified via video call. User confirmed       ││
│ │             they forgot both password and recovery phrase."         ││
│ │                                                                     ││
│ │ ⏳ Secondary Authorization                                          ││
│ │    Status: Awaiting approval                                        ││
│ │    Eligible approvers: admin2@org.uk, admin3@org.uk                 ││
│ │                                                                     ││
│ │    [Approve as Secondary] [Reject with Reason]                      ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ TIME DELAY                                                              │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Status: Not yet started (awaiting secondary approval)               ││
│ │ Configured delay: 48 hours                                          ││
│ │ User tier: Individual                                               ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ AUDIT TRAIL                                                             │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ 30 Nov 16:00 │ admin1@org.uk │ Primary approval granted            ││
│ │ 30 Nov 15:30 │ admin1@org.uk │ Video call completed                 ││
│ │ 30 Nov 15:00 │ admin1@org.uk │ Photo ID verified                    ││
│ │ 30 Nov 14:50 │ SYSTEM        │ Security questions answered (3/3)   ││
│ │ 30 Nov 14:45 │ s.jones@nhs.uk│ Photo ID uploaded                   ││
│ │ 30 Nov 14:30 │ s.jones@nhs.uk│ Recovery request submitted          ││
│ │ [Load More...]                                                      ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Identity Verification Review

**URL**: `/admin/recovery/<request_id>/verification/`

**Purpose**: Review submitted identity documents

#### Document Viewer

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Identity Document Review                                                │
│ Request: ABC-123-XYZ • User: Dr. Sarah Jones                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │                             │  │ VERIFICATION CHECKLIST          │  │
│  │    [Photo ID Image]         │  │                                 │  │
│  │                             │  │ □ Document is government-issued │  │
│  │    UK Driving Licence       │  │ □ Document is not expired       │  │
│  │                             │  │ □ Photo matches account holder  │  │
│  │    [Zoom] [Rotate]          │  │ □ Name matches account name     │  │
│  │                             │  │ □ No signs of tampering         │  │
│  └─────────────────────────────┘  │ □ Document is clearly legible   │  │
│                                    │                                 │  │
│  Submitted: 30 Nov 2025, 14:45    │ Notes:                          │  │
│  File: driving_licence.jpg         │ ┌─────────────────────────────┐ │  │
│  Size: 2.4 MB                      │ │                             │ │  │
│                                    │ │                             │ │  │
│                                    │ └─────────────────────────────┘ │  │
│                                    │                                 │  │
│                                    │ [Mark as Verified] [Request    │  │
│                                    │  New Document]    [Flag Issue] │  │
│                                    └─────────────────────────────────┘  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ ⚠️ SECURITY: Document images are encrypted at rest and automatically   │
│ deleted 30 days after request completion.                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4. Video Verification Interface

**URL**: `/admin/recovery/<request_id>/video-call/`

**Purpose**: Conduct or review video verification calls

#### Video Call Interface

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Video Verification Call                                                 │
│ Request: ABC-123-XYZ • User: Dr. Sarah Jones                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │                     [Video Call Window]                          │   │
│  │                                                                   │   │
│  │                    User's video feed here                        │   │
│  │                                                                   │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [🎤 Mute] [📹 Camera] [📱 Screen Share] [⏺️ Record] [📞 End Call]      │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ VERIFICATION CHECKLIST                                                  │
│                                                                         │
│ □ User's face matches photo ID                                         │
│ □ User can display photo ID on camera                                  │
│ □ User confirms they initiated the recovery request                    │
│ □ User can answer security questions verbally                          │
│ □ User confirms current employment (if applicable)                     │
│                                                                         │
│ Notes:                                                                  │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Type verification notes here...                                     ││
│ │                                                                     ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ [Complete Verification - PASS] [Complete Verification - FAIL]          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5. Dual Authorization Workflow

**URL**: `/admin/recovery/<request_id>/authorize/`

**Purpose**: Approve or reject recovery requests

#### Authorization Form

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Authorization Required                                                  │
│ Request: ABC-123-XYZ                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ You are authorizing as: SECONDARY APPROVER                             │
│                                                                         │
│ Primary approver: admin1@org.uk (30 Nov 2025, 16:00)                   │
│ Primary reason: "Identity verified via video call..."                   │
│                                                                         │
│ ⚠️ IMPORTANT: You must independently verify this request.              │
│ Do not rely solely on the primary approver's assessment.               │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ VERIFICATION SUMMARY                                                    │
│ ✅ Photo ID: UK Driving Licence (verified by admin1@org.uk)            │
│ ✅ Video Call: 12 minutes (conducted by admin1@org.uk)                  │
│ ✅ Security Questions: 3/3 correct                                      │
│                                                                         │
│ [Review Photo ID] [View Video Recording] [View Q&A]                    │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ YOUR DECISION                                                           │
│                                                                         │
│ ○ APPROVE - I have independently verified this request                 │
│ ○ REJECT - I have concerns about this request                          │
│                                                                         │
│ Reason (required):                                                      │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Enter your reason for approval or rejection...                      ││
│ │                                                                     ││
│ │                                                                     ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ □ I confirm I am not the primary approver                              │
│ □ I confirm I have reviewed the verification evidence                  │
│ □ I understand this action will be logged                              │
│                                                                         │
│                                          [Cancel] [Submit Decision]     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6. Time Delay Monitor

**URL**: `/admin/recovery/time-delays/`

**Purpose**: Monitor all requests in time delay period

#### Time Delay Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Time Delay Monitor                                          [Refresh]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Requests Currently in Time Delay: 3                                     │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Progress │ User              │ Survey           │ Time Remaining    ││
│ ├─────────────────────────────────────────────────────────────────────┤│
│ │ ████████░│ Dr. Emma Wilson   │ Research Study   │ 18h 45m          ││
│ │ █████░░░░│ Dr. James Smith   │ Clinic Survey    │ 32h 15m          ││
│ │ ██░░░░░░░│ Dr. Lisa Chen     │ Patient Records  │ 44h 30m          ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ READY FOR EXECUTION: 1                                                  │
READY FOR EXECUTION: 1
┌─────────────────────────────────────────────────────────────────────┐│
│ │ 🔵 Dr. Robert Taylor │ Annual Audit │ Time delay complete           ││
│ │    [View Details] [Show CLI Instructions]                          ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

> **Execution is CLI-only.** The web dashboard does not execute recovery.
> When a request is `Ready for Execution`, the detail page shows the
> `execute_platform_recovery` management command (with the request code
> pre-filled) for the operator to run on a secure terminal with 3 of 4
> custodian shares. See F6 in `docs/compliance/security-review-august-2026.md`.

### 7. Audit Trail Viewer

**URL**: `/admin/recovery/audit/`

**Purpose**: View complete audit trail across all requests

#### Audit Log View

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Audit Trail                                                [Export CSV] │
├─────────────────────────────────────────────────────────────────────────┤
│ Filters: [Date Range ▼] [Event Type ▼] [User ▼] [Admin ▼] [Search...]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ ┌───────────────────────────────────────────────────────────────────┐  │
│ │ Timestamp           │ Event                │ Actor    │ Details   │  │
│ ├───────────────────────────────────────────────────────────────────┤  │
│ │ 30 Nov 16:31:05    │ recovery_completed   │ admin1   │ ABC-123   │  │
│ │ 30 Nov 16:31:00    │ custodian_accessed   │ admin1   │ ABC-123   │  │
│ │ 30 Nov 16:30:00    │ time_delay_complete  │ SYSTEM   │ ABC-123   │  │
│ │ 28 Nov 16:30:00    │ time_delay_started   │ SYSTEM   │ ABC-123   │  │
│ │ 28 Nov 16:30:00    │ secondary_approval   │ admin2   │ ABC-123   │  │
│ │ 28 Nov 16:00:00    │ primary_approval     │ admin1   │ ABC-123   │  │
│ │ 28 Nov 15:30:00    │ video_call_complete  │ admin1   │ ABC-123   │  │
│ │ 28 Nov 15:00:00    │ photo_id_verified    │ admin1   │ ABC-123   │  │
│ │ 28 Nov 14:50:00    │ questions_answered   │ user     │ ABC-123   │  │
│ │ 28 Nov 14:45:00    │ photo_id_uploaded    │ user     │ ABC-123   │  │
│ │ 28 Nov 14:30:00    │ request_submitted    │ user     │ ABC-123   │  │
│ └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│ Showing 1-11 of 156 entries                    [Previous] [1] [2] [Next]│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8. Recovery Rate Monitor

**URL**: `/admin/recovery/monitoring/`

**Purpose**: Monitor recovery rates and detect anomalies

#### Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Recovery Rate Monitoring                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ CURRENT STATUS: ✅ NORMAL                                               │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Metric                    │ Current │ Threshold │ Status           ││
│ ├─────────────────────────────────────────────────────────────────────┤│
│ │ Requests (24h)            │ 2       │ ⚠️ 5 / 🔴 10 │ ✅ Normal      ││
│ │ Recovery Rate (%)         │ 0.3%    │ ⚠️ 1% / 🔴 2% │ ✅ Normal      ││
│ │ Failed Verifications (24h)│ 0       │ ⚠️ 3 / 🔴 5  │ ✅ Normal      ││
│ │ User Objections (30d)     │ 0       │ ⚠️ 1 / 🔴 2  │ ✅ Normal      ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ TREND (30 DAYS)                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Requests                                                            ││
│ │ 5│                                                                  ││
│ │ 4│                                           ▄                      ││
│ │ 3│          ▄                                █                      ││
│ │ 2│    ▄     █     ▄                    ▄     █                      ││
│ │ 1│ ▄  █  ▄  █  ▄  █  ▄     ▄  ▄  ▄     █  ▄  █  ▄                  ││
│ │ 0│ █  █  █  █  █  █  █  ░  █  █  █  ░  █  █  █  █  ░               ││
│ │   └────────────────────────────────────────────────────────────────││
│ │    1  5  10    15    20    25    30                                 ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ ALERTS                                                                  │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ No active alerts                                                    ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ [Configure Thresholds] [View Alert History] [Test Alert]               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9. SIEM Integration Status

**URL**: `/admin/recovery/siem/`

**Purpose**: Monitor SIEM connection and log forwarding

#### SIEM Status Panel

```
┌─────────────────────────────────────────────────────────────────────────┐
│ SIEM Integration Status                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ CONNECTION STATUS: ✅ CONNECTED                                         │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ SIEM Type:        Elasticsearch (self-hosted)                       ││
│ │ Endpoint:         https://elasticsearch.internal:9200               ││
│ │ Index Pattern:    checktick-audit-*                                 ││
│ │ Last Sync:        2 minutes ago                                     ││
│ │ Events Today:     1,234                                             ││
│ │ Queue Depth:      0 (real-time)                                     ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ RECENT SYNC HISTORY                                                     │
│ ┌─────────────────────────────────────────────────────────────────────┐│
│ │ Time            │ Events │ Status │ Latency                        ││
│ ├─────────────────────────────────────────────────────────────────────┤│
│ │ 14:28:00        │ 15     │ ✅     │ 45ms                            ││
│ │ 14:27:00        │ 8      │ ✅     │ 38ms                            ││
│ │ 14:26:00        │ 12     │ ✅     │ 52ms                            ││
│ │ 14:25:00        │ 6      │ ✅     │ 41ms                            ││
│ └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│ [Test Connection] [View Logs] [Configure]                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Models

### RecoveryRequest Model

```python
class RecoveryRequest(models.Model):
    """Model for tracking recovery requests."""

    STATUS_CHOICES = [
        ('pending_verification', 'Pending Identity Verification'),
        ('verification_in_progress', 'Identity Verification In Progress'),
        ('awaiting_primary', 'Awaiting Primary Authorization'),
        ('awaiting_secondary', 'Awaiting Secondary Authorization'),
        ('in_time_delay', 'In Time Delay Period'),
        ('ready_for_execution', 'Ready for Execution'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)

    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    verification_completed_at = models.DateTimeField(null=True)
    approved_at = models.DateTimeField(null=True)
    time_delay_until = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    # Authorization
    primary_approver = models.ForeignKey(User, related_name='primary_approvals', null=True)
    primary_approved_at = models.DateTimeField(null=True)
    primary_reason = models.TextField(null=True)

    secondary_approver = models.ForeignKey(User, related_name='secondary_approvals', null=True)
    secondary_approved_at = models.DateTimeField(null=True)
    secondary_reason = models.TextField(null=True)

    # Rejection/cancellation
    rejected_by = models.ForeignKey(User, related_name='rejections', null=True)
    rejected_at = models.DateTimeField(null=True)
    rejection_reason = models.TextField(null=True)

    cancelled_by = models.ForeignKey(User, related_name='cancellations', null=True)
    cancelled_at = models.DateTimeField(null=True)
    cancellation_reason = models.TextField(null=True)

    # Execution
    executed_by = models.ForeignKey(User, related_name='executions', null=True)
    custodian_component_used = models.BooleanField(default=False)


class IdentityVerification(models.Model):
    """Model for identity verification documents and results."""

    VERIFICATION_TYPES = [
        ('photo_id', 'Photo ID'),
        ('video_call', 'Video Verification Call'),
        ('security_questions', 'Security Questions'),
        ('employment_verification', 'Employment Verification'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    recovery_request = models.ForeignKey(RecoveryRequest, on_delete=models.CASCADE)
    verification_type = models.CharField(max_length=50, choices=VERIFICATION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    # Document storage (encrypted)
    document_path = models.CharField(max_length=500, null=True)

    # Verification details
    submitted_at = models.DateTimeField(null=True)
    verified_by = models.ForeignKey(User, null=True)
    verified_at = models.DateTimeField(null=True)
    verification_notes = models.TextField(null=True)

    # For security questions
    questions_asked = models.JSONField(null=True)
    correct_answers = models.IntegerField(null=True)
    total_questions = models.IntegerField(null=True)


class RecoveryAuditEntry(models.Model):
    """Immutable audit trail for recovery actions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recovery_request = models.ForeignKey(RecoveryRequest, on_delete=models.CASCADE)

    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20)

    actor_type = models.CharField(max_length=20)  # user, admin, system
    actor_id = models.IntegerField(null=True)
    actor_email = models.EmailField(null=True)
    actor_ip = models.GenericIPAddressField(null=True)

    details = models.JSONField()

    # Hash for tamper detection
    entry_hash = models.CharField(max_length=64)
    previous_hash = models.CharField(max_length=64, null=True)

    class Meta:
        ordering = ['-timestamp']
        # Prevent deletion
        managed = True
```

## API Endpoints

### Recovery Request Endpoints

```python
# GET /api/admin/recovery/
# List all recovery requests (filtered by user's scope)

# GET /api/admin/recovery/<request_id>/
# Get single recovery request details

# POST /api/admin/recovery/<request_id>/verify/
# Submit verification result (photo_id, video_call, etc.)

# POST /api/admin/recovery/<request_id>/authorize/
# Submit authorization decision (approve/reject)

# Note: There is no web/HTTP execution endpoint. Recovery is executed
# exclusively via the `execute_platform_recovery` management command on a
# secure terminal, which reconstructs the custodian component from 3 of 4
# Shamir shares supplied on the command line. See F6 in
# docs/compliance/security-review-august-2026.md.

# DELETE /api/admin/recovery/<request_id>/
# Cancel recovery request

# GET /api/admin/recovery/<request_id>/audit/
# Get audit trail for request

# GET /api/admin/recovery/monitoring/
# Get recovery rate monitoring data

# GET /api/admin/recovery/siem/status/
# Get SIEM integration status
```

## Security Considerations

### Recovered Key Scope

A completed recovery grants the survey **private key**, which allows decryption of all responses encrypted with the survey's public key (including demographics, which are encrypted inside the same response payload). Legacy symmetric-KEK-encrypted responses remain readable via the same recovery flows. All recovery actions are recorded in the immutable audit trail.

### Document Storage

- All identity documents encrypted at rest (AES-256-GCM)
- Documents stored in separate encrypted storage (not database)
- Automatic deletion 30 days after request completion
- Access logged to audit trail

### Video Call Recording

- Recording optional (configurable per organisation)
- If enabled, recordings encrypted and stored separately
- Automatic deletion 90 days after request completion
- Access requires explicit admin action + logging

### Session Security

- Admin sessions require MFA for recovery actions
- Session timeout: 15 minutes for recovery dashboard
- Re-authentication required for authorization decisions
- All actions logged with full context

### Rate Limiting

- Max 3 recovery requests per user per 30 days
- Max 10 authorization actions per admin per hour
- Automatic lockout after 5 failed verification attempts

## Implementation Checklist

- [ ] Recovery request model and migrations
- [ ] Identity verification model and migrations
- [ ] Audit entry model (append-only)
- [ ] Dashboard views (list, detail, verification, authorization)
- [ ] API endpoints
- [ ] Email notification integration
- [ ] SIEM forwarding
- [ ] Document storage service
- [ ] Video call integration (optional)
- [ ] Rate limiting middleware
- [ ] Admin permissions
- [ ] Unit tests
- [ ] Integration tests
- [ ] Security review

## Related Documentation

- [Key Management for Administrators](/docs/key-management-for-administrators/) - Admin procedures
- [Audit Logging and Notifications](/docs/audit-logging-and-notifications/) - Logging requirements
- [Vault Integration](/docs/vault/) - Developer API
- [Business Continuity](/docs/business-continuity/) - Disaster recovery
