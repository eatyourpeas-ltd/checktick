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
| NM-02 | 01/08/2026 | Near-Miss | High | Web recovery console (`recovery_execute`) reads removed `PLATFORM_CUSTODIAN_COMPONENT` setting, bypassing the 3-of-4 Shamir custodian-share control. Either crashes (DoS on recovery) or allows single-superuser KEK recovery without custodian shares. | Removed web execution; recovery now requires 3 of 4 shares through the management command, and the legacy environment setting is rejected. | Closed |
| NM-03 | 01/08/2026 | Near-Miss | High | SVG upload in survey builder image-choice questions (`_validate_and_process_image`) allows stored XSS via direct `/media/` navigation. SVG files skip sanitisation and execute embedded scripts in the CheckTick origin. | Removed SVG upload support, added script-bearing SVG and animation regression tests, and confirmed no legacy SVG records or files existed in production media. | Closed |

**Production Incidents to date: 0**
**Near-Misses to date: 3 (3 resolved, 0 open)**

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
* **Corrective Action:** Removed the web execution endpoint and routed operators
  to the `execute_platform_recovery` management command. The model method now
  requires a caller-supplied custodian component, and application startup rejects
  `PLATFORM_CUSTODIAN_COMPONENT` in the environment.
* **Verification:** Repository review confirmed there is no web recovery execution
  URL and that the secure management command requires 3 of 4 custodian shares.
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
* **Corrective Action:** Removed SVG from the survey-image extension/MIME
  allowlists and browser file picker. Added server-side rejection of animated
  variants of allowed raster formats so survey image choices remain static.
* **Verification:** Regression tests pass for rejection of a script-bearing SVG
  and animated PNG without persistence. A production console audit reported
  zero SVG-backed `QuestionImage` records and zero `.svg` files under
  `MEDIA_ROOT`, so no legacy cleanup migration or media-header exception was
  required.
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
