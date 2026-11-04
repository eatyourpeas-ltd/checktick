---
title: "Backup Isolation & Immutability Procedure"
category: dspt-7-continuity
---

# Backup Isolation & Immutability Procedure

**Last Reviewed:** March 2026
**Owner:** CTO

## 1. Protection Against Ransomware and Accidental Deletion

{{ platform_name }} employs logical isolation to ensure that a compromise of
production application services cannot result in the deletion or corruption
of backups.

* **Backup Isolation:** Database backups are managed by the CloudNativePG
  operator and stored in a dedicated Civo Object Storage bucket with its own
  scoped credentials. Application service accounts operate
  under least-privilege principles and have no permissions to delete
  backup objects. A compromise of the application layer therefore
  cannot cascade to the backup layer.
* **Access Control:** Backup restoration is restricted to named administrators
  (CTO and SIRO) authenticated via MFA-protected Civo accounts. No
  automated process or service account has restore permissions.
* **Vault Key Independence:** The custodian component of the HashiCorp Vault
  platform master key is stored offline by named administrators using Shamir's
  Secret Sharing, split across multiple secure locations. This component is
  never stored within the hosting environment. Even a complete loss of the
  Civo account cannot result in permanent loss of the ability to
  reconstruct encryption keys, provided custodian shares are intact.

## 2. Source Code and Configuration Independence

To provide a recovery path independent of the primary hosting provider:

* **GitHub Repository:** All application source code and infrastructure
  configuration is version-controlled in GitHub, which is operationally
  independent of Civo. In the event of a complete Civo account
  loss, the application can be redeployed from GitHub to an alternative
  hosting provider.
* **Vault Unseal Keys:** Vault unseal keys are distributed across secure
  offline locations held by named administrators, independent of any
  cloud provider account.

## 3. Cloud Syncing Policy

* **Prohibition:** Personal cloud syncing services (OneDrive, Google Drive,
  Dropbox) are strictly prohibited for storage of patient data, backup exports,
  or encryption keys.
* **Compliance:** All automated backups are managed via the CloudNativePG
  operator into Civo Object Storage (UK). Civo's current security
  certifications are recorded in the Supplier Register.
  Personal accounts and consumer cloud services are excluded from all
  backup and data handling processes.

## 4. Pre-Production Note

{{ platform_name }} is currently in pre-production. No clinical patient data
is held in the system at this time. Backup and isolation procedures are
documented and tested ahead of live deployment to ensure controls are verified
before any health data is processed.
