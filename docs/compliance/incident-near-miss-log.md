---
title: "Incident & Near-Miss Log"
category: dspt-6-incidents
---

# Incident & Near-Miss Log (2025-2026)

**Owner:** {{ siro_name }} (SIRO)
**Review Frequency:** Quarterly

---

## 1. Summary Table

| ID | Date | Type | Severity | Description | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| NM-01 | 21/01/2026 | Near-Miss | Low | Automated scan detected an outdated dependency (axe-core). | Updated axe-core 4.10.2 → 4.11.0 and merged via PR. | Closed |
| NM-02 | 01/08/2026 | Near-Miss | High | Web recovery console (`recovery_execute`) reads removed `PLATFORM_CUSTODIAN_COMPONENT` setting, bypassing the 3-of-4 Shamir custodian-share control. Either crashes (DoS on recovery) or allows single-superuser KEK recovery without custodian shares. | Identified in security deep-dive (F6). Remediation planned via atomic PR — remove web execution path, route to management command. | Open |
| NM-03 | 01/08/2026 | Near-Miss | High | SVG upload in survey builder image-choice questions (`_validate_and_process_image`) allows stored XSS via direct `/media/` navigation. SVG files skip sanitisation and execute embedded scripts in the CheckTick origin. | Identified in security deep-dive (F12). Remediation planned via atomic PR — remove SVG from allowlist, serve `/media/` SVGs with `Content-Disposition: attachment`. | Open |

**Production Incidents to date: 0**
**Near-Misses to date: 3 (1 resolved, 2 open — remediation in progress)**

---

## 2. Detailed Near-Miss Records

### Record: NM-01 — Vulnerable Dependency (axe-core)

* **Discovery Date:** 10/01/2026
* **Reporter:** GitHub Dependabot (Automated)
* **Severity:** Low
* **Impact:** None. Vulnerability identified and resolved by automated process
  before any exploitation was possible.
* **Root Cause:** Third-party library released a security patch for a known CVE.
  Automated monitoring detected the outdated version within the standard scan cycle.
* **Corrective Action:** CTO merged the patch and updated `pyproject.toml`.
  Updated SRI hash computed and verified.
* **Verification:** CI/CD pipeline passed with zero security vulnerabilities
  post-merge. Confirmed in Vulnerability & Patch Log.
* **Lessons Learned:** No process change required. Automated detection and
  remediation pipeline functioned as designed. Confirms that the zero-exception
  CI/CD policy is effective at catching dependency vulnerabilities before
  they reach production.

### Record: NM-02 — Web recovery console bypasses Shamir custodian-share control (F6)

* **Discovery Date:** 01/08/2026
* **Reporter:** CTO (security deep-dive review)
* **Severity:** High
* **Impact:** None at time of discovery. The web recovery path was identified
  during static review before any exploitation. No patient data was accessed.
* **Root Cause:** `RecoveryRequest.execute_recovery` (model method) reads the
  removed `PLATFORM_CUSTODIAN_COMPONENT` setting directly, while the documented
  security model requires 3-of-4 Shamir custodian shares via management command.
  The web view `recovery_execute` calls this model method, creating a second
  execution path that bypasses the custodian control.
* **Corrective Action:** Remove the web execution path; route recovery execution
  to the `execute_platform_recovery` management command. Delete the model method
  that reads the setting. Coordinate with `docs/compliance/recovery-dashboard.md`.
* **Verification:** Regression test asserting the web recovery path redirects to
  CLI documentation and that `settings.PLATFORM_CUSTODIAN_COMPONENT` is not read
  by any web-reachable code path.
* **Lessons Learned:** When a security control is migrated (settings → Shamir
  shares), all code paths that read the old setting must be removed in the same
  change. A commented-out setting is not sufficient — delete it so any deploy
  that sets it fails loudly.

### Record: NM-03 — SVG upload stored XSS via `/media/` (F12)

* **Discovery Date:** 01/08/2026
* **Reporter:** CTO (security deep-dive review)
* **Severity:** High
* **Impact:** None at time of discovery. The vulnerability was identified
  during static review before any exploitation. No patient data was accessed.
* **Root Cause:** `_validate_and_process_image` explicitly allows `.svg` /
  `image/svg+xml` and skips all sanitisation for SVG files. Uploaded SVGs are
  stored unmodified under `/media/` and served same-origin. While `<img src>`
  does not execute SVG scripts, direct navigation to the `/media/` URL renders
  the SVG as a document and executes embedded `<script>` in the CheckTick origin.
* **Corrective Action:** Remove SVG from the allowed image extensions/MIME list.
  Serve `/media/` SVGs with `Content-Disposition: attachment` as defence in
  depth. Apply the same validation to the `SiteBranding.icon_file` upload.
* **Verification:** Regression test asserting `.svg` uploads are rejected and
  that existing SVGs in `/media/` are served with `Content-Disposition: attachment`.
* **Lessons Learned:** SVG is a dual-purpose format (image + document). Allowing
  SVG upload to a same-origin media store is equivalent to allowing HTML upload.
  Image validators should treat SVG as script-capable unless sanitised.

---

## 3. Statement of No Production Incidents

EatYourPeas Ltd confirms that {{ platform_name }} has had **zero production
data security or protection incidents** since the platform's launch. This is
attributed to:

- Continuous automated vulnerability scanning (pip-audit, Dependabot, CodeQL)
  blocking vulnerable code from reaching production
- Mandatory MFA on all administrative accounts with no exceptions
- Field-level AES-256-GCM encryption ensuring data is protected at rest
- Network isolation of production infrastructure

This statement is reviewed and confirmed at each quarterly SIRO sign-off below.

---

## 4. Quarterly SIRO Sign-off

| Quarter | Incidents | Near-Misses | Notes | Signed |
| :--- | :--- | :--- | :--- | :--- |
| Q3 2025 (Jul–Sep) | 0 | 0 | Platform in pre-launch hardening phase. | {{ siro_name }}, SIRO |
| Q4 2025 (Oct–Dec) | 0 | 0 | No incidents or near-misses. | {{ siro_name }}, SIRO |
| Q1 2026 (Jan–Mar) | 0 | 1 | NM-01 detected and resolved via auto
