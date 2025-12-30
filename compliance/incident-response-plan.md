# Incident Response Plan & Data Breach Policy

**Version:** 1.0
**Last Reviewed:** [Insert Date post-July 1, 2025]
**SIRO:** [Name 1] | **Cyber Lead:** [Name 2]

## 1. Definition of an Incident

An incident is any event that threatens the confidentiality, integrity, or availability of CheckTick data or services. This includes:

* **Cyber Security Incidents:** Malware, Ransomware, DDoS, or unauthorized DB access.
* **Physical Incidents:** Loss/theft of a staff laptop.
* **Data Breaches:** Accidental or unlawful destruction, loss, or disclosure of personal data.

## 2. Immediate Response Steps (The "4-Hour" Window)

1. **Identify & Contain:** [Name 2] isolates the affected system (e.g., revoking API keys, shutting down a Northflank service, or remote-wiping a laptop).
2. **Assess:** Determine what data was involved. Is it "Special Category" (health) data?
3. **Notify SIRO:** [Name 2] briefs [Name 1] on the technical scope.

## 3. Notification Requirements

### 3.1 To the ICO

If the breach is likely to result in a risk to the rights and freedoms of individuals, [Name 1] must report it to the **ICO** within **72 hours** of becoming aware.

### 3.2 To the Data Controller (Our Customers)

As a Data Processor, CheckTick has a legal obligation under GDPR to notify our customers (the Healthcare Orgs) **without undue delay** if their survey data is compromised.

### 3.3 To the DSPT (Data Security On-Line Reporting)

If the incident meets the "Severity" threshold (e.g., affecting >150 individuals or clinical safety), it must be reported via the **DSPT Incident Reporting Tool**.

## 4. Triage Levels

| Level | Description | Action |
| :--- | :--- | :--- |
| **P1 (Critical)** | Data breach involving health data or total system outage. | Immediate containment; 72hr ICO clock starts. |
| **P2 (High)** | Suspicious activity detected; account compromise without data leak. | Password resets; MFA audit; notify affected user. |
| **P3 (Normal)** | Localized bug or hardware failure with no data risk. | Standard patch/repair process. |

## 5. Post-Incident Review

Within 5 business days of any P1 or P2 incident, the team will:

* Identify the root cause.
* Update the **Vulnerability Management Policy** if required.
* Update the **Asset Register** or **Data Flow Map** if the incident revealed new risks.
