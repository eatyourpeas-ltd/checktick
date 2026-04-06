---
title: "Software Security Code of Practice (SSCoP) Assessment"
category: dspt-5-process-reviews
---

# Software Security Code of Practice (SSCoP) Assessment

- **Product:** CheckTick Survey Platform
- **Organisation:** Eatyourpeas Ltd
- **Assessment Date:** March 2026
- **Senior Responsible Owner:** {{ cto_name }} (CTO)
- **Governance Oversight:** {{ siro_name }} (SIRO)
- **Next Review:** March 2027

This assessment covers all 14 principles of the Government Software Security
Code of Practice (updated January 2026). CheckTick is classified as a software
developer and distributor and is therefore subject to all 14 principles.

---

## Theme 1: Secure design and development

This theme ensures that products are secure when first provided to customers, along with subsequent updates. The use of appropriate design and development practices reduces the likelihood of errors and the presence of vulnerabilities in software and updates.

### Principle 1.1 - Follow an established secure development framework

CheckTick follows a documented Secure Software Development Lifecycle (SSDLC) aligned with OWASP Top 10 (2021). The SSDLC covers threat modelling, secure coding practices, requirements capture, governance and roles, test strategy, data management, and configuration management. All code changes are managed through a pull request process requiring CTO review before merging to the main branch. The CI/CD pipeline enforces that no code reaches production without passing automated security gates.

**Status: Met**

#### Claim 1.1.1 - The development framework used is documented.

**Evidence:**

