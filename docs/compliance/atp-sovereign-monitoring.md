---
title: "Sovereign Advanced Threat Protection (ATP) Procedure"
category: dspt-9-it-protection
---

# Sovereign Advanced Threat Protection (ATP) Procedure

**Strategy:** {{ platform_name }} maintains a high-security posture using UK-sovereign infrastructure and application-layer active defenses.

## 1. Active Defense Stack (ATP Equivalent)

| Layer | Technology | Function |
| :--- | :--- | :--- |
| **Identity** | `django-axes` | Actively monitors login attempts; automatically locks IPs/Accounts after 5 failed attempts (Brute Force Protection). |
| **Traffic** | `django-ratelimit` | Prevents automated scraping and DoS attacks by limiting requests to sensitive endpoints (e.g., survey submissions). |
| **Code** | `CodeQL` | Scans for logic-based security threats (SAST) on every commit. |
| **Infrastructure** | Northflank Logs | Managed UK-based intrusion monitoring and DDoS mitigation at the platform level. |

## 2. Monitoring & Alerting

* **Automated Blocking:** `django-axes` and `django-ratelimit` operate in real-time, blocking threats before they reach the database.
* **Alert Triage:** Critical errors (e.g., 403/429 spikes) are logged and reviewed daily by the CTO.
* **Audit Trail:** All blocked attempts are recorded in the application database and are available for SIRO review during quarterly security audits.

## 3. SIRO Review

The SIRO ({{ cto_name }}) has reviewed this stack and confirms it meets the requirement for active threat management while maintaining {{ platform_name }}'s commitment to UK data sovereignty.
