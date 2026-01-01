# Logging & Audit Policy

**Policy Owner:** [Name 2] (CTO) | **Review Date:** [Insert Date]

## 1. Scope

This policy covers the generation, protection, and retention of audit logs for all CheckTick systems processing NHS data.

## 2. Log Retention Schedule

CheckTick adopts a 'Retain by Default' posture. Logs are stored securely within our cloud infrastructure (hosting provider/AWS S3).

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
* **Access:** Only platform superusers (CTO/DPO) have access to the log review dashboard.
* **Availability:** Logs are backed up alongside our primary database to prevent loss during a system failure.

## 5. Review Procedure

* **Automated:** Sentry/Slack alerts for 'Level: Error' or 'Level: Critical' events.
* **Quarterly:** CTO and DPO review logs via the Platform Admin dashboard (`/platform-admin/logs/`) to:
  * Analyse 'Authentication Success/Fail' ratios for unusual patterns
  * Review critical and warning events
  * Verify no unauthorized access attempts
  * Document findings for DPST compliance
* **On-Demand:** Security events can be reviewed at any time through the dashboard with filtering by severity, action type, date range, and search.

## 6. Platform Admin Log Dashboard

The Platform Admin dashboard provides superuser-only access to:

* **Application Logs:** All `AuditLog` entries from the database including authentication events, 2FA actions, account changes, and survey access.
* **Infrastructure Logs:** Container/application logs from the hosting provider (if configured via `HOSTING_API_TOKEN`, `HOSTING_PROJECT_ID`, `HOSTING_SERVICE_ID`).

### Log Categories Tracked

| Category | Events Logged |
| :--- | :--- |
| **Authentication** | login_success, login_failed, logout, account_locked |
| **Two-Factor Auth** | 2fa_enabled, 2fa_disabled, 2fa_verified, 2fa_failed, backup_codes_generated, backup_code_used |
| **Account Changes** | password_changed, password_reset, email_changed, user_created, user_deactivated |
| **Data Access** | survey unlock, key recovery, data exports |

### Severity Levels

* **Critical:** Account locked, 2FA disabled, password changed, user deactivated, key recovery
* **Warning:** Login failed, 2FA failed
* **Info:** All other events

## 7. Hosting Provider Audit Logs

The Platform Admin Log Dashboard captures application and container logs, but does **not** capture hosting provider platform-level events. These must be reviewed separately via the hosting provider's dashboard.

### Events Not Captured in Platform Admin Dashboard

| Event Type | Where to Review | Why It Matters |
| :--- | :--- | :--- |
| Container console access (SSH/exec) | Hosting provider audit log | Tracks who accessed the container shell |
| Environment variable changes | Hosting provider audit log | Configuration and secrets modifications |
| Deployments and rollbacks | Hosting provider audit log | Code changes to production |
| Scaling and resource changes | Hosting provider audit log | Infrastructure modifications |
| Team member access changes | Hosting provider audit log | Who has platform access |

### Northflank Audit Log Location

For Northflank-hosted deployments:

1. Log in to [Northflank Dashboard](https://app.northflank.com)
2. Navigate to **Settings → Audit Log**
3. Review events for the relevant time period

### Quarterly Review Checklist

During quarterly CTO/DPO log reviews, check **both** sources:

- [ ] **Platform Admin Dashboard** (`/platform-admin/logs/`)
  - [ ] Application Logs: Review CRITICAL and WARNING events
  - [ ] Infrastructure Logs: Review ERROR-level container logs
- [ ] **Hosting Provider Audit Log** (e.g., Northflank Settings → Audit Log)
  - [ ] Container console access sessions
  - [ ] Environment variable modifications
  - [ ] Deployment activity
  - [ ] Team member access changes

Document findings from both sources for DPST evidence.
