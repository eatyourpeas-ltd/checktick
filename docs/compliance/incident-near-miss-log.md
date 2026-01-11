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
| NM-01 | 10/01/26 | Near-Miss | Low | Automated scan detected an outdated dependency  | Update axe-core from 4.10.2 to 4.11.0 and merged | Closed |
| INC-01| [Date] | Incident | [S/M/H] | *No production incidents to date.* | N/A | Open |

---

## 2. Detailed Incident/Near-Miss Records

### Record: NM-01 (Vulnerable Dependency)

* **Discovery Date:** 10 Jan 2026
* **Reporter:** GitHub Dependabot (Automated)
* **Impact:** None. Vulnerability was identified by automated process
* **Root Cause:** Third-party library released a security patch for a known CVE.
* **Corrective Action:** CTO merged the patch and updated the `pyproject.toml`.
* **Verification:** CI/CD pipeline passed with 0 security vulnerabilities.

---

## 3. Quarterly SIRO Sign-off

* **Q3 2025:** No incidents. 1 Near-Miss reviewed. (Signed: {{ siro_name }})
* **Q4 2025:** No incidents. No near-misses. (Signed: {{ siro_name }})
* **Q1 2026:** (Pending Review)
