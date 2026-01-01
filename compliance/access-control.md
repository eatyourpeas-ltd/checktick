# Access Control Policy (Internal & Application)

**Version:** 1.0
**Owner:** [Name 2] (CTO)
**Last Reviewed:** [Insert Date post-July 2024]
**Approval:** [Name 1] (SIRO)

## 1. Purpose
This policy defines the rules for granting, reviewing, and revoking access to CheckTick’s information assets, ensuring the **Principle of Least Privilege (PoLP)** is maintained at all times.

## 2. Infrastructure Access (Founders/Admin)
Access to the production environment is restricted to the founding team.

* **Individual Accounts:** No shared "admin" or "root" accounts are permitted.
* **Authentication:** Mandatory Multi-Factor Authentication (MFA) is enforced for Northflank (Infrastructure), GitHub (Source Code), and Google Workspace (Management).
* **Workstations:** Administrative tasks must be performed on encrypted devices (FileVault/BitLocker).

## 3. Application Role-Based Access Control (RBAC)
CheckTick implements a tiered RBAC model to ensure users only access data necessary for their role.

| Role | Access Level | Permissions |
| :--- | :--- | :--- |
| **Organization Owner** | Full Admin | User management, Billing, Data Export, Survey Deletion. |
| **Editor** | Survey Mgmt | Create/Edit surveys; Cannot view or export response data. |
| **Data Custodian** | Data Mgmt | View and Export assigned survey data; Cannot edit survey logic. |
| **Viewer** | Read Only | View survey metadata; No access to PII/Sensitive data. |

## 4. Provisioning & Deprovisioning (Leaver's Process)

### 4.1 Internal (CheckTick Team)

Upon the departure of any founding partner or future contractor:

1. **Immediate Revocation:** Access to GitHub and Northflank is revoked within 1 hour.
2. **Secret Rotation:** Any shared environmental variables or API keys they had access to are rotated.
3. **Audit:** A final audit of the 'Access Log' is conducted to ensure no unauthorized exports occurred.

### 4.2 External (Customer Organisations)

As the **Data Processor**, CheckTick provides the tools for **Data Controllers** (Trusts) to manage their own staff.

* Customers are responsible for removing users who leave their organisation via the 'Organization Settings' dashboard.
* Access is revoked in real-time upon deletion by the Organisation Owner.

## 5. Access Review Schedule

* **Monthly:** CTO reviews the list of 'Collaborators' on GitHub and Northflank.
* **Bi-Annually:** SIRO performs a spot-check of the 'Audit Log' to ensure Data Custodian exports match authorized clinical requests.

## 6. Authentication & Identity Standards

### 6.1 Multi-Factor Authentication (MFA)

* **Mandatory:** MFA is strictly enforced for all administrative roles and any account with 'Data Custodian' or 'Organization Owner' privileges.
* **Methods:** Support for TOTP (e.g., Google Authenticator) and OIDC-inherited MFA.

### 6.2 Password Policy (Non-SSO Accounts)

For accounts not utilizing OIDC, the following complexity is enforced via Django's auth validators:

* **Minimum Length:** 12 characters.
* **Entropy:** Must include a mix of uppercase, lowercase, numbers, and symbols.
* **Protection:** Passwords are hashed using PBKDF2 with a SHA256 salt.
* **Lockout:** Accounts are locked after 5 consecutive failed attempts to prevent brute-force attacks.

### 6.3 Anti-Automation (CAPTCHA)

* CheckTick supports optional CAPTCHA integration for public-facing surveys to mitigate the risk of automated data injection and DoS attacks at the application layer.
