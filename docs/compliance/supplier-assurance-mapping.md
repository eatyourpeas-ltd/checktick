---
title: "Supplier Security Assurance Mapping"
category: dspt-10-suppliers
---

# Supplier Security Assurance Mapping

{{ platform_name }} has mapped the requirements of the NHS DSPT against the existing certifications and assurances held by key suppliers to ensure ‘equivalent or higher’ protection where applicable.

| Supplier | Certification / Assurance | DSPT Equivalent? | Notes |
| :--- | :--- | :--- | :--- |
| **Northflank** | ISO 27001 / SOC 2 | **Yes** | Covers physical, network, and operational security of hosting infrastructure. |
| **GitHub** | ISO 27001 / SOC 2 | **Yes** | Covers security of the code management and CI/CD pipeline. |
| **Microsoft 365 (Exchange Online)** | ISO 27001 / SOC 2 / NHS DCB1596 Conformance | **Yes** | Used for all CheckTick transactional and health/care-related email. Configured in line with NHS Secure Email Standard (DCB1596). |
| **Proton Mail** | ISO 27001 | **Not Applicable (Out of Scope)** | Used only for Eatyourpeas Ltd corporate communications. Not used for patient data or health/care communications. |

## Assurance Conclusion:

All suppliers involved in the processing, storage, or transmission of health and care data (Northflank, GitHub, and Microsoft 365) hold internationally recognised security certifications (ISO 27001 and/or SOC 2) and are subject to independent third-party audit.

Microsoft 365 is additionally configured to meet the NHS Secure Email Standard (DCB1596) and is used exclusively for all in-scope health and care communications.

Proton Mail is used only for corporate business activities and is explicitly out of scope of DSPT-controlled data flows.

Based on this, {{ platform_name }} is satisfied that all in-scope suppliers meet or exceed the security requirements expected under the DSPT.
