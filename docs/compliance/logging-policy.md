---
title: "Logging & Audit Policy"
category: dspt-9-it-protection
---

# Logging & Audit Policy

**Policy Owner:** {{ cto_name }} (CTO) | **Review Date:** [Insert Date]

---

## 1. Scope

This policy defines the generation, storage, retention, and review of logs within {{ platform_name }} systems that process NHS-related data.

It distinguishes between:

- **Application logs (operational & infrastructure logging)**
- **Audit logs (security and compliance events stored in the database)**

These two systems serve different purposes and have different retention and governance requirements.

---

## 2. Logging Architecture Overview

{{ platform_name }} uses a **dual-layer logging model**:

### 2.1 Operational Logs (Infrastructure / Observability)

- Emitted as **structured JSON to stdout**
- Captured by the hosting platform (e.g. Northflank / Azure / AWS)
- Optionally forwarded to external log systems (e.g. OpenObserve)
- Used for:
  - System debugging
  - Performance monitoring
  - Infrastructure diagnostics
  - Error tracking

These logs are **ephemeral unless explicitly stored by the hosting platform or log aggregator**.

---

### 2.2 Audit Logs (Security & Compliance)

A separate persistent audit trail is stored in the application database using the `AuditLog` model.

These logs are:

- Stored in **PostgreSQL**
- Immutable once written (append-only pattern)
- Used for:
  - Security auditing
  - Compliance reporting
  - Access tracking
  - Governance review

They represent the **system of record for security-relevant events**.

---

## 3. Log Retention Schedule

### 3.1 Operational Logs

Retention is determined by the hosting or log aggregation platform.

| Log Type | Minimum Retention | Purpose |
| :--- | :--- | :--- |
| Application Logs | 6–12 months (platform dependent) | Debugging and system monitoring |
| Infrastructure Logs | 6–12 months (platform dependent) | System health and performance monitoring |

---

### 3.2 Audit Logs (Database)

Audit logs stored in PostgreSQL are retained for:

| Log Type | Minimum Retention | Purpose |
| :--- | :--- | :--- |
| Security Audit Logs | 12 Months | Authentication, access control, and security events |
| Data Governance Logs | 12 Months | Data export, retention, and deletion tracking |

---

## 4. Audit Log Model (System of Record)

Audit logs are implemented using the `AuditLog` model and represent the authoritative compliance record.

### 4.1 Scope Classification

Audit events are categorised as:

- **Security**
  - Authentication events
  - Password changes
  - 2FA changes
  - Account locking

- **Account**
  - User creation and deletion
  - Profile changes

- **Data Governance**
  - Data exports
  - Retention actions
  - Key recovery

- **Organisation / Survey**
  - Structural and administrative changes

---

### 4.2 Data Captured

Each audit log entry includes:

- Actor (user performing the action)
- Target user (if applicable)
- Action type (e.g. login_success, password_changed)
- Severity (INFO, WARNING, CRITICAL)
- IP address
- User agent
- Metadata (structured JSON context)
- Timestamp (auto-generated)

---

### 4.3 Immutability

Audit logs are:

- Append-only
- Not modified after creation
- Not deleted except under explicit legal retention processes

This ensures forensic integrity.

---

## 5. Traceability Requirements

To satisfy NCSC and NHS-aligned requirements, both operational and audit logs must support traceability.

### 5.1 Operational Logs

Each event should include:

- Timestamp (UTC, NTP synchronised)
- Request ID / Correlation ID
- User ID (if applicable)
- Source IP address
- Service/component name
- Environment (production/staging)

---

### 5.2 Audit Logs

Audit logs MUST include:

- Actor identity (or system actor)
- Action performed
- Timestamp
- IP address (where available)
- Outcome (implicit via action type)
- Severity classification

---

## 6. Protection of Logs

### 6.1 Operational Logs

- Stored in hosting platform logging system or external aggregator
- Access restricted to platform administrators
- May include transient system diagnostics

### 6.2 Audit Logs

- Stored in PostgreSQL with restricted access
- Accessible only to authorised administrative roles (CTO/DPO)
- Treated as compliance evidence
- Included in governance reviews

---

## 7. Patient Data Handling

{{ platform_name }} is designed to ensure that:

### 7.1 Operational Logs

- Patient-identifiable data is **not intentionally logged**
- Sensitive payloads are protected via:
  - encryption at application level
  - redaction filters in logging pipeline
- Logs are considered **non-primary storage and not a data store**

### 7.2 Audit Logs

- Do not contain raw patient survey responses
- May contain metadata identifiers (e.g. survey IDs, organisation IDs)
- Do not contain decrypted sensitive health data

> The system is designed such that patient-identifiable information is not logged under normal operation. Logging safeguards and redaction filters provide an additional defensive layer.

---

## 8. Severity Levels

### Operational Logs

- ERROR: System failures requiring attention
- WARNING: Degraded or unexpected behaviour
- INFO: Normal operational events

### Audit Logs

- CRITICAL: Security-impacting actions (account lock, password change, key recovery)
- WARNING: Suspicious or failed authentication events
- INFO: Standard system and administrative actions

---

## 9. Review Procedures

### 9.1 Operational Logs

- Reviewed via hosting platform dashboards or log aggregator
- Used for:
  - debugging incidents
  - monitoring system health
  - investigating failures

### 9.2 Audit Logs (Database)

Reviewed quarterly by CTO/DPO:

- Authentication success/failure trends
- Security events (critical/warning)
- Data export activity
- Account changes and administrative actions

---

## 10. Hosting Provider Audit Logs

Platform-level logs (outside application scope) include:

- Deployment events
- Environment variable changes
- Container access sessions
- Infrastructure scaling actions

These are reviewed separately in the hosting provider dashboard (e.g. Northflank).

---

## 11. Separation of Concerns Summary

| Layer | Storage | Purpose | Retention |
| :--- | :--- | :--- | :--- |
| Operational Logs | Stdout → platform/log aggregator | Debugging & observability | Platform-defined |
| Audit Logs | PostgreSQL (`AuditLog` model) | Security & compliance | 12 months minimum |
| Hosting Logs | Provider dashboard | Infrastructure governance | Provider-defined |

---

## 12. Quarterly Compliance Review Checklist

- [ ] Audit logs reviewed (security + governance events)
- [ ] Authentication anomalies assessed
- [ ] Data export events reviewed
- [ ] Hosting provider audit logs reviewed
- [ ] Retention policies validated
- [ ] Logging redaction rules reviewed
- [ ] No patient data observed in logs

---

## 13. Key Principle

> Operational logs help us run the system.
> Audit logs prove what happened.

Both are required, but they serve fundamentally different compliance and engineering purposes.
