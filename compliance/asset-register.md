# Combined Information Asset & ROPA Register

**Version:** 1.1
**Last Reviewed & Approved by SIRO:** [Insert Date post-July 1, 2025]
**Approval Status:** Final

| Asset Name | Asset Type | Data Categories | Lawful Basis (GDPR) | Classification | Owner | Security Measures | Retention | Storage Location |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Survey Database** | Software | Health data, PII, Survey responses | Art 6(1)(b) & Art 9(2)(h) | **Highly Confidential** | [Name 1] | AES-256 Rest/Transit, RBAC | 6-24 months | Northflank (UK) |
| **Audit Logs** | Software | IP addresses, User IDs, Timestamps | Art 6(1)(f) Legit. Interest | **Confidential** | [Name 1] | Immutable Vault logs | 7 Years | Northflank / Vault |
| **Staff Laptops** | Hardware | Admin credentials, local temp files | Art 6(1)(b) Contract | **Confidential** | [Names 1 & 2] | Full Disk Encryption, MFA | Employment | Physical (UK) |
| **Secrets Vault** | Software | DB Keys, API Secrets, Recovery Keys | Art 6(1)(b) Contract | **Highly Confidential** | [Name 1] | Scoped access, MFA | Service Life | Northflank Secrets |
| **GitHub Repo** | Software | Source code, System docs | Art 6(1)(f) Legit. Interest | **Internal** | [Name 2] | MFA, No PII policy | Indefinite | GitHub Cloud |
| **Email/Support** | Software | User contact info, support queries | Art 6(1)(b) Contract | **Confidential** | [Name 2] | MFA, TLS Encryption | 2yrs post-close | Secure Mail Prov. |
| **GoCardless Portal** | Software (SaaS) | Banking / Payment info | Art 6(1)(b) | Confidential |	Dr Simon Chapman |	MFA | No local storage of banking data |	Payment Life |
