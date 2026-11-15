---
title: "Access Control Policy"
category: dspt-4-managing-access
---

# Access Control Policy (Internal & Application)

**Version:** 1.1
**Owner:** {{ cto_name }} (CTO)
**Last Reviewed:** April 2026
**Approval:** {{ siro_name }} (SIRO)

This policy applies to both EatYourPeas Ltd and the CheckTick
platform.

## 1. Purpose

This policy defines the rules for granting, reviewing, and
revoking access to {{ platform_name }}'s information assets,
ensuring the **Principle of Least Privilege (PoLP)** is
maintained at all times.

## 2. Infrastructure Access (Founders/Admin)

Access to the production environment is restricted to the
founding team.

* **Individual Accounts:** No shared "admin" or "root" accounts
  are permitted.
* **Authentication:** Mandatory Multi-Factor Authentication (MFA)
  is enforced for Civo (Infrastructure), GitHub (Source
  Code), and Microsoft 365 (Business Email). MFA is enforced
  at the tenant/organisation level on all three platforms.
* **Workstations:** Administrative tasks must be performed on
  encrypted devices (FileVault/BitLocker).

## 3. Application Role-Based Access Control (RBAC)

{{ platform_name }} implements a tiered RBAC model to ensure
users only access data necessary for their role.

| Role | Access Level | Permissions |
| :--- | :--- | :--- |
| **Organisation Owner** | Full Admin | User management, Billing, Data Export, Survey Deletion. |
| **Editor** | Survey Mgmt | Create/Edit surveys; Cannot view or export response data. |
| **Data Custodian** | Data Mgmt | View and Export assigned survey data; Cannot edit survey logic. |
| **Viewer** | Read Only | View survey metadata; No access to PII/Sensitive data. |
| **Distributor** (survey-level) | Distribution Only | Generate token batches and QR codes; view completion counts; export the token CSV. Cannot edit the survey, view or export results, or manage members. Tier-gated as for Viewer (Organisation tier). |

### 3.1 Appraisal Accountability Chain

For GMC-style 360 appraisal surveys run by a designated body, access follows a three-tier accountability chain:

* **Responsible Officer (RO):** The organisation owner or admin. The RO has portfolio oversight of every appraisal, co-signs exception reviews, and is the recovery route when an appraiser leaves.
* **Appraiser:** The survey owner of each appraisee's appraisal survey. The appraiser can unlock results via the organisation key, release reports, and raise exception reviews.
* **Appraisee (distributor):** Holds a DISTRIBUTOR membership on their own survey. The distributor can generate token batches and QR codes, see completion counts, and export the token CSV. The distributor cannot edit the survey, view or export results, or manage members. A distributor-only membership does not grant results access, and the appraisee holds no organisation key path.

Survey ownership remains with the appraiser. This is an organisational obligation, so the appraisee cannot alter or withdraw results.

### 3.2 Two-Party Exception Review

Identifying a pseudonymous colleague rater is an access control, not a view setting:

* **Default:** Reporting never shows the token-to-response linkage.
* **Raise:** The appraiser raises an exception review, recording the response and a reason.
* **Co-signature:** An RO must co-sign before the linkage (token, category values, and submission metadata) is revealed. The co-signing user must differ from the raiser; nobody can co-sign their own request.
* **Visibility:** The approved linkage is visible only to the appraiser and the RO. The appraisee never sees exception reviews.
* **Released reports:** Record only that an approved exception review occurred (a count), never its content.
* **Audit:** Raise, approve, and reject are all audit-logged. Disclosure (approval) is logged at WARNING severity. See `access-audit-logs.md`.

## 4. Provisioning & Deprovisioning (Leaver's Process)

### 4.1 Internal ({{ platform_name }} Team)

Upon the departure of any founding partner or future contractor:

1. **Immediate Revocation:** Access to GitHub, Civo, and
   Microsoft 365 is revoked within 1 hour.
2. **Secret Rotation:** Any shared environmental variables or
   API keys they had access to are rotated. Microsoft Graph
   API client secret is rotated if the departing individual
   had access to production Kubernetes Secrets.
