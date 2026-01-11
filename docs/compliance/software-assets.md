---
title: "Software Asset & Configuration Register"
category: dspt-4-managing-access
---

# Software Asset & Configuration Register

**Version:** 1.2
**Last Updated:** January 2026
**Owner:** CTO

## 1. Asset Management Process

{{ platform_name }} tracks software assets through a "Managed Repository" model:

* **Discovery:** All new software or libraries must be approved by the CTO before being added to `pyproject.toml` or `package.json`.
* **Version Tracking:** Automated via GitHub Dependency Graph.
* **Audit:** A manual reconciliation of this register is performed quarterly to ensure decommissioned tools are removed.

## 2. Core Software Inventory (Production)

| Asset Name | Category | Versioning | Hosting/Owner |
| :--- | :--- | :--- | :--- |
| **Python / Django** | Application Framework | 5.x (LTS) | Northflank |
| **PostgreSQL** | Database | 15.x | AWS RDS |
| **Ubuntu (LTS)** | Base OS (Containers) | 22.04 | Northflank |
| **HashiCorp Vault** | Secret Management | 1.15.x | Self-Hosted |

## 3. Infrastructure & Tooling

| Asset Name | Category | Configuration Method |
| :--- | :--- | :--- |
| **Northflank** | PaaS / Orchestration | Northflank.yaml |
| **GitHub** | Version Control | Enterprise Cloud |
| **Cloudflare** | DNS & WAF | API-Managed |

## 4. Configuration Baseline

All assets are configured according to the **'{{ platform_name }} Hardening Standard'**:

* Root accounts protected by MFA.
* Non-essential ports/services disabled by default.
* Production data encrypted at rest (AES-256) and in transit (TLS 1.2+).
