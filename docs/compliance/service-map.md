---
title: "CheckTick Service Dependency & Impact Map"
category: dspt-4-managing-access
---

# {{ platform_name }} Service Dependency & Impact Map

**Last Reviewed:** January 2026
**Document Version:** 1.1
**Owners:** CTO & SIRO

---

## 1. Key Operational Services

{{ platform_name }} provides the following primary service to health and care providers:

* **Clinical Survey Platform:** An end-to-end digital service for collecting patient-reported outcome measures (PROMs) and clinical survey responses. This service is used by clinicians to monitor patient health and inform care decisions.

---

## 2. Technology & Service Dependencies

To remain available and secure, our operational services rely on the following third-party technologies:

| Category | Provider | Purpose |
| :--- | :--- | :--- |
| **PaaS / Orchestration** | Northflank | Manages container deployment, scaling, and runtime. Hosts the production PostgreSQL database (RDS). |
| **Network & Security** | NameCheap | DNS management. |
| **Communication** | Mailgun | Sends transactional notifications and clinician alerts. |
| **Development** | GitHub | Stores source code and manages CI/CD pipelines. |
| **Identity** | Google/Microsoft | Provides SSO and MFA for staff administrative access. |

---

## 3. Operational Dependencies

Beyond technology, the following resources are required to maintain service continuity:

* **People:** Availability of at least one Director (CTO or SIRO) with administrative access credentials to perform emergency system recovery.
* **Connectivity:** High-speed internet access for staff to manage cloud environments via CLI/Web Console.
* **External Power & Cooling:** {{ platform_name }} relies on the physical infrastructure of AWS (London Region) and Northflank's underlying providers. Both maintain high-availability data centers with redundant power (UPS/Generators) and cooling.
* **Data Integrity:** Availability of the most recent database snapshots stored in AWS RDS.

---

## 4. Impact of Loss of Availability

We have assessed the impact of a service outage based on clinical and operational disruption.

| Outage Duration | Impact Category | Detailed Impact Description |
| :--- | :--- | :--- |
| **0 - 4 Hours** | **Low** | Minimal disruption. Patients may experience a delay in submitting surveys. Clinicians may experience minor lag in receiving real-time data. |
| **4 - 24 Hours** | **Medium** | Moderate disruption to clinical workflows. Clinicians may need to revert to manual/paper backup methods for critical patient assessments. |
| **24+ Hours** | **High** | Significant disruption. Risk of data backlogs and potential delays in clinical care decisions if {{ platform_name }} is the primary data collection tool. |

---

## 5. Review & Maintenance

This document is reviewed at least annually or following any significant change to our infrastructure or service delivery model.

* **Next Review Date:** January 2027
