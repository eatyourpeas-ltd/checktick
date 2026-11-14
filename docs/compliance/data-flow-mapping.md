---
title: "Data Flow Mapping & Information Assets"
category: dspt-1-confidential-data
---

# Data Flow Mapping & Information Assets

This document outlines how data moves through the {{ platform_name }} platform and identifies the core information assets supporting our health and care services.

## 1. System Data Flow Diagram (Logical)

| Stage | Origin | Destination | Protocol | Encryption |
| :--- | :--- | :--- | :--- | :--- |
| **Data Collection** | Patient Browser | {{ platform_name }} App (Django) | HTTPS | TLS 1.2+ (In-transit) |
| **Data Storage** | Django Backend | RDS/PostgreSQL | Internal | AES-256 (At-rest) |
| **Key Recovery** | Admin User | Vault / Environment | HTTPS | TLS + Secret Masking |
| **Data Export** | {{ platform_name }} App | Healthcare User | HTTPS | Encrypted CSV/JSON |
| **Backup** | Database Asset | Snapshot Storage | Internal | AES-256 (UK Only) |

## 2. Information Asset Register (IAR)

| Asset ID | Asset Name | Description | Location | Owner |
| :--- | :--- | :--- | :--- | :--- |
| **ASSET-01** | Production DB | Encrypted survey responses | Civo Kubernetes — in-cluster CloudNativePG PostgreSQL (UK, London LON1) | {{ platform_name }} Admin |
| **ASSET-02** | App Servers | Containerized Django Environment | Civo Kubernetes (UK, London LON1) | {{ platform_name }} Admin |
| **ASSET-03** | Secret Vault | Production keys and recovery credentials | In-cluster HashiCorp Vault (Kubernetes StatefulSet) | {{ platform_name }} Admin |
| **ASSET-04** | Source Code | Application logic and DSPT documentation | GitHub (Public) | {{ platform_name }} Admin |
| **ASSET-05** | Admin Laptops | Endpoints used for system management | UK (Encrypted) | 2x Employees |

## 3. Detailed Data Flows

### External Inflow (Collection)

Survey responses are initiated by patients via a web-native interface. Data is encrypted using TLS 1.2+ before leaving the browser. The Django backend receives the payload and processes it into the database immediately.

### Internal Storage & Processing

Data is stored on managed Kubernetes infrastructure (Civo) within the UK London (LON1) region. We utilize database-level encryption (AES-256). Sensitive credentials required for decryption are never stored in the application code; they are injected at runtime via a secure in-cluster Vault.

### Access & Outflow

Healthcare professionals access survey results via an authenticated dashboard. Data exports are only permitted after "Survey Closure" (as defined in our [Data Governance Policy](https://checktick.uk/docs/data-governance/)). Every export requires a purpose statement and is logged in the immutable audit trail.

### Backup and Residency

Automated backups are performed daily. All backup data is stored within the UK geography. We do not transfer patient-identifiable data outside of the United Kingdom for any support or maintenance purposes.

---

## 4. Document Control & Approval

* **Initial Review:** 29th December 2025
* **Last Approval Date:** 29th December 2025
* **Approved By:** {{ siro_name }}, SIRO
* **Review Cycle:** Annual (or upon major architectural change)

## 5. API Data Flows & Security

The {{ platform_name }} API allows for secure, programmatic integration with external healthcare systems (e.g., EPRs or Clinical Dashboards).

### API Data Movement

* **Direction:** Outbound (typically) – Survey data pulled by authorized external clients.
* **Protocol:** RESTful API over **HTTPS (TLS 1.2+)**.
* **Authentication:** Secured via **Scoped API Keys** or **OIDC/OAuth2 tokens**.
* **Data Format:** JSON (Encrypted in transit).

### API Security Controls

1. **Appropriate Scoping:** API keys are restricted using the "Principle of Least Privilege." A key generated for a specific survey cannot access data from other surveys or organisation settings.
2. **Rate Limiting:** To prevent brute-force attacks and ensure service availability, the API implements strict rate limiting at the application layer, behind the Traefik ingress.
3. **Audit Logging:** Every API request is logged, including the timestamp, the identity of the API key used, the endpoint accessed, and the IP address.
4. **IP Whitelisting (Optional):** For high-sensitivity healthcare integrations, we support restricting API access to specific trusted IP ranges.

### API Asset Entry (For IAR)

| Asset ID | Asset Name | Description | Location |
| :--- | :--- | :--- | :--- |
| **ASSET-06** | API Gateway | The entry point for programmatic data access. | Traefik ingress (Civo Kubernetes) |

## 6. Appraisal Workflow Data Flows

Appraisal surveys (GMC-style 360 appraisal) follow the flow below. Encryption and key handling match Section 1 unless stated.

| Stage | Origin | Destination | Protocol | Encryption |
| :--- | :--- | :--- | :--- | :--- |
| **Survey Creation** | Appraiser (from organisation instrument) | {{ platform_name }} App (Django) | HTTPS | TLS 1.2+ (In-transit); survey key wrapped with organisation master key (At-rest) |
| **Token Distribution** | Appraisee (distributor) | Patients (QR/link) and colleagues (token) | HTTPS | TLS 1.2+; random, single-purpose tokens |
| **Patient Feedback** | Patient Browser (anonymous, no token) | {{ platform_name }} App | HTTPS | TLS 1.2+ (In-transit); AES-256 (At-rest) |
| **Colleague and Self Feedback** | Colleague or appraisee (token holder) | {{ platform_name }} App | HTTPS | TLS 1.2+; pseudonymous token-to-response linkage |
| **Unlock** | Appraiser or Responsible Officer | Organisation master key to survey key | HTTPS | Org-key wrap; unlock logged as `key_recovery` (Critical) |
| **Report Release** | {{ platform_name }} App | Appraisee and Responsible Officer (immutable JSON snapshot) | HTTPS | TLS 1.2+; AES-256 (At-rest) |
| **Exception Review Disclosure** | Appraiser (raises) and Responsible Officer (co-signs) | Appraiser and Responsible Officer (linkage view) | HTTPS | Two-party approval; disclosure logged at Warning |

### Collection and Distribution

The appraiser creates the appraisal survey from an organisation-approved instrument. The appraisee, as a distributor, generates token batches and QR codes. Patient respondents answer anonymously through unlisted publication and hold no token. The appraiser approves colleague raters and issues their tokens. The appraisee's self-assessment uses a single `self` token.

### Unlock and Release

The appraiser unlocks results through the organisation master key. Unlocks and results views are audit-logged. Reports are released as immutable, versioned JSON snapshots, visible to the appraisee as released and to the Responsible Officer. A minimum-response threshold (default 5) gates release. Populations below the threshold are suppressed (counts only), except the appraisee's own self-assessment.

### Exception Review Disclosure

A response indicating serious risk prompts the appraiser to raise an exception review, stating the response and a reason. The Responsible Officer co-signs before the token-to-response linkage (token, category values, submission metadata) is shown to the appraiser and the Responsible Officer. The raiser cannot co-sign their own request. The appraisee never sees exception reviews. Released reports record only a count of approved exception reviews, never their content.
