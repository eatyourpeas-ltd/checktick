---
title: "Backup & Data Retention Policy"
category: dspt-7-continuity
---

# Backup & Data Retention Policy

**Version:** 3.0 (Revised for DSPT 7.2.1)
**Last Reviewed:** March 2026
**Owner:** CTO

## 1. Scope & Strategy

This policy covers all infrastructure used for the development, hosting, and
operation of {{ platform_name }} services provided to health and care providers.
All infrastructure is hosted on Northflank, a SOC 2 Type II compliant Platform-
as-a-Service provider. Our backup strategy relies on Northflank's native automated
snapshot capability with defined retention periods.

## 2. Backup Schedule & Scope

{{ platform_name }} ensures all critical clinical and configuration data is backed
up automatically:

* **Database (PostgreSQL — Northflank Managed Addon):** Automated daily snapshots
  managed by Northflank with a 120-day retention period. Snapshots are stored
  within Northflank's isolated backup infrastructure, separate from the live
  service environment.
* **Encryption Vault (HashiCorp Vault — Northflank Service):** Daily snapshots
  of the Vault persistent volume via Northflank's volume backup capability.
  Vault unseal keys and custodian shares are stored offline by named administrators
  independently of the Northflank environment.
* **Source Code & Configuration:** Version-controlled in GitHub, providing
  globally redundant, immutable history of all application code and
  infrastructure configuration.

Note: Backup frequency and retention will be reviewed prior to any significant
change in data volume or clinical deployment scope.

## 3. Restoration Hierarchy (Order of Operations)

In the event of a total system failure, systems must be restored in the following
specific order to maintain the cryptographic security chain:

1. **Identity & Access:** Restore MFA-protected admin access to the Northflank
   console and GitHub organisation.
2. **Encryption Vault:** Restore the Vault service from the most recent Northflank
   volume snapshot and unseal using the Shamir recovery keys held by named
   administrators. Critical: survey data cannot be decrypted without this step.
3. **Core Database:** Restore the most recent PostgreSQL snapshot via the
   Northflank addon restore interface.
4. **Application Tier:** Redeploy application containers via Northflank using
   the latest verified image from GitHub.
5. **Connectivity:** Verify Cloudflare DNS routing and confirm the platform
   is reachable and responding correctly.

## 4. Security of Backups

* **Encryption:** All Northflank-managed backups are encrypted at rest.
  Vault persistent volume backups contain only encrypted key material —
  the custodian component required to reconstruct the platform master key
  is stored offline and is never present in the Northflank environment.
* **Access:** Access to restore backups is restricted to named administrators
  (CTO and SIRO) via MFA-protected Northflank accounts. No application
  service account has permission to delete or modify snapshots.
* **Isolation:** Northflank snapshot storage is logically isolated from the
  production service environment. Application service accounts operate under
  least-privilege and have no access to the backup layer.
* **Source code independence:** GitHub provides an additional independent copy
  of all application and infrastructure configuration, ensuring recovery is
  possible even in the event of a complete Northflank account loss.

## 5. Restoration Testing

We perform restoration tests to verify that backups are recoverable and data
integrity is maintained:

* **Frequency:** Prior to live clinical deployment, a full restoration test
  will be completed and documented. Thereafter, tests will be conducted
  quarterly (January, April, July, October).
* **Procedure:** The CTO restores the most recent PostgreSQL snapshot and
  Vault volume backup into a staging environment and verifies that the
  application boots, connects to the restored database, and successfully
  decrypts a sample test record using the recovered Vault keys.
* **Success Criteria:** Full application boot, successful database connection,
  and confirmed decryption of a test record.
* **Audit:** Results are documented in the Backup Restoration Test Log.

## 6. Routine Review

This policy is reviewed annually or following any significant change to our
hosting provider or data architecture. The backup schedule and retention period
will be reviewed and updated prior to live clinical deployment.
