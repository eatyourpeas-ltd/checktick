---
title: "SIRO Approved Patching Approach"
category: dspt-8-unsupported-systems
---

# SIRO Approved Patching Approach (v1.2)

**Last Approved:** January 2026
**Approver:** {{ cto_name }} (SIRO)

## 1. Risk Categorization

We follow a CVSS-based approach for all internet-connected assets (Servers, Cloud Services, Laptops):

| Severity | Patch Window | Testing Required |
| :--- | :--- | :--- |
| **Critical** | < 48 Hours | Emergency Smoke Test |
| **High** | < 7 Days | Full Automated Test Suite |
| **Medium/Low** | < 30 Days | Standard Release Cycle |

## 2. Infrastructure & Cloud Updates

* **Managed Services:** We rely on AWS and Northflank for automated patching of physical hardware and base hypervisors.
* **Containers:** Production images are rebuilt and redeployed weekly to incorporate the latest OS security updates.

## 3. Remote Endpoint Updates

* **Automation:** All developer laptops must have 'Automatic Updates' enabled.
* **Dependency Sync:** Developers must run `poetry install` at the start of each work session to synchronize local environments with the latest patched versions in the central repository.

## 4. Safety & Availability

To ensure clinical continuity, no security patch is applied directly to production without:

1. Passing the **Pytest/Playwright** automation suite in Staging.
2. Verification of data decryption capability (via HashiCorp Vault).
3. Confirmation of no breaking changes to the NHS Data Dictionary datasets.

## 5. Formal Approval

"I confirm that the approach outlined above provides a proportionate and effective method for managing technical vulnerabilities while protecting the clinical integrity of the {{ platform_name }} service."

## 6. Risk-Based Triage (Transitive Dependencies)

{{ platform_name }} distinguishes between **Direct Dependencies** (code we call) and **Transitive Dependencies** (libraries required by our tools, e.g., `ggshield`).

**Current Exceptions (Approved by SIRO):**

The SIRO has approved the silencing of specific CVEs (e.g., `GHSA-79v4-65xg-pq4g`, `PYSEC-2024-187`) within our GitHub Security Scan.

* **Reason:** These vulnerabilities exist in the sub-dependencies of `ggshield` (our security scanner).
* **Risk Assessment:** These libraries are used only in the CI/CD environment and are not bundled into the production container.
* **Mitigation:** We monitor the `ggshield` upstream repository. Once they update their internal pins, these ignores will be removed.
* **Clinical Impact:** Zero. This code does not touch patient data or production logic.

**Signed:**{{ cto_name }} (SIRO) **Date:** 02/01/2026
