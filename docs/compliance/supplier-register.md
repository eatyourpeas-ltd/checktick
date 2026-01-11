---
title: "Supplier & Sub-Processor Register"
category: dspt-10-suppliers
---

# Supplier & Sub-Processor Register

**Version:** 1.2
**Owner:** {{ siro_name }} (SIRO)
**Last Reviewed:** 03/01/2026
**Review Status:** COMPLIANT (Meets DSPT 2024-26 Requirements)

## 1. Overview

This register identifies all third-party suppliers that provide critical IT infrastructure or process personal data on behalf of {{ platform_name }}. As a Data Processor for the NHS, we vet all suppliers to ensure they meet our data residency and security standards.

## 2. Supplier List

| Supplier Name | Service Provided | Personal Data Handled? | Contract Start | Contract End | Location | Contact Details |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Northflank** | Cloud PaaS & Hosting | **Yes** (Encrypted Survey Data) | 15/01/2024 | Rolling Monthly | UK (London) | support@northflank.com |
| **Mailgun** | Transactional Email | **Yes** (Researcher Names/Emails) | 10/02/2024 | Rolling Monthly | EEA (Frankfurt) | privacy@mailgun.com |
| **GitHub** | Source Code & CI/CD | No (Source code only) | 01/11/2023 | Continuous | Global/USA | support@github.com |
| **Namecheap** | Domain Registrar | No | 05/12/2023 | Annual (Dec) | USA | compliance@namecheap.com |

## 3. Critical Service Dependencies

The following services are identified as "Critical" to the operation of the {{ platform_name }} platform. A failure of these suppliers constitutes a Business Continuity event:

1. **Northflank:** Hosting and Database.
2. **Mailgun:** Delivery of survey invitations and password resets.

## 4. Security Assessment Summary

* **Northflank:** SOC2 Type II and ISO 27001 compliant. Data is stored in UK-Sovereign data centers.
* **Mailgun:** GDPR compliant via DPA and Standard Contractual Clauses (SCCs).

## 5. Change Log

| Date | Author | Description of Change |
| :--- | :--- | :--- |
| 15/07/2024 | {{ siro_name }} | Initial register creation for DSPT. |
| 03/01/2026 | {{ cto_name }} | Annual review; confirmed UK data residency for Northflank. |
