---
title: "Supplier Security Assurance Procedure"
category: dspt-10-suppliers
---

# Supplier Security Assurance Procedure

## 1. Scope

This procedure applies to all new and existing suppliers identified as ‘Critical’ or ‘Data Processing’ in the {{ platform_name }} Supplier Register.

Suppliers used exclusively for corporate business operations, and not involved in the processing of health or care data, are recorded but considered out of DSPT scope.

---

## 2. Pre-Contract Due Diligence

Before a contract is signed or a service is utilised, the CTO/SIRO must verify:

1. **Security Accreditations:**
   Does the supplier hold ISO 27001, SOC 2 Type II, Cyber Essentials, or equivalent?

2. **Data Residency:**
   Where is the data stored? (Preference for UK/EEA or jurisdictions with adequacy decisions).

3. **Data Protection Agreement (DPA):**
   Does the supplier provide an Article 28 UK GDPR-compliant DPA?

4. **Scope of Use:**
   Whether the supplier will process, store, or transmit health or care data.
   If yes, additional assurance requirements apply (including alignment with NHS standards such as DCB1596 where relevant).

---

## 3. Approved Accreditation Standards

{{ platform_name }} accepts the following certifications as evidence of appropriate security:

- ISO/IEC 27001:2013 or 2022
- SOC 2 Type II (Security, Confidentiality, Availability)
- Cyber Essentials / Cyber Essentials Plus
- CSA STAR

For email services used in health and care contexts, compliance with the NHS Secure Email Standard (DCB1596) is required.

---

## 4. Supplier Classification

Suppliers are classified as:

- **Critical / Data Processing (In Scope):**
  Suppliers that process, store, or transmit health or care data (e.g. hosting, email delivery, code infrastructure)

- **Corporate / Out of Scope:**
  Suppliers used only for internal business operations and not used for patient data or health/care communications (e.g. corporate email)

This distinction ensures DSPT requirements are applied proportionately and correctly.

---

## 5. Annual Audit

During the Q1 Security Review, the SIRO will:

- Verify current certifications (ISO/SOC 2) for all in-scope suppliers
- Confirm continued compliance with NHS requirements where applicable (e.g. DCB1596 for email services)
- Review any reported security incidents or breaches in the preceding 12 months
- Update the Supplier Register with review outcomes and next review dates

---

## 6. Current Application

- Microsoft 365 is approved for all CheckTick transactional and health/care email and is configured to meet DCB1596
- Northflank and GitHub are approved as critical infrastructure providers
- Proton Mail is approved for corporate use only and is not used for DSPT-scoped data
