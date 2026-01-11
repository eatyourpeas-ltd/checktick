---
title: "Data Quality & Integrity Statement"
category: dspt-1-confidential-data
---

# Data Quality & Integrity Statement

**Owner:** {{ cto_name }} (CTO/Cyber Lead)
**Scope:** Standard 1.6 (Data Quality) & 1.7 (Data Validation)

## 1. Quality at Entry (Validation)

{{ platform_name }} prevents "Garbage In, Garbage Out" through multi-layered validation:

* **Type Enforcement:** Django form fields enforce data types (e.g., IntegerFields for scores, DateFields for DOB).
* **Regex Validation:** Specific formats (like NHS Numbers or Postcodes) are validated via Regular Expressions before being accepted.
* **Choice Constraints:** Surveys use `choices` and `RadioButtons` to prevent free-text errors in clinical scoring.
* **Mandatory Fields:** Logic ensures that critical clinical safety questions cannot be skipped.

## 2. Technical Integrity (No Corruption)

To ensure data is not corrupted during processing or storage:

* **ACID Compliance:** Our PostgreSQL database ensures transactions are Atomic, Consistent, Isolated, and Durable.
* **Relational Constraints:** Foreign Key constraints ensure that a response cannot exist without being linked to a specific survey and user.
* **Encryption Integrity:** AES-256-GCM (Galois/Counter Mode) provides 'Authenticated Encryption,' meaning if a single bit of the encrypted data is tampered with or corrupted, the decryption will fail rather than return incorrect data.

## 3. Regular Data Quality Audits

As part of our **Bi-Annual Spot Checks**, the SIRO and CTO perform:

1. **Schema Review:** Ensuring field lengths and types are still appropriate for the data being collected.
2. **Review of "Other" Fields:** Analyzing free-text 'Other' inputs to see if new standardized categories should be added to improve future data quality.
3. **Accuracy Check:** Comparing a sample of raw database entries against the exported UI view to ensure zero transformation errors.
