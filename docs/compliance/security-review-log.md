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
| 2026-08-01 | {{ cto_name }} | High findings F6 and F12 remediation | Removed web recovery execution and enforced 3-of-4-share CLI recovery for F6. Removed SVG survey-image uploads for F12, rejected animated raster variants, passed focused regression tests, and audited production media (0 SVG records; 0 SVG files). | F6/F12 closed; 15 findings open |
| 2026-08-01 | {{ cto_name }} | Medium finding F1 remediation — signup open redirect | Replaced slash-prefix validation in standard and OIDC signup-completion flows with Django host/scheme validation. Regression coverage rejects protocol-relative, backslash-normalised, and external URLs; confirms local redirects remain valid; and verifies unconfirmed signup still redirects home with the confirmation notice. Full non-accessibility suite passed (1,765 tests); lint passed. | F1 closed; 14 findings open |
| 2026-08-02 | {{ cto_name }} | Low hardening batch F3, F4, F11 remediation | F3: settings now raise `ImproperlyConfigured` at startup when `ENVIRONMENT=production` and `SECRET_KEY` is unset/empty (random fallback retained for dev). F4: global DRF default permission changed to `IsAuthenticated` (fail-closed); anonymous-access endpoints already declare `AllowAny`. F11: API-key `last_used_at` write throttled to once per 60s per key via a Django cache marker. Regression tests in `checktick_app/core/tests/test_settings_hardening.py` and `checktick_app/api/tests/test_api_hardening.py`; full non-accessibility suite passed. | F3/F4/F11 closed; 5 findings open (F5, F10, F15, F17) |
| | | | | |

## Audit Procedure:

1. Login to Northflank Production Console.
2. Navigate to Networking -> Ingress.
3. Compare live rules against 'Authorized Inbound Rule Register' (Policy 9.6).
4. Identify any 'unmanaged' or 'temporary' rules.
5. If found: Disable immediately, document in a GitHub Issue, and remove from config.
