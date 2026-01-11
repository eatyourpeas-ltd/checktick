---
title: "Continuous Patching & Isolation Standard"
category: dspt-8-unsupported-systems
---

# Continuous Patching & Isolation Standard

## 1. Continuous Lifecycle

{{ platform_name }} does not use "patch Tuesdays." We use a continuous flow:

* **Detection:** GitHub Dependabot and daily `pip-audit` (06:00 UTC) identify new vulnerabilities.
* **Testing:** Patches are first applied in our 'Staging' environment where our automated Pytest and Playwright suites verify that clinical functionality is unaffected.
* **Deployment:** Once verified, the CTO merges the patch, triggering an automatic rebuild of our UK-resident production containers.

## 2. Infrastructure Support

* **Containers:** We use the `python:3.12-slim-bookworm` or `ubuntu:22.04` base images, which are actively maintained.
* **Host Hardware:** Our UK hosting provider (Northflank) is responsible for patching the underlying hypervisors and physical hardware.

## 3. Isolation of Legacy/Unsupported Assets

{{ platform_name }} currently has **zero** unsupported assets. If an asset becomes unsupported:

1. **Network Kill-Switch:** Public ingress (Port 443) is disabled via the Northflank console.
2. **Internal-Only Access:** The asset is limited to internal VPC communication only.
3. **Risk Review:** The SIRO assesses the clinical necessity of the asset. If it is not critical, it is decommissioned within 30 days.
