# Annual BCDR Test Report: 2025

**Test Date:** [Insert Date]
**Scenario:** Simulated "Vault Data Corruption" and "Complete Infrastructure Loss."
**Participants:** [Name 1], [Name 2]

## 1. Test Objectives

* Restore PostgreSQL database from Northflank backup.
* Re-deploy Vault instance and unseal using Shamir keys.
* Verify that an existing 'Individual Tier' user can still decrypt their survey.

## 2. Results

| Step | Planned Time | Actual Time | Result |
| :--- | :--- | :--- | :--- |
| DB Restoration | 30 mins | 14 mins | Pass |
| Vault Unseal | 15 mins | 8 mins | Pass |
| End-to-End Decryption | 5 mins | 3 mins | Pass |

**Total Downtime (Simulated):** 25 Minutes
**RTO Status:** Met (Target was 1 hour)

## 3. Improvements Identified

* The manual 'Setup Script' for Vault had one outdated environment variable; updated in GitHub repo.
* Emergency contact list updated to include the new Northflank support tier.
