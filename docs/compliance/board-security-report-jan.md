---
title: "Board Security Statement: Jan 2026"
category: dspt-5-process-reviews
---

# Board Security Statement: Jan 2026

**To:** {{ platform_name }} Board (SIRO & CTO)
**From:** CTO
**Date:** 02/01/2026
**Subject:** Annual Review of Unsupported Systems & Technical Risk

## 1. Executive Summary

As of January 2026, {{ platform_name }} is carrying **zero risk** from unsupported or 'End of Life' (EOL) systems. All core application components (Django 5.1, Python 3.12) and infrastructure (Ubuntu 22.04 LTS) are receiving active security updates.

## 2. Risk Acceptance Mechanism

The Board has formally approved the following process should unsupported software be required for valid business reasons in the future:

1. **Risk Triage:** CTO identifies the risk and proposes mitigating controls (e.g., network isolation).
2. **SIRO Review:** The SIRO reviews the clinical and data protection impact.
3. **Conscious Acceptance:** The SIRO provides written sign-off, which is recorded in the Corporate Risk Register for no longer than 6 months without re-review.

## 3. SIRO Declaration

"I have been briefed on the software asset register and the current vulnerability landscape. I am satisfied that there are no unsupported systems in use and that our automated monitoring (GitHub Actions/CodeQL) provides sufficient oversight of our technical debt."

**Signed:** {{ cto_name }}, SIRO
**Date:** 02/01/2026
