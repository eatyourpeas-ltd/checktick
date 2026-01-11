---
title: "Transactional Monitoring & Fraud Prevention"
category: dspt-9-it-protection
---

# Transactional Monitoring & Fraud Prevention

## 1. Risk Assessment

As a clinical survey provider, the primary fraud risks identified are:

* **Account Takeover:** Criminals gaining access to a clinician's account to view sensitive data.
* **Data Exfiltration:** Automated scripts attempting to 'scrape' the database.

## 2. Implemented Controls

| Transaction Type | Monitoring Technique | Response Action |
| :--- | :--- | :--- |
| **Login Attempt** | Failed attempt tracking (`django-axes`). | IP lockout after 5 failed attempts. |
| **Data Export** | Logging of all 'Export to CSV/Excel' events. | Log entry includes user, time, and record count. |
| **API Requests** | Rate limiting at the Nginx/Application layer. | 429 'Too Many Requests' response for bursts. |
| **Account Creation** | SIRO/Admin approval required for new clinician roles. | Prevents 'rogue' accounts from being self-generated. |

## 3. Review Process

The SIRO reviews the 'Audit Logs' monthly to identify any anomalous patterns (e.g., a user logging in from an unusual IP or exporting large volumes of data outside of office hours).
