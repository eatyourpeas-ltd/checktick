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
| **Northflank** | {{ cto_name }} | Admin/SIRO | Active | ✅ |
| **Northflank** | {{ siro_name }} | Admin/CTO | Active | ✅ |
| **GitHub** | {{ cto_name }} | Owner | Active | ✅ |
| **GitHub** | {{ siro_name }} | Owner | Active | ✅ |
| **PostgreSQL** | `ct_prod_admin` | DB Admin | Active | ✅ (Rotated) |

### Audit Findings:

* **Leavers:** 0 staff departures in this period; no accounts required deactivation.
* **Inappropriate Access:** 0 instances of over-privileged access found.
* **MFA Check:** Confirmed MFA is active on 100% of administrative entry points.
* **Action Taken:** Rotated the primary database administration credentials as a proactive measure.

**Next Audit Due:** [Date + 3 Months]
