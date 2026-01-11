---
title: "Security Monitoring & Logging Standard"
category: dspt-9-it-protection
---

# Security Monitoring & Logging Standard

## 1. Scope of Monitoring

We monitor all systems supporting the development and hosting of {{ platform_name }}:

* **Host Level:** Northflank platform logs and infrastructure metrics.
* **Application Level:** Django runtime logs, including authentication events (Success/Fail).
* **Development Level:** GitHub audit logs and automated security scans.

## 2. Detection Logic (Cyber Events)

| Event Type | Monitoring Tool | Action |
| :--- | :--- | :--- |
| **Brute Force** | `django-axes` | IP Lockout + Admin Email Alert |
| **Secret Leak** | GitHub Secret Scanning | Immediate developer alert + PR block |
| **Downtime/DoS** | Northflank Health Checks | Critical Slack Alert |
| **Vulnerabilities**| GitHub Dependabot | Weekly report / PR generation |

## 3. Log Retention

Logs are retained for a minimum of 90 days in the Northflank/GitHub consoles. For clinical audit purposes, application-level logs relating to patient data access are stored within the encrypted PostgreSQL database for a longer duration as per our Retention Policy.

## 4. Mitigation of Gaps

As a small team, we mitigate the '24/7 human monitoring' gap by utilizing **automated push alerts** to mobile devices for all critical security events.
