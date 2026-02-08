---
title: "Network Security: Web Filtering Procedure"
category: dspt-9-it-protection
---

# Network Security: Web Filtering Procedure

## 1. Protective DNS (PDNS) Baseline

To provide a network-level 'safety net,' all corporate devices must use a Protective DNS service.

* **Primary DNS:** 9.9.9.9 (Quad9) or 1.1.1.2 (Cloudflare Malware Blocking).
* **Configuration:** This is set at the OS level (System Settings > Network) to ensure protection follows the device across all Wi-Fi networks.

## 2. Browser Security

All devices must have web protection configured to prevent connections to known malicious websites:

### 2.1 Desktop and Laptop Browsers

**macOS (Chrome/Safari):**

* **Google Chrome:** Safe Browsing must be set to 'Standard Protection' or 'Enhanced Protection' (Chrome Settings > Security and Privacy > Safe Browsing)
* **Safari:** Fraudulent Website Warning must be enabled (Safari Settings > Security > "Warn when visiting a fraudulent website")
* **Pop-up Blocking:** Must be enabled on both browsers to prevent drive-by download attacks

**Windows 11 (Edge/Chrome):**

* **Microsoft Edge:** SmartScreen for Microsoft Edge must be enabled (Edge Settings > Privacy, search, and services > Security > "Microsoft Defender SmartScreen"). This provides protection against phishing sites and malicious downloads.
* **Google Chrome:** Safe Browsing must be set to 'Standard Protection' or 'Enhanced Protection'
* **Pop-up Blocking:** Must be enabled on both browsers

### 2.2 Mobile Device Browsers

**iPhone (Safari):**

* **Fraudulent Website Warning:** Must be enabled (Settings > Safari > "Fraudulent Website Warning")
* Safari uses Google Safe Browsing technology to check URLs in real-time against a constantly updated global database of malicious sites
* If a match is found, Safari blocks the connection and displays a full-screen warning

**Android (Chrome):**

* **Safe Browsing:** Must be enabled (Chrome Settings > Privacy and security > Safe Browsing)
* Android system-level protection through Google Play Protect provides additional layer against malicious scripts
* Pop-up blocking enabled by default

## 3. Blocklists and Updates

We rely on the automated, real-time blocklists maintained by our DNS and Browser providers. These lists are updated globally every few minutes to protect against 'Zero Day' phishing sites.

## 4. Audit & Verification

During the **Quarterly Spot Check**, the CTO verifies:

1. The DNS settings on all devices are correctly pointed to the PDNS (9.9.9.9 or 1.1.1.2).
2. **Desktop/Laptop Browsers:**
   - macOS: Safari Fraudulent Website Warning enabled, Chrome Safe Browsing active
   - Windows 11: Microsoft Edge SmartScreen enabled, Chrome Safe Browsing active
3. **Mobile Device Browsers:**
   - iPhone: Safari Fraudulent Website Warning enabled
   - Android: Chrome Safe Browsing active, Play Protect enabled
4. Any blocked-site alerts are reviewed to determine if further staff training (SIRO) is required.

## 5. User Policy

Staff are prohibited from bypassing browser security warnings (e.g., clicking "Continue anyway" or "Ignore warning"). Any security alert indicating a potentially malicious website must be:

1. Immediately closed/backed away from
2. Screenshot captured if possible
3. Reported to the CTO/SIRO for logging and investigation

Deliberate bypassing of web security warnings is a disciplinary matter and will be addressed in accordance with the Staff Security Agreement.
