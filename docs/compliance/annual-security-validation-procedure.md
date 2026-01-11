---
title: "Annual Security Validation (ASV) Procedure"
category: dspt-5-process-reviews
---

# Annual Security Validation (ASV) Procedure

**Standard:** DSPT Section 9.4
**Review Cycle:** Annual (January)
**Responsible:** CTO ({{ siro_name }})

## 1. Scope of Validation

The annual review assesses the effectiveness of:

* **Network Defenses:** Firewall rules, VPC isolation, and TLS configurations.
* **Access Controls:** MFA enforcement and the "Joiners/Movers/Leavers" process.
* **Vulnerability Management:** The speed and success of patching High/Critical CVEs.

## 2. Assurance Methodology

1. **Automated Evidence:** Review of the last 12 months of GitHub Action logs and `pip-audit` history to confirm zero unpatched 'Critical' vulnerabilities in production.
2. **Configuration Audit:** Manual spot-check of Northflank project settings to ensure "Zero-Default" passwords and no unauthorized port exposure.
3. **Third-Party Health:** Confirmation that Northflank and other sub-processors have maintained their security certifications (ISO/SOC2).

## 3. 2026 Validation & Action Plan

* **Status:** Validation completed 03/01/2026.
* **Findings:** Network controls remain effective; current "Shift-Left" scanning is identifying vulnerabilities before they reach production.
* **Action Items for 2026:**
    * **Q2:** Standardize all developer environment "Keychains" to prevent local SSH key exposure.
    * **Q3:** Conduct a "Tabletop Exercise" simulating a database recovery from backup.
    * **Q4:** Perform a formal review of our Sovereign Security model against the updated NCSC Cloud Security Guidance.
