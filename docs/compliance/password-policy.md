---
title: "Staff Password Policy"
category: dspt-4-managing-access
---

# Staff Password Policy

**Last Reviewed:** 29/12/2025 | **Owner:** SIRO {{ cto_name }}

## 1. Choosing Passwords

* **Complexity:** Passwords must be at least 12 characters. Staff are encouraged to use the 'Three Random Words' method to avoid obvious choices (e.g., `Correct-Horse-Battery-Staple`).
* **Non-Obvious:** Do not use easily discoverable info (birthdays, pet names, '{{ platform_name }}123').
* **Blocklists:** We technically block the most common 10,000 passwords at the application layer.

## 2. Password Management & Storage

* **No Reuse:** You must never reuse a password between systems. Your {{ platform_name }} infrastructure password must be unique.
* **Storage:** Staff must use an approved Password Manager (e.g., Bitwarden, 1Password, or iCloud Keychain). Writing passwords on paper or in unencrypted digital files is strictly prohibited.
* **Memorization:** Staff must memorize their 'Master Password' for their Password Manager and their primary device login. These must never be recorded.

## 3. High-Risk Functions

* **SSO Preference:** Wherever possible, utilize OIDC/SSO to reduce the number of managed passwords.
* **Multi-Factor Authentication (MFA):** MFA is mandatory. A password alone is considered insufficient for access to GitHub, Northflank, or the {{ platform_name }} Production Admin.

## 4. System Risks

Our internet-facing services utilize Django-axes to prevent brute-force attacks by locking accounts after 5 failed attempts.

## 5. Prohibition of Default Passwords

* **Immediate Change Requirement:** All default or vendor-supplied passwords for any new software, hardware, or cloud service must be changed immediately upon installation or account creation.
* **Complexity for System Accounts:** Passwords for infrastructure components (e.g., Database Admin, Vault, API Keys) must be at least 20 characters and stored only in an approved, encrypted password manager.
* **Social Media & Comms:** Any social media or third-party service accounts used for {{ platform_name }} business must be protected by a high-strength password and Multi-Factor Authentication (MFA).
* **Audit:** During quarterly access reviews, the CTO verifies that no 'test' or 'default' accounts exist in the production or staging environments.
