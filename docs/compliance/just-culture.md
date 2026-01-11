---
title: "Statement on Just Culture & Open Reporting"
category: dspt-2-staff-responsibilities
---

# Statement on Just Culture & Open Reporting

**Owner:** {{ cto_name }} (SIRO)

## 1. The 'Just Culture' Philosophy

At {{ platform_name }}, we recognize that human error is often a symptom of systemic issues. We foster an environment where:

* **Reporting is encouraged:** Reporting a mistake (like clicking a suspicious link or misconfiguring a permission) is treated as a contribution to the company's safety.
* **No-Blame Analysis:** We focus on *how* our technical safeguards (MFA, VPCs) failed to prevent the error, rather than *who* made it.
* **Near Miss Recognition:** We celebrate the 'catch.' If a partner notices a security flaw before it is exploited, this is documented as a victory for our audit and review process.

## 2. Public & Patient Feedback

While we do not directly interface with patients in the same way as a clinical Trust (PALS), we acknowledge our responsibility to the public:

* **Public Security Reporting:** Our documentation at `checktick.uk/docs/` provides a path for researchers or users to report concerns.
* **Response Commitment:** All security-related feedback receives an initial response within 24 hours.
* **Transparency:** Where a concern is valid, we communicate the fix openly (via GitHub issues or our changelog) to demonstrate our commitment to safety.

## 3. Incident Review Example (Simulated Near Miss)

* **Event:** Staff member noticed an old API key was still active in a test environment.
* **Action:** Key was revoked immediately.
* **Just Culture Follow-up:** Instead of reprimand, the team updated the 'Offboarding Checklist' to include a specific step for 'Test Environment Key Purge.'
* **Outcome:** The system is now stronger due to the open reporting of the error.
