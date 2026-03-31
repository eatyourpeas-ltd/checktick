---
title: "Software Asset & Configuration Register"
category: dspt-4-managing-access
---

# Software Asset & Configuration Register

**Version:** 2.0
**Last Updated:** March 2026
**Owner:** CTO

## 1. Asset Management Process

{{ platform_name }} tracks software assets through a Managed Repository model:

* **Discovery:** All new software or libraries must be approved by the CTO
  before being added to `pyproject.toml` or `package.json`. No dependency
  may be added to production without CTO review via the pull request process.
* **Version Tracking:** Automated via GitHub Dependency Graph and Dependabot,
  which monitors all declared dependencies continuously against known
  vulnerability databases. Any vulnerable dependency causes an immediate
  CI/CD pipeline failure blocking deployment.
* **Vulnerability Scanning:** `pip-audit` runs on every push, pull request,
  and daily at 06:00 UTC. CodeQL scans all application code on every commit.
  EatYourPeas Ltd is a registered NCSC Early Warning subscriber, providing
  direct notification of relevant threats and advisories.
* **Audit:** A manual reconciliation of this register is performed quarterly
  to ensure decommissioned tools are removed and version numbers are current.

---

## 2. Core Application Dependencies (Production)

Sourced from `pyproject.toml` — managed via Poetry. All versions are
locked in `poetry.lock` for reproducible builds.

| Asset Name | Category | Version Constraint | Purpose |
| :--- | :--- | :--- | :--- |
| **Python** | Runtime | >=3.10, <3.13 | Application runtime |
| **Django** | Web Framework | ~5.2.12 | Core application framework |
| **django-environ** | Configuration | ^0.11.2 | Environment variable management |
| **psycopg2-binary** | Database Driver | ^2.9.9 | PostgreSQL connectivity |
| **Jinja2** | Templating | ^3.1.4 | Template rendering |
| **django-cors-headers** | Security | ^4.4.0 | CORS policy enforcement |
| **whitenoise** | Static Files | ^6.7.0 | Static file serving |
| **django-axes** | Security | ^8.1.0 | Brute-force protection / account lockout |
| **django-ratelimit** | Security | ^4.1.0 | API rate limiting |
| **cryptography** | Encryption | ^46.0.6 | AES-256-GCM field encryption |
| **itsdangerous** | Security | ^2.2.0 | Signed token generation |
| **PyYAML** | Serialisation | ^6.0.2 | Configuration parsing |
| **nhs-number** | NHS | ^1.3.6 | NHS number validation |
| **djangorestframework** | API | ^3.15.2 | REST API framework |
| **django-csp** | Security | ^4.0 | Content Security Policy headers |
| **gunicorn** | WSGI Server | ^22.0.0 | Production application server |
| **djangorestframework-simplejwt** | Authentication | ^5.3.1 | JWT token management |
| **markdown** | Content | ^3.6 | Markdown rendering |
| **pymdown-extensions** | Content | ^10.0 | Extended Markdown support |
| **pygments** | Syntax | ^2.18.0 | Code highlighting (1 active CVE — local only, monitored) |
| **inflection** | Utilities | ^0.5.1 | String inflection |
| **uritemplate** | API | ^4.1.1 | URI template handling |
| **mozilla-django-oidc** | Authentication | ^4.0.1 | OIDC/SSO integration |
| **beautifulsoup4** | Parsing | ^4.12.0 | HTML parsing |
| **requests** | HTTP | ^2.33.0 | HTTP client |
| **hvac** | Vault | ^2.4.0 | HashiCorp Vault client |
| **pillow** | Imaging | ^12.1.1 | Image processing |
| **qrcode** | 2FA | ^8.0 | QR code generation for TOTP |
| **django-otp** | Authentication | ^1.6.3 | TOTP/MFA support |
| **marshmallow** | Serialisation | ^3.26.2 | Data validation and serialisation |

### Active Vulnerability Exceptions

| Dependency | CVE | Justification | Review Date |
| :--- | :--- | :--- | :--- |
| `pygments` | CVE-2026-4539 | Local-access-only ReDoS in `AdlLexer`. Not network-exploitable. No upstream fix available. Monitoring PyPI for patch. | 27/04/2026 |

---

## 3. Development Dependencies

Used in development and CI/CD pipeline only. Not present in production
container images.

| Asset Name | Category | Version Constraint | Purpose |
| :--- | :--- | :--- | :--- |
| **pytest** | Testing | ^8.3.2 | Test runner |
| **pytest-django** | Testing | ^4.8.0 | Django test integration |
| **pytest-xdist** | Testing | ^3.5.0 | Parallel test execution |
| **pytest-env** | Testing | ^1.1.5 | Environment variable injection for tests |
| **pytest-playwright** | Testing | ^0.6.2 | End-to-end browser testing |
| **axe-playwright-python** | Accessibility | ^0.1.5 | Automated accessibility testing |
| **ruff** | Code Quality | ^0.15.6 | Linting |
| **black** | Code Quality | ^26.3.1 | Code formatting |
| **isort** | Code Quality | ^8.0.1 | Import sorting |
| **django-stubs** | Type Checking | ^5.0.4 | Django type annotations |
| **virtualenv** | Environment | ^20.36.1 | Virtual environment management |
| **pip-audit** | Security | ^2.10.0 | Dependency vulnerability scanning |

