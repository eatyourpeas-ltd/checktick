---
title: "Infrastructure Hardening & Configuration Standard"
category: dspt-9-it-protection
---

# Infrastructure Hardening & Configuration Standard

## 1. Network Hardening (Sovereign Defense)

* **Zero-Trust Ingress:** Only HTTPS (443) is permitted. All other ports (SSH, DB, FTP) are blocked at the Northflank platform edge.
* **Database Isolation:** The PostgreSQL database is not assigned a public IP address and is only reachable via the internal virtual private network (VPC) from the application containers.
* **TLS Enforcement:** We enforce TLS 1.3 for all data in transit, with HSTS enabled to prevent protocol downgrade attacks.

## 2. Operating System & Container Hardening

* **Minimal Base Images:** We use Ubuntu 22.04 LTS "slim" images to reduce the attack surface (removing unnecessary shells, compilers, and tools).
* **Non-Root Execution:** All application processes within containers run as a non-privileged user.
* **Immutability:** Production containers are immutable; changes are only permitted via a fresh CI/CD deployment after security scans pass.

## 3. Application-Layer Protection

* **Brute Force:** `django-axes` is configured to lock accounts and IPs after 5 failed login attempts.
* **DoS Protection:** Rate-limiting is applied to all sensitive endpoints (Login, Reset Password, Survey Submission).
* **Dependency Auditing:** Daily cron jobs run `pip-audit` to ensure zero 'Critical' vulnerabilities exist in the production stack.

## 4. Logical Separation (Mitigations)

Where dependencies cannot be patched due to upstream constraints (e.g., development tools):

* **Build-Time Isolation:** These tools are excluded from the production build.
* **Local Development Isolation:** Developers use isolated Python virtual environments (Poetry) to ensure local vulnerabilities do not leak into the production codebase.
