---
title: "Software Security Code of Practice (SSCoP) Assessment"
category: dspt-5-process-reviews
---

# Software Security Code of Practice (SSCoP) Assessment

**Product:** {{ platform_name }} Survey Platform
**Date:** 03/01/2026
**Assessor:** {{ siro_name }} (CTO)

## Principle 1: Protect your ecosystem

* **Source Control:** Private GitHub repository with branch protection (no direct merges to main).
* **Environment:** Infrastructure-as-Code (Northflank) ensures consistent, audited environments.

## Principle 2: Protect your software

* **Security Testing:** Every Pull Request is scanned by CodeQL.
* **Integrity:** Code is signed and verified through the GitHub/Northflank build pipeline.

## Principle 3: Protect your people

* **Access:** Role-Based Access Control (RBAC) ensures developers only have access to the secrets required for their scope of work.
* **Audit:** All administrative actions in production are logged.

## Principle 4: Secure by Design

* **Protocols:** Use of HTTPS (TLS 1.2+), HSTS, and secure cookie flags (`Secure; HttpOnly; SameSite=Lax`).
* **Authentication:** Outsourced to proven providers via OIDC; no 'home-grown' crypto or auth.

## Principle 5: Secure by Default

* **Initial Setup:** The platform requires MFA to be set up immediately for all clinical/admin accounts.
* **Default Deny:** Firewall and API rules are set to 'Deny All' by default, allowing only specifically authorized traffic.

## 6. Unused Software & Service Removal

As part of our annual security validation, we review all installed software and cloud services to identify and remove unused items:

**Desktop/Mobile Devices:**

* Review Applications folder on all Mac devices
* Identify software not used in the previous 12 months
* Uninstall via Finder > Applications > Move to Bin (requires admin authentication)
* Disable unused macOS system services in System Settings > Login Items & Extensions
* Remove unused mobile apps from Android/iOS devices

**Cloud Services:**

* Review all active SaaS/PaaS subscriptions against business requirements
* Cancel unused services
* Disable unused features within active platforms (e.g., unused GitHub features)
* Document in Technical Change Log

**Development Dependencies:**

* Quarterly review of Python/JavaScript dependencies
* Remove unused packages from requirements.txt and package.json
* Verify minimal Docker base images contain only required packages

**Last Review:** 8/2/26
**Next Review:** January 2027 (Annual Compliance Checklist)