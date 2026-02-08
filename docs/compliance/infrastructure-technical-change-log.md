---
title: "Infrastructure Technical Change Log"
category: dspt-9-it-protection
---

# Infrastructure Technical Change Log

**Organization:** eatyourpeas
**Document Owner:** Directors
**Scope:** Boundary Firewalls, Cloud Infrastructure (PaaS/SaaS), and End-User Device Configurations.

---

## 1. Annual Infrastructure & Firewall Review Schedule

*In accordance with Cyber Essentials requirements, we perform a formal review of our network security settings at least once every 12 months.*

| Scheduled Date | Review Category | Assigned Auditor | Completion Date | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Feb 2026** | Firewall & Cloud Audit | [CTO] | 2026-02-07 | Completed |
| **Feb 2027** | Firewall & Cloud Audit | [Director Name] | | Pending |

### Review Checklist:

- [ ] Verify BT Router admin password is 12+ characters and unique.
- [ ] Confirm **Remote Management** is DISABLED on the router.
- [ ] Confirm **UPnP** is DISABLED on the router.
- [ ] Verify **No Inbound Port Forwarding** rules exist (Deny by Default).
- [ ] Check that all Mac/PC local firewalls are still enabled and in "Stealth Mode."
- [ ] **Device User Accounts:** Verify only necessary user accounts exist on all devices:
  - [ ] Confirm Guest accounts DISABLED on all Mac devices (System Settings > Users and Groups)
  - [ ] Verify only ONE standard user account per device (single user per device policy)
  - [ ] Confirm Administrator accounts exist but only used with password manager authentication
  - [ ] Remove any test, temporary, or unused accounts
  - [ ] **Verify all default passwords changed** on all devices (CE requirement)
  - [ ] **Mobile Device Check:** Verify mobile phones/tablets have 6+ digit PIN or biometric lock
- [ ] Audit user access to GitHub and Northflank (Remove old users).
- [ ] Verify cloud service accounts follow user/admin separation principles.
- [ ] **Cloud Service Passwords:** Confirm no default or guessable passwords on any cloud accounts

---

## 2. Firewall & Inbound Rule Change Log
*Use this table to document any time a change is made to the firewall or if a port is opened.*

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-02-07 | Director | Policy Baseline | Initial "Deny by Default" configuration | Board | Active |
| 2026-02-07 | Director | Router Credential Update | Changed default to 12+ char unique password | Board | Active |
| | | | | | |

---

## 3. Policy Statement: Approval Process

1. **Request:** Any technical change (opening a port, adding an admin) must be documented in the table above.
2. **Review:** A Director must review the business need and potential security risks.
3. **Approval:** Board-level sign-off (agreement between directors) is required before implementation.
4. **Validation:** Once implemented, the change is verified by a Director to ensure no excess "permissiveness" was added.
