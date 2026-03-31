---
title: "Infrastructure Technical Change Log"
category: dspt-9-it-protection
---

# Infrastructure Technical Change Log

**Organisation:** EatYourPeas Ltd
**Document Owner:** Dr Simon Chapman (CTO) & Dr Serena Haywood (SIRO)
**Last Reviewed:** March 2026
**Scope:** Boundary firewalls, cloud infrastructure (PaaS/SaaS), DNS
management, and end-user device configurations.

---

## 1. Annual Infrastructure & Firewall Review Schedule

In accordance with Cyber Essentials Plus requirements, a formal review of
all network security settings is performed at least once every 12 months.

| Scheduled Date | Review Category | Assigned Auditor | Completion Date | Status |
| :--- | :--- | :--- | :--- | :--- |
| Feb 2026 | Firewall, Cloud & DNS Audit | Dr Simon Chapman (CTO) | 07/02/2026 | ✅ Completed |
| Feb 2027 | Firewall, Cloud & DNS Audit | Dr Simon Chapman (CTO) | — | Pending |

### Review Checklist

**Network Equipment**

- [ ] Verify router admin password is 12+ characters, unique, and stored in Bitwarden
- [ ] Confirm remote management is disabled on the router
- [ ] Confirm UPnP is disabled on the router
- [ ] Verify no inbound port forwarding rules exist (deny by default)
- [ ] Confirm router firmware is on current supported version

**Device Security**

- [ ] Confirm all device local firewalls are enabled
- [ ] Verify only necessary user accounts exist on all devices
- [ ] Confirm guest accounts disabled on all Mac devices
- [ ] Verify one standard user account per device
- [ ] Confirm administrator accounts exist but are used only with
  password manager authentication
- [ ] Remove any test, temporary, or unused accounts
- [ ] Verify all default passwords changed on all devices
- [ ] Confirm mobile devices have 6+ digit PIN or biometric lock enabled
- [ ] Verify Quad9 (9.9.9.9) configured as DNS resolver on all devices

**Cloud and SaaS Access**

- [ ] Audit user access to GitHub — remove any unnecessary accounts
- [ ] Audit user access to Northflank — remove any unnecessary accounts
- [ ] Verify MFA active on all GitHub and Northflank accounts
- [ ] Verify MFA active on Namecheap DNS management account
- [ ] Confirm no default or guessable passwords on any cloud accounts
- [ ] Verify cloud service accounts follow least-privilege principles
- [ ] Review Northflank service tokens — confirm scope and expiry

**DNS Management**

- [ ] Verify Namecheap console access restricted to named administrators only
- [ ] Confirm no unauthorised DNS record changes since last review
- [ ] Review all current DNS records for checktick.uk and confirm accuracy
- [ ] Confirm 2FA active on Namecheap account

---

## 2. Change Log

### 2a. Firewall & Inbound Rule Changes

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 07/02/2026 | Dr Simon Chapman | Policy baseline established — deny by default inbound configuration documented | Initial CE+ compliance baseline | Dr Serena Haywood (SIRO) | ✅ Active |
| 07/02/2026 | Dr Simon Chapman | Router admin credential updated to 12+ character unique password stored in Bitwarden | CE+ requirement — no default credentials | Dr Serena Haywood (SIRO) | ✅ Active |

### 2b. DNS Record Changes (checktick.uk)

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| — | — | No DNS record changes to date | — | — | — |

### 2c. Cloud Infrastructure Changes

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| — | — | Changes tracked via Northflank audit log and GitHub pull request history | — | — | — |

---

## 3. Change Approval Process

All technical changes to infrastructure, firewall rules, DNS records, or
cloud access controls follow this process:

1. **Request:** The proposing administrator documents the change in this
   log with a business justification before implementation
2. **Review:** The other director reviews the business need and assesses
   potential security risks
3. **Approval:** Board-level sign-off (agreement between both directors)
   is required before implementation. For DNS changes, both named
   administrators must be notified regardless of who makes the change
4. **Implementation:** Change is made by the CTO from an assured,
   MFA-authenticated device
5. **Validation:** Once implemented, the change is verified by the SIRO
   to confirm no unintended permissions or exposures were introduced
6. **Logging:** Completion date and verifying administrator are recorded
   in this log

---

## 4. Current Confirmed Configuration (March 2026)

| Asset | Configuration | Last Verified | Verified By |
| :--- | :--- | :--- | :--- |
| Router | Deny-by-default, remote management disabled, UPnP disabled, unique admin password | 07/02/2026 | CTO |
| Staff devices (macOS, Windows) | Firewalls enabled, full-disk encryption active, auto-updates on, Quad9 DNS | 07/02/2026 | CTO |
| GitHub organisation | MFA enforced, access restricted to named administrators | 07/02/2026 | CTO |
| Northflank | MFA enforced, access restricted to named administrators | 07/02/2026 | CTO |
| Namecheap (DNS) | 2FA enforced, access restricted to named administrators, no recent record changes | 07/02/2026 | CTO |
| Mobile devices | 6+ digit PIN or biometric, auto-updates enabled | 07/02/2026 | CTO |