---

## 4. Frontend Build Dependencies

Managed via `package.json`. Used at build time only to generate compiled
CSS. No JavaScript framework is shipped to the browser.

| Asset Name | Category | Version Constraint | Purpose |
| :--- | :--- | :--- | :--- |
| **Tailwind CSS** | CSS Framework | ^4.1.17 | Utility-first CSS generation |
| **@tailwindcss/cli** | Build Tool | ^4.1.17 | CSS compilation |
| **@tailwindcss/typography** | CSS Plugin | ^0.5.19 | Prose typography styles |
| **DaisyUI** | Component Library | ^5.4.7 | UI component themes |

---

## 5. Self-Hosted JavaScript Assets

Served from `checktick_app/static/js/` with SHA-384 Subresource Integrity
(SRI) verification. No external CDN calls are made in production.

| Asset Name | Version | SRI Verified | Purpose |
| :--- | :--- | :--- | :--- |
| **ReDoc** | 2.5.2 | ✅ Yes | API documentation rendering |
| **axe-core** | 4.11.1 | ✅ Yes | Accessibility testing |
| **SortableJS** | 1.15.7 | ✅ Yes | Drag-and-drop UI |

---

## 6. Infrastructure & Platform Services

| Asset Name | Category | Version / Config Method | Hosting |
| :--- | :--- | :--- | :--- |
| **Northflank** | PaaS / Orchestration | Northflank console + API | Northflank |
| **PostgreSQL** | Database | 15.x — Northflank managed addon | Northflank |
| **HashiCorp Vault** | Secret Management | 1.21.1 — Northflank container service | Northflank |
| **Ubuntu LTS** | Base OS (Containers) | 22.04 | Northflank |
| **GitHub** | Version Control / CI | Enterprise Cloud | GitHub |
| **Gunicorn** | WSGI Server | ^22.0.0 (see above) | Northflank |

---

## 7. Approved Staff Software (EatYourPeas Ltd Devices)

All software installed on staff devices must be pre-approved by the CTO.
This satisfies the Cyber Essentials Plus requirement for controlled
software installation.

### 7.1 Approval Process

1. Staff member identifies need for new software
2. CTO evaluates security posture, data handling, and business necessity
3. CTO adds approved software to this register
4. Installation permitted only from official sources (App Store, identified
   developers, Google Play Store)

### 7.2 Approved Software List

| Software Name | Category | Platforms | Business Purpose | Vendor | Review Date |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Visual Studio Code** | Development IDE | macOS, Windows | Code editing | Microsoft | Jan 2026 |
| **Docker Desktop** | Container Platform | macOS, Windows | Local development | Docker Inc | Jan 2026 |
| **Postman** | API Testing | macOS, Windows | API development | Postman Inc | Jan 2026 |
| **Bitwarden** | Password Manager | macOS, Windows, iOS, Android | Credential storage | Bitwarden Inc | Jan 2026 |
| **Signal** | Secure Messaging | iOS, Android | Encrypted communications | Signal Foundation | Jan 2026 |
| **Chrome / Safari / Edge** | Web Browser | macOS, Windows, iOS, Android | Web access | Google/Apple/Microsoft | Jan 2026 |
| **GPG / GnuPG** | Encryption | macOS, Windows | Code signing | GnuPG | Jan 2026 |
| **Git** | Version Control | macOS, Windows | Source code management | Software Freedom Conservancy | Jan 2026 |

### 7.3 Prohibited Software Categories

* Remote access or screen sharing tools not explicitly approved
* Consumer file sharing services (OneDrive personal, Google Drive personal,
  Dropbox) for any business or patient data
* Cryptocurrency mining software
* Penetration testing tools on production systems
* Software that disables security features
* Pirated or unlicensed software
* Software from unverified or unknown sources

### 7.4 Technical Enforcement

* **macOS:** Gatekeeper restricts installation to App Store and identified
  developers
* **Windows:** SmartScreen blocks unrecognised or unsigned applications
* **iOS/Android:** App Store / Google Play only; jailbreaking and rooting
  prohibited
* **Administrative controls:** Standard user accounts prevent unauthorised
  software installation on all devices

---

## 8. Configuration Baseline

All assets are configured in accordance with the
{{ platform_name }} Infrastructure Hardening Standard:

* All administrative accounts protected by MFA with zero exceptions
* Non-essential ports and services disabled by default on all infrastructure
* Production data encrypted at rest (AES-256-GCM) and in transit (TLS 1.2+)
* No default or vendor-supplied credentials retained on any system
* All configuration changes managed via pull request review and logged in
  the Infrastructure Technical Change Log
