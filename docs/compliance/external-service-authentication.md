---
title: "External Service Authentication Policy"
category: compliance
---

# External Service Authentication Policy (Cyber Essentials)

**Last Reviewed:** 08/02/2026 | **Owner:** {{ cto_name }} (CTO)
**Cyber Essentials Compliance:** Control 5.4 & 5.5 - Authentication for External Services

## 1. External Services Overview

This policy covers authentication requirements for internet-facing services that {{ company_name }} operates or accesses that contain business or customer data.

### 1.1 External Services WE PROVIDE

These are services **operated and hosted by {{ company_name }}** for customers:

* **CheckTick Web Application** - Django-based SaaS platform hosted on Northflank (Port 443/HTTPS)
  * Service we run for NHS Trusts and healthcare providers
  * Contains patient and organisational data
  * **This is what CE section A5.4/A5.5 refers to**

### 1.2 External Services WE USE

These are third-party cloud services **used by {{ company_name }} staff** to operate the business:

* **Infrastructure Management** - Northflank dashboard (hosting console)
* **Version Control** - GitHub repositories (code and documentation)
* **Business Services** - Personal Google accounts for email (custom domain redirects)

**Note:** Authentication requirements for services we use are covered in this policy, but are NOT in scope for CE question A5.4/A5.5 about "external services you run or host."

**Out of Scope:** Internal network services (file shares, printers), staff device authentication (covered in Endpoint Software Policy).

## 2. Authentication Requirements

### 2.1 Services WE PROVIDE (CheckTick Platform)

**Cyber Essentials Control 5.5:** For the CheckTick web application we operate:

**Staff Administrative Access (Backend/Admin Portal):**

* Password: Minimum 12 characters, no maximum length
* MFA: Mandatory TOTP, biometric (Touch ID), or WebAuthn/Passkey
* Common passwords blocked (NCSC deny list - 100,000+ entries)
* SSO: OIDC integration with Google OAuth available (for CheckTick customer authentication)

**Customer/End-User Access:**

* Authentication handled by application (details in DSPT documentation)
* Exceeds CE requirements: 8+ char passwords, common password blocking, MFA available
* **Note:** CE focuses on YOUR staff's admin access, not how end-users authenticate

### 2.2 Services WE USE (Third-party Cloud Services)

**Staff Access to Business Cloud Services:**

For GitHub and Northflank accounts used by {{ company_name }} staff:

* Password: Minimum 12 characters, no maximum length
* MFA: Mandatory TOTP, biometric (Touch ID), or WebAuthn/Passkey
* Common passwords blocked (NCSC deny list)
* Stored in Bitwarden password manager

**Note:** These are covered under general password policy for staff accounts, not CE "external services you run or host."

## 3. Technical Controls

### 3.1 CheckTick Application Security (Service We Provide)

* **TLS 1.2+ mandatory** - All connections encrypted end-to-end
* **Session management** - 24-hour inactivity timeout, secure cookies (HttpOnly, SameSite)
* **Brute force protection** - django-axes locks accounts after 5 failed attempts (exceeds CE 10-attempt requirement)
* **Rate limiting** - django-ratelimit throttles login endpoints to 10 attempts/minute per IP
* **Password hashing** - PBKDF2-SHA256 with 600,000 iterations
* **CSRF protection** - Django framework built-in

### 3.2 CheckTick Infrastructure Security

* **Network isolation** - Production databases on private subnets (no internet exposure)
* **Public access** - Limited to Port 443 (HTTPS) only
* **No VPN/DMZ** - Not applicable to external-facing SaaS platform

### 3.3 Third-party Cloud Services (Services We Use)

Authentication for GitHub and Northflank relies on vendor-provided security controls:
* Vendor-managed TLS/HTTPS encryption
* Vendor default brute force protection (login throttling, account lockouts)
* Our enforcement: 12-char passwords + mandatory MFA for all staff accounts

## 4. Verification & Review

### 4.1 Monthly Checks

**For CheckTick (service we provide):**

* Verify MFA enabled on all administrative/backend accounts
* Review authentication failure logs for suspicious patterns
* Confirm django-axes brute force protection functioning

**For cloud services we use (GitHub, Northflank):**

* Verify MFA enabled on all staff accounts (part of general access control audit)
* Confirm no default/weak passwords in use

### 4.2 Annual Review

* Full authentication security review during Cyber Essentials re-certification (February)
* Verify compliance with password policy and MFA requirements for all services
* Update deny lists and authentication technologies as needed

## 5. Cyber Essentials Response

**Question A5.4:** Do you run or host external services that provide access to data (that shouldn't be made public) to users across the internet?

**Answer:** **Yes** - We operate CheckTick, a web-based SaaS application for healthcare data collection.

**Clarification:** This refers to services WE PROVIDE (CheckTick platform), NOT third-party services we use like GitHub/Northflank.

---

**Question A5.5:** Which authentication option do you use?

**Answer:** **Option A - Multi-factor authentication, with a minimum password length of 8 characters and no maximum length**

**Notes for Assessor:**

**For CheckTick (the external service we provide):**

We enforce MFA with 12-character minimum passwords (exceeding the 8-character requirement) for all staff administrative access to the CheckTick backend/admin portal.

Technical controls:
- Minimum 12-character passwords (exceeds CE 8-char requirement), no maximum length
- NCSC common password deny list (100,000+ entries)
- TOTP, biometric (Touch ID), or WebAuthn/Passkey MFA
- TLS 1.2+, secure session management, brute force protection

Monthly verification: All CheckTick administrative accounts confirmed to have MFA enabled (see [annual-compliance-checklist-2026.md](annual-compliance-checklist-2026.md) Ongoing Monthly tasks).

---

**For third-party cloud services we use (GitHub, Northflank):**

These follow the same 12-character + MFA requirements in our Password Policy, but are NOT covered by CE question A5.4/A5.5 (we don't "run or host" these services).

**Last Verified:** 08/02/2026
**Next Review:** February 2027 (Annual Cyber Essentials re-certification)

---

## Related Policies

* [Password Policy](password-policy.md) - Staff password requirements and MFA controls
* [Access Control Policy](access-control.md) - Administrative account management
* [Endpoint Software Policy](endpoint-software-policy.md) - User account management on devices
* [Network Security Policy](network-security-policy.md) - Network-layer protections
