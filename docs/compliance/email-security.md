---
title: "Email Authentication & Anti-Spoofing Policy"
category: dspt-6-incidents
---

# Email Authentication & Anti-Spoofing Policy

**Owner:** Dr Simon Chapman (CTO)
**Last Reviewed:** April 2026
**Scope:** checktick.uk (Microsoft 365) and eatyourpeas.co.uk (Proton Mail)

This policy protects the integrity of email communications from
EatYourPeas Ltd and the {{ platform_name }} platform, preventing
spoofing and phishing attacks against NHS Trust partners and
clinical users.

---

## 1. Domain Scope and DCB1596 Status

| Domain | Platform | Contains Health Data | DCB1596 Scope |
| :--- | :--- | :--- | :--- |
| checktick.uk | Microsoft 365 Business | Yes — platform notifications and compliance communications | In scope — compliant |
| eatyourpeas.co.uk | Proton Mail Business | No — company/brand communications only | Out of scope |

---

## 2. checktick.uk — Microsoft 365 (DCB1596 Compliant)

### 2.1 Compliance Status

checktick.uk email is provided via Microsoft 365 Business Basic.
Microsoft Office 365 is a pre-approved compliant service for the
DCB1596 Secure Email Standard, with a published NHS England
conformance statement. EatYourPeas Ltd has configured Microsoft
365 in accordance with the NHS England Office 365 Secure Email
Configuration Guide.

### 2.2 Staff and Compliance Mailboxes

The following mailboxes are hosted on Microsoft 365 for
checktick.uk and are used for compliance, governance, and
customer communications:

* compliance@checktick.uk
* siro@checktick.uk
* security@checktick.uk
* support@checktick.uk

All mailboxes require MFA-authenticated access via individually
named Microsoft 365 accounts. Access is restricted to named
administrators (Dr Simon Chapman and Dr Serena Haywood).

### 2.3 Transactional Email (Django Application)

Outbound transactional email from the CheckTick platform (survey
notifications, account management, signup emails) is sent via
the Microsoft Graph API using an application registration with
the minimum required permission scope:

* **Permission granted:** Mail.Send only
* **Permission denied:** Mail.Read, Mail.ReadWrite, and all
  other Graph API permissions
* **Secret management:** Application client ID and client secret
  are stored as encrypted environment variables within the
  Northflank platform and injected into the application container
  at runtime. They are not present in source code, version
  control, or any other storage location. GitGuardian pre-commit
  hooks would block any accidental commit of these credentials.

This least-privilege configuration ensures the application can
send email on behalf of the platform but cannot read, modify,
or delete any mailbox content. A compromise of the application
layer cannot result in unauthorised access to email data.

### 2.4 Authentication Records (checktick.uk)

The following DNS-based authentication records are active for
checktick.uk, managed via Namecheap DNS and reviewed quarterly
by the CTO:

* **SPF:** Configured to authorise Microsoft 365 sending
  infrastructure only. Hard fail policy (`-all`) rejects all
  other senders.
* **DKIM:** 2048-bit RSA keys provided by Microsoft 365,
  published as CNAME records pointing to Microsoft's signing
  infrastructure. Keys are rotated automatically by Microsoft
  365.
* **DMARC:** `v=DMARC1; p=quarantine; pct=100` — 100% of
  unauthenticated emails are directed to spam. Aggregate
  reports (RUA) monitored via OnDMARC. Target: move to
  `p=reject` within three months of go-live.
* **MTA-STS:** To be configured prior to live clinical
  deployment as part of full DCB1596 accreditation submission.

### 2.5 Inbound Security

All inbound email to checktick.uk mailboxes is processed by
Microsoft 365's Exchange Online Protection, providing spam
filtering, malware scanning of attachments, phishing detection,
and URL rewriting against real-time threat intelligence. DMARC
enforcement is applied to all inbound email from external
senders.

### 2.6 Mobile Access

checktick.uk email is accessed on mobile devices via the
official Microsoft Outlook iOS and Android applications, which
enforce TLS transport security and require Entra ID MFA
authentication consistent with the Microsoft 365 tenant policy.

---

## 3. eatyourpeas.co.uk — Proton Mail Business

### 3.1 Scope

eatyourpeas.co.uk is the company domain for Eatyourpeas Ltd
business communications. It is used for general company
correspondence, supplier communications, and brand enquiries.
No patient identifiable data, survey data, or health-related
clinical information is ever processed via eatyourpeas.co.uk
email.

Because eatyourpeas.co.uk does not carry sensitive health or
personal data in the context of health and care services, it
falls outside the scope of the DCB1596 Secure Email Standard.

### 3.2 Authentication Records (eatyourpeas.co.uk)

Standard email authentication records are maintained for
eatyourpeas.co.uk via Proton Mail Business:

* **SPF:** Configured to authorise Proton Mail sending
  infrastructure only.
* **DKIM:** Configured and managed by Proton Mail Business.
* **DMARC:** Active with quarantine policy.

### 3.3 Security Posture

Proton Mail Business provides end-to-end encryption for
email in transit and at rest, zero-access encryption for
stored messages, and MFA enforcement on all accounts.
All eatyourpeas.co.uk accounts are MFA-protected and
accessed exclusively by named administrators.

---

## 4. Maintenance and Review

* **Quarterly Review:** The CTO verifies during spot checks
  that no unauthorised services have been added to the
  checktick.uk SPF record, DKIM keys are valid, and DMARC
  reports show no anomalous authentication failures.
* **Decommissioning:** When a sending service is no longer
  in use, its SPF and DKIM entries are removed immediately
  and the change is logged in the Infrastructure Technical
  Change Log.
* **DMARC Monitoring:** Aggregate reports for checktick.uk
  are reviewed quarterly via OnDMARC to identify spoofing
  campaigns and verify authentication compliance.
* **Graph API Secret Rotation:** The Microsoft Graph API
  client secret used for transactional email is rotated
  annually and stored in HashiCorp Vault.

---

## 5. Minimising Email-Based Data Transfer

The CheckTick platform is designed to minimise the transfer
of sensitive data via email. All survey response data is
accessed through the secure authenticated web interface
rather than transmitted via email. Transactional emails sent
by the platform contain notification text only and do not
include patient identifiable data or survey responses.

---

## 6. Breach Notification

Eatyourpeas Ltd maintains a documented process to notify
relevant parties upon becoming aware of any actual, potential,
or attempted breach of email security, as set out in the
Incident Response Plan and Incident Reporting Procedure.