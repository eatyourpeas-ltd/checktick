---
title: "Standard Device Build Specification"
category: dspt-9-it-protection
---

# Standard Device Build Specification (macOS & Windows 11)

**Version:** 1.1
**Last Reviewed:** 08/02/2026

All devices used for {{ platform_name }} business must meet the following "Standard Build" requirements before accessing GitHub, Northflank, or internal data.

**Current Device Inventory:**
- 1x macOS laptop (Touch ID)
- 1x Windows 11 laptop (Windows Hello Face unlock)
- 1x iPhone (Face ID + Touch ID)
- 1x Android phone (Android 16, Fingerprint)

---

## 1. macOS Laptop Configuration

### 1.1 Operating System & Updates

* **OS Version:** Must be one of the three most recent versions of macOS (currently Sonoma or Sequoia).
* **Updates:** 'Check for updates' and 'Install Security Responses and system files' must be enabled.

### 1.2 Security Configuration

* **Encryption:** FileVault Full-Disk Encryption must be turned ON.
* **Firewall:** macOS Stealth Mode Firewall must be turned ON.
* **Sudo/Admin:** Day-to-day work must be done on a Standard User account; Administrator credentials must be stored in a password manager.
* **Biometric Authentication (Touch ID):** PAM module (pam_tid.so) configured to authorize sudo operations via Touch ID, providing high-strength authentication while maintaining operational efficiency.
* **Login & Screen Lock (Cyber Essentials):** 
  - Automatic Login must be DISABLED
  - Password or Touch ID required immediately after sleep or screen saver
  - Screen saver activation: Maximum 10 minutes of inactivity (recommended: 5 minutes)
  - Lock immediately when closing lid or manually locking (Cmd + Ctrl + Q)
* **Password Requirements:** Minimum 12 characters for all accounts; admin passwords stored in Bitwarden (see Password Policy).
* **Failed Login Attempts:** After 10 unsuccessful login attempts, device should require restart or extended delay (native macOS throttling)

### 1.3 Network & Software

* **DNS:** Configured to use Protective DNS (9.9.9.9).
* **Browser:** Hardened browser profile with Bitwarden and uBlock Origin installed.
* **Installation:** Gatekeeper set to "App Store and identified developers."

---

## 2. Windows 11 Laptop Configuration

### 2.1 Operating System & Updates

* **OS Version:** Windows 11 Pro (required for BitLocker encryption)
* **Updates:** Windows Update set to automatic; Windows Defender definitions updated automatically

### 2.2 Security Configuration

* **Encryption:** BitLocker Full-Disk Encryption must be turned ON
* **Firewall:** Windows Firewall must be enabled with 'Block all incoming connections' as default
* **Admin Account:** Day-to-day work done on Standard User account; Administrator credentials stored in Bitwarden
* **Biometric Authentication (Windows Hello):** Face recognition configured for device unlock and credential manager access
* **Login & Screen Lock (Cyber Essentials):**
  - Automatic Login must be DISABLED
  - Password or Windows Hello Face required immediately after wake from sleep
  - Screen lock activation: Maximum 10 minutes of inactivity (recommended: 5 minutes)
  - Lock immediately when closing lid or manually locking (Windows + L)
* **Password Requirements:** Minimum 12 characters for all accounts; admin passwords stored in Bitwarden
* **Failed Login Attempts:** Native Windows throttling after 10 unsuccessful attempts

### 2.3 Network & Software

* **DNS:** Configured to use Protective DNS (9.9.9.9)
* **Browser:** Hardened browser profile with Bitwarden and uBlock Origin installed
* **Windows Defender:** Real-time protection enabled, automatic sample submission enabled
* **SmartScreen:** Microsoft Defender SmartScreen enabled for apps and files

---

## 3. Cross-Platform Requirements

### 3.1 Audit Cycle

The CTO reviews these settings on all registered devices twice per year. Results are noted in the 'Security Audit Log.'

## 4. AutoRun & Execution Controls (Cyber Essentials)

**Cyber Essentials Requirement:** Disable any auto-run feature which allows file execution without user authorization.

### 4.1 Removable Media & Network Volumes

* **AutoRun Disabled:** No code is permitted to execute automatically from removable media (USB drives, external hard drives) or network volumes without explicit user initiation.
* **macOS:** AutoRun disabled by default. No auto-mounting scripts configured.
* **Windows 11:** AutoPlay disabled for all media and devices (Settings > Bluetooth & devices > AutoPlay)

### 4.2 Browser Download Settings

All browsers must be configured to prevent automatic execution or opening of downloaded files:

**Safari (macOS):**

* 'Open "safe" files after downloading' setting: **DISABLED**
* Location: Safari > Settings > General > "Open 'safe' files after downloading" (unchecked)

**Google Chrome (macOS & Windows):**

* All 'Auto-open' file type preferences: **CLEARED**
* Location: Chrome > Settings > Downloads > Check that no file types are listed under "Open certain file types automatically after downloading"

**Microsoft Edge (Windows 11):**

* Ask what to do with each download: **ENABLED**
* Location: Edge > Settings > Downloads > Verify no automatic actions configured

**Firefox (if used):**

* 'Always ask' for file actions: **ENABLED**
* Location: Firefox > Settings > General > Applications > Verify no automatic actions configured

### 4.3 System-Level Execution Controls

**macOS:**

