---
title: "Software Security Code of Practice (SSCoP) Assessment"
category: dspt-5-process-reviews
---

# Software Security Code of Practice (SSCoP) Assessment

**Product:** CheckTick Survey Platform
**Organisation:** EatYourPeas Ltd
**Assessment Date:** March 2026
**Senior Responsible Owner:** Dr Simon Chapman (CTO)
**Governance Oversight:** Dr Serena Haywood (SIRO)
**Next Review:** March 2027

This assessment covers all 14 principles of the Government Software Security
Code of Practice (updated January 2026). CheckTick is classified as a software
developer and distributor and is therefore subject to all 14 principles.

---

## Theme 1: Secure Design and Development

### Principle 1.1 — Follow an established secure development framework

CheckTick follows a documented Secure Software Development Lifecycle (SSDLC)
aligned with OWASP Top 10 (2021). The SSDLC covers threat modelling, secure
coding practices, requirements capture, governance and roles, test strategy,
data management, and configuration management. All code changes are managed
through a pull request process requiring CTO review before merging to the
main branch. The CI/CD pipeline enforces that no code reaches production
without passing automated security gates.

**Status: Met**
**Evidence:** SSDLC Policy, OWASP alignment statement, Secure Development
and Patching Policy

### Principle 1.2 — Understand the composition of the software and assess
risks linked to third-party components

All Python dependencies are declared in pyproject.toml and locked in
poetry.lock. GitHub Dependabot and pip-audit monitor all dependencies
continuously against known vulnerability databases. Any new dependency
requires CTO approval via the pull request process. All self-hosted
JavaScript assets are monitored weekly with SHA-384 SRI verification.
The full dependency inventory is maintained in the Software Asset and
Configuration Register. Third-party component risks are assessed and
documented in the Vulnerability and Patch Log.

**Status: Met**
**Evidence:** Software Asset Register, Vulnerability and Patch Log,
Automation Overview

### Principle 1.3 — Have a clear process for testing software and software
updates before distribution

All changes are tested through an automated test suite (Pytest and
Playwright) before deployment. Security patches are applied in a staging
environment and verified before production promotion. CodeQL static analysis
runs on every commit. Automated RBAC negative testing verifies that
permission boundaries are enforced correctly. Any test failure blocks the
CI/CD pipeline preventing deployment.

**Status: Met**
**Evidence:** SSDLC Policy, Vulnerability and Patch Log

### Principle 1.4 — Follow secure by design and secure by default principles

Privacy by Design is applied throughout the development lifecycle. All
survey response data is encrypted at field level using AES-256-GCM before
reaching the database. MFA is enforced by default for all privileged
accounts. API and firewall rules are set to deny-by-default. The Django
admin interface is served from a non-default path. Content Security Policy
headers are enforced. DPIAs are conducted for all new processing activities
involving health data. Secure cookie flags (Secure; HttpOnly; SameSite=Lax)
are enforced on all sessions.

**Status: Met**
**Evidence:** SSDLC Policy, DPIA Procedure, Encryption Technical Reference,
Infrastructure Hardening Standard

---

## Theme 2: Build Environment Security

### Principle 2.1 — Protect the build environment against unauthorised access

Access to GitHub (source control and CI/CD) and Northflank (production
hosting) is restricted to named administrators only — Dr Simon Chapman
(CTO) and Dr Serena Haywood (SIRO). Both accounts require MFA enforced
at the organisation level. No third party or contractor has standing access
to the build environment. Any temporary access is pre-approved, time-limited,
and revoked immediately on completion. GitGuardian (ggshield) prevents
secrets or credentials from entering the repository via pre-commit hooks.

**Status: Met**
**Evidence:** Enhanced Acceptable Use Policy, Access Control Policy,
Access Audit Log

### Principle 2.2 — Control and log changes to the build environment

All changes to the build environment are managed through pull requests
requiring CTO review and automated security gate approval before merging.
The Git history provides an immutable timestamped record of every change,
who proposed it, who approved it, and the automated scan results. Northflank
infrastructure changes are logged in the Infrastructure Technical Change Log.
No direct changes to the production environment are permitted outside the
CI/CD pipeline.

**Status: Met**
**Evidence:** Change Management Policy, Infrastructure Technical Change Log,
SSDLC Policy

---

## Theme 3: Secure Deployment and Maintenance

### Principle 3.1 — Distribute software securely to customers

CheckTick is distributed as a SaaS platform over HTTPS with TLS 1.2 or
better enforced on all connections. HSTS is enforced at the application
layer. All data in transit is encrypted. No insecure delivery mechanism
is used. Container images are rebuilt from a clean base on every deployment
ensuring a known and consistent production state.

