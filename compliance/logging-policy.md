# Logging & Audit Policy

**Policy Owner:** [Name 2] (CTO) | **Review Date:** [Insert Date]

## 1. Scope

This policy covers the generation, protection, and retention of audit logs for all CheckTick systems processing NHS data.

## 2. Log Retention Schedule

CheckTick adopts a 'Retain by Default' posture. Logs are stored securely within our cloud infrastructure (Northflank/AWS S3).

| Log Type | Minimum Retention | Purpose |
| :--- | :--- | :--- |
| **Authentication Logs** | 12 Months | To trace account compromises or brute-force attempts. |
| **Application Audit** | 12 Months | To track changes to patient data or survey logic. |
| **Network Ingress** | 12 Months | To identify source IPs and potential DDoS/SQLi patterns. |
| **System Errors** | 6 Months | To monitor for stability and potential exploit attempts. |

## 3. Traceability (End-to-End)

To satisfy NCSC guidelines, every logged event must contain:

* **Timestamp:** Synchronized via NTP to UTC.
* **Identity:** The User ID or Service Account involved.
* **Source:** The originating IP address (X-Forwarded-For headers are preserved).
* **Outcome:** Success or failure of the requested action.

## 4. Protection of Logs

* **Integrity:** Logs are stored in a read-only format for standard users.
* **Access:** Only the CTO has administrative access to raw log files.
* **Availability:** Logs are backed up alongside our primary database to prevent loss during a system failure.

## 5. Review Procedure

* **Automated:** Sentry/Slack alerts for 'Level: Error' or 'Level: Critical' events.
* **Manual:** Monthly review of 'Authentication Success/Fail' ratios to identify unusual patterns.
