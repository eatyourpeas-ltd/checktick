---
title: "Business Impact Analysis"
category: dspt-7-continuity
---

# Business Impact Analysis (BIA)

**Policy Lead:** {{ cto_name }} (SIRO)
**Technical Lead:** {{ siro_name }} (CTO)
**Scope:** {{ platform_name }} Managed SaaS Platform

## 1. Service Prioritization

| Service Component | Criticality | RTO (Max Downtime) | RPO (Max Data Loss) |
| :--- | :--- | :--- | :--- |
| **Data Decryption (Vault)** | **Critical** | 1 Hour | 0 (Keys are immutable) |
| **Survey Submission** | **High** | 4 Hours | 0 (Real-time sync) |
| **Audit Logging** | **High** | 1 Hour | 0 (Local queuing) |
| **Admin Dashboard** | **Medium** | 12 Hours | 24 Hours |

## 2. Impact Assessment

* **Clinical Safety:** Prolonged unavailability of Vault keys prevents clinicians from viewing patient results.
* **Compliance:** Failure to recover Audit Logs within 1 hour violates our DSPT accountability commitments.