- Secure Software Development Lifecycle (SSDLC) Policy: [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Secure Development and Patching Policy: [checktick.uk/compliance/secure-development_and-patching-policy/](https://checktick.uk/compliance/secure-development_and-patching-policy/)
- SSCoP Assessment: [checktick.uk/compliance/software-security-assessment/](https://checktick.uk/compliance/software-security-assessment/)
- GitHub repository pull request history (branch protection rules enforcing mandatory CTO review on every merge): [github.com/eatyourpeas/checktick](https://github.com/eatyourpeas/checktick)

**Arguments:** The SSDLC Policy is the primary documented framework. As a two-person organisation, the framework simultaneously serves as process documentation and developer reference material. Its public availability on the compliance site provides transparency to all users (especially NHS organisations and health care professionals). The SSCoP Assessment cross-references the framework against the Code of Practice principles, providing a second layer of documentation.

#### Claim 1.1.2 - Developers are trained in the use of the framework and tools.

**Evidence:**

- Data Security & Protection Training Log 2025/26: [checktick.uk/compliance/training/](https://checktick.uk/compliance/training/)
- Training Needs Analysis & Communication Plan: [checktick.uk/compliance/training-needs-analysis/](https://checktick.uk/compliance/training-needs-analysis/)
- Training Evaluation Report 2025: [checktick.uk/compliance/training-evaluation/](https://checktick.uk/compliance/training-evaluation/)
- Caldicott Guardian Statement: [checktick.uk/compliance/caldicott-statement/](https://checktick.uk/compliance/caldicott-statement/)
- Cyber Essentials Plus certification (independent verification of staff security competence)

**Arguments:** Both founders have completed NHS Data Security Awareness Level 1 and Caldicott Guardian training, covering the regulatory context in which the framework operates. The CTO holds Cyber Essentials Plus certification and undertakes ongoing OWASP and Secure SDLC training. As a two-person organisation, training records cover 100% of development staff with no gaps. The Training Evaluation Report independently assesses training effectiveness.

#### Claim 1.1.3 - Tools are maintained and updated.

**Evidence:**

- Vulnerability and Patch Log (records all tool updates with dates and versions since November 2025): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)
- Software Asset and Configuration Register: [checktick.uk/compliance/software-assets/](https://checktick.uk/compliance/software-assets/)
- pyproject.toml in GitHub repository (all dev tools declared as versioned dependencies)
- GitHub Actions Security Scan workflow (pip-audit 2.10.0, CodeQL, Dependabot - all current as of March 2026)

**Arguments:** All development tools are declared as versioned dependencies in pyproject.toml and locked in poetry.lock, ensuring reproducible and auditable tool versions. Security scanning tools (ggshield) are isolated in pre-commit environments rather than production dependencies, preventing tool version constraints from blocking security updates to the application. The Vulnerability and Patch Log provides a dated history of every tool update applied. Dependency vulnerability scans are run daily and issues are posted automatically on GitHub.

#### Claim 1.1.4 - Items requiring configuration control are identified and version control is used.

**Evidence:**

- GitHub repository (private, branch-protected): [github.com/eatyourpeas/checktick](https://github.com/eatyourpeas/checktick)
- Infrastructure Technical Change Log: [checktick.uk/compliance/infrastructure-technical-change-log/](https://checktick.uk/compliance/infrastructure-technical-change-log/)
- Change Management Policy: [checktick.uk/compliance/change-management-policy/](https://checktick.uk/compliance/change-management-policy/)
- poetry.lock (pinned dependency manifest in version control)

**Arguments:** All application code, dependency versions (poetry.lock), and compliance documentation are version-controlled in GitHub. Branch protection rules ensure no change reaches main without mandatory CTO review. Infrastructure configuration changes that fall outside the Git-managed codebase are captured in the Infrastructure Technical Change Log. This provides a complete, immutable audit trail of every change made to the system.

#### Claim 1.1.5 - Requirements are captured and recorded.

**Evidence:**

- DPIA Procedure: [checktick.uk/compliance/dpia-procedure/](https://checktick.uk/compliance/dpia-procedure/)
- DPIA Summary (CheckTick Survey Platform): [checktick.uk/compliance/dpia-survey-platform/](https://checktick.uk/compliance/dpia-survey-platform/)
- SSDLC Policy (defines security requirements): [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Data Security & Protection Training Log: [checktick.uk/compliance/training/](https://checktick.uk/compliance/training/)

**Arguments:** Security and data protection requirements are formally captured through DPIAs conducted for all new processing activities. The SSDLC Policy defines the security requirements that must be met before any feature is deployed. NHS Data Security Awareness training ensures both developers understand the regulatory requirements governing health data processing, informing requirements capture from the outset of any new feature.

#### Claim 1.1.6 - Software is designed for user need.

**Evidence:**

- DPIA Procedure: [checktick.uk/compliance/dpia-procedure/](https://checktick.uk/compliance/dpia-procedure/)
- DPIA Summary (CheckTick Survey Platform): [checktick.uk/compliance/dpia-survey-platform/](https://checktick.uk/compliance/dpia-survey-platform/)
- Caldicott Guardian Statement: [checktick.uk/compliance/caldicott-statement/](https://checktick.uk/compliance/caldicott-statement/)
- Accessibility documentation: [checktick.uk/docs/accessibility/](https://checktick.uk/docs/accessibility/)
- Survey Translation documentation: [checktick.uk/docs/survey-translation/](https://checktick.uk/docs/survey-translation/)
- axe-playwright-python automated accessibility tests (run on every build in CI/CD pipeline)

**Arguments:** CheckTick is purpose-built for clinical survey collection in NHS settings. User need is informed by Caldicott Guardian principles ensuring data minimisation and proportionate processing. DPIAs are conducted for all new processing activities to ensure clinical utility justifies the scope of data collection. Accessibility is tested automatically on every build using axe-playwright-python, ensuring clinical users with accessibility needs are not excluded from the platform.

---

### Principle 1.2 - Understand the composition of the software and assess risks linked to the ingestion and maintenance of third-party components throughout the development lifecycle

All Python dependencies are declared in pyproject.toml and locked in poetry.lock. GitHub Dependabot and pip-audit monitor all dependencies continuously against known vulnerability databases. Any new dependency requires CTO approval via the pull request process. All self-hosted JavaScript assets are monitored weekly with SHA-384 SRI verification. The full dependency inventory is maintained in the Software Asset and Configuration Register. Third-party component risks are assessed and documented in the Vulnerability and Patch Log.

**Status: Met**

#### Claim 1.2.1 - All third-party components are identified and documented.

**Evidence:**

- Software Asset and Configuration Register: [checktick.uk/compliance/software-assets/](https://checktick.uk/compliance/software-assets/)
- pyproject.toml (Python dependencies with version constraints, in GitHub repository)
- package.json (JavaScript build dependencies)
- GitHub Dependency Graph (automated real-time inventory)
- CDN Libraries documentation (self-hosted JS assets): [checktick.uk/docs/cdn-libraries/](https://checktick.uk/docs/cdn-libraries/)

**Arguments:** All third-party components are explicitly declared in pyproject.toml and package.json with pinned version constraints. The Software Asset Register provides a human-readable inventory cross-referenced against the live codebase. GitHub Dependency Graph provides automated real-time inventory. Undeclared dependencies cannot enter the production environment as the CI/CD pipeline builds only from the locked dependency manifest (poetry.lock).

#### Claim 1.2.2 - Integrity of third-party components and updates is verified.

**Evidence:**

- CDN Libraries documentation (SRI hashes for all self-hosted JS assets): [checktick.uk/docs/cdn-libraries/](https://checktick.uk/docs/cdn-libraries/)
- GitHub Actions CDN Library Monitor workflow (weekly SRI recalculation, automated PR on change)
- Vulnerability and Patch Log (records SRI update history): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)
- GitGuardian (ggshield) pre-commit hook configuration in GitHub repository

**Arguments:** All self-hosted JavaScript assets (HTMX, ReDoc, SortableJS, axe-core) are verified using SHA-384 Subresource Integrity hashes computed from npm package bytes via npm pack, ensuring exact asset bytes are verified against a reproducible source rather than relying on CDN availability. GitGuardian pre-commit hooks detect any supply chain anomalies before they reach the repository. This approach eliminates CDN-based supply chain attack vectors entirely.

#### Claim 1.2.3 - Each third-party component is tested before being first deployed.

**Evidence:**

- GitHub Actions Security Scan workflow (pip-audit on every push and pull request)
- SSDLC Policy (test requirements for new dependencies): [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Pytest test suite (full suite runs on every PR)
- Playwright end-to-end test suite
- CodeQL static analysis (runs on every commit)

**Arguments:** All new dependencies must pass pip-audit vulnerability scanning before merging. The full automated test suite (Pytest and Playwright) runs against every pull request, verifying that new dependencies do not break existing functionality or introduce regressions. CodeQL static analysis checks for security issues introduced by new dependencies. The CI/CD pipeline blocks deployment if any check fails, providing a technical backstop to the review process.

#### Claim 1.2.4 - Third-party component updates are tested.

**Evidence:**

- Vulnerability and Patch Log (dated history of all dependency updates with verification status): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)
- GitHub Dependabot pull request history (automated update PRs triggering full test suite)
- GitHub Actions CI/CD pipeline logs

**Arguments:** All dependency updates are tested through the same automated pipeline as any other code change before merging. Dependabot raises pull requests for updates which trigger the full test suite automatically. No dependency update can be merged without passing all security and functional checks. The Vulnerability and Patch Log records the outcome and verification for every security-relevant update applied since November 2025, providing an auditable history.

#### Claim 1.2.5 - Processes are in place to manage and deploy updates to third-party components.s

**Evidence:**

- Patch Management Strategy: [checktick.uk/compliance/patch-management-strategy/](https://checktick.uk/compliance/patch-management-strategy/)
- SIRO-Approved Patching Approach: [checktick.uk/compliance/siro-patching-approval/](https://checktick.uk/compliance/siro-patching-approval/)
- Vulnerability Management Policy: [checktick.uk/compliance/vulnerability-management-policy/](https://checktick.uk/compliance/vulnerability-management-policy/)
- Vulnerability and Patch Log (active exception: pygments CVE-2026-4539, SIRO signed off 29/03/2026): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)

**Arguments:** CVSS-based remediation timelines ensure proportionate response: Critical within 48 hours, High within 7 days, Medium within 30 days. The CI/CD pipeline hard-blocks deployment if any vulnerability is present at any severity level, creating a technical enforcement backstop independent of human triage. The SIRO formally approves all exceptions and signs off any risk acceptance. Currently one low-risk exception exists (pygments CVE-2026-4539, local-access-only ReDoS, non-network-exploitable) with SIRO sign-off and monthly review.

---

### Principle 1.3 - Have a clear process for testing software and software updates before distribution.

All changes are tested through an automated test suite (Pytest and Playwright) before deployment. Security patches are applied in a staging environment and verified before production promotion. CodeQL static analysis runs on every commit. Automated RBAC negative testing verifies that permission boundaries are enforced correctly. Any test failure blocks the CI/CD pipeline preventing deployment.

**Status: Met**

#### Claim 1.3.1 - A test plan exists that covers all requirements and third-party components.

**Evidence:**

- SSDLC Policy (defines test strategy): [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Pytest test suite in GitHub repository (unit, integration, RBAC permission tests)
- Playwright end-to-end browser test suite
- axe-playwright-python accessibility test suite
- GitHub Actions CI/CD pipeline (automated test execution)

**Arguments:** The SSDLC Policy defines the test strategy covering all requirements and third-party components. The test suite includes unit tests, integration tests, RBAC permission tests, end-to-end browser tests, and automated accessibility tests. Critically, negative testing verifies that every restricted endpoint returns HTTP 403 to unauthorised users, directly testing access control requirements. Third-party components are covered by dependency vulnerability scanning running on every build.

#### Claim 1.3.2 - Execution of the test plan is automated and repeatable wherever possible.

**Evidence:**

- GitHub Actions Security Scan workflow (automated on every push, PR, and daily at 06:00 UTC)
- Continuous Patching Lifecycle Standard: [checktick.uk/compliance/continuous-patching-lifecycle/](https://checktick.uk/compliance/continuous-patching-lifecycle/)
- Automation Overview: [checktick.uk/compliance/automation-overview/](https://checktick.uk/compliance/automation-overview/)
- Vulnerability and Patch Log (zero-exception policy enforced since January 2026): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)

**Arguments:** The entire test suite runs automatically via GitHub Actions on every push and pull request with no manual step required for deployment. The zero-exception policy enforced since January 2026 means the pipeline cannot be bypassed even under time pressure. All test results are logged in GitHub Actions history providing a reproducible and timestamped audit trail of every test run.

#### Claim 1.3.3 - Defects identified during testing are addressed.

**Evidence:**

- Vulnerability and Patch Log (all security defects and resolutions since November 2025): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)
- Security Remediation Process: [checktick.uk/compliance/remediation-process/](https://checktick.uk/compliance/remediation-process/)
- GitHub Issues (Security label) in repository
- Internal Audit & Spot Check Log: [checktick.uk/compliance/internal-audit-spot-check-log/](https://checktick.uk/compliance/internal-audit-spot-check-log/)

**Arguments:** All security defects are logged as GitHub Issues with the Security label and must be linked to a remediation pull request. No issue may be closed without verified remediation evidence in the CI/CD pipeline. The Vulnerability and Patch Log provides a dated history of every security defect identified and resolved. The SIRO reviews this log quarterly to verify that all identified issues have been actioned and closed.

---

### Principle 1.4 - Follow secure by design and secure by default principles throughout the development lifecycle of the software.

Privacy by Design is applied throughout the development lifecycle. All survey response data is encrypted at field level using AES-256-GCM before reaching the database. MFA is enforced by default for all privileged accounts. API and firewall rules are set to deny-by-default. The Django admin interface is served from a non-default path. Content Security Policy headers are enforced. DPIAs are conducted for all new processing activities involving health data. Secure cookie flags (Secure; HttpOnly; SameSite=Lax) are enforced on all sessions.

**Status: Met**

#### Claim 1.4.1 - Techniques to understand how the software might be exploited (threat modelling) have been used in the design of the software.

**Evidence:**

- SSDLC Policy (OWASP Top 10 alignment): [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- DPIA Procedure: [checktick.uk/compliance/dpia-procedure/](https://checktick.uk/compliance/dpia-procedure/)
- DPIA Summary (CheckTick Survey Platform): [checktick.uk/compliance/dpia-survey-platform/](https://checktick.uk/compliance/dpia-survey-platform/)
- Penetration Test Remediation Response (AD24502): [checktick.uk/compliance/pentest-remediation-response-AD24502/](https://checktick.uk/compliance/pentest-remediation-response-AD24502/)
- Software Security Code of Practice Assessment: [checktick.uk/compliance/software-security-assessment/](https://checktick.uk/compliance/software-security-assessment/)

**Arguments:** OWASP Top 10 (2021) threat modelling is applied throughout the development lifecycle, addressing injection, broken access control, cryptographic failures, SSRF, and all other major web application threat categories. An external penetration test (AD24502) was conducted against a production-equivalent environment to provide independent validation of the threat model. All findings were remediated. DPIAs are conducted for all new processing activities involving health data, ensuring privacy threats are considered alongside security threats.

#### Claim 1.4.2 - Multi-factor authentication for privileged users of the software is enforced.

**Evidence:**

- Access Control Policy (Section 11): [checktick.uk/compliance/access-control/](https://checktick.uk/compliance/access-control/)
- Enhanced Acceptable Use Policy (signed by both named administrators 29/12/2025): [checktick.uk/compliance/enhanced-acceptable-use-policy/](https://checktick.uk/compliance/enhanced-acceptable-use-policy/)
- Authentication and Permissions documentation: [checktick.uk/docs/authentication-and-permissions/](https://checktick.uk/docs/authentication-and-permissions/)
- OIDC SSO Setup documentation: [checktick.uk/docs/oidc-sso-setup/](https://checktick.uk/docs/oidc-sso-setup/)

**Arguments:** MFA is technically enforced for all Data Custodian and Organisation Owner accounts within CheckTick. NHS Trust users authenticating via OIDC/SSO inherit their Trust's MFA enforcement - CheckTick does not weaken or bypass Trust-level authentication requirements. For infrastructure administrative accounts (GitHub, Northflank, Microsoft 365), MFA is enforced at the organisation/tenant level with zero exceptions. The Enhanced Acceptable Use Policy commits both named administrators personally to MFA maintenance.

#### Claim 1.4.3 - Default (and persistent) passwords are not used.

**Evidence:**

- Staff Password Policy: [checktick.uk/compliance/password-policy/](https://checktick.uk/compliance/password-policy/)
- Infrastructure Technical Change Log (records default credential changes on provisioning): [checktick.uk/compliance/infrastructure-technical-change-log/](https://checktick.uk/compliance/infrastructure-technical-change-log/)
- Cyber Essentials Plus certification (independent verification of zero-default policy)
- Hardware Asset Register: [checktick.uk/compliance/hardware-assets/](https://checktick.uk/compliance/hardware-assets/)

**Arguments:** The Staff Password Policy explicitly prohibits all default and vendor-supplied passwords across all systems and scopes. This was independently verified at Cyber Essentials Plus assessment. All infrastructure credentials are Bitwarden-generated unique high-entropy strings. Default credentials are changed on provisioning and the change is logged in the Infrastructure Technical Change Log. GitGuardian pre-commit hooks provide a technical backstop preventing any credential from being committed to the repository.

#### Claim 1.4.4 - Data input to the software is validated.

**Evidence:**

- Data Quality and Integrity Statement: [checktick.uk/compliance/data-quality-and-integrity/](https://checktick.uk/compliance/data-quality-and-integrity/)
- Encryption Technical Reference: [checktick.uk/docs/encryption-technical-reference/](https://checktick.uk/docs/encryption-technical-reference/)
- SSDLC Policy: [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Pytest test suite (input validation test cases in GitHub repository)

**Arguments:** Input validation operates at multiple layers: Django form validation at the point of entry, marshmallow serialisation validation at the API layer, and database-level integrity constraints via ACID-compliant PostgreSQL. AES-256-GCM authenticated encryption provides an additional integrity check - any unauthorised modification of encrypted data at rest is detectable. This multi-layer approach ensures data integrity is maintained even if one validation layer is bypassed. Negative testing verifies that invalid inputs are rejected at every endpoint.

#### Claim 1.4.5 - Credentials and sensitive data are securely stored.

**Evidence:**

- Encryption for Users documentation: [checktick.uk/docs/encryption-for-users/](https://checktick.uk/docs/encryption-for-users/)
- Key Management for Administrators documentation: [checktick.uk/docs/key-management-for-administrators/](https://checktick.uk/docs/key-management-for-administrators/)
- Vault Integration documentation: [checktick.uk/docs/vault/](https://checktick.uk/docs/vault/)
- Encryption Technical Reference: [checktick.uk/docs/encryption-technical-reference/](https://checktick.uk/docs/encryption-technical-reference/)
- Staff Password Policy: [checktick.uk/compliance/password-policy/](https://checktick.uk/compliance/password-policy/)
- Infrastructure Technical Change Log (Microsoft Graph API secret stored as encrypted Northflank environment variable, logged April 2026): [checktick.uk/compliance/infrastructure-technical-change-log/](https://checktick.uk/compliance/infrastructure-technical-change-log/)

**Arguments:** All survey response data containing patient-identifiable information is encrypted at field level using AES-256-GCM before reaching the database. Encryption keys are managed via HashiCorp Vault using a split-knowledge architecture where neither the Vault component nor the offline custodian component alone can decrypt data. Staff credentials are stored in Bitwarden. The Microsoft Graph API client secret is stored as an encrypted Northflank environment variable injected at runtime - it is not present in source code or version control. GitGuardian pre-commit hooks provide a technical backstop against accidental credential exposure.

---

## Theme 2: Build environment security

This theme ensures appropriate steps are taken to prevent the build environment from being accessed by a person (or machine) without a legitimate need. This helps prevent interference with the software during the build and release process. The 'build environment' refers to the environment where software is compiled, built and packaged ready for release. This should be logically or physically separate from areas where code is written and tested.

### Principle 2.1 - Protect the build environment against unauthorised access.

Access to GitHub (source control and CI/CD) and Northflank (production hosting) is restricted to named administrators only - Dr Simon Chapman (CTO) and Dr Serena Haywood (SIRO). Both accounts require MFA enforced at the organisation level. No third party or contractor has standing access to the build environment. Any temporary access is pre-approved, time-limited, and revoked immediately on completion. GitGuardian (ggshield) prevents secrets or credentials from entering the repository via pre-commit hooks.

**Status: Met**

#### Claim 2.1.1 - Roles are defined that specify the data and functionality that each role is allowed to access.

**Evidence:**

- Access Control Policy (Section 3 - RBAC table): [checktick.uk/compliance/access-control/](https://checktick.uk/compliance/access-control/)
- Information Governance: Roles and Responsibilities: [checktick.uk/compliance/roles-and-responsibilities/](https://checktick.uk/compliance/roles-and-responsibilities/)
- Authentication and Permissions documentation: [checktick.uk/docs/authentication-and-permissions/](https://checktick.uk/docs/authentication-and-permissions/)

**Arguments:** GitHub organisation enforces role-based access with admin, write, and read roles clearly defined. Northflank project roles restrict console access to named administrators only. No service account has write access to production secrets or infrastructure configuration. As a two-person organisation, the entire privileged access population is fully enumerated and individually named, making role definition and enforcement straightforward to verify.

#### Claim 2.1.2 - Users of the build environment are required to authenticate on a regular basis.

**Evidence:**

- Access Control Policy (Section 11 - session persistence): [checktick.uk/compliance/access-control/](https://checktick.uk/compliance/access-control/)
- Enhanced Acceptable Use Policy: [checktick.uk/compliance/enhanced-acceptable-use-policy/](https://checktick.uk/compliance/enhanced-acceptable-use-policy/)

**Arguments:** GitHub and Northflank both enforce session expiry and require re-authentication after inactivity. MFA is required on every login - there is no persistent session bypass mechanism. The Enhanced Acceptable Use Policy explicitly prohibits using Stay Logged In features on shared or public networks. This ensures that build environment access cannot persist undetected after a legitimate session has ended, limiting the window of exposure from a compromised device.

#### Claim 2.1.3 - Users of the build environment are issued with credentials bound to their role.

**Evidence:**

- Enhanced Acceptable Use Policy (signed by both named administrators, 29/12/2025): [checktick.uk/compliance/enhanced-acceptable-use-policy/](https://checktick.uk/compliance/enhanced-acceptable-use-policy/)
- Access Control Policy (Section 8 - authorised devices): [checktick.uk/compliance/access-control/](https://checktick.uk/compliance/access-control/)
- Access Audit Log: [checktick.uk/compliance/access-audit-logs/](https://checktick.uk/compliance/access-audit-logs/)

**Arguments:** Both named administrators (Dr Simon Chapman and Dr Serena Haywood) hold individually named accounts on GitHub and Northflank that are bound to their specific roles. No shared or generic accounts exist. Credentials are independently revocable per individual, ensuring that departure of one administrator does not require rotation of shared credentials. The Enhanced Acceptable Use Policy documents personal accountability for these credentials and is signed by both individuals.

#### Claim 2.1.4 - Credentials are securely managed and stored.

**Evidence:**

- Staff Password Policy: [checktick.uk/compliance/password-policy/](https://checktick.uk/compliance/password-policy/)
- Vault Integration documentation: [checktick.uk/docs/vault/](https://checktick.uk/docs/vault/)
- Infrastructure Technical Change Log (Microsoft Graph API secret in Northflank environment variables): [checktick.uk/compliance/infrastructure-technical-change-log/](https://checktick.uk/compliance/infrastructure-technical-change-log/)
- GitGuardian (ggshield) pre-commit hook configuration in GitHub repository

**Arguments:** Staff credentials are stored in Bitwarden, which is itself MFA-protected. Infrastructure secrets (database credentials, Vault tokens) are stored in HashiCorp Vault. The Microsoft Graph API client secret is stored as an encrypted Northflank environment variable injected at runtime, not in source code or version control. GitGuardian scans every commit for accidentally included credentials. No credential is stored in plain text anywhere in the build or deployment pipeline.

#### Claim 2.1.5 - Credentials are multi factor.

**Evidence:**

- Enhanced Acceptable Use Policy: [checktick.uk/compliance/enhanced-acceptable-use-policy/](https://checktick.uk/compliance/enhanced-acceptable-use-policy/)
- Access Control Policy (Section 11): [checktick.uk/compliance/access-control/](https://checktick.uk/compliance/access-control/)
- Cyber Essentials Plus certification (independent verification of MFA enforcement)

**Arguments:** MFA is mandatory on all GitHub accounts with FIDO2/WebAuthn hardware token authentication preferred and TOTP as a fallback. MFA is mandatory on all Northflank accounts. GitHub organisation policy enforces MFA at the organisation level - any account without MFA active cannot be a member of the CheckTick GitHub organisation. This provides a technical enforcement backstop independent of individual policy compliance. Cyber Essentials Plus independently verified MFA enforcement across all in-scope accounts.

---

### Principle 2.2 - Control and log changes to the build environment.

All changes to the build environment are managed through pull requests requiring CTO review and automated security gate approval before merging. The Git history provides an immutable timestamped record of every change, who proposed it, who approved it, and the automated scan results. Northflank infrastructure changes are logged in the Infrastructure Technical Change Log. No direct changes to the production environment are permitted outside the CI/CD pipeline.

**Status: Met**

#### Claim 2.2.1 - Access and changes to the build environment are logged.

**Evidence:**

- Infrastructure Technical Change Log: [checktick.uk/compliance/infrastructure-technical-change-log/](https://checktick.uk/compliance/infrastructure-technical-change-log/)
- Logging and Audit Policy: [checktick.uk/compliance/logging-policy/](https://checktick.uk/compliance/logging-policy/)
- Access Audit Log: [checktick.uk/compliance/access-audit-logs/](https://checktick.uk/compliance/access-audit-logs/)
- GitHub audit log (Enterprise Cloud, accessible to organisation administrators)
- Northflank platform audit log

**Arguments:** GitHub's immutable audit log records all repository access, code pushes, pull request approvals, merges, and configuration changes with full timestamp and actor attribution. Northflank's audit log records all infrastructure configuration changes. The Infrastructure Technical Change Log provides a human-readable summary of significant changes reviewed by named administrators. These logs are reviewed quarterly by the CTO and by the SIRO at bi-annual infrastructure audits.

#### Claim 2.2.2 - Only authorised personnel can make changes to the build environment.

**Evidence:**

- Change Management Policy: [checktick.uk/compliance/change-management-policy/](https://checktick.uk/compliance/change-management-policy/)
- SSDLC Policy (pull request requirement): [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Access Control Policy (Section 12 - third-party access): [checktick.uk/compliance/access-control/](https://checktick.uk/compliance/access-control/)
- GitHub branch protection rules (in repository settings)

**Arguments:** Branch protection rules prevent any direct push to the main branch - all changes require a pull request with CTO review and approval. The CI/CD security gates must pass before any merge is permitted. Only the two named administrators can modify Northflank infrastructure settings. No third party or contractor has standing access to the build environment. Any temporary access requires pre-approval, is time-limited, and is revoked immediately on task completion.

#### Claim 2.2.3 - Logs are auditable and retained for an agreed period.

**Evidence:**

- Logging and Audit Policy: [checktick.uk/compliance/logging-policy/](https://checktick.uk/compliance/logging-policy/)
- Access Audit Log: [checktick.uk/compliance/access-audit-logs/](https://checktick.uk/compliance/access-audit-logs/)
- Data and Records Management Policy (7-year retention): [checktick.uk/compliance/data-policy/](https://checktick.uk/compliance/data-policy/)

**Arguments:** Application-level audit logs are retained for 7 years in line with the NHS Records Management Code of Practice. GitHub Enterprise Cloud audit logs are retained per GitHub's enterprise retention policy. The Logging and Audit Policy defines retention periods for all log categories. The Access Audit Log is formally reviewed quarterly by the SIRO providing regular human oversight of the automated log retention and ensuring logs remain usable for audit purposes throughout the retention period.

#### Claim 2.2.4 - The confidentiality and integrity of logs is protected.

**Evidence:**

- Logging and Audit Policy: [checktick.uk/compliance/logging-policy/](https://checktick.uk/compliance/logging-policy/)
- Security Monitoring and Logging Standard: [checktick.uk/compliance/monitoring-standard/](https://checktick.uk/compliance/monitoring-standard/)
- Automated Security and Integrity Monitoring: [checktick.uk/compliance/automation-overview/](https://checktick.uk/compliance/automation-overview/)

**Arguments:** GitHub audit logs are protected by GitHub's own infrastructure integrity controls and cannot be modified by repository administrators. Northflank platform logs are protected by platform-level access controls. Application logs are written in an append-only SIEM-ready format. Application service accounts have no access to audit logs, ensuring a compromise of the application cannot result in log tampering or deletion.

---

## Theme 3: Secure deployment and maintenance

This theme ensures that the software remains secure throughout its lifetime. The use of appropriate mechanisms and processes for managing and deploying updates to software reduces the likelihood of errors and vulnerabilities persisting in the software.

### Principle 3.1 - Distribute software securely to customers

CheckTick is distributed as a SaaS platform over HTTPS with TLS 1.2 or better enforced on all connections. HSTS is enforced at the application layer. All data in transit is encrypted. No insecure delivery mechanism is used. Container images are rebuilt from a clean base on every deployment ensuring a known and consistent production state.

**Status: Met**

#### Claim 3.1.1 - The integrity of software (including updates) can be verified in the customer environment.

**Evidence:**

- Data in Transit Security Standard: [checktick.uk/compliance/encryption-transit/](https://checktick.uk/compliance/encryption-transit/)
- CDN Libraries documentation (SRI hashes): [checktick.uk/docs/cdn-libraries/](https://checktick.uk/docs/cdn-libraries/)
- Infrastructure Hardening and Configuration Standard: [checktick.uk/compliance/infrastructure-hardening/](https://checktick.uk/compliance/infrastructure-hardening/)
- Northflank deployment pipeline (container image verification on every deployment)

**Arguments:** CheckTick is SaaS - customers access the platform via their browser and do not install any software locally. Software integrity is maintained centrally by Eatyourpeas Ltd rather than requiring customer-side verification. All code is deployed via Northflank from the verified GitHub repository, with container images rebuilt from a clean base on every deployment. SHA-384 SRI hashes verify the integrity of all self-hosted JavaScript assets served to the browser. TLS 1.2+ on all connections ensures integrity in transit.

#### Claim 3.1.2 - Software (including updates) is distributed over trusted channels.

**Evidence:**

- Data in Transit Security Standard: [checktick.uk/compliance/encryption-transit/](https://checktick.uk/compliance/encryption-transit/)
- Network Security and Infrastructure Statement: [checktick.uk/compliance/network-security/](https://checktick.uk/compliance/network-security/)
- Infrastructure Hardening and Configuration Standard: [checktick.uk/compliance/infrastructure-hardening/](https://checktick.uk/compliance/infrastructure-hardening/)

**Arguments:** As SaaS, all software is distributed via HTTPS with TLS 1.2+ enforced and HSTS preventing protocol downgrade. There are no alternative download channels, package distributions, or installers. Customers receive updates automatically through the platform without any action required on their part. The Northflank CI/CD pipeline ensures only reviewed and security-scanned code is deployed, maintaining the integrity of the distribution channel from source to production.

---

### Principle 3.2 - Implement and publish an effective vulnerability disclosure process.

A vulnerability disclosure process is in place. Security researchers and customers can report vulnerabilities via security@checktick.uk. Reports are triaged by the CTO, risk-assessed, and remediated according to CVSS-based timelines. Reporters receive acknowledgement and are kept informed of remediation progress. The process is documented in our Vulnerability Management Policy.

**Status: Met**

#### Claim 3.2.1 - A vulnerability disclosure policy and process is published.

**Evidence:**

- Vulnerability Management Policy: [checktick.uk/compliance/vulnerability-management-policy/](https://checktick.uk/compliance/vulnerability-management-policy/)
- Security Remediation Process: [checktick.uk/compliance/remediation-process/](https://checktick.uk/compliance/remediation-process/)
- NCSC Early Warning service (registered subscriber): [ncsc.gov.uk/information/early-warning-service](https://ncsc.gov.uk/information/early-warning-service)
- Contact: security@checktick.uk

**Arguments:** The vulnerability disclosure process is publicly available via the Vulnerability Management Policy and the security@checktick.uk contact. As a SaaS platform serving NHS organisations processing patient data, maintaining an accessible and responsive disclosure channel is essential for trust with health and care customers. Eatyourpeas Ltd is a registered NCSC Early Warning subscriber, providing proactive national threat intelligence in addition to reactive disclosure handling.

#### Claim 3.2.2 - The vulnerability disclosure process describes how to confidentially report vulnerabilities.

**Evidence:**

- Vulnerability Management Policy: [checktick.uk/compliance/vulnerability-management-policy/](https://checktick.uk/compliance/vulnerability-management-policy/)
- Incident Reporting and Escalation Procedure: [checktick.uk/compliance/incident-reporting-procedure/](https://checktick.uk/compliance/incident-reporting-procedure/)
- Contact: security@checktick.uk

**Arguments:** security@checktick.uk provides a direct confidential channel to the CTO for responsible disclosure. The Vulnerability Management Policy commits to acknowledgement of reports and ongoing communication with reporters throughout the remediation process. The SIRO is notified of all significant disclosures to ensure governance oversight. Confidential reporting is particularly important given that CheckTick processes health data and any vulnerability could have patient safety implications.

---

### Principle 3.3 - Have processes and documentation in place for proactively detecting, prioritising and managing vulnerabilities in software components.

Vulnerabilities are detected through four continuous automated mechanisms: pip-audit running daily at 06:00 UTC and on every push and pull request, GitHub Dependabot monitoring the full dependency graph continuously, CodeQL static analysis on every commit, and a weekly CDN Library Monitor for self-hosted JavaScript assets. Vulnerabilities are triaged by CVSS score with documented remediation timelines - critical within 48 hours, high within 7 days, medium within 30 days. All findings and remediations are recorded in the Vulnerability and Patch Log. Eatyourpeas Ltd is a registered NCSC Early Warning subscriber.

**Status: Met**

#### Claim 3.3.1 - Knowledge of public vulnerabilities is kept up to date.

**Evidence:**

- Vulnerability and Patch Log (complete history since November 2025): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)
- Continuous Patching Lifecycle Standard: [checktick.uk/compliance/continuous-patching-lifecycle/](https://checktick.uk/compliance/continuous-patching-lifecycle/)
- Automation Overview (daily scanning at 06:00 UTC): [checktick.uk/compliance/automation-overview/](https://checktick.uk/compliance/automation-overview/)
- NCSC Early Warning service (registered subscriber)

**Arguments:** Vulnerability knowledge is maintained through four continuous automated mechanisms: GitHub Dependabot (real-time dependency monitoring), pip-audit (daily CVE scanning at 06:00 UTC and on every push), CodeQL (static analysis on every commit), and NCSC Early Warning service (national threat intelligence). This multi-source approach ensures new CVE disclosures are identified within 24 hours of publication and actioned within the documented CVSS-based remediation timelines.

#### Claim 3.3.2 - A vulnerability management plan exists that assesses and prioritises responses to vulnerabilities.

**Evidence:**

- Vulnerability Management Policy: [checktick.uk/compliance/vulnerability-management-policy/](https://checktick.uk/compliance/vulnerability-management-policy/)
- Patch Management Strategy: [checktick.uk/compliance/patch-management-strategy/](https://checktick.uk/compliance/patch-management-strategy/)
- SIRO-Approved Patching Approach: [checktick.uk/compliance/siro-patching-approval/](https://checktick.uk/compliance/siro-patching-approval/)
- Vulnerability and Patch Log (active exception with SIRO sign-off 29/03/2026): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)

**Arguments:** The Vulnerability Management Policy defines CVSS-based prioritisation with documented remediation timelines approved by the SIRO. The CI/CD pipeline enforces a zero-exception policy that blocks deployment on any vulnerability, providing a technical backstop independent of human triage. The Vulnerability and Patch Log provides a complete auditable history of all vulnerability management decisions. Currently one low-risk exception exists with SIRO sign-off and monthly review, demonstrating that the exception process functions as designed.

---

### Principle 3.4 - Report vulnerabilities to relevant parties where appropriate.

Vulnerabilities in CheckTick that may affect customer organisations are reported to affected customers promptly. Vulnerabilities in third-party components are reported upstream to the relevant open source project or vendor where appropriate. Significant vulnerabilities are escalated to the SIRO and reported via the DSPT Incident Reporting Tool where they meet the notification threshold.

**Status: Met**

#### Claim 3.4.1 - Internal security teams are informed.

**Evidence:**

- Incident Reporting and Escalation Procedure: [checktick.uk/compliance/incident-reporting-procedure/](https://checktick.uk/compliance/incident-reporting-procedure/)
- Board Minutes - DSPT: [checktick.uk/compliance/board-suite-minutes-dpst/](https://checktick.uk/compliance/board-suite-minutes-dpst/)
- Risk Register: [checktick.uk/compliance/risk-register/](https://checktick.uk/compliance/risk-register/)
- Roles and Responsibilities: [checktick.uk/compliance/roles-and-responsibilities/](https://checktick.uk/compliance/roles-and-responsibilities/)

**Arguments:** As a two-person organisation, the CTO and SIRO together constitute the entire internal security team. Both are notified simultaneously and automatically via GitHub on all vulnerability findings. Monthly board-level security briefings ensure the SIRO has full visibility of all outstanding security items. The Risk Register is updated for all significant findings. This direct notification model eliminates any risk of internal communication delay or escalation failure common in larger organisations.

#### Claim 3.4.2 - Affected customers are informed.

**Evidence:**

- Incident Response Plan and Data Breach Policy: [checktick.uk/compliance/incident-response-plan/](https://checktick.uk/compliance/incident-response-plan/)
- Incident Reporting and Escalation Procedure: [checktick.uk/compliance/incident-reporting-procedure/](https://checktick.uk/compliance/incident-reporting-procedure/)
- Crisis Communication and Press Templates: [checktick.uk/compliance/press-templates/](https://checktick.uk/compliance/press-templates/)
- Incident and Near-Miss Log: [checktick.uk/compliance/incident-near-miss-log/](https://checktick.uk/compliance/incident-near-miss-log/)

**Arguments:** The Incident Response Plan defines customer notification within 2 hours of a confirmed significant incident. The SIRO directly emails all registered Trust Clinical Admins. For incidents meeting the personal data breach threshold, the ICO is notified within 72 hours and the DSPT Incident Reporting Tool is used for health and care incidents. Given that CheckTick serves NHS organisations processing patient data, timely and transparent incident communication is a core commitment. Crisis communication templates ensure consistent and accurate messaging under pressure.

---

### Principle 3.5 - Provide timely security updates, patches and notifications to customers.

Security updates are applied within documented timelines - critical within 48 hours, high within 7 days - well within the 14-day maximum required by DSPT. As a SaaS platform, patches are applied centrally by Eatyourpeas Ltd and do not require customer action. Customers are notified of significant security updates via the platform status communications process. The full patch history from November 2025 is documented in the Vulnerability and Patch Log.

**Status: Met**

#### Claim 3.5.1 - Security updates are distributed as soon as is practicable.

**Evidence:**

- Patch Management Strategy: [checktick.uk/compliance/patch-management-strategy/](https://checktick.uk/compliance/patch-management-strategy/)
- SIRO-Approved Patching Approach: [checktick.uk/compliance/siro-patching-approval/](https://checktick.uk/compliance/siro-patching-approval/)
- Vulnerability and Patch Log (timestamped remediation history demonstrating actual timelines achieved): [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)

**Arguments:** As SaaS, security updates are applied centrally by Eatyourpeas Ltd without requiring any customer action. This model eliminates the risk of customers running outdated vulnerable versions. Critical patches are targeted within 48 hours and high-risk patches within 7 days - both significantly within the 14-day maximum required by NHS DSPT. The Vulnerability and Patch Log provides a timestamped history of actual patch application times, demonstrating that targets have been consistently met in practice since November 2025.

#### Claim 3.5.2 - Security updates are tested and secure by default.

**Evidence:**

- SSDLC Policy: [checktick.uk/compliance/ssdlc-policy/](https://checktick.uk/compliance/ssdlc-policy/)
- Secure Development and Patching Policy: [checktick.uk/compliance/secure-development_and-patching-policy/](https://checktick.uk/compliance/secure-development_and-patching-policy/)
- GitHub Actions CI/CD pipeline (staging environment test runs prior to production deployment)
- Vulnerability and Patch Log: [checktick.uk/compliance/vulnerability-patch-log/](https://checktick.uk/compliance/vulnerability-patch-log/)

**Arguments:** All security updates are tested in a staging environment against the full automated test suite (Pytest and Playwright) before production deployment. The CI/CD pipeline enforces that security updates do not introduce regressions or weaken existing security controls. Secure by default configurations - MFA enforcement, deny-by-default API rules, HTTPS-only access, CSP headers - are verified as part of the test suite and preserved in all updates. The SIRO reviews significant security updates before they are marked as closed in the Vulnerability and Patch Log.

---

## Theme 4: Communication with customers

This theme ensures that vendors provide sufficient information to customers to enable them to effectively manage risks and incidents throughout the software's lifetime.

### Principle 4.1 - Provide information to the customer specifying the level of support and maintenance provided for the software being sold.

CheckTick's support commitments, maintenance approach, and security practices are published in the Terms of Service, public documentation, and DSPT compliance pages. Customers are informed of the platform's security architecture, encryption approach, and data handling practices through the public documentation portal.

**Status: Met**

#### Claim 4.1.1 - 'End of support' dates are published for all software components.

**Evidence:**

- Software Asset and Configuration Register (component versions and support status): [checktick.uk/compliance/software-assets/](https://checktick.uk/compliance/software-assets/)
- Terms of Service (12-month notice commitment): [checktick.uk/docs/terms-of-service/](https://checktick.uk/docs/terms-of-service/)
- Patch Management Strategy: [checktick.uk/compliance/patch-management-strategy/](https://checktick.uk/compliance/patch-management-strategy/)

**Arguments:** CheckTick is actively maintained with no current end-of-support date planned. All major dependencies are on LTS versions with published support windows: Django 5.2 LTS supported until April 2028, PostgreSQL 15.x until November 2027, Ubuntu 22.04 LTS until April 2027. Eatyourpeas Ltd's commitment to 12 months minimum notice is important for NHS Trust customers who operate within procurement and planning cycles that may require 6-12 months of lead time to transition to alternative systems.

#### Claim 4.1.2 - A policy on frequency of updates and the process for applying them is published.

**Evidence:**

- Patch Management Strategy: [checktick.uk/compliance/patch-management-strategy/](https://checktick.uk/compliance/patch-management-strategy/)
- SIRO-Approved Patching Approach: [checktick.uk/compliance/siro-patching-approach/](https://checktick.uk/compliance/siro-patching-approach/)
- Continuous Patching Lifecycle Standard: [checktick.uk/compliance/continuous-patching-lifecycle/](https://checktick.uk/compliance/continuous-patching-lifecycle/)

**Arguments:** The Patch Management Strategy and SIRO-Approved Patching Approach are published publicly on the CheckTick compliance site, with documented CVSS-based remediation timelines. As SaaS, all updates are applied centrally - customers do not need to take any action for security patches. This transparency allows NHS Trust customers to understand and verify the security maintenance posture of the platform they rely on for clinical data collection.

#### Claim 4.1.3 - User documentation describes how to correctly and securely apply updates and use software.

**Evidence:**

- Security Overview: [checktick.uk/docs/security-overview/](https://checktick.uk/docs/security-overview/)
- Authentication and Permissions documentation: [checktick.uk/docs/authentication-and-permissions/](https://checktick.uk/docs/authentication-and-permissions/)
- Encryption for Users documentation: [checktick.uk/docs/encryption-for-users/](https://checktick.uk/docs/encryption-for-users/)
- OIDC SSO Setup guide: [checktick.uk/docs/oidc-sso-setup/](https://checktick.uk/docs/oidc-sso-setup/)
- Key Management for Administrators: [checktick.uk/docs/key-management-for-administrators/](https://checktick.uk/docs/key-management-for-administrators/)
- Audit Logging and Notifications: [checktick.uk/docs/audit-logging-and-notifications/](https://checktick.uk/docs/audit-logging-and-notifications/)

**Arguments:** As SaaS there are no software installations for customers to manage. The public documentation portal covers secure configuration of the platform, including OIDC SSO setup, authentication and permissions, encryption architecture, key management, and audit logging. This documentation enables NHS Trust IT teams to verify the platform's security posture and configure their own integration correctly and securely. Documentation is maintained publicly and updated when platform capabilities change.

---

### Principle 4.2 - Provide at least 1 year's notice to customers of when the software will no longer be supported or maintained by the vendor.

Eatyourpeas Ltd commits to providing a minimum of 12 months written notice to all active customers prior to any end-of-support or decommissioning date for the CheckTick platform. This commitment is documented in the Terms of Service. No end-of-support date is currently planned.

**Status: Met**

#### Claim 4.2.1 - Customers are given at least 1 year's notice of when software will no longer be supported.

**Evidence:**

- Terms of Service (12-month notice commitment): [checktick.uk/docs/terms-of-service/](https://checktick.uk/docs/terms-of-service/)
- Software Asset and Configuration Register (LTS versions in use): [checktick.uk/compliance/software-assets/](https://checktick.uk/compliance/software-assets/)

**Arguments:** The 12-month minimum notice commitment is documented in the Terms of Service, providing contractual assurance rather than just a policy statement. No end-of-support date is currently planned. This commitment is particularly important for NHS Trust customers who operate within procurement and planning cycles that may require months of lead time to identify, procure, and transition to an alternative system. All major dependencies are on LTS versions ensuring the technical foundation remains supported well beyond the current planning horizon.

---

### Principle 4.3 - Make information available to customers about notable incidents that may cause significant impact to customer organisations.

Significant security incidents that may cause material impact to customer organisations are communicated within 2 hours of confirmation, as documented in our Incident Response Plan and Crisis Communication and Press Templates. The communication process covers direct notification to affected Trust Clinical Admins, ICO notification within 72 hours where applicable, and DSPT incident reporting tool notification where the threshold is met.

**Status: Met**

#### Claim 4.3.1 - Customers are informed of relevant incidents in a timely manner.

**Evidence:**

- Incident Response Plan and Data Breach Policy: [checktick.uk/compliance/incident-response-plan/](https://checktick.uk/compliance/incident-response-plan/)
- Incident Reporting and Escalation Procedure: [checktick.uk/compliance/incident-reporting-procedure/](https://checktick.uk/compliance/incident-reporting-procedure/)
- Crisis Communication and Press Templates: [checktick.uk/compliance/press-templates/](https://checktick.uk/compliance/press-templates/)
- Incident and Near-Miss Log: [checktick.uk/compliance/incident-near-miss-log/](https://checktick.uk/compliance/incident-near-miss-log/)

**Arguments:** The 2-hour notification target for significant incidents is critical given that CheckTick processes health data used in clinical audit and research. NHS Trust customers need timely notification to take their own protective action, notify their own SIRO and DPO, and assess whether they have downstream reporting obligations to the ICO. The SIRO directly emails Trust Clinical Admins rather than relying solely on automated notifications, ensuring human-verified communication in high-stakes situations. Crisis communication templates maintain consistent messaging under pressure.

---

## Summary

| Principle | Status |
| :--- | :--- |
| 1.1 Follow an established secure development framework | Met |
| 1.2 Understand the composition of the software and assess third-party component risks | Met |
| 1.3 Have a clear process for testing software and updates | Met |
| 1.4 Follow secure by design and secure by default principles | Met |
| 2.1 Protect the build environment against unauthorised access | Met |
| 2.2 Control and log changes to the build environment | Met |
| 3.1 Distribute software securely to customers | Met |
| 3.2 Implement and publish an effective vulnerability disclosure process | Met |
| 3.3 Proactively detect, prioritise and manage vulnerabilities | Met |
| 3.4 Report vulnerabilities to relevant parties | Met |
| 3.5 Provide timely security updates, patches and notifications | Met |
| 4.1 Provide information about support and maintenance | Met |
| 4.2 Provide at least 1 year's notice of end of support | Met |
| 4.3 Make information available about notable incidents | Met |

**Overall Assessment: All 14 principles met.**

**Approved by:** Dr Serena Haywood (SIRO)
**Date:** March 2026
