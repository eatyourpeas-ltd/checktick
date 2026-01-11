---
title: "NCSC Early Warning Monitoring Procedure"
category: dspt-6-incidents
---

# NCSC Early Warning Monitoring Procedure

**Purpose:** To define how {{ platform_name }} responds to threat intelligence provided by the UK National Cyber Security Centre (NCSC).

## 1. Registration Details

* **Registered Entity:** {{ platform_name }}
* **Primary Contact:** CTO
* **Assets Monitored:** `checktick.uk` [and production IP addresses]

## 2. Alert Categories & Response Times

| Alert Type | Description | Target Response |
| :--- | :--- | :--- |
| **Incident Notifications** | Evidence of an active compromise (e.g., malware beaconing). | **Immediate (< 4 hours)** |
| **Network Abuse** | Evidence of your assets being used for malicious activity. | **< 12 hours** |
| **Vulnerability Alerts** | Detection of an unpatched or vulnerable public service. | **< 24 hours** |

## 3. Triage Process

1. **Verification:** CTO verifies the alert against Northflank logs and GitHub security dashboards.
2. **Remediation:** If valid, the CTO applies the necessary patch or rotates compromised credentials immediately.
3. **Reporting:** Any confirmed incident identified via NCSC Early Warning is reported to the SIRO ({{ cto_name }}) and logged in the *Cyber Incident Log*.
