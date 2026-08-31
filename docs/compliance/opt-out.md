---
title: "National Data Opt-Out"
category: dspt-1-confidential-data
---

# National Data Opt-Out

{{ platform_name }} is a platform provider. Compliance with the National Data Opt-Out is the responsibility of our customers (the Data Controllers). However, our platform provides the technical capability for Controllers to remove specific records if a patient exercises their right to opt-out via the national service.

## Encryption and the Controller's Declaration

The same controller-responsibility principle applies to response encryption. The platform provides the technical capability: responses are encrypted at rest by default on surveys covered by the encryption predicate (patient data, patient/public audience, SSO-authenticated owners, or surveys with a submission keypair). For staff-audience, password-user surveys, the **survey creator (Data Controller) decides whether to opt out** of whole-response encryption by making an explicit declaration. That declaration is the controller-side record: it is stored on the survey (`encryption_opt_out_at` / `_by` / declaration version) and written to the audit log (`encryption_opt_out_declared`).

See [Individual Rights Procedure](/docs/compliance/individual-rights-procedure/) for how encrypted data is handled in rights requests, and [Encryption for Users](/docs/encryption-for-users/) for the technical detail.
