---
title: "Endpoint Software & Installation Policy"
category: dspt-9-it-protection
---

# Endpoint Software & Installation Policy

## 1. Account Management

* **Standard Accounts:** All {{ platform_name }} business activities (coding, email, administration) must be performed on a standard user account.
* **Privileged Accounts:** Administrator passwords are stored in an encrypted password manager and are only used for system-wide updates or approved software installation.

## 2. Software Restrictions

* **Verification:** Only software from known, notarized developers or the official App Store is permitted.
* **Browser Extensions:** Only essential, reputable extensions (e.g., uBlock Origin, Bitwarden) are permitted in the browser used for {{ platform_name }} administration.
* **Prohibited Software:** Peer-to-peer (P2P) file sharing, unapproved VPNs, and software from untrusted/unnotarized sources are strictly prohibited on business devices.

## 3. Developer Environment Control

* All third-party libraries used in the {{ platform_name }} platform must be installed via `Poetry`.
* **Lockfiles:** Every dependency is pinned in a `poetry.lock` file, ensuring the exact same code is used across all development and production environments.
* **Audit:** Dependencies are scanned daily for vulnerabilities; any library found to be insecure is removed or patched within the timelines defined in our Vulnerability Policy.
