---
title: "Security Review & Firewall Audit Log"
category: dspt-5-process-reviews
---

# Security Review & Firewall Audit Log

| Date | Reviewer | Item Audited | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- |
| 2025-10-01 | {{ siro_name }} | Production Ingress Rules | Verified FW-01 (443) only. | Clean |
| 2026-01-03 | {{ siro_name }} | Production Ingress Rules | Confirmed no temp rules from Dec deployment. | Clean |
| 2026-08-01 | {{ cto_name }} | Application-layer static security review (full codebase) | Deep-dive review of auth/redirects, email rendering, settings, Vault, LLM, API, OIDC, icon uploads, billing, styling. 18 findings (F1–F18): 2 High, 6 Medium, 9 Low, 1 Info. Documented in `security-review-august-2026.md`. Remediation via atomic PRs. | All 18 findings closed (see rows below) |
| 2026-08-01 | {{ cto_name }} | High findings F6 and F12 remediation | Removed web recovery execution and enforced 3-of-4-share CLI recovery for F6. Removed SVG survey-image uploads for F12, rejected animated raster variants, passed focused regression tests, and audited production media (0 SVG records; 0 SVG files). | F6/F12 closed; 15 findings open |
| 2026-08-01 | {{ cto_name }} | Medium finding F1 remediation — signup open redirect | Replaced slash-prefix validation in standard and OIDC signup-completion flows with Django host/scheme validation. Regression coverage rejects protocol-relative, backslash-normalised, and external URLs; confirms local redirects remain valid; and verifies unconfirmed signup still redirects home with the confirmation notice. Full non-accessibility suite passed (1,765 tests); lint passed. | F1 closed; 14 findings open |
| 2026-08-02 | {{ cto_name }} | Low hardening batch F3, F4, F11 remediation | F3: settings now raise `ImproperlyConfigured` at startup when `ENVIRONMENT=production` and `SECRET_KEY` is unset/empty (random fallback retained for dev). F4: global DRF default permission changed to `IsAuthenticated` (fail-closed); anonymous-access endpoints already declare `AllowAny`. F11: API-key `last_used_at` write throttled to once per 60s per key via a Django cache marker. Regression tests in `checktick_app/core/tests/test_settings_hardening.py` and `checktick_app/api/tests/test_api_hardening.py`; full non-accessibility suite passed. | F3/F4/F11 closed; 5 findings open (F5, F10, F15, F17) |
| 2026-08-02 | {{ cto_name }} | Medium/Low batch F2, F7, F8, F9, F13, F14, F16, F18 remediation | F2: team/org invitation emails now use autoescaped Markdown templates with escaped fallbacks. F7: LLM debug dumps moved to a private, retention-bounded directory with the outgoing messages payload omitted. F8: datasets API now authenticated-only with server-rendered professional-field options. F9: CSP `style-src 'unsafe-inline'` documented as accepted risk with server-side mitigation via the strengthened CSS sanitiser (F16). F13: `icon_url` validated at write time (http(s):// or relative) and re-checked at read time across all survey views. F14: GoCardless webhook replay protection via `WebhookEvent` idempotency table + per-event `get_or_create` in `transaction.atomic()`, plus a partial unique constraint on `Payment.payment_id`. F16: `sanitize_css_block` now strips `{` `}` and `url()` references, preventing CSS rule breakout and data exfiltration. F18: SNOMED snapshot view now enforces dataset-creation permission. Regression tests across `checktick_app/core/tests/`, `checktick_app/api/tests/`, `checktick_app/surveys/tests/`, and `tests/test_billing.py`; full non-accessibility suite passed. | F2/F7/F8/F9/F13/F14/F16/F18 closed; 5 findings open (F5, F10, F15, F17) |
| 2026-08-02 | {{ cto_name }} | Final batch F5, F10, F15, F17 remediation — all findings closed | F5: `email_utils` module docstring now documents the `.md`-template / f-string convention so the F2 HTML-injection class is not reintroduced. F10: dead `HealthcareLoginView` (which carried an unvalidated `next` and used a non-existent reverse namespace) removed; the live `/accounts/login/` page inherits `LoginView.get_redirect_url()` validation. F15: `llm-security.md` §4 reframed — instruction-based role enforcement is a deterrent, not a control; output validation + manual review + no tool access is the boundary. F17: OIDC callback view no longer mutates global `django.conf.settings`; provider config is resolved per-request in `CustomOIDCAuthenticationBackend.authenticate` (re-resolving endpoints/credentials from `OIDC_PROVIDERS` before the token exchange) and in `HealthcareOIDCAuthView` (instance attributes for the authorization URL), eliminating the Google/Azure race condition. Regression tests in `checktick_app/core/tests/test_oidc_auth.py` and `checktick_app/core/tests/test_security_review_docs.py`; full non-accessibility suite passed (1,844 tests); lint passed. | **All 18 findings closed (F1–F18)** |
| | | | | |

## Audit Procedure:

1. Login to Northflank Production Console.
2. Navigate to Networking -> Ingress.
3. Compare live rules against 'Authorized Inbound Rule Register' (Policy 9.6).
4. Identify any 'unmanaged' or 'temporary' rules.
5. If found: Disable immediately, document in a GitHub Issue, and remove from config.
