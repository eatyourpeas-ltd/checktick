---
title: "National Data Opt-Out"
category: dspt-1-confidential-data
---

# National Data Opt-Out

{{ platform_name }} is a platform provider. Compliance with the National Data Opt-Out is the responsibility of our customers (the Data Controllers). However, our platform provides the technical capability for Controllers to remove specific records if a patient exercises their right to opt-out via the national service.

## Encryption and the Controller's Declaration

Responses are encrypted at rest on **every** survey — patient, public, and staff alike. The publish flow requires encryption setup before any first publish, and there is no mechanism to store responses in plaintext. This is the platform's security posture: encryption cannot be waived by survey creators.

Historically (before the opt-out's removal), staff-audience password-user surveys could store plaintext when the creator recorded an explicit, audit-logged opt-out declaration, and surveys predating the encryption upgrade were grandfathered (`legacy-1.0`). Those rows remain honoured by the encryption predicate solely so their owners keep access to data stored plaintext under the old policy; the fields and audit records are retained as historical evidence. Owners of such surveys can migrate them to encryption at any time via `migrate_survey_encryption` (per-slug, using the owner's credentials).

The remaining creator declaration in the publication workflow is the **no-patient-data confirmation** (required for Public, Unlisted, and Token visibility): the creator asserts the survey is not patient-facing and gathers no patient-identifiable data — patient-facing surveys must not be published on a public or unlisted link. It is audit-logged at publication (`no_patient_data_declared`).

See [Individual Rights Procedure](/docs/compliance/individual-rights-procedure/) for how encrypted data is handled in rights requests, and [Encryption for Users](/docs/encryption-for-users/) for the technical detail.

## Opt-Out Tokens for Public Surveys

In addition to the encryption opt-out declaration above, CheckTick provides an **opt-out token** mechanism for participants in public and unlisted surveys. This extends the existing receipt token pattern (used for pseudonymous surveys) to anonymous responses.

- **Survey creator control:** The `allow_response_redaction` toggle (default: True) in the publication workflow controls whether opt-out tokens are issued. If disabled, public-survey responses are fully anonymous and cannot be redacted.
- **Automatic issue (issue #376):** When the toggle is enabled, every participant is shown a one-time token on the thank-you page after submission — a short, random code (8 characters, like a 2FA token) with a copy button and a warning that it will not be shown again. No opt-in step is required. The token is stored on the response and can be used to locate it for deletion via the DSR workflow.
- **Effective anonymity preserved:** The token contains no personal information and is not linked to any identity. A participant who discards their token leaves their response effectively anonymous.
- **Token delivery:** The participant can optionally email the token to themselves from the thank-you page. The email address is used only to send that one email — it is not stored on CheckTick's servers, never appears in logs, and no copy of the sent email is kept (the Graph sending path sets `saveToSentItems: false`). Delivery is handled by Microsoft 365, which may retain transport metadata for a limited period under its standard service terms.
- **Lost tokens:** If the participant loses their token, the response cannot be identified for deletion. This is the privacy trade-off for not collecting participant identity.

See [Survey Progress Tracking](/docs/survey-progress-tracking/) for the user-facing guide and [Survey Progress Tracking (Technical)](/docs/survey-progress-tracking-technical/) for the developer reference.
