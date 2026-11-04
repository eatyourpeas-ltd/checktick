---
title: "Cloud Shared Responsibility Matrix"
category: dspt-10-suppliers
---

# Cloud Shared Responsibility Matrix

{{ platform_name }} uses this matrix to ensure clarity of accountability for our outsourced services (primarily managed Kubernetes on Civo).

| Security Layer | Responsible Party | Description |
| :--- | :--- | :--- |
| **Physical Security** | Civo | Security of the London (LON1) data centre, power, and hardware. |
| **Host Infrastructure**| Civo | Security and patching of the managed k3s node images and hypervisors. |
| **Network Boundary** | Joint | Civo manages the cluster edge; {{ platform_name }} configures Traefik ingress and Kubernetes NetworkPolicies. |
| **Application Code** | {{ platform_name }} | Security of the Django/Python code and dependencies. |
| **Identity & Access** | {{ platform_name }} | Management of staff accounts and MFA enforcement. |
| **Data Encryption** | {{ platform_name }} | Configuring SSL/TLS and database encryption-at-rest. |
| **Backups & Recovery** | Joint | Civo provides the Object Storage target; {{ platform_name }} defines the CNPG backup schedule and retention. |

## Verification

This matrix is reviewed annually alongside our Supplier Register to ensure no changes in service level agreements (SLAs) have altered these responsibilities.
