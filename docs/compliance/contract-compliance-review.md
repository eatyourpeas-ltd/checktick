---
title: "GDPR Article 28 Contract Review Log"
category: dspt-5-process-reviews
---

# GDPR Article 28 Contract Review Log

**Date of Review:** 03/01/2026
**Reviewer:** {{ siro_name }} (SIRO)

| Supplier | DPA Status | Article 28 Compliant? | Mechanism |
| :--- | :--- | :--- | :--- |
| **Northflank** | Active (at review date) | Yes | Online DPA (UK Data Residency) |
| **Mailgun** | Active | Yes | Online DPA + UK Addendum |
| **Github** | Active | Yes | GitHub Data Protection Agreement (included in Standard Terms) |

## Supplier Change Review — 04/11/2026

Following the Northflank security incident of 30/10/2026, production hosting
moved to Civo (managed Kubernetes, UK London LON1) on 2026-11-03 — see the
Infrastructure Technical Change Log. Supplier status at 04/11/2026:

| Supplier | DPA Status | Article 28 Compliant? | Mechanism |
| :--- | :--- | :--- | :--- |
| **Civo** | Active | Yes | Civo Data Processing Agreement (UK data residency) |
| **Northflank** | Terminated (account closure scheduled 05/11/2026) | Yes (historical) | Online DPA (UK Data Residency) |

## Review Checklist for Article 28 Compliance:

- [x] Processing is only on written instructions from {{ platform_name }}.
- [x] Duty of confidence for supplier personnel.
- [x] Appropriate technical and organisational security measures.
- [x] Sub-processor rules ({{ platform_name }} must be notified of changes).
- [x] Assistance with data subject rights (DSARs).
- [x] Deletion or return of data at the end of the contract.
- [x] Audit and inspection rights.
