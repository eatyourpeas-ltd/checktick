---
title: "Data in Transit Security Standard"
category: dspt-9-it-protection
---

# Data in Transit Security Standard

## 1. Web Traffic (HTTPS)

* **Protocols:** Only TLS 1.2 and TLS 1.3 are permitted.
* **Ciphers:** We prioritize AEAD ciphers (e.g., AES-GCM) to ensure Forward Secrecy.
* **HSTS:** `SECURE_HSTS_SECONDS` is set to 31,536,000 (1 year) with `includeSubdomains` and `preload` enabled.

## 2. Email Security

* **Transport:** Mandatory TLS for communication with our email provider.
* **Identity & Integrity:**
    * **SPF:** Restricts which IP addresses can send mail on behalf of checktick.uk.
    * **DKIM:** Cryptographically signs all outbound emails to prevent tampering.
    * **DMARC:** Policy set to `quarantine` or `reject` for any emails failing SPF/DKIM checks.

## 3. Internal Infrastructure

* **VPC Encryption:** All traffic between application pods and the in-cluster database is encrypted at the pod-network layer.
* **Management Access:** Access to the Civo dashboard and GitHub is strictly via HTTPS or SSH (with Ed25519 keys).
