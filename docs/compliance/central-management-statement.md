---
title: "Centralized Device Management Statement"
category: dspt-9-it-protection
---

# Centralized Device Management Statement

## 1. Management Philosophy

{{ platform_name }} employs a "Policy-as-Management" approach for its endpoint devices (macOS laptops). Due to the small team size, a dedicated MDM (Mobile Device Management) server is not currently deployed. Instead, central control is achieved through:

* **Standardized Build Specs:** A central master document that dictates all security settings.
* **Administrative Separation:** Staff use standard accounts; the "Admin" keys are held centrally in the corporate password manager.

## 2. Remote Wipe & Access Control

In the event of a device compromise, central management is executed via our Cloud Service Providers:

* **GitHub:** Central revocation of SSH keys and MFA sessions.
* **Northflank:** Central revocation of infrastructure access.
* **Password Manager:** Central vault access revocation.

## 3. Auditing

The CTO acts as the 'Human MDM,' conducting a physical and configuration audit of all devices every 90 days to ensure 100% alignment with the central security policy.
