---
title: "Access Control Policy"
category: dspt-4-managing-access
---

# Access Control Policy (Internal & Application)

**Version:** 1.0
**Owner:** {{ cto_name }} (CTO)
**Last Reviewed:** [Insert Date post-July 2024]
**Approval:** {{ siro_name }} (SIRO)

## 1. Purpose

This policy defines the rules for granting, reviewing, and revoking access to {{ platform_name }}’s information assets, ensuring the **Principle of Least Privilege (PoLP)** is maintained at all times.

## 2. Infrastructure Access (Founders/Admin)

Access to the production environment is restricted to the founding team.

* **Individual Accounts:** No shared "admin" or "root" accounts are permitted.
* **Authentication:** Mandatory Multi-Factor Authentication (MFA) is enforced for Northflank (Infrastructure) and GitHub (Source Code). Personal email accounts also have MFA enabled.
* **Workstations:** Administrative tasks must be performed on encrypted devices (FileVault/BitLocker).

## 3. Application Role-Based Access Control (RBAC)

{{ platform_name }} implements a tiered RBAC model to ensure users only access data necessary for their role.

| Role | Access Level | Permissions |
| :--- | :--- | :--- |
| **Organisation Owner** | Full Admin | User management, Billing, Data Export, Survey Deletion. |
| **Editor** | Survey Mgmt | Create/Edit surveys; Cannot view or export response data. |
| **Data Custodian** | Data Mgmt | View and Export assigned survey data; Cannot edit survey logic. |
| **Viewer** | Read Only | View survey metadata; No access to PII/Sensitive data. |

## 4. Provisioning & Deprovisioning (Leaver's Process)

### 4.1 Internal ({{ platform_name }} Team)

Upon the departure of any founding partner or future contractor:

1. **Immediate Revocation:** Access to GitHub and Northflank is revoked within 1 hour.
2. **Secret Rotation:** Any shared environmental variables or API keys they had access to are rotated.
3. **Audit:** A final audit of the 'Access Log' is conducted to ensure no unauthorized exports occurred.

### 4.2 External (Customer Organisations)

As the **Data Processor**, {{ platform_name }} provides the tools for **Data Controllers** (Trusts) to manage their own staff.

* Customers are responsible for removing users who leave their organisation via the 'Organisation Settings' dashboard.
* Access is revoked in real-time upon deletion by the Organisation Owner.

## 5. Access Review Schedule

* **Monthly:** CTO reviews the list of 'Collaborators' on GitHub and Northflank.
* **Bi-Annually:** SIRO performs a spot-check of the 'Audit Log' to ensure Data Custodian exports match authorized clinical requests.

## 6. Authentication & Identity Standards

### 6.1 Multi-Factor Authentication (MFA)

* **Mandatory:** MFA is strictly enforced for all administrative roles and any account with 'Data Custodian' or 'Organisation Owner' privileges.
* **Methods:** Support for TOTP (e.g., Google Authenticator) and OIDC-inherited MFA.

### 6.2 Password Policy (Non-SSO Accounts)

For accounts not utilizing OIDC, the following complexity is enforced via Django's auth validators:

* **Minimum Length:** 12 characters.
* **Entropy:** Must include a mix of uppercase, lowercase, numbers, and symbols.
* **Protection:** Passwords are hashed using PBKDF2 with a SHA256 salt.
* **Lockout:** Accounts are locked after 5 consecutive failed attempts to prevent brute-force attacks.

### 6.3 Anti-Automation (CAPTCHA)

* {{ platform_name }} supports optional CAPTCHA integration for public-facing surveys to mitigate the risk of automated data injection and DoS attacks at the application layer.

## 6.4 Routine Account Maintenance

To prevent 'account sprawl' and security risks from dormant credentials:

* **Monthly Review:** The CTO reviews all 'Active' seats on Northflank and GitHub. Any account that has not been utilized for 90 days is flagged for disabling unless a specific justification is provided.
* **Privileged Review:** Access to production secrets and DB-admin roles is reviewed during every deployment cycle. Access is 'stripped back' to the minimum required for the current infrastructure state.
* **Leaver Synchronization:** Upon notification of a departure, the SIRO verifies the 'Access Audit Log' to ensure all identified touchpoints (SaaS tools, Cloud Ingress, VPNs) have been successfully neutralized.

## 7. Separation of Privileged Activities

To mitigate the risk of cross-contamination from high-risk activities (email/browsing), the following rules apply to System Administrators:

* **No High-Risk Activity on Admin Sessions:** Administrators must not check email, engage in social media, or perform general web browsing while logged into the Northflank production console or database.
* **Isolated Browser Profiles:** Privileged access must be conducted via a dedicated browser profile (e.g., Chrome/Firefox Profile) that contains zero saved passwords for non-work sites and no third-party extensions.
* **Session Termination:** Administrative sessions must be terminated immediately upon completion of the specific maintenance task.
* **Zero Infrastructure Browsing:** Our server infrastructure (containers) is 'headless.' There are no web browsers or email clients installed on the production images, preventing 'Server-side' browsing risks.

