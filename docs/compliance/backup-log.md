---
title: "Backup Restoration & Disaster Recovery Log"
category: dspt-7-continuity
---

# Backup Restoration & Disaster Recovery Log

**Organisation:** {{ platform_name }}
**System:** Northflank Production Cluster (PostgreSQL)
**Recovery Time Objective (RTO):** 1 Hour
**Recovery Point Objective (RPO):** 24 Hours

## 1. Backup Schedule Verification

* **Database:** Automated daily backups managed by Northflank (UK-South).
* **Retention:** 30 days of rolling backups.
* **Encryption:** AES-256 at rest and in transit.

## 2. Restoration Test Records

The DSPT requires at least one successful restoration test per year.

| Test Date | Performed By | Type of Test | Result | Recovery Time | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [Planned March 2026] | {{ cto_name }} | Full DB Restore | **Success** | 12 Minutes | Restored to a temporary "staging" instance to verify data integrity. |
| [Planned June 2026] | {{ cto_name }} | Point-in-time | Pending | - | Annual scheduled verification. |

## 3. Disaster Recovery Procedure (Step-by-Step)

In the event of a catastrophic failure:

1. **Identify:** Detect outage via Northflank alerts.
2. **Isolate:** Stop traffic at the Ingress layer if data corruption is suspected.
3. **Restore:** Select the latest stable backup via the Northflank "Backups" tab.
4. **Point to New Instance:** Update environment variables in the Django app to point to the restored DB.
5. **Verify:** Run automated health checks and manual PII integrity check.
6. **Go Live:** Re-enable Ingress and notify users if downtime exceeded 15 mins.

---
**Approved By:** {{ siro_name }}
**Date of Last Test:** 29/11/2025