3. **Audit:** A final audit of the Access Log is conducted to
   ensure no unauthorized exports occurred.

### 4.2 External (Customer Organisations)

As the **Data Processor**, {{ platform_name }} provides the
tools for **Data Controllers** (Trusts) to manage their own
staff.

* Customers are responsible for removing users who leave their
  organisation via the 'Organisation Settings' dashboard.
* Access is revoked in real-time upon deletion by the
  Organisation Owner.

## 5. Access Review Schedule

* **Monthly:** CTO reviews the list of 'Collaborators' on
  GitHub and Civo, and active accounts on Microsoft 365.
* **Bi-Annually:** SIRO performs a spot-check of the Audit Log
  to ensure Data Custodian exports match authorized clinical
  requests.

## 6. Authentication & Identity Standards

### 6.1 Multi-Factor Authentication (MFA)

* **Mandatory:** MFA is strictly enforced for all administrative
  roles and any account with 'Data Custodian' or 'Organisation
  Owner' privileges.
* **Methods:** Support for TOTP (e.g., Google Authenticator),
  FIDO2/WebAuthn hardware tokens, and OIDC-inherited MFA.
* **Microsoft 365:** MFA is enforced at the tenant level via
  Entra ID Conditional Access policies. All checktick.uk
  mailbox access requires MFA authentication.

### 6.2 Password Policy (Non-SSO Accounts)

For accounts not utilizing OIDC, the following complexity is
enforced via Django's auth validators:

* **Minimum Length:** 12 characters.
* **Entropy:** Must include a mix of uppercase, lowercase,
  numbers, and symbols.
* **Protection:** Passwords are hashed using PBKDF2 with a
  SHA256 salt.
* **Lockout:** Accounts are locked after 5 consecutive failed
  attempts to prevent brute-force attacks.

### 6.3 Anti-Automation (CAPTCHA)

* {{ platform_name }} supports optional CAPTCHA integration
  for public-facing surveys to mitigate the risk of automated
  data injection and DoS attacks at the application layer.

### 6.4 Routine Account Maintenance

To prevent 'account sprawl' and security risks from dormant
credentials:

* **Monthly Review:** The CTO reviews all 'Active' seats on
  Civo, GitHub, and Microsoft 365. Any account that has
  not been utilised for 90 days is flagged for disabling unless
  a specific justification is provided.
* **Privileged Review:** Access to production secrets and
  DB-admin roles is reviewed during every deployment cycle.
  Access is stripped back to the minimum required for the
  current infrastructure state.
* **Leaver Synchronization:** Upon notification of a departure,
  the SIRO verifies the Access Audit Log to ensure all
  identified touchpoints (SaaS tools, Cloud Ingress, Microsoft
  365, in-cluster Kubernetes Secrets) have been successfully
  neutralized.

## 7. Separation of Privileged Activities

To mitigate the risk of cross-contamination from high-risk
activities (email/browsing), the following rules apply to
System Administrators:

* **No High-Risk Activity on Admin Sessions:** Administrators
  must not check email, engage in social media, or perform
  general web browsing while logged into the Civo
  production console or database.
* **Isolated Browser Profiles:** Privileged access must be
  conducted via a dedicated browser profile that contains
  zero saved passwords for non-work sites and no third-party
  extensions.
* **Session Termination:** Administrative sessions must be
  terminated immediately upon completion of the specific
  maintenance task.
* **Zero Infrastructure Browsing:** Our server infrastructure
  (containers) is 'headless.' There are no web browsers or
  email clients installed on the production images, preventing
  server-side browsing risks.

## 8. Authorized Administrative Devices

Privileged access to {{ platform_name }} infrastructure is only
permitted from the following assured devices:

| Device ID | Assigned To | OS | Encryption Status | Verified Date |
| :--- | :--- | :--- | :--- | :--- |
| **CT-DEV-01** | {{ siro_name }} | macOS | FileVault | 29/12/2025 |
| **CT-DEV-02** | {{ cto_name }} | Windows | BitLocker | 29/12/2025 |

