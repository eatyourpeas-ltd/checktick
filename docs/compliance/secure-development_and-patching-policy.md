---
title: "Secure Development & Patching Policy"
category: dspt-9-it-protection
---

# Secure Development & Patching Policy (SDLC)

**Version:** 1.0
**Owner:** {{ siro_name }} (CTO)
**Approval:** {{ cto_name }} (SIRO)
**Effective Date:** 29/12/2025

## 1. Purpose

This policy outlines the security controls integrated into the {{ platform_name }} Software Development Life Cycle (SDLC) to ensure that security is "baked in" from the first line of code, mitigating risks from vulnerabilities and supply chain attacks.

## 2. Secure Development Framework

{{ platform_name }} follows the **OWASP Top 10** and **NCSC Secure Development Principles**.

### 2.1 Technical Controls in CI/CD

Our GitHub Actions pipeline is configured to enforce the following checks before any code is merged into the `main` (production) branch:

* **Automated Testing:** 100% pass rate required for our RBAC and security-critical unit tests.
* **Static Analysis (SAST):** Automated scanning for hardcoded secrets, SQL injection patterns, and insecure Django configurations.
* **Dependency Scanning:** Verification that no known vulnerable libraries are included in the build.

### 2.2 Peer Review

All code changes must undergo a mandatory Peer Review via GitHub Pull Requests. Reviewers specifically check for:

* Correct application of permission decorators (`@team_member_required`, etc.).
* Safe handling of user input (avoiding `mark_safe` or raw SQL queries).
* Proper logging of administrative actions.

## 3. Vulnerability & Patch Management

{{ platform_name }} adopts a proactive approach to patching to protect against "Zero Day" and known exploits.



### 3.1 Monitoring

* **Dependabot:** Automated monitoring of our `requirements.txt` and `package.json`. Dependabot alerts the CTO immediately if a high-severity vulnerability is discovered in a third-party dependency (e.g., a Django security update).

### 3.2 Patching SLAs

Security patches are applied based on the severity of the risk:

| Severity | Timeline for Mitigation |
| :--- | :--- |
| **Critical** | Within 24 Hours of discovery/release |
| **High** | Within 7 Days |
| **Medium/Low** | Included in the next scheduled release cycle |

## 4. Environment Isolation

* **Development:** Local environments use anonymized or "dummy" data. No patient-identifiable data (PII) is ever used in development.
* **Staging:** A separate Northflank environment used for final QA.
* **Production:** The only environment containing encrypted health data. Access is strictly limited to System Administrators via MFA.

## 5. Supply Chain Security

We only use reputable, well-maintained libraries. Our primary infrastructure providers (Northflank and AWS) are verified for:

* ISO 27001 Certification.
* Compliance with the NHS Data Security and Protection Toolkit (DSPT) standards for data centers.
