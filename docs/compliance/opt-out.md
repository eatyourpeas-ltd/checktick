---
title: "National Data Opt-Out"
category: dspt-1-confidential-data
---

# National Data Opt-Out

{{ platform_name }} is a platform provider. Compliance with the National Data Opt-Out is the responsibility of our customers (the Data Controllers). However, our platform provides the technical capability for Controllers to remove specific records if a patient exercises their right to opt-out via the national service.

## Encryption and the Controller's Declaration

The same controller-responsibility principle applies to response encryption. The platform provides the technical capability: responses are encrypted at rest by default on surveys covered by the encryption predicate (patient data, patient/public audience, SSO-authenticated owners, or surveys with a submission keypair). For staff-audience, password-user surveys, the **survey creator (Data Controller) decides whether to opt out** of whole-response encryption by making an explicit declaration. That declaration is the controller-side record: it is stored on the survey (`encryption_opt_out_at` / `_by` / declaration version) and written to the audit log (`encryption_opt_out_declared`).

See [Individual Rights Procedure](/docs/compliance/individual-rights-procedure/) for how encrypted data is handled in rights requests, and [Encryption for Users](/docs/encryption-for-users/) for the technical detail.

## Opt-Out Tokens for Public Surveys

In addition to the encryption opt-out declaration above, CheckTick provides an **opt-out token** mechanism for participants in public and unlisted surveys. This extends the existing receipt token pattern (used for pseudonymous surveys) to anonymous responses on an opt-in basis.

- **Survey creator control:** The `allow_response_redaction` toggle (default: True) in the publication workflow controls whether opt-out tokens are offered. If disabled, public-survey responses are fully anonymous and cannot be redacted.
- **Participant opt-in:** On the thank-you page after submission, the participant can choose to receive a token. If they accept, the token is stored on the response and can be used to locate it for deletion via the DSR workflow. If they decline, the response remains anonymous.
- **Token delivery:** The participant can optionally email the token to themselves. The email address is not stored on CheckTick's servers — it is used to send the email and then discarded.
- **Lost tokens:** If the participant loses their token, the response cannot be identified for deletion. This is the privacy trade-off for not collecting participant identity.

See [Survey Progress Tracking](/docs/survey-progress-tracking/) for the user-facing guide and [Survey Progress Tracking (Technical)](/docs/survey-progress-tracking-technical/) for the developer reference.
