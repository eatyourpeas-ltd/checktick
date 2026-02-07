---
title: "Staff Password Policy"
category: dspt-4-managing-access
---

# Staff Password Policy

**Last Reviewed:** 07/02/2026 | **Owner:** SIRO {{ cto_name }}

## 1. Choosing Passwords

* **Complexity:** Passwords for accounts without MFA must be at least 12 characters. Staff are encouraged to use the 'Three Random Words' method (e.g., `Correct-Horse-Battery-Staple`).
* **MFA Minimums:** For accounts protected by MFA, passwords must be at least 8 characters.
* **Non-Obvious:** Do not use easily discoverable info (birthdays, pet names, '{{ platform_name }}123').
* **Blocklists:** We technically block the most common 100,000 passwords at the application layer using NCSC-recommended deny lists.

## 2. Password Management & Storage

* **No Reuse:** You must never reuse a password between systems. Your {{ platform_name }} infrastructure password must be unique.
* **Storage:** Staff must use an approved Password Manager (Bitwarden). Writing passwords on paper or in unencrypted digital files is strictly prohibited.
* **Memorization:** Staff must memorize their 'Master Password' for Bitwarden and their primary device login. These must never be recorded.

## 3. High-Risk Functions

* **SSO Preference:** Wherever possible, utilize OIDC/SSO (Google/GitHub) to reduce the number of managed passwords.
* **Multi-Factor Authentication (MFA):** MFA is mandatory for all cloud services (GitHub, Northflank, Google Workspace). Passkeys and Biometric (Touch ID) authentication are the preferred methods.

## 4. System Risks

Our internet-facing services utilize Django-axes to prevent brute-force attacks by locking accounts after 5 failed attempts.

## 5. Prohibition of Default Passwords

* **Immediate Change:** All default or vendor-supplied passwords must be changed immediately upon account creation.
* **Infrastructure:** Passwords for infrastructure (Databases, API Keys) must be at least 20 characters and stored only in Bitwarden.

## 6. Response to Compromise (Rotation Process)

If a password is known or suspected to be compromised (e.g., through a phishing attempt, device loss, or service breach notification), the following "Prompt Rotation" process must be followed:

1.  **Immediate Reset:** The user must immediately change the password for the affected service using the Password Manager to generate a new, unique, 12+ character credential.
2.  **Session Invalidation:** After the reset, the user must use the service's "Sign out of all sessions" feature to force-evict any unauthorized active sessions.
3.  **MFA Review:** The user must verify that MFA settings (recovery codes, phone numbers, or authenticator devices) have not been altered.
4.  **Device Scan:** Any device used to access the compromised account must be checked for malware using native macOS security tools (XProtect/XProtect Remediator).
5.  **Reporting:** All suspected compromises must be reported to the CTO to be logged in the Technical Change Log for audit purposes.
