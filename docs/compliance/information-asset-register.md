---
title: "Information Asset Register"
category: dspt-1-confidential-data
---

# Information Asset Register (IAR)

**Owner:** {{ cto_name }} (SIRO)
**Last Review:** Jan 2026

| Asset ID | Asset Name | Description | Data Type | Location | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AS-01** | Production DB | PostgreSQL database for {{ platform_name }}. | Patient IDs, Survey Responses. | Civo Kubernetes - in-cluster CloudNativePG (London LON1) | CTO |
| **AS-02** | Auth Provider | Microsoft Entra ID / Google Auth. | Staff Credentials, Names. | Cloud (SaaS) | CTO |
| **AS-03** | Source Code | GitHub Repository. | Code, Config (No Secrets). | GitHub | CTO |
| **AS-04** | Email System | Personal Google accounts (custom domain) / Mailgun. | Business Communications. | Cloud (SaaS) | SIRO |
| **AS-05** | Local Devices | Laptops used by Founders/Directors. | Local Config, Temp Files. | Physical | User |
| **AS-06** | Staging Environment | Pre-production mirror at `staging.checktick.uk` (same Civo London cluster): separate web deployment + PostgreSQL database, shared encryption Vault. Disposable data, GoCardless sandbox, excluded from the OpenObserve production log stream. | Synthetic/test accounts and survey responses (no real patient data). | Civo Kubernetes - in-cluster CloudNativePG (London LON1) | CTO |

## Asset Classification

* **Public:** Marketing site, Public docs.
* **Internal:** Non-sensitive business docs.
* **Confidential:** Staff PII, Technical configs.
* **Highly Confidential:** Patient Data (Survey Responses).
