---
title: Privacy Notice
category: None
priority: 2
---

# Privacy Notice

**Last Updated: 6 April 2026**

This Privacy Notice explains how Eatyourpeas Ltd ("we", "us", or "our"), trading as CheckTick, collects, uses, stores, and protects your personal information when you use our survey platform and services.

## 1. Introduction

Eatyourpeas Ltd is committed to protecting your privacy and complying with data protection laws, including the UK General Data Protection Regulation (UK GDPR) and the Data Protection Act 2018.

CheckTick is a non-clinical survey and data collection platform and does not provide diagnostic or decision-support functionality. It is not classified as a medical device. Any future integration with clinical systems would be subject to separate clinical safety assessment and governance processes.

### 1.1 Key Principles

* We only collect data necessary to provide our services
* We use strong encryption to protect your data
* We will never sell your personal data to third parties
* You have control over your data and can request deletion at any time
* We are transparent about how we use your information

### 1.2 Data Controller

For your CheckTick account data, Eatyourpeas Ltd is the data controller.

For survey data you collect, **you are the data controller** and Eatyourpeas Ltd (trading as CheckTick) is the data processor.

## 2. Information We Collect

### 2.1 Account Information

* Username
* Email address
* Password (hashed)
* Organisation details
* IP address
* Account activity metadata

### 2.2 Survey Data

* Survey questions and configuration
* Survey responses (encrypted)
* Respondent data as defined by the controller

### 2.3 Usage Data

* Access logs
* Error logs
* Device/browser metadata

### 2.4 Payment Information

Handled by payment provider (**GoCardless**). We do not store bank details.

### 2.5 Cookies

Used only for:
* Authentication
* Session management
* Security

---

## 3. How We Use Your Information

* Provide and operate the service
* Maintain security
* Improve performance
* Communicate service updates

---

## 4. Data Sharing and Disclosure

### 4.1 We Do Not Sell Data

We never sell personal data.

### 4.2 Service Providers

We use the following processors:

* **Northflank** – hosting and infrastructure (UK)
* **Microsoft 365** – CheckTick email and identity services
* **Proton Mail** – corporate communications
* **GoCardless** – payment processing
* **GitHub** – code repository and CI/CD (no production personal data)

All providers operate under UK GDPR-compliant Data Processing Agreements.

All primary service data is hosted within UK data centres. Where limited international processing occurs, appropriate safeguards (e.g. SCCs) are in place.

---

## 5. Data Security

### 5.1 Encryption

* AES-256-GCM encryption for survey data
* TLS 1.2+ in transit

### 5.2 Key Management

Encryption keys are managed using a split architecture:

* **HashiCorp Vault (self-hosted, air-gapped)** – master key management
* **Northflank environment variables** – runtime secrets only

This ensures no single system can decrypt data independently.

### 5.3 Access Controls

* Role-based access control
* MFA enforced for administrative accounts
* SSO supported (Microsoft / Google)

### 5.4 Infrastructure Security

* Network isolation
* Firewall controls
* Continuous vulnerability scanning

---

## 6. Data Retention

* Active accounts: retained while in use
* Deleted data: removed within 30 days
* Backups: retained up to 90 days

---

## 7. Your Rights

You have rights under UK GDPR including:

* Access
* Rectification
* Erasure
* Restriction
* Portability
* Objection

Requests: support@checktick.uk

---

## 8. Children's Data

Users collecting children’s data must:

* Obtain appropriate consent
* Follow safeguarding and NHS guidance
* Ensure lawful processing

---

## 9. International Transfers

Data is primarily stored in the UK.

Where transfers occur, safeguards include:
* Standard Contractual Clauses
* UK GDPR-compliant DPAs

---

## 10. Your Responsibilities (Controllers)

You must:

* Define lawful basis
* Provide privacy notices
* Respond to data subject requests
* Conduct DPIAs where required

---

## 11. Survey Respondents

### 11.1 Controller Responsibility

The survey creator is the data controller.

### 11.2 Your Rights

Contact the survey creator first.

If unresolved, contact: dpo@checktick.uk

### 11.3 Anonymous vs Pseudonymous

Anonymous responses cannot be linked to individuals and rights cannot be exercised.

### 11.4 Receipt Tokens

Used to identify responses without revealing identity.

### 11.5 Dispute Resolution

We may:

* Contact the controller
* Restrict processing
* Escalate issues

### 11.6 Complaints

You may complain to:

**Information Commissioner's Office (ICO)**
https://ico.org.uk

---

## 12. Changes

We will notify users of material changes.

---

## 13. Contact

* support@checktick.uk
* dpo@checktick.uk

---

**Last Updated: 6 April 2026**
