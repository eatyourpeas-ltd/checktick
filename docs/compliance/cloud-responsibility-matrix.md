---
title: "Cloud Shared Responsibility Matrix"
category: dspt-10-suppliers
---

# Cloud Shared Responsibility Matrix

{{ platform_name }} uses this matrix to ensure clarity of accountability for our outsourced services (primarily Northflank/PaaS).

| Security Layer | Responsible Party | Description |
| :--- | :--- | :--- |
| **Physical Security** | Northflank / GCP | Security of data centers, power, and hardware. |
| **Host Infrastructure**| Northflank | Security of the OS/Hypervisor running the containers. |
| **Network Boundary** | Joint | Northflank provides the firewall; {{ platform_name }} configures the rules. |
| **Application Code** | {{ platform_name }} | Security of the Django/Python code and dependencies. |
| **Identity & Access** | {{ platform_name }} | Management of staff accounts and MFA enforcement. |
| **Data Encryption** | {{ platform_name }} | Configuring SSL/TLS and database encryption-at-rest. |
| **Backups & Recovery** | Joint | Northflank provides the tool; {{ platform_name }} defines the schedule. |

## Verification

This matrix is reviewed annually alongside our Supplier Register to ensure no changes in service level agreements (SLAs) have altered these responsibilities.
