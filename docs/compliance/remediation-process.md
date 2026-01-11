---
title: "Security Remediation Process"
category: dspt-6-incidents
---

# Security Remediation Process

**Standard:** {{ platform_name }} uses GitHub as the primary record for security deficiency management.

## 1. Discovery & Logging

All security deficiencies (CVEs, misconfigurations, logic flaws) are logged in the Private GitHub Repository Issue Tracker.

## 2. Tracking Requirements

Each security issue must contain:

* **Source:** (e.g., NCSC Alert, Dependabot, CodeQL)
* **Severity:** (Critical/High/Med/Low)
* **Status:** Open/In-Progress/Closed/Risk-Accepted

## 3. The "Evidence Chain"

{{ platform_name }} satisfies DSPT audit requirements by maintaining the link between:

1. **The Issue:** The record of the deficiency.
2. **The Pull Request (PR):** The record of the fix and the automated CI/CD security scan results.
3. **The Merge:** The record of CTO approval and deployment.

## 4. Risk Acceptance

If a fix is not applied, the reasoning (Business Case) must be added as a comment to the GitHub Issue and the 'Risk-Accepted' label applied. The SIRO performs a quarterly review of all 'Risk-Accepted' labels.
