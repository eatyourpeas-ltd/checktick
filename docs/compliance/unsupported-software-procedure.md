---
title: "Unsupported Software & Decommissioning Procedure"
category: dspt-8-unsupported-systems
---

# Unsupported Software & Decommissioning Procedure

## 1. Monitoring EOL Dates

The CTO is responsible for tracking the 'End of Life' (EOL) dates for our core technology stack. We use [endoflife.date](https://endoflife.date) as our reference for:

* **Python Versions** (Current: 3.12+)
* **Django Versions** (Current: 5.x LTS)
* **Ubuntu Base Images** (Current: 22.04 LTS)

## 2. Quarterly Audit Process

Every three months, the following checks are performed:

1. **GitHub Audit:** Scan `requirements.txt` and `package.json` for deprecated libraries.
2. **Local Device Audit:** Check macOS versions on founder laptops to ensure they are within the 'Current - 2' support window.
3. **Northflank Audit:** Review container logs for "deprecated image" warnings.

## 3. Removal & Isolation

* **Standard Action:** Unsupported software must be uninstalled within 30 days of discovery.
* **Exceptional Circumstances:** If a legacy tool is required, it must be:
    * Removed from the production network.
    * Run on an isolated machine with no internet access.
    * Documented in the 'Risk Register' with a firm decommissioning date.

## 4. Documented Decommissioning

* Any software uninstalled due to security risks is recorded in the `compliance/asset-change-log.csv` to maintain a clear audit trail of our application landscape.
