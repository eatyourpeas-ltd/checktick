---
title: "Infrastructure Technical Change Log"
category: dspt-9-it-protection
---

# Infrastructure Technical Change Log

**Organisation:** EatYourPeas Ltd
**Document Owner:** Dr Simon Chapman (CTO) & Dr Serena Haywood (SIRO)
**Last Reviewed:** April 2026
**Scope:** Boundary firewalls, cloud infrastructure (PaaS/SaaS),
DNS management, and end-user device configurations.

---

## 1. Annual Infrastructure & Firewall Review Schedule

In accordance with Cyber Essentials Plus requirements, a formal
review of all network security settings is performed at least
once every 12 months.

| Scheduled Date | Review Category | Assigned Auditor | Completion Date | Status |
| :--- | :--- | :--- | :--- | :--- |
| Feb 2026 | Firewall, Cloud & DNS Audit | Dr Simon Chapman (CTO) | 07/02/2026 | ✅ Completed |
| Feb 2027 | Firewall, Cloud & DNS Audit | Dr Simon Chapman (CTO) | — | Pending |

### Review Checklist

**Network Equipment**

- [ ] Verify router admin password is 12+ characters, unique,
  and stored in Bitwarden
- [ ] Confirm remote management is disabled on the router
- [ ] Confirm UPnP is disabled on the router
- [ ] Verify no inbound port forwarding rules exist
  (deny by default)
- [ ] Confirm router firmware is on current supported version

**Device Security**

- [ ] Confirm all device local firewalls are enabled
- [ ] Verify only necessary user accounts exist on all devices
- [ ] Confirm guest accounts disabled on all Mac devices
- [ ] Verify one standard user account per device
- [ ] Confirm administrator accounts used only with password
  manager authentication
- [ ] Remove any test, temporary, or unused accounts
- [ ] Verify all default passwords changed on all devices
- [ ] Confirm mobile devices have 6+ digit PIN or biometric
  lock enabled
- [ ] Verify Quad9 (9.9.9.9) configured as DNS resolver on
  all devices

**Cloud and SaaS Access**

- [ ] Audit user access to GitHub — remove any unnecessary
  accounts
- [ ] Audit user access to Northflank — remove any unnecessary
  accounts
- [ ] Audit user access to Microsoft 365 — confirm only named
  administrators have global admin rights
- [ ] Verify MFA active on all GitHub accounts
- [ ] Verify MFA active on all Northflank accounts
- [ ] Verify MFA enforced at Microsoft 365 tenant level
- [ ] Verify MFA active on Namecheap DNS management account
- [ ] Confirm no default or guessable passwords on any cloud
  accounts
- [ ] Verify Microsoft Graph API application registration
  scoped to Mail.Send only — confirm no additional permissions
  have been granted
- [ ] Review Northflank service tokens — confirm scope and
  expiry
- [ ] Verify Microsoft Graph API client secret expiry date
  and rotate if within 30 days

**DNS Management**

- [ ] Verify Namecheap console access restricted to named
  administrators only
- [ ] Confirm no unauthorised DNS record changes since last
  review
- [ ] Review all current DNS records for checktick.uk and
  confirm accuracy
- [ ] Verify checktick.uk SPF record authorises Microsoft 365
  sending infrastructure correctly
- [ ] Verify checktick.uk DKIM CNAME records are present and
  valid
- [ ] Verify checktick.uk DMARC record is active (p=quarantine
  minimum)
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
| Apr 2026 | Dr Simon Chapman | MX records updated to point to Microsoft 365 Exchange Online | Migration to Microsoft 365 for DCB1596 compliance | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | SPF record updated to authorise Microsoft 365 sending infrastructure | DCB1596 compliance — Microsoft 365 migration | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | DKIM CNAME records added for Microsoft 365 signing | DCB1596 compliance — Microsoft 365 migration | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | DMARC record set to p=quarantine pct=100 | DCB1596 compliance — enforce authentication on all outbound email | Dr Serena Haywood (SIRO) | ✅ Active |

### 2c. Cloud Infrastructure Changes

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Apr 2026 | Dr Simon Chapman | Microsoft 365 Business Basic tenant provisioned for checktick.uk domain | DCB1596 secure email compliance for health and care communications | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | Microsoft Entra app registration created with Mail