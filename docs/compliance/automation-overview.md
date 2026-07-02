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

* **HTMX / SortableJS / axe-core / ReDoc / NHS Frontend:** Versions, static paths, source paths, and SHA-384 SRI hashes are tracked in `checktick_app/cdn_assets.json`.
* **Automation:** The update workflow downloads the source from the manifest-defined package/source, calculates the SHA-384 hash, and verifies it matches our local version.
* **Template Sync:** Django templates read CDN paths and SRI hashes from the manifest-backed `cdn_assets` context variable rather than hardcoding integrity attributes.

## 3. Code Scanning (`CodeQL`)

* **Languages:** Python and JavaScript.
* **Scope:** Analyzes data flow and logic to catch vulnerabilities that simple linters miss.
* **Alerting:** Security events are sent directly to the GitHub Security Tab and the CTO's secure notification channel.

## 4. Secret Scanning (`ggshield`)

* **Implementation:** Handled via pre-commit hooks and CI scans.
* **Function:** Prevents the accidental commit of API keys or encryption secrets.
