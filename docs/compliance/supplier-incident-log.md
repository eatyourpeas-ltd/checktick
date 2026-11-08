---
title: "Supplier Data Security Incident Log"
category: dspt-6-incidents
---

# Supplier Data Security Incident Log

**Reporting Period:** January 2024 - January 2026
**Review Status:** 1 supplier incident recorded (08/11/2026) — under monitoring.

| Date | Supplier | Incident Description | Impact on {{ platform_name }} | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| N/A | | No historical incidents reported. | None | Quarterly monitoring of status pages. | Closed |
| 08/11/2026 | Civo | Kubernetes API server endpoint (74.220.17.170:6443) intermittently unreachable from external clients ~16:42–17:50+ UTC — the deploy workflow's logs captured `http2: client connection lost` and `dial tcp 74.220.17.170:6443: i/o timeout`; the operator's kubectl was affected into the evening. Cluster workloads kept serving throughout (data plane unaffected) | Deploy (Civo) workflow steps failed (CronJob roll + its rollback); a ~8 min site-availability dip (~17:40–17:51 UTC) while replaced web pods flapped through containerd create-errors. No data accessed, lost, altered or exposed | Reported to Civo support; `status.civo.com` monitored per the routine below; deploy workflow hardened so API blips can no longer fail the deploy or trigger web rollbacks, and web scaled to 3 spread replicas (see Infrastructure Technical Change Log, 08/11) | Monitoring |

## Monitoring Routine:

The CTO reviews the following security/status dashboards monthly to identify potential supplier incidents:

* **Civo:** https://status.civo.com/
* **GitHub:** https://www.githubstatus.com/
* **Mailgun:** https://status.mailgun.com/

**Incident Response:** In the event of a supplier breach, the {{ platform_name }} Incident Response Plan (Section 7) will be activated, and the SIRO will determine if notification to the ICO/NHS is required.
