---
title: "IP Address Management (IPAM) Register"
category: dspt-4-managing-access
---

# IP Address Management (IPAM) Register

**Last Reviewed:** 03/01/2026
**Owner:** CTO

## 1. Production Infrastructure (Northflank UK)

| Asset | Type | IP Address / Range | Purpose |
| :--- | :--- | :--- | :--- |
| **Web Production** | Ingress | [Insert Northflank IP] | Public access to {{ platform_name }} |
| **Worker Egress** | Egress | [Insert Static IP] | Outbound requests to OIDC/Mail |
| **Database** | Internal | 10.x.x.x (VPC) | Private internal communication |

## 2. Administrative Access (Founders)

| Asset | Type | Range / Description | Security Control |
| :--- | :--- | :--- | :--- |
| **Founder 1 Home** | Static/Dynamic | [Insert Range] | Allowed for GH/NF Admin |
| **Founder 2 Home** | Static/Dynamic | [Insert Range] | Allowed for GH/NF Admin |

## 3. Review Process

* **Quarterly Audit:** The CTO verifies that only these recorded IPs have administrative access to the Northflank console.
* **Decommissioning:** When a founder changes location or ISP, the old IP range is removed from the "Allow-List" within 24 hours.
