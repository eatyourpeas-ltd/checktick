---
title: "Patch Management Strategy & Procedure"
category: dspt-8-unsupported-systems
---

# Patch Management Strategy & Procedure

**Owner:** CTO
**Reviewed:** January 2026

## 1. Patching Layers & Responsibility

| Layer | Responsible Party | Update Mechanism | Frequency |
| :--- | :--- | :--- | :--- |
| **Cloud Infrastructure** | AWS / Northflank | Automatic Vendor Managed | Immediate |
| **Base OS (Containers)** | {{ platform_name }} (CTO) | Rebuild of Docker/OCI images | Weekly or on Critical Alert |
| **Database (RDS)** | AWS / {{ platform_name }} | Managed 'Minor Version' Upgrades | Monthly Maintenance Window |
| **App Dependencies** | {{ platform_name }} (CTO) | Poetry / GitHub Dependabot | Daily Scans / Weekly PRs |

## 2. The Patching Lifecycle (Standard Procedure)

1. **Detection:** Vulnerabilities are detected via daily `pip-audit` runs in GitHub Actions or Dependabot alerts.
2. **Triage:** CTO assesses the CVSS score. **Critical** vulnerabilities (CVSS 9.0+) trigger an immediate emergency patch cycle.
3. **Staging:**
    * Dependencies are updated in `pyproject.toml` and `poetry.lock`.
    * The code is pushed to the `staging` branch.
    * **Automated Tests:** Full Pytest suite and Playwright end-to-end tests must pass (100% success rate required).
4. **Production Deployment:**
    * Once verified, the Pull Request is merged to `main`.
    * Northflank executes a 'Zero-Downtime' rolling deployment.
5. **Verification:** The CTO monitors production logs and Cloudflare analytics for 30 minutes post-deploy to ensure stability.

## 3. Emergency Patching ("Zero-Day" Response)

In the event of a high-severity zero-day vulnerability (e.g., in Django or Python-Jose), {{ platform_name }} will bypass the weekly schedule. The CTO will apply the patch or mitigating control (e.g., a WAF block) within **48 hours**, following the same Staging-to-Production testing flow to ensure clinical continuity.

## 4. Record Keeping

All security patches are recorded in the `compliance/vulnerability-patch-log.md` to maintain an audit trail for DSPT compliance.

## 5. Automated Housekeeping & Maintenance

In addition to software patching, {{ platform_name }} executes automated maintenance tasks to ensure the essential service remains secure and compliant.

| Task Name | Frequency | Purpose | Security/Compliance Link |
| :--- | :--- | :--- | :--- |
| `process_data_governance` | Daily | Auto-deletion of expired surveys | **GDPR Data Minimization** |
| `process_recovery_time_delays` | 5 Mins | Processes ethical key recovery | **Resilience & Business Continuity** |
| `sync_nhs_dd_datasets` | Weekly | Scrapes NHS Data Dictionary | **Clinical Data Accuracy** |
| `cleanup_survey_progress` | Daily | Purges stale session drafts (>30d) | **Storage Optimization / Security** |

### Monitoring & Failure Response

* **Logs:** All cron job outputs are captured in the Northflank 'Log Streams'.
* **Alerting:** Any task returning a non-zero exit code triggers an immediate 'Critical' alert to the CTO via the GitHub/Northflank integration.
* **Idempotency:** All maintenance commands are designed to be idempotent; if a task fails once, the subsequent run will safely resume the work.
