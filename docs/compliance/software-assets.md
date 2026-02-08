---
title: "Software Asset & Configuration Register"
category: dspt-4-managing-access
---

# Software Asset & Configuration Register

**Version:** 1.2
**Last Updated:** January 2026
**Owner:** CTO

## 1. Asset Management Process

{{ platform_name }} tracks software assets through a "Managed Repository" model:

* **Discovery:** All new software or libraries must be approved by the CTO before being added to `pyproject.toml` or `package.json`.
* **Version Tracking:** Automated via GitHub Dependency Graph.
* **Audit:** A manual reconciliation of this register is performed quarterly to ensure decommissioned tools are removed.

## 2. Core Software Inventory (Production)

| Asset Name | Category | Versioning | Hosting/Owner |
| :--- | :--- | :--- | :--- |
| **Python / Django** | Application Framework | 5.x (LTS) | Northflank |
| **PostgreSQL** | Database | 15.x | AWS RDS |
| **Ubuntu (LTS)** | Base OS (Containers) | 22.04 | Northflank |
| **HashiCorp Vault** | Secret Management | 1.15.x | Self-Hosted |

## 3. Infrastructure & Tooling

| Asset Name | Category | Configuration Method |
| :--- | :--- | :--- |
| **Northflank** | PaaS / Orchestration | Northflank.yaml |
| **GitHub** | Version Control | Enterprise Cloud |
| **Cloudflare** | DNS & WAF | API-Managed |

## 4. Approved Staff Software (Desktop/Mobile)

All software installed on staff devices must be pre-approved by the CTO and listed in this register. This ensures only verified, secure applications are used for business purposes (Cyber Essentials requirement).

### 4.1 Approval Process

1. **Request:** Staff member identifies need for new software
2. **Assessment:** CTO evaluates security posture, data handling, vendor reputation, and business necessity using [Software Security Assessment](software-security-assessment.md) criteria
3. **Approval:** CTO adds approved software to this register
4. **Installation:** Only code-signed applications from official sources (App Store, identified developers, Google Play Store) may be installed

### 4.2 Approved Software List

| Software Name | Category | Approved Platforms | Business Purpose | Vendor/Source | Review Date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Visual Studio Code** | Development IDE | macOS, Windows | Code editing, development | Microsoft | Jan 2026 |
| **Docker Desktop** | Container Platform | macOS, Windows | Local development, testing | Docker Inc | Jan 2026 |
| **Postman** | API Testing | macOS, Windows | API development, testing | Postman Inc | Jan 2026 |
| **Bitwarden** | Password Manager | macOS, Windows, iOS, Android | Secure credential storage | Bitwarden Inc | Jan 2026 |
| **Signal** | Secure Messaging | iOS, Android | Encrypted business communications | Signal Foundation | Jan 2026 |
| **Chrome/Safari/Edge** | Web Browser | macOS, Windows, iOS, Android | Web access, development | Google/Apple/Microsoft | Jan 2026 |
| **GPG/GnuPG** | Encryption Tools | macOS, Windows | Code signing, encryption | GnuPG | Jan 2026 |
| **Git** | Version Control | macOS, Windows | Source code management | Software Freedom Conservancy | Jan 2026 |

### 4.3 Prohibited Software

The following categories of software are explicitly prohibited without CTO authorization:

* Remote access/screen sharing tools (except approved business tools)
* File sharing services (except approved business tools)
* Cryptocurrency mining software
* Penetration testing tools on production systems
* Software that disables security features (antivirus, firewall)
* Pirated or unlicensed software
* Software from untrusted/unknown sources

### 4.4 Technical Enforcement

Software installation is enforced through:

* **macOS:** Gatekeeper restricts to App Store and identified developers ([Standard Build Specification](standard-build-specification.md) Section 4.3)
* **Windows 11:** SmartScreen blocks unrecognized/unsigned apps ([Standard Build Specification](standard-build-specification.md) Section 4.3)
* **iOS:** App Store only, jailbreaking prohibited ([Standard Build Specification](standard-build-specification.md) Section 6)
* **Android:** Google Play Store only, rooting/sideloading prohibited ([Standard Build Specification](standard-build-specification.md) Section 7)
* **Administrative Controls:** Standard user accounts prevent unauthorized software installation

### 4.5 Quarterly Reconciliation

During quarterly Software Asset Register Reconciliation ([Annual Compliance Checklist](annual-compliance-checklist-2026.md)), the CTO:

1. Reviews installed software on all authorized devices
2. Verifies all software matches approved list
3. Identifies and removes unauthorized "shadow IT" applications
4. Updates register to reflect current approved software
5. Reviews and removes unused/obsolete software

## 5. Configuration Baseline

All assets are configured according to the **'{{ platform_name }} Hardening Standard'**:

* Root accounts protected by MFA.
* Non-essential ports/services disabled by default.
* Production data encrypted at rest (AES-256) and in transit (TLS 1.2+).
