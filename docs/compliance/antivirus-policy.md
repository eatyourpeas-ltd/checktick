---
title: "Antivirus & Malware Protection Procedure"
category: dspt-9-it-protection
---

# Antivirus & Malware Protection Procedure

## 1. Automated Updates

To mitigate the risk of emerging threats, all anti-malware software must be configured for automatic updates:

* **Microsoft Defender (Windows 11):** Must be set to check for updates at least daily. Cloud-protection must remain active to provide real-time protection against new variants.
* **Apple XProtect/MRT (macOS):** The macOS setting 'Install Security Responses and System Files' must be toggled ON.
* **iOS Security (iPhone):** Automatic security updates must be enabled (Settings > General > Software Update > Automatic Updates). iOS includes built-in malware protection through app sandboxing and App Store code signing.
* **Google Play Protect (Android):** Must be enabled with automatic scanning active (Settings > Security > Google Play Protect > Settings > Scan apps with Play Protect). Android includes built-in malware protection through app sandboxing, Play Protect scanning, and Play Store code signing.
* **Third-Party Tools:** If any additional tools (e.g., Malwarebytes) are used, they must be set to 'Auto-Update' both the application and the threat database.

## 2. Real-Time Scanning

All anti-malware solutions must have 'Real-Time Protection' or 'On-Access Scanning' enabled:

* **Windows 11:** Microsoft Defender real-time protection mandatory
* **macOS:** XProtect and Gatekeeper provide real-time protection (always active)
* **iPhone:** iOS app sandboxing and App Store verification provide continuous protection (native to iOS)
* **Android:** Google Play Protect provides real-time scanning and app verification (native to Android)

Periodic full-disk scans are encouraged but real-time interception is the mandatory baseline.

## 3. Handling Detections

In the event of a malware detection:

1. The software is configured to automatically quarantine the threat.
2. The user must take a screenshot of the alert and notify the CTO/SIRO immediately.
3. The device must be disconnected from the {{ platform_name }} Northflank/GitHub environment until a full system scan confirms the threat has been neutralized.

## 4. Maintenance

As part of the **Internal Audit & Spot Check Log**, the CTO will inspect authorized devices quarterly to ensure that:

* Antivirus services are active and running.
* The last update check was performed within the previous 24-hour window.

  ## 5. Real-Time and On-Access Scanning

To prevent the latent storage or accidental execution of malware, the following configurations are mandatory:

### 5.1 On-Access Requirements

* **Real-Time Interception:** Antivirus software must be active at all times. It is strictly forbidden to disable 'Real-Time Protection' or 'Always-on scanning' to improve system performance.
* **Trigger Events:** Scanning must be triggered by:
    * **File Open:** When a user or process attempts to read a file.
    * **File Download:** When a file is written to the local disk from a web browser or email client.
    * **External Media:** Immediate scanning of any USB or external drive upon mounting.

### 5.2 Handling Network Data

While {{ platform_name }} primarily uses cloud-based storage (GitHub, AWS), any files synchronized to local machines (e.g., via OneDrive or iCloud) are treated as local files and are subject to immediate on-access scanning by the device's resident anti-malware engine.

### 5.3 Compliance Verification

During quarterly audits, the CTO will verify that:

1. **Windows 11 laptop:** 'Real-time protection' toggle is locked in the 'On' position, Microsoft Defender SmartScreen enabled for apps, files, and web browsing (Edge browser).
2. **macOS laptop:** Gatekeeper and XProtect services are running (verified via `spctl --status`). Safari Fraudulent Website Warning and Chrome Safe Browsing verified active.
3. **iPhone:** iOS version is current and supported, automatic security updates enabled, App Store is the only app source (no jailbreaking), Safari Fraudulent Website Warning enabled.
4. **Android phone:** Google Play Protect is enabled and active, Android version is current and supported, automatic security updates enabled, Play Store is the only app source (no rooting or sideloading), Chrome Safe Browsing active.

Additional web filtering configuration and verification details in [Web Filtering Procedure](web-filtering-policy.md).
