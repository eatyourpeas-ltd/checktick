---
title: "Access Audit Log"
category: dspt-4-managing-access
---

# Access Audit Log (Personnel & Infrastructure)

**Policy:** Comprehensive audit of all '{{ platform_name }}' staff accounts with access to NHS-related infrastructure.

## Audit Record: 29/12/2025

**Performed by:** {{ cto_name }} (SIRO)

| System | Account Found | Role | Status | Verified? |
| :--- | :--- | :--- | :--- | :--- |
| **Civo** | {{ cto_name }} | Admin/SIRO | Active | ✅ |
| **Civo** | {{ siro_name }} | Admin/CTO | Active | ✅ |
| **GitHub** | {{ cto_name }} | Owner | Active | ✅ |
| **GitHub** | {{ siro_name }} | Owner | Active | ✅ |
| **PostgreSQL** | `ct_prod_admin` | DB Admin | Active | ✅ (Rotated) |

### Audit Findings:

* **Leavers:** 0 staff departures in this period; no accounts required deactivation.
* **Inappropriate Access:** 0 instances of over-privileged access found.
* **MFA Check:** Confirmed MFA is active on 100% of administrative entry points.
* **Action Taken:** Rotated the primary database administration credentials as a proactive measure.

**Next Audit Due:** [Date + 3 Months]

## Appraisal Workflow Audited Events (Reference)

Appraisal events are written to the existing `AuditLog` model, using the `SURVEY` and `ORGANIZATION` scopes. Audit metadata never contains response content, exception review reasons, or decrypted data. Severities are as recorded by the application.

| Event | Scope | Action | Severity | Metadata Recorded |
| :--- | :--- | :--- | :--- | :--- |
| **Survey unlock (organisation key recovery)** | Survey | `key_recovery` | Critical | Recovery method, survey owner, actor's organisation role. |
| **Results view (survey summary)** | Survey | `update` | Info | Survey ID and slug, total responses, date range, encryption flag. |
| **Report release** | Survey | `create` | Info | Snapshot ID, version, total responses. |
| **Exception review raised** | Survey | `create` | Warning | Exception review ID, response ID. Reason text is not recorded. |
| **Exception review approved (rater linkage disclosed)** | Survey | `update` | Warning | Exception review ID. |
| **Exception review rejected** | Survey | `update` | Info | Exception review ID. |
| **Token batch generation** | Survey | `create` (proposed) | Info (proposed) | Token count and category dimensions. Token strings are never recorded. **Not yet emitted** at commit `18cea3ef`. |
| **Distributor membership changes** | Survey | `add` / `update` / `remove` | Info | Membership role. |
| **Appraisee survey created** | Survey | `create` | Info | Survey created from organisation instrument. |
| **Organisation master key generated** | Organisation | `create` | Info | Generated lazily when absent. |

### Open Items

* **Token batch generation:** No audit entry is currently written when token batches or QR codes are generated. An `AuditLog` entry is required before live appraisal use.
* **Linkage view:** Viewing an approved rater linkage is not separately logged. The disclosure itself is recorded at approval (Warning).
