---
title: "Standard Device Build Specification"
category: dspt-9-it-protection
---

# Standard Device Build Specification (macOS)

**Version:** 1.0
**Last Reviewed:** 03/01/2026

All laptops used for {{ platform_name }} business must meet the following "Standard Build" requirements before accessing GitHub, Northflank, or internal data.

## 1. Operating System & Updates

* **OS Version:** Must be one of the three most recent versions of macOS (currently Sonoma or Sequoia).
* **Updates:** 'Check for updates' and 'Install Security Responses and system files' must be enabled.

## 2. Security Configuration (The Hardening)

* **Encryption:** FileVault Full-Disk Encryption must be turned ON.
* **Firewall:** macOS Stealth Mode Firewall must be turned ON.
* **Sudo/Admin:** Day-to-day work must be done on a Standard User account; Administrator credentials must be stored in a password manager.
* **Login:** Automatic Login must be DISABLED. Password required immediately after sleep or screen saver.

## 3. Network & Software

* **DNS:** Configured to use Protective DNS (9.9.9.9).
* **Browser:** Hardened browser profile with Bitwarden and uBlock Origin installed.
* **Installation:** Gatekeeper set to "App Store and identified developers."

## 4. Audit Cycle

The CTO reviews these settings on all registered devices twice per year. Results are noted in the 'Security Audit Log.'

## 5. AutoRun & Execution Controls

* **AutoRun:** Disabled. No code is permitted to execute from removable media or network volumes without explicit user initiation.
* **Browser Safety:** 'Open "safe" files after downloading' is disabled on all browsers to ensure no downloaded content executes/opens without a manual check.

## 6. Personal Firewall Settings

* **Status:** Must be enabled at all times.
* **Inbound Policy:** 'Block all incoming connections' (macOS) or 'Inbound connections that do not match a rule are blocked' (Windows).
* **Stealth Mode:** Enabled (macOS) to prevent discovery on public Wi-Fi networks.
* **Authorized Exceptions:** Only core OS services and signed business applications (e.g., Zoom/Teams for communication) are permitted exceptions. No server-side services (e.g., local web servers) may be exposed to the network.
