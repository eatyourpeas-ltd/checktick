---
title: "Backup & Data Retention Policy"
category: dspt-7-continuity
---

# Backup & Data Retention Policy

**Version:** 3.1 (Revised for DSPT 7.2.1)
**Last Reviewed:** November 2026
**Owner:** CTO

## 1. Scope & Strategy

This policy covers all infrastructure used for the development, hosting, and
operation of {{ platform_name }} services provided to health and care providers.
All infrastructure is hosted on managed Kubernetes (Civo, UK London LON1 region).
Our backup strategy uses the CloudNativePG operator's scheduled base backups
and continuous WAL archiving to Civo Object Storage (UK region), with a defined
retention period.

## 2. Backup Schedule & Scope

{{ platform_name }} ensures all critical clinical and configuration data is backed
up automatically:

* **Database (PostgreSQL 17 — in-cluster via CloudNativePG):** Nightly scheduled
  base backups (02:00 UTC) plus continuous WAL archiving to Civo Object Storage
  (UK region), with a 120-day retention period. Backups are stored in an object
  storage bucket separate from the live cluster.
* **Encryption Vault (HashiCorp Vault — in-cluster StatefulSet, integrated
  Raft storage):** Nightly automated raft snapshots (03:45 UTC) taken while
  the Vault is unsealed, via a least-privilege AppRole — no unseal keys
  ever touch a scheduled job. Each snapshot is encrypted with an
  operator-held age key BEFORE upload to Civo Object Storage (UK region,
  14-snapshot retention): the stored object is useless without BOTH the
  3-of-4 Shamir unseal shares AND the operator's age private key (held
  offline). Vault unseal keys and custodian shares are stored offline by
  named administrators independently of the hosting environment.
* **Source Code & Configuration:** Version-controlled in GitHub, providing
  globally redundant, immutable history of all application code and
  infrastructure configuration.

Note: Backup frequency and retention will be reviewed prior to any significant
change in data volume or clinical deployment scope.

## 3. Restoration Hierarchy (Order of Operations)

In the event of a total system failure, systems must be restored in the following
specific order to maintain the cryptographic security chain:

1. **Identity & Access:** Restore MFA-protected admin access to the Civo
   dashboard and GitHub organisation.
2. **Encryption Vault:** Restore the Vault service from the most recent storage
   backup and unseal using the Shamir recovery keys held by named
   administrators. Critical: survey data cannot be decrypted without this step.
3. **Core Database:** Restore the most recent base backup and WAL archive from
   Civo Object Storage into a fresh CloudNativePG cluster.
4. **Application Tier:** Redeploy application containers to the Kubernetes
   cluster using the latest verified image from GitHub.
5. **Connectivity:** Verify Cloudflare DNS routing and confirm the platform
   is reachable and responding correctly.

## 4. Security of Backups

* **Encryption:** All backups in Civo Object Storage are encrypted at rest.
  Vault snapshots are doubly protected — barrier-encrypted by Vault, then
  age-encrypted with an operator-held key before upload — and contain only
  encrypted key material: the custodian component required to reconstruct
  the platform master key is stored offline and is never present in the
  hosting environment.
* **Access:** Access to restore backups is restricted to named administrators
  (CTO and SIRO) via MFA-protected Civo accounts. No application
  service account has permission to delete or modify backups.
* **Isolation:** The backup object store is logically isolated from the
  production service environment, with dedicated scoped credentials. Application
  service accounts operate under least-privilege and have no access to the
  backup layer beyond write-only WAL/base-backup uploads.
* **Source code independence:** GitHub provides an additional independent copy
  of all application and infrastructure configuration, ensuring recovery is
  possible even in the event of a complete Civo account loss.

## 5. Restoration Testing

We perform restoration tests to verify that backups are recoverable and data
integrity is maintained:

* **Frequency:** Prior to live clinical deployment, a full restoration test
  will be completed and documented. Thereafter, tests will be conducted
  quarterly (January, April, July, October).
* **Procedure:** The CTO restores the most recent nightly base backup and WAL
  archive from Civo Object Storage into a scratch CloudNativePG cluster, then
  verifies exact per-table row counts against production and that the
  application schema is current (`migrate --check`). The step-by-step
  procedure is documented in [Quarterly Restore Rehearsal](../restore-rehearsal.md).
* **Success Criteria:** Restored cluster healthy, exact count match on every
  public table, and no pending migrations.
* **Audit:** Results are documented in the Backup Restoration Test Log.

## 6. Routine Review

This policy is reviewed annually or following any significant change to our
hosting provider or data architecture. The backup schedule and retention period
will be reviewed and updated prior to live clinical deployment.
