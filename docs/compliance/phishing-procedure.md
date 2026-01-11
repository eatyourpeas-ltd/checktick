---
title: "Phishing Escalation & Management Procedure"
category: dspt-6-incidents
---

# Phishing Escalation & Management Procedure

## 1. Identification
xs
Staff are trained to look for common phishing indicators:

* Mismatched sender domains (e.g., `nhs.net.com` instead of `nhs.net`).
* Urgent or threatening language regarding account access.
* Unexpected attachments or links to non-standard login pages.

## 2. Reporting Protocol

If a suspicious email is identified:

1. **Do Not Click:** Do not open links or download attachments.
2. **Technical Report:** Use the 'Report Phishing' feature in the email client.
3. **Internal Escalation:** Notify the CTO via the `#security-alerts` Slack channel with a screenshot of the email.

## 3. Technical Response (CTO)

Upon receiving a report, the CTO will:

* **Analyze:** Inspect the email headers for spoofing.
* **Block:** Add the sender's domain or IP to the organization-wide blocklist.
* **Purge:** Search for and remove any similar emails from other team member inboxes.

## 4. Log of Reports

All reported phishing attempts are recorded in the **Incident & Near-Miss Log** for quarterly review to identify if {{ platform_name }} is being specifically targeted.
