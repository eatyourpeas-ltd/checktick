---
title: "Supplier & Sub-Processor Register"
category: dspt-10-suppliers
---

# Supplier & Sub-Processor Register

**Version:** 1.3
**Owner:** {{ siro_name }} (SIRO, IG Lead, Caldicott Guardian)
**Last Reviewed:** 06/04/2026
**Review Status:** COMPLIANT (Meets DSPT 2024-26 Requirements)

## 1. Overview

This register identifies all third-party suppliers that provide critical IT infrastructure or process personal data on behalf of {{ platform_name }}.

## 2. Supplier List

| Supplier Name | Service Provided | Personal Data Handled? | Contract Start | Contract End | Location | Contact Details |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Northflank** | Cloud PaaS & Hosting | **Yes** (Encrypted Survey Data) | 15/01/2024 | Rolling Monthly | UK (London) | support@northflank.com |
| **Microsoft 365** | Email & Identity Platform | **Yes** (User Emails, Admin Data) | 01/03/2026 | Rolling | UK/EU | privacy@Microsoft.com |
| **Proton Mail** | Corporate Email | Limited (Staff Contact Data) | 01/02/2026 | Rolling | Switzerland | security@proton.me |
| **GoCardless** | Payment Processing | **Yes** (Billing Data) | 10/02/2024 | Rolling Monthly | UK/EU | help@gocardless.com |
| **GitHub** | Source Code & CI/CD | No (Source code only) | 01/11/2023 | Continuous | Global/USA | support@github.com |
| **Namecheap** | Domain Registrar | No | 05/12/2023 | Annual | USA | compliance@namecheap.com |

## 3. Critical Service Dependencies

1. **Northflank** – Hosting and database
2. **Microsoft 365** – Identity and email delivery

## 4. Security Assessment Summary

* **Northflank:** ISO 27001 / SOC2 Type II
* **Microsoft 365:** ISO 27001 / SOC2 Type II
* **Proton Mail:** GDPR-compliant secure email provider
* **GoCardless:** FCA-regulated, GDPR compliant

## 5. Change Log

| Date | Author | Description |
| :--- | :--- | :--- |
| 15/07/2024 | {{ siro_name }} | Initial creation |
| 03/01/2026 | {{ cto_name }} | Annual review |
| 06/04/2026 | {{ cto_name }} | Removed Mailgun; added Microsoft 365 and Proton Mail |
