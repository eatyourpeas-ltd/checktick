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
| NM-01 | 10/01/2026 | Near-Miss | Low | Automated scan detected an outdated dependency (axe-core). | Updated axe-core 4.10.2 → 4.11.0 and merged via PR. | Closed |

**Production Incidents to date: 0**
**Near-Misses to date: 1 (resolved)**

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
