---
title: "Security Review & Firewall Audit Log"
category: dspt-5-process-reviews
---

# Security Review & Firewall Audit Log

| Date | Reviewer | Item Audited | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- |
| 2025-10-01 | {{ siro_name }} | Production Ingress Rules | Verified FW-01 (443) only. | Clean |
| 2026-01-03 | {{ siro_name }} | Production Ingress Rules | Confirmed no temp rules from Dec deployment. | Clean |
| | | | | |

## Audit Procedure:

1. Login to Northflank Production Console.
2. Navigate to Networking -> Ingress.
3. Compare live rules against 'Authorized Inbound Rule Register' (Policy 9.6).
4. Identify any 'unmanaged' or 'temporary' rules.
5. If found: Disable immediately, document in a GitHub Issue, and remove from config.