* **Gatekeeper:** Set to "App Store and identified developers" minimum
  * Requires explicit user approval (Open context menu > Open) for unidentified developer apps
  * Prevents automatic execution of untrusted code
* **XProtect:** macOS built-in malware scanning active (automatically scans downloads)
* **Quarantine Attribute:** macOS applies `com.apple.quarantine` extended attribute to downloaded files, preventing immediate execution

**Windows 11:**

* **SmartScreen:** Microsoft Defender SmartScreen enabled for apps and files
  * Warns before running unrecognized apps from the internet
  * Blocks known malicious files
* **Windows Defender:** Real-time protection scans downloads automatically
* **User Account Control (UAC):** Set to high; requires approval for system changes

### 4.4 Verification Schedule

* **Bi-annual Device Security Audit:** February and June each year (documented in annual-compliance-checklist-2026.md)
* **Verification Items:**
  * macOS: Safari 'Open safe files' disabled, Gatekeeper active, XProtect running
  * Windows: AutoPlay disabled, SmartScreen enabled, Windows Defender active
  * Both platforms: Chrome/Edge auto-open preferences cleared

---

## 5. Personal Firewall Settings

* **Status:** Must be enabled at all times on both macOS and Windows devices.
* **macOS:** 'Block all incoming connections' with Stealth Mode enabled to prevent discovery on public Wi-Fi networks.
* **Windows 11:** 'Inbound connections that do not match a rule are blocked' configured on all network profiles (Domain, Private, Public).
* **Authorized Exceptions:** Only core OS services and signed business applications (e.g., Zoom/Teams for communication) are permitted exceptions. No server-side services (e.g., local web servers) may be exposed to the network.

---

## 6. Mobile Device Security (iPhone)

The iPhone used for {{ platform_name }} business (MFA authentication, email access, emergency management) must meet the following requirements:

**Authentication & Access Control:**

* **Screen Lock:** Minimum 6-digit PIN or biometric authentication (Face ID or Touch ID) required
* **Auto-Lock:** Maximum 2 minutes of inactivity before auto-lock
* **Default Passwords Changed:** Factory default settings disabled during initial setup
* **Failed Attempt Limits:** Device wipe after 10 failed passcode attempts (Erase Data enabled)

**Security Configuration:**

* **iOS Version:** Must run one of the three most recent iOS versions with automatic security updates enabled
* **App Sources:** Only install apps from official App Store (no jailbreaking)
  * **Exception for Development:** TestFlight may be used for installing {{ platform_name }} apps under development with CTO authorization. Third-party apps via TestFlight are prohibited.
* **Business App Security:** GitHub, email, and other business apps protected by device biometric authentication
* **Remote Management:** Find My iPhone enabled for remote wipe capability
* **Public WiFi:** Avoid accessing sensitive business services on public WiFi; use mobile data where possible
* **Backup:** Encrypted iCloud backup enabled or local encrypted iTunes/Finder backup

**Prohibited Actions:**

* Jailbreaking device
* Installing third-party apps from unknown sources or TestFlight without CTO authorization
* Disabling security features (Face ID, passcode, Find My iPhone)
* Sharing device PIN/passwords

**Review:** iPhone compliance verified during bi-annual infrastructure audits alongside laptop devices.
---

## 7. Mobile Device Security (Android)

The Android phone used for {{ platform_name }} business (MFA authentication, email access, emergency management) must meet the following requirements:

**Authentication & Access Control:**

* **Screen Lock:** Minimum 6-digit PIN or biometric authentication (Fingerprint) required
* **Auto-Lock:** Maximum 2 minutes of inactivity before screen lock
* **Default Passwords Changed:** Factory default settings disabled during initial setup
* **Failed Attempt Limits:** Device wipe after 10 failed PIN attempts (configured in Security settings)

**Security Configuration:**

* **Android Version:** Must run Android 16 or one of the three most recent Android versions with automatic security updates enabled
* **Google Play Protect:** Must be enabled for real-time malware scanning (Settings > Security > Google Play Protect)
* **App Sources:** Only install apps from official Google Play Store (no sideloading APKs or rooting)
  * **Exception for Development:** Developer mode and USB debugging may be enabled for installing {{ platform_name }} apps under development with CTO authorization. Third-party APKs and sideloading other apps are prohibited.
* **Unknown Sources:** "Install unknown apps" permission disabled for all apps except authorized development tools (e.g., Android Studio for {{ platform_name }} app development)
* **Business App Security:** GitHub, email, and other business apps protected by device biometric authentication
* **Remote Management:** Find My Device enabled for remote wipe capability
* **Public WiFi:** Avoid accessing sensitive business services on public WiFi; use mobile data where possible
* **Backup:** Encrypted Google One backup enabled or equivalent encrypted backup solution

**Malware Protection:**

* **Google Play Protect:** Active scanning for malware in installed apps and during app installation
* **App Sandboxing:** Android's built-in app isolation prevents malicious apps from accessing data from other apps
* **Verified Boot:** Ensures device boots only with verified Android software

**Prohibited Actions:**

* Rooting device
* Installing third-party apps from unknown sources or enabling "Developer mode" for non-{{ platform_name }} purposes without CTO authorization
* Disabling security features (Fingerprint, PIN, Find My Device, Play Protect)
* Sharing device PIN/passwords

**Review:** Android compliance verified during bi-annual infrastructure audits alongside other mobile and laptop devices.