---
title: Security Overview
category: security
priority: 0
---

# Security Overview

CheckTick implements comprehensive security controls aligned with the [OWASP Top 10 (2021)](https://owasp.org/Top10/) to protect healthcare data. This document provides an overview of our security architecture and maps features to OWASP categories.

CheckTick is committed to **UK Data Sovereignty**; we intentionally prioritize UK-resident infrastructure and application-layer defenses over US-based interception services.

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

- **Organisation level**: Owner, Admin, Creator, Viewer roles
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

**Risk**: SQL injection, command injection, XSS, or other code injection attacks.

### Controls Implemented

#### SQL Injection Prevention

- Django ORM used exclusively (no raw SQL)
- Parameterized queries for all database operations
- Input validation on all user-supplied data

#### Template Injection Prevention

- Django templates with autoescaping enabled by default
- User content sanitized before display (see XSS Prevention below)
- CSP headers restrict inline script execution

#### Command Injection Prevention

- No shell command execution from user input
- File operations use safe path handling
- Subprocess calls avoided; pure Python implementations preferred

#### XSS Prevention

Django's template auto-escaping provides the primary defence. Additional sanitization layers protect the surfaces where content is rendered via `|safe` or placed in JSON contexts.

##### Content Security Policy

CheckTick uses `django-csp` (v4+) with per-request nonces to restrict which scripts may execute:

```python
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src":  ("'self'",),
        "script-src":   ("'self'", "https://cdn.jsdelivr.net",
                         "https://js.hcaptcha.com", "https://*.hcaptcha.com",
                         # Two SHA-256 hashes for known inline snippets
                         "'sha256-VgCjwSQ...'", "'sha256-Ern26...'",
                         CSP_NONCE),          # per-request nonce (django-csp 4.0+)
        "style-src":    ("'self'", "'unsafe-inline'",   # required: HTMX + DaisyUI
                         "https://fonts.googleapis.com", "https://*.hcaptcha.com"),
        "font-src":     ("'self'", "https://fonts.gstatic.com", "data:"),
        "img-src":      ("'self'", "data:"),
        "connect-src":  ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com"),
        "frame-src":    ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com"),
        "frame-ancestors": ("'self'",),   # DENY in production
    }
}
```

- Every server-rendered `<script>` tag injects the request-scoped nonce; scripts without it are blocked by the browser.
- `style-src: 'unsafe-inline'` is intentionally retained because HTMX and DaisyUI rely on inline styles. CSS-context injection is mitigated via server-side sanitization (see below) rather than CSP.

##### Server-Side CSS Sanitization

Survey and organisation branding allows owners to supply custom CSS themes. Three helper functions in `checktick_app/core/theme_utils.py` gate all surfaces where this CSS is rendered:

| Helper | Strips | Applied at |
|--------|--------|-----------|
| `sanitize_css_block(css)` | `<` `>` characters | Read-time before rendering theme blocks |
| `_sanitize_css_value(val)` | `<` `>` `{` `}` `;` `url()` `http(s)://` | Individual CSS property values |
| `sanitize_font_family(val)` | `{` `}` `;` `url()` protocol prefixes | Font family strings at write-time |

Sanitization is applied at both **write time** (view layer, before storage) and **read time** (context processors and view functions, before template rendering). This defence-in-depth approach means malicious values stored before the fix was deployed are still scrubbed on output.

##### Input Sanitization for Builder Content

Survey question text, option labels, and group names are passed through `django.utils.html.strip_tags()` before storage so that HTML markup cannot be re-emitted via the `|safe` builder payload filter.

Font CSS URL fields reject any value that does not begin with `http://` or `https://`, blocking `javascript:` and `data:` URI injection via `<link>` elements.

##### Survey Answer Storage

Respondent answers are stored in a `JSONField` on `SurveyResponse`. They are rendered back to owners only via:

- **CSV export** (`Content-Disposition: attachment`) — not an HTML surface.
- **Response insights chart** — option labels are Django-auto-escaped in the template (`{{ option.label }}`); no `|safe` filter is applied.
- **Progress restore** — loaded via Django's `json_script` filter into a `<script type="application/json">` element; JavaScript restores values using `.value =` (property assignment), never `innerHTML`.

CSV formula injection (values beginning with `=`, `@`, `+`, `-`) is blocked at export time so spreadsheet applications cannot execute embedded formulas.

##### Attack Surface Reference

| Surface | Attack Class | Fix Applied |
|---------|-------------|-------------|
| S1–S8: Brand/org theme CSS | CSS injection → style breakout | `sanitize_css_block` + `sanitize_font_family` in context processor and `update_branding` view |
| S9: Question text (builder) | Stored XSS via `|safe` payload | `strip_tags` in `_parse_builder_question_form` |
| S10: Option labels (builder) | Stored XSS via `|safe` payload | `strip_tags` on each option label |
| S11: Group name (builder) | Stored XSS via HTMX response | `strip_tags` in `builder_group_create` |
| S12: Survey-level theme CSS | CSS injection in dashboard/respondent views | `sanitize_css_block` at read-time in view context |
| S13: Font CSS URL | `javascript:`/`data:` URI injection | Protocol allowlist in `survey_style_update` |
| S14: Theme CSS in respondent views | CSS injection against anonymous respondents | `sanitize_css_block` in `survey_take`/`survey_detail` views |
| S15: CSV formula injection | Spreadsheet formula execution | Formula prefix stripping in `_format_answer_for_export` |

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
# Content Security Policy (django-csp 4.0+ dict format)
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src":     ("'self'",),
        "script-src":      ("'self'", "https://cdn.jsdelivr.net",
                            "https://js.hcaptcha.com", "https://*.hcaptcha.com",
                            "'sha256-...'",   # known inline hashes
                            CSP_NONCE),       # per-request nonce
        "style-src":       ("'self'", "'unsafe-inline'",
                            "https://fonts.googleapis.com", "https://*.hcaptcha.com"),
        "font-src":        ("'self'", "https://fonts.gstatic.com", "data:"),
        "img-src":         ("'self'", "data:"),
        "connect-src":     ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com"),
        "frame-src":       ("'self'", "https://hcaptcha.com", "https://*.hcaptcha.com"),
        "frame-ancestors": ("'self'",),
    }
}

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

