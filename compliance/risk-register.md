# Data Security & Protection Risk Register

**Owner:** [Name 1] (SIRO) | **Reviewed:** [Monthly]

## Risk Scoring Matrix

* **Likelihood:** 1 (Rare) to 5 (Almost Certain)
* **Impact:** 1 (Negligible) to 5 (Catastrophic)
* **Total Risk:** Likelihood x Impact

| ID | Risk Description | Category | L | I | Total | Mitigation Strategy | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R01** | Unauthorized DB Access | Security | 2 | 5 | **10** | AES-256-GCM encryption; MFA for all admins; Private VPC. | [Name 2] |
| **R02** | Supply Chain: Northflank Outage | Availability | 2 | 4 | **8** | Daily off-site backups; BCDR plan tested annually. | [Name 2] |
| **R03** | Supply Chain: GitHub/Code Breach | Integrity | 1 | 4 | **4** | Mandatory GPG signed commits; MFA; Branch protection. | [Name 2] |
| **R04** | Insider Threat (Staff Error) | Security | 2 | 3 | **6** | Annual NHS Training; Least Privilege access; Audit logs. | [Name 1] |
| **R05** | Loss of Staff Laptop | Physical | 2 | 3 | **6** | Full Disk Encryption; Remote wipe capability; No local DB. | [Name 2] |
| **R06** | Supply Chain: GoCardless Breach | Financial | 1 | 3 | **3** | No banking data stored locally; Rely on provider PCI-DSS. | [Name 1] |

## Risk Review Frequency

This register is a live document. It is reviewed:

1. **Monthly:** At Founders' Board meetings.
2. **Ad-hoc:** Following any security incident or major infrastructure change.
3. **Annually:** As part of the DSPT submission process.