**Status: Met**
**Evidence:** Data in Transit Security Standard, Infrastructure Hardening
Standard

### Principle 3.2 — Implement and publish an effective vulnerability
disclosure process

A vulnerability disclosure process is in place. Security researchers and
customers can report vulnerabilities via security@checktick.uk. Reports
are triaged by the CTO, risk-assessed, and remediated according to CVSS-based
timelines. Reporters receive acknowledgement and are kept informed of
remediation progress. The process is documented in our Vulnerability
Management Policy.

**Status: Met**
**Evidence:** Vulnerability Management Policy, Security Remediation Process

### Principle 3.3 — Have processes for proactively detecting, prioritising
and managing vulnerabilities

Vulnerabilities are detected through four continuous automated mechanisms:
pip-audit running daily at 06:00 UTC and on every push and pull request,
GitHub Dependabot monitoring the full dependency graph continuously, CodeQL
static analysis on every commit, and a weekly CDN Library Monitor for
self-hosted JavaScript assets. Vulnerabilities are triaged by CVSS score
with documented remediation timelines — critical within 48 hours, high
within 7 days, medium within 30 days. All findings and remediations are
recorded in the Vulnerability and Patch Log. EatYourPeas Ltd is a registered
NCSC Early Warning subscriber.

**Status: Met**
**Evidence:** Vulnerability and Patch Log, Vulnerability Management Policy,
Automation Overview

### Principle 3.4 — Report vulnerabilities to relevant parties

Vulnerabilities in CheckTick that may affect customer organisations are
reported to affected customers promptly. Vulnerabilities in third-party
components are reported upstream to the relevant open source project or
vendor where appropriate. Significant vulnerabilities are escalated to the
SIRO and reported via the DSPT Incident Reporting Tool where they meet
the notification threshold.

**Status: Met**
**Evidence:** Incident Reporting Procedure, Vulnerability Management Policy

### Principle 3.5 — Provide timely security updates, patches and
notifications to customers

Security updates are applied within documented timelines — critical within
48 hours, high within 7 days — well within the 14-day maximum required by
DSPT. As a SaaS platform, patches are applied centrally by EatYourPeas Ltd
and do not require customer action. Customers are notified of significant
security updates via the platform status communications process. The full
patch history from November 2025 is documented in the Vulnerability and
Patch Log.

**Status: Met**
**Evidence:** Vulnerability and Patch Log, Patch Management Strategy,
SIRO-Approved Patching Approach

---

## Theme 4: Communication with Customers

### Principle 4.1 — Provide information to customers about support and
maintenance

CheckTick's support commitments, maintenance approach, and security
practices are published in the Terms of Service, public documentation,
and DSPT compliance pages. Customers are informed of the platform's
security architecture, encryption approach, and data handling practices
through the public documentation portal.

**Status: Met**
**Evidence:** Terms of Service, Documentation portal, DSPT Compliance
pages

### Principle 4.2 — Provide at least 12 months notice of end of support

EatYourPeas Ltd commits to providing a minimum of 12 months written
notice to all active customers prior to any end-of-support or
decommissioning date for the CheckTick platform. This commitment is
documented in the Terms of Service. No end-of-support date is currently
planned.

**Status: Met**
**Evidence:** Terms of Service

### Principle 4.3 — Make information available about notable incidents

Significant security incidents that may cause material impact to customer
organisations are communicated within 2 hours of confirmation, as
documented in our Incident Response Plan and Crisis Communication and
Press Templates. The communication process covers direct notification
to affected Trust Clinical Admins, ICO notification within 72 hours where
applicable, and DSPT incident reporting tool notification where the
threshold is met.

**Status: Met**
**Evidence:** Incident Response Plan, Crisis Communication and Press
Templates, Incident Reporting Procedure

---

## Summary

| Principle | Status |
| :--- | :--- |
| 1.1 Secure development framework | ✅ Met |
| 1.2 Third-party component management | ✅ Met |
| 1.3 Testing process | ✅ Met |
| 1.4 Secure by design and default | ✅ Met |
| 2.1 Build environment access control | ✅ Met |
| 2.2 Build environment change control | ✅ Met |
| 3.1 Secure distribution | ✅ Met |
| 3.2 Vulnerability disclosure process | ✅ Met |
| 3.3 Vulnerability detection and management | ✅ Met |
| 3.4 Vulnerability reporting | ✅ Met |
| 3.5 Timely security updates | ✅ Met |
| 4.1 Support and maintenance information | ✅ Met |
| 4.2 End of support notice | ✅ Met |
| 4.3 Incident communication | ✅ Met |

**Overall Assessment: All 14 principles met.**

**Approved by:** Dr Serena Haywood (SIRO)
**Date:** March 2026
