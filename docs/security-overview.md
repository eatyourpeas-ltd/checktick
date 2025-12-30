---
title: Security Overview
category: security
priority: 0
---

# Security Overview

CheckTick implements comprehensive security controls aligned with the [OWASP Top 10 (2021)](https://owasp.org/Top10/) to protect healthcare data. This document provides an overview of our security architecture and maps features to OWASP categories.

**Related Security Documentation**:

- [Authentication & Permissions](/docs/authentication-and-permissions/) – Access control, SSO, and role-based permissions
- [Encryption for Users](/docs/encryption-for-users/) – How your data is encrypted
- [Key Management for Administrators](/docs/key-management-for-administrators/) – Enterprise key management
- [Business Continuity](/docs/business-continuity/) – Disaster recovery and backup
- [Audit Logging and Notifications](/docs/audit-logging-and-notifications/) – Security event logging
- [Recovery Dashboard](/docs/recovery-dashboard/) – Account and data recovery
- [AI Security and Safety](/docs/llm-security/) – LLM and AI feature security

## Summary

| OWASP Category | Status | Key Controls |
|----------------|--------|--------------|
| A01: Broken Access Control | ✅ Mitigated | Role-based access, survey-level permissions, team/org hierarchy |
| A02: Cryptographic Failures | ✅ Mitigated | AES-256-GCM encryption, secure key derivation, Vault integration |
| A03: Injection | ✅ Mitigated | Parameterized queries, Django ORM, input validation |
| A04: Insecure Design | ✅ Mitigated | Privacy-by-design, threat modelling, security reviews |
| A05: Security Misconfiguration | ✅ Mitigated | Secure defaults, CSP headers, environment separation |
| A06: Vulnerable Components | ✅ Mitigated | pip-audit scanning, automated updates, SRI verification |
| A07: Auth Failures | ✅ Mitigated | 2FA, password policies, session management, lockout |
| A08: Software/Data Integrity | ✅ Mitigated | SRI hashes, signed commits, CI/CD security |
| A09: Logging Failures | ✅ Mitigated | Comprehensive audit logging, SIEM-ready format |
| A10: SSRF | ✅ Mitigated | Restricted network access, URL validation |

---

## A01:2021 – Broken Access Control

**Risk**: Users acting outside their intended permissions.

### Controls Implemented

#### Role-Based Access Control (RBAC)

CheckTick implements a hierarchical permission model:

- **Organization level**: Owner, Admin, Creator, Viewer roles
- **Team level**: Owner, Admin, Creator, Viewer roles
- **Survey level**: Creator (owner), Editor, Viewer roles

Each action is verified against the user's role at the appropriate level.

#### Survey-Level Permissions

- Survey encryption keys are derived per-user
- Collaborator access is explicitly granted by survey owners
- Public survey links have read-only access for submissions

#### API Authentication

- JWT tokens with short expiration (access: 15 min, refresh: 7 days)
- Token refresh requires valid refresh token
- API endpoints enforce same permissions as web UI

**Related Documentation**:
- [Authentication & Permissions](/docs/authentication-and-permissions/)
- [Account Types & Tiers](/docs/getting-started-account-types/)

---

## A02:2021 – Cryptographic Failures

**Risk**: Exposure of sensitive data due to weak or missing encryption.

### Controls Implemented

#### Data Encryption at Rest

- **Survey data**: AES-256-GCM encryption for patient-identifiable fields
- **Key derivation**: Argon2id with memory-hard parameters
- **Key hierarchy**: User KEK → Survey DEK → Field encryption

#### Encryption in Transit

- TLS 1.2+ required for all connections
- HSTS headers enforced
- Certificate pinning for API clients (recommended)

#### Key Management

- HashiCorp Vault integration for enterprise deployments
- Key escrow for ethical recovery (prevents data loss)
- Automatic key rotation support

**Related Documentation**:
- [Encryption for Users](/docs/encryption-for-users/)
- [Key Management for Administrators](/docs/key-management-for-administrators/)
- [Encryption Technical Reference](/docs/encryption-technical-reference/)

---

## A03:2021 – Injection

**Risk**: SQL injection, command injection, or other code injection attacks.

### Controls Implemented

#### SQL Injection Prevention

- Django ORM used exclusively (no raw SQL)
- Parameterized queries for all database operations
- Input validation on all user-supplied data

#### Template Injection Prevention

- Django templates with autoescaping enabled
- User content sanitized before display
- CSP headers prevent inline script execution

#### Command Injection Prevention

- No shell command execution from user input
- File operations use safe path handling
- Subprocess calls avoided; pure Python implementations preferred

---

## A04:2021 – Insecure Design

**Risk**: Missing or ineffective security controls due to design flaws.

### Controls Implemented

#### Privacy by Design

- Encryption is the default for patient data
- Data minimization principles applied
- Survey responses stored with minimal metadata

#### Threat Modelling

- Security review for all new features
- Healthcare-specific threat scenarios considered
- Recovery procedures designed with abuse prevention

#### Security Requirements

- All PRs reviewed for security implications
- Automated security scanning in CI/CD
- Pre-commit hooks for secret detection

**Related Documentation**:
- [Data Governance Overview](/docs/data-governance-overview/)
- [Business Continuity](/docs/business-continuity/)

---

## A05:2021 – Security Misconfiguration

**Risk**: Insecure default settings, incomplete configurations, or exposed debug features.

### Controls Implemented

#### Secure Defaults

- `DEBUG=False` enforced in production
- Secret keys generated securely
- Database credentials via environment variables

#### HTTP Security Headers

```python
# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Required for HTMX
CSP_IMG_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)

# Additional headers
X_FRAME_OPTIONS = "DENY"
X_CONTENT_TYPE_OPTIONS = "nosniff"
SECURE_BROWSER_XSS_FILTER = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
```

#### Environment Separation

- Separate configurations for dev/staging/production
- Production secrets never in source control
- Environment variables for all sensitive configuration

**Related Documentation**:

- [Self-Hosting Configuration](/docs/self-hosting-configuration/)
- [Self-Hosting Quickstart](/docs/self-hosting-quickstart/)

---

## A06:2021 – Vulnerable and Outdated Components

**Risk**: Using components with known vulnerabilities.

### Controls Implemented

#### Dependency Vulnerability Scanning

- **pip-audit** integrated in CI/CD pipeline
- Daily scheduled vulnerability scans
- Pre-commit hook for dependency changes
- Local `s/security-audit` script for developers

#### Automated Updates

- Dependabot enabled for security updates
- GitHub Actions workflows check for library updates
- Weekly version checks for CDN libraries

#### Self-Hosted Libraries with SRI

All client-side JavaScript libraries are self-hosted with Subresource Integrity verification:

| Library | Purpose | SRI Verified |
|---------|---------|--------------|
| HTMX | Dynamic updates | ✅ SHA-384 |
| SortableJS | Drag-and-drop | ✅ SHA-384 |

See [CDN Libraries](/docs/cdn-libraries/) for current versions and hashes.

#### Known Limitations

Some vulnerabilities are blocked by upstream dependencies:

- `ggshield` pins older versions of `cryptography` and `urllib3`
- These are tracked and will be updated when upstream releases fixes

**Related Documentation**:

- [CDN Libraries](/docs/cdn-libraries/)

---

## A07:2021 – Identification and Authentication Failures

**Risk**: Weak authentication allowing unauthorized access.

### Controls Implemented

#### Two-Factor Authentication (2FA)

- **TOTP-based 2FA** using authenticator apps (Google Authenticator, Authy, etc.)
- **Mandatory for password users** accessing sensitive features
- **Backup codes** for account recovery (10 single-use codes)
- SSO/OIDC users exempt (rely on provider's MFA)

#### Password Policies

Healthcare-compliant password requirements:

| Requirement | Value |
|-------------|-------|
| Minimum length | 12 characters |
| Character types | 3 of 4 (uppercase, lowercase, digits, symbols) |
| Repeating characters | Max 4 consecutive identical |
| Sequential characters | Max 3 sequential (abc, 123) |
| Common passwords | Blocked (Django default list) |
| User attribute similarity | Blocked |

#### Session Management

| Setting | Value | Purpose |
|---------|-------|---------|
| Inactivity timeout | 30 minutes | Protect unattended sessions |
| Maximum session age | 8 hours | Force daily re-authentication |
| Expire on browser close | Yes | Clear sessions on close |
| Cookie security | Secure, HttpOnly, SameSite=Lax | Prevent cookie theft |

#### Brute Force Protection

- **django-axes** limits failed login attempts
- Default: 5 failures → 1 hour lockout
- IP-based and username-based tracking
- **Email notification** sent when account is locked

**Related Documentation**:

- [Authentication & Permissions](/docs/authentication-and-permissions/)
- [OIDC SSO Setup](/docs/oidc-sso-setup/)

---

## A08:2021 – Software and Data Integrity Failures

**Risk**: Code and infrastructure without integrity verification.

### Controls Implemented

#### Subresource Integrity (SRI)

All external JavaScript includes SRI hashes:

```html
<script src="/static/js/htmx.min.js"
        integrity="sha384-EfwldhYywH4qYH9vU8lMn+pd6pcH0kGpPUVJuwyHnj/5felkkIUVxf1wMAEX7rCY"
        crossorigin="anonymous"></script>
```

#### CI/CD Security

- **Pre-commit hooks**: Secret scanning (GitGuardian), formatting, linting
- **GitHub Actions**: Automated testing, security scanning
- **CodeQL**: Static analysis for Python and JavaScript

#### Signed Commits

- GPG signing recommended for all contributors
- Verified commits badge on GitHub

**Related Documentation**:
- [CDN Libraries](/docs/cdn-libraries/)

---

## A09:2021 – Security Logging and Monitoring Failures

**Risk**: Insufficient logging preventing detection of breaches.

### Controls Implemented

#### Unified Audit Logging

All security-relevant events are logged to the `AuditLog` model:

**Authentication Events**:
- `login_success` / `login_failed` – with IP and user agent
- `logout` – session termination
- `account_locked` – after failed attempts

**2FA Events**:
- `2fa_enabled` / `2fa_disabled` – configuration changes
- `2fa_verified` / `2fa_failed` – verification attempts
- `backup_codes_generated` / `backup_code_used` – backup code lifecycle

**Account Events**:
- `user_created` – new account registration
- `password_changed` – password updates

#### Log Entry Structure

Each audit entry includes:
- Timestamp
- Actor (user performing action)
- Action type with severity (INFO/WARNING/CRITICAL)
- IP address and user agent
- Target user (if different from actor)
- Structured metadata

#### SIEM-Ready Format

Audit logs are structured for export to SIEM systems:
- JSON format compatible with Elasticsearch, Splunk, etc.
- Correlation IDs for request tracing
- Severity levels for alerting

*Note: SIEM integration is not pre-configured; administrators can export logs to their preferred system.*

#### Retention

| Log Type | Minimum Retention |
|----------|-------------------|
| Authentication | 2 years |
| Recovery events | 7 years |
| Admin actions | 7 years |

**Related Documentation**:
- [Audit Logging and Notifications](/docs/audit-logging-and-notifications/)

---

## A10:2021 – Server-Side Request Forgery (SSRF)

**Risk**: Server making requests to unintended locations.

### Controls Implemented

#### URL Validation

- User-provided URLs validated before use
- Allowlists for external service integrations
- Internal network addresses blocked

#### Network Segmentation

- Database not accessible from internet
- Vault (if used) on private network
- Outbound requests limited to known services

#### Container Isolation

- Docker containers with minimal privileges
- Network policies restrict inter-container communication
- No privileged containers

---

## Continuous Improvement

### Security Scanning Schedule

| Scan Type | Frequency | Tool |
|-----------|-----------|------|
| Dependency vulnerabilities | Daily | pip-audit (GitHub Actions) |
| Secrets detection | Every commit | GitGuardian (pre-commit) |
| Static analysis | Every PR | CodeQL (GitHub Actions) |
| Container scanning | On build | Docker Scout (optional) |


### Reporting Security Issues

If you discover a security vulnerability:

1. **Do not** open a public issue
2. Email security@checktick.uk with details
3. Include steps to reproduce
4. Allow 90 days for fix before disclosure

We follow responsible disclosure and credit researchers who report valid issues.

---

## References

- [OWASP Top 10 (2021)](https://owasp.org/Top10/)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [NHS DSPT](https://www.dsptoolkit.nhs.uk/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
