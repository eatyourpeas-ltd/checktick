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

* **Authorized Browsers:** Google Chrome or Microsoft Edge.
* **Safe Browsing:** Must be set to 'Standard Protection' or 'Enhanced Protection.'
* **Pop-up Blocking:** Must be enabled to prevent drive-by download attacks.

## 3. Blocklists and Updates

We rely on the automated, real-time blocklists maintained by our DNS and Browser providers. These lists are updated globally every few minutes to protect against 'Zero Day' phishing sites.

## 4. Audit & Verification

During the **Quarterly Spot Check**, the CTO verifies:

1. The DNS settings on all devices are correctly pointed to the PDNS.
2. The browser 'Safe Browsing' feature is active.
3. Any blocked-site alerts are reviewed to determine if further staff training (SIRO) is required.
