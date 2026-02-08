---
title: "Staff Password Policy"
category: dspt-4-managing-access
---

# Staff Password Policy (Cyber Essentials Aligned)

**Last Reviewed:** 08/02/2026 | **Owner:** SIRO {{ cto_name }}
**Cyber Essentials Compliance:** Control 4.1 - Password-based Authentication

## 1. Password Requirements (Technical Controls)

{{ platform_name }} enforces password quality through the following technical controls, meeting Cyber Essentials standards:

### 1.1 Desktop/Laptop Devices (macOS/Windows/Linux)

**All Default Passwords Changed:** Upon initial device setup, all vendor-supplied default passwords are immediately replaced with unique passwords meeting the requirements below.

* **Standard User Accounts:**
  - Minimum length: 12 characters (no maximum length restriction)
  - Must be unique (not used on any other system)
  - Protected by biometric authentication (Touch ID/Face ID/Windows Hello) where available
  - Password required immediately after sleep/screen saver
  
* **Administrator Accounts:**
  - Minimum length: 12 characters (no maximum length restriction)
  - Must be stored in approved password manager (Bitwarden)
  - Authentication via PAM module (pam_tid.so on macOS) using Touch ID/biometrics for sudo operations
  - Never used for day-to-day work activities

* **No Default or Guessable Passwords:** Prohibited patterns include "password", "admin", "12345", organization name, or predictable sequences

### 1.2 Mobile Devices (iOS/Android)

* **Screen Lock:** Minimum 6-digit PIN or biometric authentication (Touch ID/Face ID/Fingerprint) required
* **All Default Passwords Changed:** Factory default settings disabled on first boot
* **Remote Wipe Capability:** Enabled via Apple/Google native management
* **App Passwords:** All business apps (GitHub, email) protected by device biometric authentication

### 1.3 Cloud Services (GitHub, Northflank)

All cloud service accounts meet one of these Cyber Essentials-compliant configurations:

**Administrative Accounts (Organization Owners, Infrastructure Admin):**

* Minimum password length: 12 characters (exceeds CE requirement)
* MFA mandatory (TOTP, Passkeys, or Biometric)
* No maximum length restriction
* Stored in Bitwarden password manager

**Standard User Accounts:**

* Minimum password length: 8 characters with MFA, OR
* Minimum password length: 12 characters with automatic common password blocking (100,000+ NCSC deny list)
* No maximum length restriction

### 1.4 Technical Controls Summary (CE Requirement)

We implement **all three** Cyber Essentials technical control options:

1. ✅ **Multi-factor authentication** - Mandatory on all cloud administrative accounts (12+ char minimum, exceeds CE requirement)
2. ✅ **12+ character minimum, no maximum** - Enforced on all devices and standard cloud accounts
3. ✅ **8+ character minimum with deny list** - Enforced on standard user accounts with MFA and NCSC blocklist

## 2. Password Quality & Construction

* **Recommended Method:** Use 'Three Random Words' method (e.g., `Correct-Horse-Battery-Staple`)
* **Non-Obvious:** Do not use easily discoverable info (birthdays, pet names, '{{ platform_name }}123')
* **Blocklists:** Application layer blocks the most common 100,000 passwords using NCSC-recommended deny lists
* **No Maximum Length:** Systems do not impose arbitrary maximum password lengths

## 3. Password Management & Storage

* **No Reuse:** You must never reuse a password between systems. Your {{ platform_name }} infrastructure password must be unique.
* **Storage:** Staff must use an approved Password Manager (Bitwarden). Writing passwords on paper or in unencrypted digital files is strictly prohibited.
* **Memorization:** Staff must memorize their 'Master Password' for Bitwarden and their primary device login. These must never be recorded.

## 4. Authentication Methods & SSO

* **SSO Preference:** Wherever possible, utilize OIDC/SSO (Google/GitHub) to reduce the number of managed passwords.
* **Multi-Factor Authentication (MFA):** MFA is mandatory for all cloud services (GitHub, Northflank) and personal email accounts. Passkeys and Biometric (Touch ID) authentication are the preferred methods.
* **Biometric Authentication (macOS):** Touch ID configured via PAM module (pam_tid.so) to authorize administrative tasks (sudo operations), providing high-strength authentication without compromising efficiency.

## 5. Application-Level Password Controls

Our internet-facing services utilize Django-axes to prevent brute-force attacks by locking accounts after 5 failed attempts.

## 6. Prohibition of Default Passwords (Cyber Essentials Requirement)

* **Immediate Change:** All default or vendor-supplied passwords must be changed immediately upon account creation.
* **Infrastructure:** Passwords for infrastructure (Databases, API Keys) must be at least 20 characters and stored only in Bitwarden.
**Policy Statement:** All default or vendor-supplied passwords must be changed immediately upon device setup, account creation, or service provisioning.

**Scope:**

* **Network Equipment:** Router admin passwords changed to 12+ character unique passwords (documented in Infrastructure Technical Change Log)
* **Desktop/Laptop Devices:** macOS/Windows default passwords replaced on first boot
* **Mobile Devices:** Factory default PINs/passwords changed during initial setup
* **Cloud Services:** Default passwords on new accounts changed immediately
* **Infrastructure:** Database admin passwords (20+ characters minimum), API keys, all stored in Bitwarden
* **Social Media/Third-party Services:** All accounts used for business protected by unique passwords + MFA

**Verification:**

* Initial setup documented in Hardware Assets register
* Regular review during bi-annual Infrastructure & Firewall audits (February & June)
* Network device passwords verified during annual Cyber Essentials review

## 7. Regular Password Review & Maintenance

**Cyber Essentials Requirement:** Regular review to ensure no default or guessable passwords remain in use.

**Review Schedule:**

* **Monthly:** Cloud service accounts reviewed for MFA compliance (Access Control Policy section 6.4)
* **Bi-annual:** Device password compliance verified during infrastructure audits (February & June)
* **Annual:** Full password policy compliance review during Cyber Essentials assessment
* **Ad-hoc:** Immediate review following any security incident or staff departure

## 8. Response to Compromise (Rotation Process)

If a password is known or suspected to be compromised (e.g., through a phishing attempt, device loss, or service breach notification), the following "Prompt Rotation" process must be followed:

1. **Immediate Reset:** The user must immediately change the password for the affected service using the Password Manager to generate a new, unique, 12+ character credential.
2. **Session Invalidation:** After the reset, the user must use the service's "Sign out of all sessions" feature to force-evict any unauthorized active sessions.
3. **MFA Review:** The user must verify that MFA settings (recovery codes, phone numbers, or authenticator devices) have not been altered.
4. **Device Scan:** Any device used to access the compromised account must be checked for malware using native macOS security tools (XProtect/XProtect Remediator).
5. **Reporting:** All suspected compromises must be reported to the CTO to be logged in the Technical Change Log for audit purposes.
