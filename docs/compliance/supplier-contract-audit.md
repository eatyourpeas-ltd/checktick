---
title: "Supplier Data Processing Contract Audit"
category: dspt-10-suppliers
---

# Supplier Data Processing Contract Audit

**Date of Audit:** 03/01/2026
**Auditor:** {{ siro_name }} (SIRO)
**Scope:** All third-party suppliers identified in the Supplier Register that handle Personal Identifiable Information (PII).

## 1. Audit Summary

| Metric | Value |
| :--- | :--- |
| Total Suppliers Handling PII | 4 |
| Total with Compliant Security Clauses | 4 |
| **Compliance Percentage** | **100%** |

## 2. Detailed Verification

| Supplier | Data Category | Clause Mechanism | Article 28 Verified? |
| :--- | :--- | :--- | :--- |
| **Northflank** | Patient/App Data | Northflank Data Processing Agreement | Yes |
| **Mailgun** | User Contact Info | Mailgun DPA + UK SCC Addendum | Yes |
| **GitHub** | Developer PII | GitHub Global DPA | Yes |

## 3. Mandatory Clause Checklist

Each contract listed above has been verified to contain the following mandatory security requirements:

* **Security Measures:** Obligation to implement appropriate technical and organisational measures (Encryption, MFA, etc.).
* **Breach Notification:** Requirement to notify {{ platform_name }} without undue delay after becoming aware of a personal data breach.
* **Sub-processing:** Restrictions on appointing sub-processors without prior written authorization/notification.
* **Audit Rights:** Provision for {{ platform_name }} (or a third party) to audit compliance or receive audit reports (e.g., SOC2/ISO 27001).

## 4. Conclusion

As of the date of this audit, 100% of suppliers handling personal data are under contract with terms that meet or exceed the ICO guidance and UK GDPR requirements. No new suppliers may be onboarded without the SIRO first verifying the presence of these clauses.