## 8. Authorized Administrative Devices

Privileged access to {{ platform_name }} infrastructure is only permitted from the following assured devices:

| Device ID | Assigned To | OS | Encryption Status | Verified Date |
| :--- | :--- | :--- | :--- | :--- |
| **CT-DEV-01** | {{ siro_name }} | macOS | FileVault | 29/12/2025 |
| **CT-DEV-02** | {{ cto_name }} | Windows | BitLocker | 29/12/2025 |

### 9.1 Device Security Requirements

Access from any device not listed above is an automatic breach of policy. All authorized devices must:

1. Have a 'Lock Screen' timeout of no more than 5 minutes.
2. Be used exclusively by the assigned System Administrator.
3. Be wiped remotely (if supported) or have credentials revoked immediately if the device is lost or stolen.

## 10. Technical Assurance & Testing

{{ platform_name }} treats Access Control as a 'Breaking Change' priority.

* **Automated RBAC Testing:** Our Django test suite (Pytest/Unittest) includes dedicated test cases for every permission class and decorator (`can_view_survey`, `can_edit_survey`, etc.).
* **Negative Testing:** We specifically write 'Negative Tests' to ensure that a 403 Forbidden is returned when a user attempts to access a resource they do not own or have membership for.
* **CI/CD Enforcement:** Our Northflank deployment pipeline is configured to fail automatically if any RBAC test fails. This prevents the accidental introduction of 'over-privileged' access into the production environment.

## 11. Mandatory MFA Enforcement

{{ platform_name }} operates a 'No MFA, No Access' policy for all critical systems:

* **Infrastructure (Northflank):** Every account with access to production clusters or secrets must have TOTP (Time-based One-Time Password) or FIDO2/WebAuthn MFA enabled.
* **Source Control (GitHub):** 2FA is required for all members of the {{ platform_name }} organisation.
* **Identity Provider (OIDC):** We enforce MFA via our Google/Microsoft corporate identity providers for all staff.
* **Exceptions:** Any request to bypass MFA (e.g., for automated service accounts) must be formally risk-assessed by the SIRO and documented in our exceptions log. Currently, there are 0 active exceptions.
* **Session Persistence** Administrative sessions for Northflank and GitHub are configured to require re-authentication after a period of inactivity. We do not use "Stay Logged In" on public or shared networks.
* **Phishing-Resistant MFA** Where supported (GitHub/Google), we prioritize FIDO2/WebAuthn (TouchID/FaceID) to prevent MFA-prompt fatigue or interception.

## 12. Third-Party and Temporary Privileged Access

To mitigate the risk of 'persistent' access by external parties or service accounts:

* **Pre-Approval:** Any third-party access (e.g., for external security audits or emergency vendor support) must be approved by both the SIRO and CTO.
* **Time-Limiting:** Access is granted for a defined window (e.g., 24 hours). We utilize GitHub's 'Temporary Contributor' or Northflank's granular 'Team Permissions' to ensure access automatically expires or is manually revoked immediately after the activity.
* **Scoped API Access:** Service-to-service credentials (such as the Northflank API token for log monitoring) are restricted to the absolute minimum permissions required (Read-Only).
* **Audit Trail:** Every action performed by a third-party account or via an API token is captured in the infrastructure audit logs. These logs are cross-referenced during our quarterly spot checks to verify that access was used only for the approved purpose.
* **SaaS & Supplier Security** Any SaaS tool used for business operations (e.g., Mailgun, Sentry, Postmark) is subjected to an access review. MFA is enforced on these platforms where available. If a supplier does not support MFA, a risk assessment is conducted and a unique, high-entropy 32-character password is used and rotated annually.

## 13. Device Security & Malware Protection

To maintain the integrity of the {{ platform_name }} environment, all 'Authorized Devices' must meet the following technical baseline:

1. **Antivirus/Malware:** * **Windows:** Microsoft Defender must be active.
    * **macOS:** XProtect must be enabled.
2. **Disk Encryption:** FileVault (macOS) or BitLocker (Windows) must be active to protect data at rest.
3. **Automatic Updates:** Operating systems and browsers must be set to 'Auto-Update' to ensure security patches are applied within 14 days of release.
4. **Firewall:** Native OS firewalls must be enabled and set to 'Block all unsolicited incoming connections.'
5. **Protective DNS** All authorized devices must be configured to use a Protective DNS service (e.g., Quad9 9.9.9.9) to block connections to known malicious domains and C2 (Command & Control) servers.

Compliance is verified during our **Quarterly Spot Checks**. Any device failing these requirements is immediately revoked from the GitHub and Northflank organisations.
