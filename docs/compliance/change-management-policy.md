---
title: "Change Management Policy"
category: dspt-9-it-protection
---

# Change Management Policy

## 1. Scope

This policy applies to all changes to the {{ platform_name }} production environment, including application code, database schema, and Northflank infrastructure configurations.

## 2. Standard Change Procedure (Git-Ops)

1. **Initiation:** Changes are developed in a separate 'Feature Branch.'
2. **Review:** A Pull Request (PR) is opened. The PR must describe the change and its impact on data security.
3. **Validation:** Automated CI/CD tests must pass. These include:
    * Unit/Integration tests.
    * Static Analysis (SAST) via CodeQL.
    * Dependency scanning via `pip-audit`.
4. **Approval:** The CTO ({{ siro_name }}) or SIRO ({{ cto_name }}) must review the code and manually approve the PR.
5. **Deployment:** Once merged, the Northflank pipeline automatically builds and deploys the change to the production environment.

## 3. Emergency Changes

In the event of a Critical security patch or system failure:

* The change may be implemented immediately to restore service/security.
* A retrospective PR must be created within 24 hours to document the change and ensure it passes all standard security gates.

## 4. Documentation

The GitHub commit history and merged Pull Request logs serve as the official Change Management Record for {{ platform_name }}.
