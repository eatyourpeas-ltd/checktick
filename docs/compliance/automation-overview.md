---
title: "Automated Security & Integrity Monitoring"
category: dspt-9-it-protection
---

# Automated Security & Integrity Monitoring

## 1. Dependency Auditing (`pip-audit`)

* **Frequency:** Every PR and daily at 06:00 UTC.
* **Action:** If a non-ignored vulnerability is found, the build fails, blocking deployment.
* **Risk Management:** Specific GHSA/CVE IDs pinned by upstream security tools (e.g., `ggshield`) are documented in the workflow and reviewed monthly for upstream availability.

## 2. CDN & SRI Integrity (`Check CDN Library Updates`)

To prevent "Magecart" style supply chain attacks, we self-host critical JS libraries:

* **HTMX / SortableJS / axe-core:** Versions are pinned in the workflow environment.
* **Automation:** The workflow downloads the source, calculates the SHA-384 hash, and verifies it matches our local version.
* **Template Sync:** If a change is needed, the workflow automatically updates `integrity` attributes in our Django templates (`base.html`, `builder.html`, etc.) and opens a PR for human review.

## 3. Code Scanning (`CodeQL`)

* **Languages:** Python and JavaScript.
* **Scope:** Analyzes data flow and logic to catch vulnerabilities that simple linters miss.
* **Alerting:** Security events are sent directly to the GitHub Security Tab and the CTO's secure notification channel.

## 4. Secret Scanning (`ggshield`)

* **Implementation:** Handled via pre-commit hooks and CI scans.
* **Function:** Prevents the accidental commit of API keys, AWS credentials, or encryption secrets.
