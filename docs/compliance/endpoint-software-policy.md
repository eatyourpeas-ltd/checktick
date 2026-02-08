---
title: "Endpoint Software & Installation Policy"
category: dspt-9-it-protection
---

# Endpoint Software & Installation Policy

## 1. User Account Management (Cyber Essentials Aligned)

**Policy Statement:** {{ platform_name }} maintains a "Minimum Necessary Accounts" policy across all devices and cloud services to reduce attack surface and ensure accountability.

### 1.1 Desktop/Laptop Device Accounts (macOS/Windows/Linux)

* **Guest Accounts:** DISABLED on all business devices. No guest, temporary, or anonymous access permitted.
* **Single User Per Device:** Each physical device is assigned to one individual. Only one standard user account exists per device for day-to-day operations.
* **Standard User Accounts:** All {{ platform_name }} business activities (coding, email, web browsing, document editing) must be performed on a standard (non-administrator) user account.
* **Administrator Accounts:** 
  - Maintained separately from standard user accounts
  - Only used for system-wide updates, software installation, or security configuration changes
  - Administrator credentials stored in encrypted password manager (Bitwarden/1Password)
  - Must not be used for routine work activities
* **Unnecessary Accounts Removed:** Test accounts, vendor default accounts, and unused accounts are prohibited and must be removed during initial device setup.

**Verification:** To check user accounts on macOS: System Settings > Users and Groups

### 1.2 Cloud Service Account Management (GitHub, Northflank)

* **Individual Named Accounts:** All cloud services use individual, named accounts. No shared credentials permitted.
* **User/Admin Separation:** Where the service supports it, standard user access and administrative access are separated:
  - **GitHub:** Separate accounts or limited repository access for routine work; full admin rights only when needed
  - **Northflank:** Role-based access; administrative console access restricted to CTO/SIRO only
* **MFA Required:** Multi-Factor Authentication enforced on all cloud service accounts and personal email accounts without exception.
* **Monthly Account Review:** The CTO reviews all active accounts on GitHub and Northflank monthly. Any account inactive for >90 days is flagged for disabling (documented in Access Control Policy section 6.4).

### 1.3 Production Server/Container Accounts

* **No Local User Accounts:** Production containers are "headless" with no SSH user accounts or interactive login capability.
* **Cloud-Managed Authentication:** All administrative access to production infrastructure is via cloud-managed consoles (Northflank) with MFA-protected authentication.
* **No Default Accounts:** Container images based on minimal distros; default system accounts (e.g., 'demo', 'test') removed from base images.

### 1.4 Regular Account Review Schedule

* **Bi-annual Device Audit:** All local device accounts verified during infrastructure & firewall review (February and June as per Annual Compliance Checklist)
* **Monthly Cloud Review:** Active cloud service accounts reviewed monthly as documented in Access Control Policy
* **Leaver Process:** Immediate account removal within 1 hour of staff departure (documented in Access Control Policy section 4.1)

**Last Policy Review:** 08/02/2026  
**Next Review:** 08/02/2027  
**Cyber Essentials Requirement:** Control 1.2 - User Account Management

## 2. Software Restrictions

* **Verification:** Only software from known, notarized developers or the official App Store is permitted.
* **Browser Extensions:** Only essential, reputable extensions (e.g., uBlock Origin, Bitwarden) are permitted in the browser used for {{ platform_name }} administration.
* **Prohibited Software:** Peer-to-peer (P2P) file sharing, unapproved VPNs, and software from untrusted/unnotarized sources are strictly prohibited on business devices.

## 3. Developer Environment Control

* All third-party libraries used in the {{ platform_name }} platform must be installed via `Poetry`.
* **Lockfiles:** Every dependency is pinned in a `poetry.lock` file, ensuring the exact same code is used across all development and production environments.
* **Audit:** Dependencies are scanned daily for vulnerabilities; any library found to be insecure is removed or patched within the timelines defined in our Vulnerability Policy.
