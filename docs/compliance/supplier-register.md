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
| **Civo** | Managed Kubernetes (k3s) hosting | **Yes** (Encrypted Survey Data) | 31/10/2026 (to be confirmed) | Rolling | UK (London LON1) | via the Civo dashboard |
| **Northflank** | Cloud PaaS & Hosting (to 2026-11-05) | **Yes** (Encrypted Survey Data) | 15/01/2024 | Terminated — account closed at migration close-out | UK (London) | n/a (account closed) |
| **Microsoft 365** | Email & Identity Platform | **Yes** (User Emails, Admin Data) | 01/03/2026 | Rolling | UK/EU | privacy@Microsoft.com |
| **Proton Mail** | Corporate Email | Limited (Staff Contact Data) | 01/02/2026 | Rolling | Switzerland | security@proton.me |
| **GoCardless** | Payment Processing | **Yes** (Billing Data) | 10/02/2024 | Rolling Monthly | UK/EU | help@gocardless.com |
| **GitHub** | Source Code & CI/CD | No (Source code only) | 01/11/2023 | Continuous | Global/USA | support@github.com |
| **Namecheap** | Domain Registrar | No | 05/12/2023 | Annual | USA | compliance@namecheap.com |

## 3. Critical Service Dependencies

1. **Civo** – Managed Kubernetes hosting (database runs in-cluster)
2. **Microsoft 365** – Identity and email delivery

## 4. Security Assessment Summary

* **Civo:** ISO 27001 / SOC 2 — certificates requested from Civo (04/11/2026), verification pending. DPA: https://www.civo.com/legal/data-processing-agreement (Civo Ltd, London; UK GDPR + Data Protection Act 2018; England & Wales law; sub-processor clause with 30-day change notice and objection rights; cross-border transfer clause/IDTA). Evidence of DPA acceptance to be retained with the compliance records.
* **Microsoft 365:** ISO 27001 / SOC2 Type II
* **Proton Mail:** GDPR-compliant secure email provider
* **GoCardless:** FCA-regulated, GDPR compliant

## 5. Change Log

| Date | Author | Description |
| :--- | :--- | :--- |
| 15/07/2024 | {{ siro_name }} | Initial creation |
| 03/01/2026 | {{ cto_name }} | Annual review |
| 06/04/2026 | {{ cto_name }} | Removed Mailgun; added Microsoft 365 and Proton Mail |
| 04/11/2026 | {{ cto_name }} | Hosting supplier change: Northflank (terminated 05/11/2026 — account closed at migration close-out) replaced by Civo managed Kubernetes (UK, London LON1), following the 30/10/2026 Northflank security incident. See the Infrastructure Technical Change Log |
