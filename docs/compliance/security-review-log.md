---
title: "Security Review & Firewall Audit Log"
category: dspt-5-process-reviews
---

# Security Review & Firewall Audit Log

| Date | Reviewer | Item Audited | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- |
| 2025-10-01 | {{ siro_name }} | Production Ingress Rules | Verified FW-01 (443) only. | Clean |
| 2026-01-03 | {{ siro_name }} | Production Ingress Rules | Confirmed no temp rules from Dec deployment. | Clean |
| 2026-08-01 | {{ cto_name }} | Application-layer static security review (full codebase) | Deep-dive review of auth/redirects, email rendering, settings, Vault, LLM, API, OIDC, icon uploads, billing, styling. 17 findings (F1–F17): 2 High, 6 Medium, 8 Low, 1 Info. Documented in `security-review-august-2026.md`. Remediation via atomic PRs. | Findings open |
| | | | | |

## Audit Procedure:

1. Login to Northflank Production Console.
2. Navigate to Networking -> Ingress.
3. Compare live rules against 'Authorized Inbound Rule Register' (Policy 9.6).
4. Identify any 'unmanaged' or 'temporary' rules.
5. If found: Disable immediately, document in a GitHub Issue, and remove from config.