---

## National Cyber Security Centre (NCSC) Integration

CheckTick is registered for and actively utilizes the **NCSC Early Warning Service**.

* **Threat Intelligence:** We receive automated notifications from the NCSC regarding malicious activity, compromised credentials, or vulnerabilities detected on our registered UK IP addresses and domains.
* **Triage Process:** Critical alerts from the NCSC are triaged by the CTO within 4 hours.
* **National Grid:** This integration ensures CheckTick is connected to the UK's national cyber defense infrastructure, providing an advanced layer of threat detection.

---

## Sovereign Advanced Threat Protection (ATP)

In alignment with DSPT Standard 8.3, CheckTick manages an active ATP capability through application-layer and platform-native tools, ensuring data never leaves UK jurisdiction for security processing.

| Component | Technology | Role |
|-----------|------------|------|
| **Intrusion Detection** | `django-axes` | Actively blocks brute-force IPs and accounts after 5 failed attempts. |
| **Rate Limiting** | `django-ratelimit` | Prevents application-layer DoS and automated scraping. |
| **Threat Feeds** | NCSC Early Warning | National-level intelligence on infrastructure threats. |
| **Static Analysis** | GitHub CodeQL | Continuous automated scanning for 0-day logic flaws. |
| **Secrets Protection** | `ggshield` | Real-time prevention of credential leakage in the CI/CD pipeline. |

---

### Reporting Security Issues

If you discover a security vulnerability:

1. **Do not** open a public issue
2. Email security@checktick.uk with details
3. Include steps to reproduce
4. Allow 90 days for fix before disclosure

We follow responsible disclosure and credit researchers who report valid issues.

## Developer Environment Security Standard

### 1. Tooling & Patching

Because developer machines hold access tokens for GitHub and Northflank, they are treated as 'Remote Endpoints':

* **Automated OS Updates:** macOS is configured to install security response files automatically (Window: <7 days).
* **IDE & Tooling:** VS Code and Extensions are set to auto-update.
* **Git Client:** Checked monthly for security updates to prevent 'Clone-based' vulnerabilities.

### 2. Dependency Sync (Poetry)

We avoid 'Version Drift' between laptops and production:
* Local development must be performed within a virtual environment managed by `Poetry`.
* Running `poetry install` is a prerequisite for any local development session to ensure the local stack is patched to the latest approved versions in `pyproject.toml`.

### 3. Credential Protection

* **No Hardcoded Secrets:** Local `.env` files are added to `.gitignore`.
* **MFA:** Access to the GitHub repository and Northflank console requires Hardware/App-based MFA.
* **SSH Keys:** SSH keys used for Git pushes are stored in the macOS Keychain and protected by biometric/password lock.

---

## References

- [OWASP Top 10 (2021)](https://owasp.org/Top10/)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [NHS DSPT](https://www.dsptoolkit.nhs.uk/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [NCSC Early Warning Service](https://www.ncsc.gov.uk/information/early-warning-service)
