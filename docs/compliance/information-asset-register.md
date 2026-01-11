---
title: "Information Asset Register"
category: dspt-1-confidential-data
---

# Information Asset Register (IAR)

**Owner:** {{ cto_name }} (SIRO)
**Last Review:** Jan 2026

| Asset ID | Asset Name | Description | Data Type | Location | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AS-01** | Production DB | PostgreSQL database for {{ platform_name }}. | Patient IDs, Survey Responses. | AWS (London) | CTO |
| **AS-02** | Auth Provider | Microsoft Entra ID / Google Auth. | Staff Credentials, Names. | Cloud (SaaS) | CTO |
| **AS-03** | Source Code | GitHub Repository. | Code, Config (No Secrets). | GitHub | CTO |
| **AS-04** | Email System | Google Workspace / Mailgun. | Business Communications. | Cloud (SaaS) | SIRO |
| **AS-05** | Local Devices | Laptops used by Founders/Directors. | Local Config, Temp Files. | Physical | User |

## Asset Classification

* **Public:** Marketing site, Public docs.
* **Internal:** Non-sensitive business docs.
* **Confidential:** Staff PII, Technical configs.
* **Highly Confidential:** Patient Data (Survey Responses).