### 9. Device Security Requirements

Access from any device not listed above is an automatic breach
of policy. All authorised devices must:

1. Have a 'Lock Screen' timeout of no more than 5 minutes.
2. Be used exclusively by the assigned System Administrator.
3. Be wiped remotely or have credentials revoked immediately
   if the device is lost or stolen.

## 10. Technical Assurance & Testing

{{ platform_name }} treats Access Control as a 'Breaking Change'
priority.

* **Automated RBAC Testing:** Our Django test suite includes
  dedicated test cases for every permission class and decorator
  (`can_view_survey`, `can_edit_survey`, etc.).
* **Negative Testing:** We specifically write 'Negative Tests'
  to ensure that a 403 Forbidden is returned when a user
  attempts to access a resource they do not own or have
  membership for.
* **CI/CD Enforcement:** Our GitHub Actions deployment pipeline
  fails automatically if any RBAC test fails.

## 11. Mandatory MFA Enforcement

{{ platform_name }} operates a 'No MFA, No Access' policy for
all critical systems:

* **Infrastructure (Civo):** Every account with access
  to production clusters or secrets must have TOTP or
  FIDO2/WebAuthn MFA enabled.
* **Source Control (GitHub):** 2FA is required for all members
  of the {{ platform_name }} organisation.
* **Business Email (Microsoft 365):** MFA is enforced at the
  Entra ID tenant level for all checktick.uk accounts. This
  is the same identity infrastructure as NHSmail, enabling
  future OIDC integration with NHS Trust users.
* **Exceptions:** Any request to bypass MFA must be formally
  risk-assessed by the SIRO and documented in our exceptions
  log. Currently, there are 0 active exceptions.
* **Session Persistence:** Administrative sessions for
  Civo, GitHub, and Microsoft 365 are configured to
  require re-authentication after a period of inactivity.
  We do not use "Stay Logged In" on public or shared networks.
* **Phishing-Resistant MFA:** Where supported (GitHub,
  Microsoft 365), we prioritize FIDO2/WebAuthn (TouchID/
  FaceID) to prevent MFA-prompt fatigue or interception.

## 12. Third-Party and Temporary Privileged Access

EatYourPeas Ltd follows a Just-in-Time (JIT) and Least
Privilege approach for all third-party and privileged access.

* **Pre-Approval:** Any third-party access must be approved
  by both the SIRO and CTO.
* **Time-Limiting:** Access is granted for a defined window
  (e.g., 24 hours) and revoked immediately after the activity.
* **Scoped API Access:** Service-to-service credentials are
  restricted to the absolute minimum permissions required.
  The Microsoft Graph API application registration holds
  `Mail.Send` (email delivery) and `Mail.Read` (bounce/NDR
  processing — added 2026-11-08 for the signup bounce-pruning
  feature; admin consent granted + verified same day; an
  Exchange Online ApplicationAccessPolicy scoping it to the
  sending mailbox is REQUIRED and pending). No write, delete,
  or mailbox-content-modifying permissions are granted.
* **Audit Trail:** Every action performed by a third-party
  account or API token is captured in the infrastructure
  audit logs and cross-referenced during quarterly spot checks.
* **SaaS & Supplier Security:** Any SaaS tool used for business
  operations is subjected to an access review. MFA is enforced
  where available. If a supplier does not support MFA, a risk
  assessment is conducted and a unique, high-entropy 32-
  character password is used and rotated annually.

## 13. Device Security & Malware Protection

All 'Authorized Devices' must meet the following technical
baseline:

1. **Antivirus/Malware:**
   * **Windows:** Microsoft Defender must be active.
   * **macOS:** XProtect must be enabled.
2. **Disk Encryption:** FileVault (macOS) or BitLocker
   (Windows) must be active.
3. **Automatic Updates:** Operating systems and browsers must
   be set to auto-update with patches applied within 14 days
   of release.
4. **Firewall:** Native OS firewalls must be enabled and set
   to block all unsolicited incoming connections.
5. **Protective DNS:** All authorized devices must be
   configured to use Quad9
