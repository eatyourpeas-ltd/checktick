---
title: "Supplier Data Processing Contract Audit"
category: dspt-10-suppliers
---

# Supplier Data Processing Contract Audit

**Date of Audit:** 06/04/2026
**Auditor:** {{ siro_name }} (SIRO)
**Scope:** All third-party suppliers identified in the Supplier Register that handle Personal Identifiable Information (PII).

## 1. Audit Summary

| Metric | Value |
| :--- | :--- |
| Total Suppliers Handling PII | 3 |
| Total with Compliant Security Clauses | 3 |
| **Compliance Percentage** | **100%** |

## 2. Detailed Verification

| Supplier | Data Category | Clause Mechanism | Article 28 Verified? |
| :--- | :--- | :--- | :--- |
| **Northflank** | Patient/Application Data | Northflank Data Processing Agreement | Yes |
| **Microsoft 365 (Exchange Online)** | User Contact Data (Email Metadata) | Microsoft Online Services Data Protection Addendum (DPA) | Yes |
| **GitHub** | Developer Account Data | GitHub Global Data Protection Agreement | Yes |

## 3. Mandatory Clause Checklist

Each contract listed above has been verified to contain the following mandatory security requirements:

* **Security Measures:** Obligation to implement appropriate technical and organisational measures (e.g. encryption, access controls, MFA).
* **Breach Notification:** Requirement to notify {{ platform_name }} without undue delay after becoming aware of a personal data breach.
* **Sub-processing:** Controls governing the use of sub-processors, including transparency and contractual flow-down of obligations.
* **Audit Rights:** Provision for {{ platform_name }} (or reliance on independent third-party audits such as ISO 27001/SOC 2 reports) to verify compliance.

## 4. Scope Clarification

Proton Mail is used for corporate communications only and does not process personal data related to health or care services. It is therefore خارج the scope of this audit.

Namecheap does not process personal data on behalf of {{ platform_name }} and is also خارج scope.

## 5. Conclusion

As of the date of this audit, 100% of suppliers handling personal data on behalf of {{ platform_name }} are under contract with terms that meet or exceed UK GDPR Article 28 requirements and ICO guidance.

No new supplier may be onboarded to process personal data without the SIRO first verifying the presence of appropriate data processing terms.
