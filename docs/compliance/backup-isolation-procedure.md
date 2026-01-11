---
title: "Backup Isolation & Immutability Procedure"
category: dspt-7-continuity
---

# Backup Isolation & Immutability Procedure

## 1. Protection Against Ransomware

{{ platform_name }} employs 'Logical Air-Gapping' to ensure that a compromise of the production web servers cannot result in the deletion of backups.

* **Immutable Storage:** Database snapshots are configured with AWS 'Deletion Protection' and S3 Object Lock. Data cannot be overwritten or deleted by the application service accounts.
* **Network Isolation:** Backups are stored in a separate VPC (Virtual Private Cloud) and are only accessible via restricted administrative roles requiring Multi-Factor Authentication (MFA).

## 2. 'Offline' Physical Backup

To satisfy the requirement for a backup not permanently connected to the network:

* **Frequency:** Weekly (Every Friday).
* **Process:** The CTO performs a manual export of the GitHub repository (Source Code) and Infrastructure-as-Code (Terraform) to a FIPS 140-2 encrypted hardware drive.
* **Storage:** Once the sync is complete, the drive is physically disconnected and stored in a secure fireproof safe.
* **Purpose:** This provides a "Ground Zero" recovery path if all cloud provider accounts (AWS/Northflank/GitHub) were simultaneously compromised.

## 3. Cloud Syncing Policy

* **Prohibition:** Personal cloud syncing services (OneDrive, Google Drive) are strictly prohibited for the storage of patient data backups or encryption keys.
* **Compliance:** All automated backups are handled via enterprise-grade, encrypted AWS S3/RDS services which are verified as ISO 27001 compliant.
