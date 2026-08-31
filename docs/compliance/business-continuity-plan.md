---
title: "Business Continuity & Disaster Recovery Plan"
category: dspt-7-continuity
---

# Business Continuity & Disaster Recovery Plan

**Last Reviewed:** August 2026
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

* **Hosting Failure:** {{ platform_name }} will redeploy to secondary AWS regions if Northflank is unavailable. See [Vault Integration](/docs/vault/) for the full recovery procedure.
* **Data Corruption:** Daily RDS snapshots are restored. RPO is 24 hours.

#### Platform Key / Survey KEK Recovery

Surveys that use whole-response encryption (per the encryption predicate —
see [Encryption for Users](/docs/encryption-for-users/)) hold a per-survey
X25519 keypair: responses are encrypted at submission time with the public
key, and the private key is stored wrapped in the owner's key material
(password / recovery phrase / OIDC / organisation key). This applies to **all
encrypted surveys**, not only those collecting patient data.

If a user loses both their password and recovery phrase, and there is no
organisation or platform escrow, responses on keypair surveys are
cryptographically unrecoverable — the server can encrypt but cannot decrypt
without the owner's key material. Where platform key recovery is available,
it is a **split-knowledge** operation — no single administrator can perform it:

1. A recovery request is submitted and goes through **identity verification**
   (photo ID, video call, security questions).
2. **Dual authorization** by two different admins (primary + secondary).
3. A mandatory **time delay** (24h organisation / 48h individual) during
   which the user can cancel if they did not request it.
4. After the delay, a platform admin runs the
   `execute_platform_recovery` management command on a secure terminal,
   presenting **3 of 4 Shamir custodian shares**. The custodian component is
   reconstructed in memory only and never persisted.

The web Platform Recovery Console **does not execute recovery** — it only
routes the request through approval + time delay, then hands off to the CLI.
See [Key Management for Administrators](/docs/key-management-for-administrators/)
and F6 in `docs/compliance/security-review-august-2026.md`.

**Recoverability by survey type:**

* **Encrypted (keypair) surveys** — recoverable only via owner unlock or the
  split-knowledge platform recovery above; if the owner loses their password
  and recovery phrase and there is no organisation or platform escrow, the
  responses are unrecoverable.
* **Surveys with a recorded encryption opt-out** (staff-audience,
  password-user surveys where the creator declared an opt-out) — responses
  are stored in plaintext and remain recoverable by a database administrator.
* **Grandfathered legacy surveys** — pre-existing password-user, non-patient
  surveys were migrated with a recorded legacy opt-out declaration
  (audit-logged), so their existing plaintext responses stay readable without
  owner keys.

### 3.2 Manual Workarounds (Essential Service Continuity)

If the digital service is unavailable for >4 hours:

* **Clinician Action:** {{ platform_name }} will notify affected Trust leads.
* **Fallback:** Clinicians are advised to utilize their Trust's standard **Paper-Based Survey Continuity Process**.
* **Support:** {{ platform_name }} staff will provide PDF versions of survey templates via email to facilitate manual data collection where possible.

### 3.3 People & Resource Dependencies

* **Remote Operations:** {{ platform_name }} is a remote-first team. If a staff member’s local site (home office) fails (power/internet), they will relocate to a secondary site with 4G/5G backup.
* **Succession:** If the CTO is unavailable, the SIRO holds emergency "Break-Glass" credentials to the Northflank consoles to initiate infrastructure recovery with 3rd party support. Note: platform **key** recovery still requires 3 of 4 custodian shares — the SIRO's break-glass access covers infrastructure only, not single-party key decryption. See §3.1 above.

## 4. Communication Plan

In a "High" severity outage:

1. **Internal:** CTO alerts SIRO via Slack/Phone.
2. **Customers:** SIRO emails all registered 'Clinical Admins' at the Trusts within 2 hours.
3. **External:** Notify the ICO/DSPT if the outage involves a data breach (per Incident Response Plan).

## 5. Testing & Maintenance

* **Annually:** A full restoration drill (RDS snapshot to a fresh environment).
* **Quarterly:** Review of 'Emergency Contacts' and 'Unseal Key' locations.
