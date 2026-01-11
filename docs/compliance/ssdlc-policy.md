---
title: "Secure Software Development Lifecycle (SSDLC) Policy"
category: dspt-9-it-protection
---

# Secure Software Development Lifecycle (SSDLC) Policy

**Standard:** OWASP Top 10 (2021) Alignment

## 1. Planning & Design

* **Threat Modelling:** New features involving patient data require a brief threat model to identify potential attack vectors (e.g., SSRF or Broken Access Control).
* **Data Minimization:** We design schemas to only collect the minimum PII necessary for the clinical survey task.

## 2. Secure Development (Coding)

* **Framework Security:** We leverage Django’s built-in security features (ORM for SQLi prevention, auto-escaping for XSS, and CSRF middleware).
* **Secrets Management:** No secrets (API keys, DB passwords) are ever stored in source code. We use Northflank Environment Secrets and local `.env` files (excluded via `.gitignore`).
* **Input Validation:** All user input is treated as untrusted and validated against strict schemas.

## 3. Security Testing (The Pipeline)

Our GitHub Actions pipeline acts as our security "Gatekeeper":

1. **Static Analysis:** CodeQL scans for 0-day vulnerabilities in Python and JavaScript logic.
2. **Dependency Audit:** `pip-audit` checks for known CVEs in the library stack.
3. **Secret Scanning:** `ggshield` prevents accidental credential pushes.
4. **Automated Testing:** Pytest and Playwright suites ensure security logic (e.g., login lockouts) remains functional.

## 4. Peer Review

* At least one founding partner must review and approve code changes.
* Reviews specifically check for:
    * Proper permission checks (`user.has_perm`).
    * Correct use of encryption utilities.
    * Compliance with the [Security Overview](/docs/security-overview/).

## 5. Deployment

* Deployments are automated via Northflank (UK).
* Any security scan failure in the CI/CD pipeline automatically blocks the deployment to production.
