---
title: "Backup & Data Retention Policy"
category: dspt-7-continuity
---

# Backup & Data Retention Policy

**Version:** 2.0 (Unified for DSPT 7.2.1)
**Last Reviewed:** January 2026
**Owner:** CTO

## 1. Scope & Strategy

This policy covers all infrastructure used for the development, hosting, and operation of {{ platform_name }} services provided to health and care providers. Our strategy relies on automated, encrypted snapshots with geographic redundancy.

## 2. Backup Schedule & Scope

{{ platform_name }} ensures all critical clinical and configuration data is backed up automatically:

* **Database (PostgreSQL/RDS):** Automated daily snapshots with a 30-day retention period. Point-in-time recovery (PITR) is enabled.
* **Encryption Vault:** Daily backups of Vault storage to a separate, encrypted S3 bucket.
* **Source Code & Config:** Version-controlled in GitHub (Global Redundancy) with daily local clones maintained by the CTO to ensure development continuity.

## 3. Restoration Hierarchy (Order of Operations)

In the event of a total system failure, systems must be restored in the following specific order to maintain the security chain:

1. **Identity & Access:** Restore SSO and admin access to cloud consoles (AWS/Northflank).
2. **Encryption Vault:** Restore the Vault service and unseal using recovery keys. (Critical: Data cannot be decrypted without this layer).
3. **Core Database:** Restore the most recent RDS snapshot.
4. **Application Tier:** Redeploy containers via Northflank using the latest verified GitHub image.
5. **Connectivity:** Re-enable Cloudflare WAF and DNS routing.

## 4. Security of Backups

* **Encryption:** All backups are encrypted at rest using AES-256 (via AWS KMS).
* **Access:** Access to restore backups is restricted to the CTO and requires Multi-Factor Authentication (MFA).
* **Isolation:** Backups are stored in a physically separate AWS Availability Zone from the production environment to protect against localized data center failure.

## 5. Restoration Testing (NHS Compliance)

We perform quarterly restoration tests to prove our backups are suitable for recovery:

* **Frequency:** Quarterly (Jan, April, July, Oct).
* **Procedure:** The CTO restores the most recent production snapshot into a 'Staging' environment to verify data integrity.
* **Success Criteria:** The application must successfully boot, connect to the restored database, and decrypt a sample test record using the recovered Vault keys.
* **Audit:** Results are documented in the `compliance/restoration-test-log.csv`.

## 6. Routine Review

This policy is reviewed annually or following any significant change to our hosting provider or data architecture.
