---
title: "Supplier Data Security Incident Log"
category: dspt-6-incidents
---

# Supplier Data Security Incident Log

**Reporting Period:** January 2024 - January 2026
**Review Status:** 2 supplier incidents recorded (08/11/2026, 21/11/2026) — under monitoring.

| Date | Supplier | Incident Description | Impact on {{ platform_name }} | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| N/A | | No historical incidents reported. | None | Quarterly monitoring of status pages. | Closed |
| 08/11/2026 | Civo | Kubernetes API server endpoint (74.220.17.170:6443) intermittently unreachable from external clients ~16:42–17:50+ UTC — the deploy workflow's logs captured `http2: client connection lost` and `dial tcp 74.220.17.170:6443: i/o timeout`; the operator's kubectl was affected into the evening. Cluster workloads kept serving throughout (data plane unaffected) | Deploy (Civo) workflow steps failed (CronJob roll + its rollback); a ~8 min site-availability dip (~17:40–17:51 UTC) while replaced web pods flapped through containerd create-errors. No data accessed, lost, altered or exposed | Reported to Civo support; `status.civo.com` monitored per the routine below; deploy workflow hardened so API blips can no longer fail the deploy or trigger web rollbacks, and web scaled to 3 spread replicas (see Infrastructure Technical Change Log, 08/11) | Monitoring |
| 21/11/2026 | Civo | Platform-wide network failure affecting ALL regions (LON1, NYC1, FRA1, MUM1, JKT1) from 06:35 UTC: Network components Down while Compute/Storage remained Operational; the Civo API and website were also Down. All TCP connections to the cluster node (74.220.17.170) time out on every port — site totally unreachable, kubectl unusable. Civo timeline: 06:35 Investigating → 12:26 Identified → 17:12 restoration expected progressively within ~2h | Total site unavailability from 06:35 UTC (11+ hours at time of logging). No data accessed, lost, altered or exposed — data at rest and all backups unaffected (Compute/Storage Operational) | Detected via StatusCake external monitor (Civo sent no incident email). Status page monitored; post-recovery checklist prepared (nodes, pod placement, Vault seal check, /healthz, backup-chain verify); SLA review + service-credit claim and PIR request to Civo; hardening escalated (cross-provider UK backup copy, degraded-mode fallback page, second external monitor, DR drill) — see INC-03 in the Incident & Near-Miss Log | Open |

## Monitoring Routine:

The CTO reviews the following security/status dashboards monthly to identify potential supplier incidents:

* **Civo:** https://status.civo.com/
* **GitHub:** https://www.githubstatus.com/
* **Mailgun:** https://status.mailgun.com/

**Incident Response:** In the event of a supplier breach, the {{ platform_name }} Incident Response Plan (Section 7) will be activated, and the SIRO will determine if notification to the ICO/NHS is required.
