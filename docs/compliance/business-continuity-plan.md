---
title: "Business Continuity & Disaster Recovery Plan"
category: dspt-7-continuity
---

# Business Continuity & Disaster Recovery Plan

**Last Reviewed:** January 2026
**Version:** 1.0 (DSPT Compliant)
**Owners:** CTO & SIRO

## 1. Scope & Purpose

This plan ensures that {{ platform_name }} can continue to support clinical workflows during a data security incident or technical failure. It prioritizes **Clinical Safety** and **Data Integrity**.

## 2. Business Impact Analysis (BIA)

| Critical Activity | Recovery Time Objective (RTO) | Dependency |
| :--- | :--- | :--- |
| Patient Survey Intake | 4 Hours | Northflank/Database |
| Clinician Data Access | 4 Hours | Encryption Vault/SSO |
| New Account Creation | 24 Hours | Admin Portal |

## 3. Continuity Strategies

### 3.1 Technical Recovery (SaaS Infrastructure)

* **Hosting Failure:** See [Technical Guide: Vault Recovery Section]. {{ platform_name }} will redeploy to secondary AWS regions if Northflank is unavailable.
* **Data Corruption:** Daily RDS snapshots are restored. RPO is 24 hours.

### 3.2 Manual Workarounds (Essential Service Continuity)

If the digital service is unavailable for >4 hours:

* **Clinician Action:** {{ platform_name }} will notify affected Trust leads.
* **Fallback:** Clinicians are advised to utilize their Trust's standard **Paper-Based Survey Continuity Process**.
* **Support:** {{ platform_name }} staff will provide PDF versions of survey templates via email to facilitate manual data collection where possible.

### 3.3 People & Resource Dependencies

* **Remote Operations:** {{ platform_name }} is a remote-first team. If a staff member’s local site (home office) fails (power/internet), they will relocate to a secondary site with 4G/5G backup.
* **Succession:** If the CTO is unavailable, the SIRO holds emergency "Break-Glass" credentials to the Northflank/AWS consoles to initiate recovery with 3rd party support.

## 4. Communication Plan

In a "High" severity outage:

1. **Internal:** CTO alerts SIRO via Slack/Phone.
2. **Customers:** SIRO emails all registered 'Clinical Admins' at the Trusts within 2 hours.
3. **External:** Notify the ICO/DSPT if the outage involves a data breach (per Incident Response Plan).

## 5. Testing & Maintenance

* **Annually:** A full restoration drill (RDS snapshot to a fresh environment).
* **Quarterly:** Review of 'Emergency Contacts' and 'Unseal Key' locations.
