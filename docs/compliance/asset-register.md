---
title: "Combined Information Asset & ROPA Register"
category: dspt-4-managing-access
---

# Combined Information Asset & ROPA Register

**Version:** 1.2
**Last Reviewed & Approved by SIRO:** 02/01/2026
**Approval Status:** Final

## 1. Asset & Data Processing Register

| Asset Name | Asset Type | OS / Version | Support Status | Lawful Basis (GDPR) | Classification | Security Measures | Storage Location |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Survey Database** | Software | PostgreSQL 16.x | **Supported** | Art 9(2)(h) | **Highly Confidential** | AES-256, Managed Upgrades | Northflank (UK) |
| **Web/Worker App** | Software | Ubuntu 22.04 LTS | **Supported** | Art 6(1)(b) | **Highly Confidential** | OCI Isolation, `pip-audit` | Northflank (UK) |
| **Secrets Vault** | Software | Northflank Secrets| **Supported** | Art 6(1)(b) | **Highly Confidential** | Scoped Access, MFA | Northflank (UK) |
| **Staff Laptop 1** | Hardware | macOS 15.x | **Supported** | Art 6(1)(f) | **Confidential** | FileVault, Auto-Update | Physical (UK) |
| **Staff Laptop 2** | Hardware | macOS 15.x | **Supported** | Art 6(1)(f) | **Confidential** | FileVault, Auto-Update | Physical (UK) |
| **GitHub Repo** | Software | GitHub Enterprise | **Supported** | Art 6(1)(f) | **Internal** | MFA, Branch Protection | GitHub Cloud |
| **GoCardless** | SaaS | Vendor Managed | **Supported** | Art 6(1)(b) | **Confidential** | MFA, TLS 1.3 | SaaS |
| **Email/Support** | Software | Vendor Managed | **Supported** | Art 6(1)(b) | **Confidential** | MFA, TLS Encryption | Secure Provider |

## 2. Estate Compliance Summary

| Estate Category | Requirement | Current Status | Compliance % |
| :--- | :--- | :--- | :--- |
| **Server Estate** | 95% Supported | 100% (Ubuntu 22.04 LTS) | **100%** |
| **Desktop Estate** | 98% Supported | 100% (macOS 15.x) | **100%** |

## 3. Medical Device & IoT Scope Statement

**Scope Review Date:** 03/01/2026

{{ platform_name }} has performed a scope assessment of its network estate.

* **Physical Medical Devices:** {{ platform_name }} does not own, lease, or operate any physical medical devices (e.g., diagnostic hardware, wearables, or IoT sensors) connected to its network.
* **Software as a Medical Device (SaMD):** {{ platform_name }} is a survey and data collection platform. It does not perform clinical calculations, provide diagnostic recommendations, or contribute to clinical decision-making. Therefore, it is not classified as a Medical Device.
* **Assurance Process:** Our hardware lifecycle is limited to founder laptops. Should any medical device be introduced to the network in the future, it will be subject to a clinical safety review (DCB0129) and recorded in this register with specific patching and isolation controls.

## 4. SIRO Estate Compliance Statement

> "I, {{ cto_name }} (SIRO), confirm that as of January 2026, **100% of {{ platform_name }}’s server estate** and **100% of our desktop estate** are running on versions of operating systems currently supported by their respective vendors.
>
> We maintain a 'Zero-Legacy' architecture; all infrastructure is deployed via modern OCI containers, and founder hardware is kept current via automated macOS security updates. This register is reviewed every 6 months to ensure we remain compliant with NHS DSPT Standard 8."
>
> **Signed:** {{ cto_name }} (SIRO)
> **Date:** 02/01/2026
