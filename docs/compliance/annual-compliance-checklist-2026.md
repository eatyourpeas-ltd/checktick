---
title: "Annual Compliance Checklist 2026"
category: dspt-overview
priority: 2
---

# Annual Compliance Checklist 2026

**Organization:** {{ platform_name }}
**Year:** 2026
**Owner:** SIRO & CTO
**Status:** Living Document - Update Monthly

---

## January 2026

### Week 1-2 (Jan 1-15)

- [ ] **Annual Security Validation (ASV)** - Complete validation of network defenses, access controls, and vulnerability management [Annual Security Validation Procedure](annual-security-validation-procedure.md)
  - Review GitHub Action logs (past 12 months)
  - Review pip-audit history
  - Configuration audit of Northflank settings
  - Verify zero unpatched 'Critical' vulnerabilities in production
  - Confirm sub-processor security certifications (Northflank, ISO/SOC2)
- [ ] **Asset Register Review** - Update and SIRO approval [Asset Register](asset-register.md)
  - Verify all software versions
  - Confirm 100% estate support status
  - Update OS versions and support status
- [ ] **Board Security Statement** - SIRO sign-off on unsupported systems status [Board Security Report](board-security-report-jan.md)
- [ ] **Contract Compliance Review (Q1)** - Review Article 28 compliance for all suppliers [Contract Compliance Review](contract-compliance-review.md)
  - Northflank DPA status
  - Mailgun DPA status
  - GitHub DPA status
- [ ] **Supplier Assurance Annual Audit** - Re-download and verify latest ISO/SOC2 certificates [Supplier Assurance Procedure](supplier-assurance-procedure.md)
  - Confirm no major security breaches reported
  - Update Supplier Register with next review dates

### Week 3-4 (Jan 16-31)

- [ ] **Unused Software & Service Removal** - Annual review and cleanup [Software Security Assessment](software-security-assessment.md)
  - Desktop/Mobile: Review and uninstall unused applications from all laptops (macOS & Windows 11) and mobile device (iPhone)
  - Cloud Services: Review and cancel unused SaaS/PaaS subscriptions
  - Development: Remove unused dependencies from requirements.txt and package.json
  - Disable unused system services and mobile apps (macOS, Windows 11, iOS)
  - Document removals in Technical Change Log
- [ ] **Software Asset Register Reconciliation (Q1)** - Quarterly review [Software Assets](software-assets.md)
  - Verify all software in register matches actual deployments
  - Remove decommissioned tools from register
  - Update version numbers and support status
- [ ] **Business Continuity Plan Review** - Annual review and update [Business Continuity Plan](business-continuity-plan.md)
- [ ] **Risk Register Review** - Board-level annual review [Risk Register](risk-register.md)
- [ ] **Vulnerability Management Policy Review** - SIRO approval [Vulnerability Management Policy](vulnerability-management-policy.md)
- [ ] **Board Meeting - January** - Review all annual reports and approve policies for 2026
  - Data Security & Protection policies approval
  - DSPT preparation review
  - Document minutes for DSPT evidence

### Ongoing Monthly (January)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## February 2026

### Week 1-2 (Feb 1-15)

- [ ] **Annual Infrastructure & Firewall Review (Cyber Essentials)** - Annual audit per CE requirements [Infrastructure Technical Change Log](infrastructure-technical-change-log.md)
  - Verify router security (unique admin password, remote management disabled, UPnP disabled, no port forwarding)
  - Verify all device firewalls enabled with stealth mode
  - **Device User Account Audit:** Verify only necessary accounts on all devices
    - Confirm Guest accounts DISABLED on all laptops (macOS & Windows 11)
    - Verify single standard user per device + separate admin account
    - Remove any test/temporary/unused accounts
  - **Device Security Configuration (Cyber Essentials):** [Standard Build Specification](standard-build-specification.md)
    - Automatic Login DISABLED on all devices
    - Screen lock: Password/Touch ID required immediately after sleep (laptops max 10min inactivity, mobile max 2min)
    - FileVault encryption enabled on all Macs
    - Safari: Verify 'Open safe files after downloading' DISABLED
    - Chrome: Verify all auto-open file preferences CLEARED
    - Gatekeeper: Verify enabled (`spctl --status`)
    - XProtect: Verify malware scanning active and up-to-date
    - Failed login throttling: Verify 10-attempt limits active
  - Audit cloud service user accounts (GitHub, Northflank)
  - Verify user/admin separation on cloud services
  - Document completion in Infrastructure Technical Change Log
- [ ] **External Service Authentication Review (Cyber Essentials)** - Annual verification per CE Control 5.4 & 5.5 [External Service Authentication](external-service-authentication.md)
  
  **Organization Compliance (CE Scope - Staff Admin Access):**
  - Verify MFA enabled for all staff administrative accounts (CheckTick backend/admin portal)
  - Confirm 12-character minimum passwords on staff admin accounts (exceeds CE 8-char requirement)
  - Test common password blocking (100,000+ NCSC deny list active)
  - Verify django-axes brute force protection functioning (5 failed attempts lockout)
  - Confirm rate limiting active (10 attempts/minute per IP)
  - Review staff authentication logs for suspicious patterns (past 12 months)
  
  **Application Maintenance (DSPT Scope - Customer/User Authentication):**
  - Verify MFA enforcement for customer Organization Owner and Data Custodian roles
  - Review RBAC role assignments for least privilege
  - Confirm session timeout settings (24 hours)
  - Document completion in External Service Authentication policy
- [ ] **DSPT Submission Preparation** - Begin compiling evidence for annual submission
  - Review all policies updated in January
  - Compile training records
  - Gather backup logs and restoration evidence
  - Collect security audit reports

### Week 3-4 (Feb 16-28)

- [ ] **Staff Training Review** - Verify all mandatory training current [Training Log](training.md)
  - NHS Data Security Awareness (Level 1) - All staff
  - OWASP/Secure Coding - Technical staff
  - Review training log completion status (target: 100%)
- [ ] **Password Policy Compliance Check** - Verify MFA enforcement [Password Policy](password-policy.md)

### Ongoing Monthly (February)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## March 2026

### Week 1-2 (Mar 1-15)

- [ ] **Annual Disaster Recovery Drill** - Full restoration test [Annual DR Drill](annual-disaster-recovery-drill.md)
  - Simulate vault data corruption scenario
  - Test PostgreSQL database restoration from backup
  - Verify Vault unseal process with Shamir keys
  - Test end-to-end decryption for Individual Tier users
  - Document actual vs. planned time for each step
  - Verify RTO status (target: 1 hour)
  - Identify and document improvements
- [ ] **Backup Restoration Test Record** - Complete annual DSPT requirement [Backup Log](backup-log.md)
  - Restore to temporary staging instance
  - Verify data integrity
  - Document recovery time

### Week 3-4 (Mar 16-31)

- [ ] **DSPT Annual Submission** - Complete and submit (if due)
  - Final SIRO sign-off
  - Submit via DSPT portal
- [ ] **Quarterly Access Review (Q1) (Cyber Essentials)** - Comprehensive user account and privilege audit [Access Control Policy](access-control.md)
  - **Automated Export & Reconciliation:** Export GitHub organisation members list and Northflank team members list; compare against Privileged Account Inventory for discrepancies
  - **Device Privileges:** Verify standard/admin account separation maintained on all devices
  - **Device Admin Credentials:** Verify device administrator credentials remain securely stored in password manager
  - **Admin Usage Verification:** Confirm admin accounts (device and cloud) not used for routine work activities
  - **Cloud Accounts:** Verify no orphaned or inactive accounts exist on GitHub and Northflank
  - **Role Alignment:** Confirm all current users are authorized with appropriate role assignments (Owner vs Member)
  - **Privilege Verification:** Verify account privileges match current role requirements and identify any 'privilege creep'
  - **Admin Controls:** Verify administrative privileges only assigned to designated administrative accounts
  - **Operational Restrictions:** Confirm operational accounts cannot perform security-critical operations
  - **Contractor Access:** Ensure subcontractors only retain access to active projects
  - **Leaver Verification:** Confirm any accounts belonging to departed staff have been fully removed
  - **Emergency Contacts:** Review emergency contacts and Unseal Key locations
  - **Documentation Check:** Verify Movers/Leavers Log is current and audit logs reviewed
- [ ] **Data Flow Mapping Review** - Verify current state matches documentation

### Ongoing Monthly (March)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## April 2026

### Week 1-4 (Apr 1-30)

- [ ] **Software Asset Register Reconciliation (Q2)** - Quarterly review [Software Assets](software-assets.md)
  - Verify all software in register matches actual deployments
  - Remove decommissioned tools from register
  - Update version numbers and support status
- [ ] **DPIA Annual Review** - Review all existing DPIAs (minimum annually) [DPIA Procedure](dpia-procedure.md)
  - Survey Platform DPIA
  - Any new feature DPIAs from previous year
  - Update risk assessments
  - SIRO sign-off on residual risks
- [ ] **Privacy Notice Review** - Annual review and update if required
- [ ] **Terms of Service Review** - Annual review and update if required

### Ongoing Monthly (April)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## May 2026

### Week 1-4 (May 1-31)

- [ ] **Internal Audit Spot Check** - Semi-annual comprehensive audit [Internal Audit Spot Check Log](internal-audit-spot-check-log.md)
  - User access review (GitHub & Northflank)
  - Encryption verification test
  - Staff awareness test (random questions)
  - Backup verification
  - Individual rights tracker review
  - Document findings and actions
- [ ] **Training Needs Analysis Review** - Review and update for coming year [Training Needs Analysis](training-needs-analysis.md)
- [ ] **Staff Security Agreement Review** - Annual review [Staff Security Agreement](staff-security-agreement.md)

### Ongoing Monthly (May)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## June 2026

### Week 1-2 (Jun 1-15)

- [ ] **Backup Restoration Test (Mid-Year)** - Point-in-time recovery verification [Backup Log](backup-log.md)
  - Test point-in-time restore functionality
  - Document recovery time
  - Verify data integrity

### Week 3-4 (Jun 16-30)

- [ ] **Quarterly Access Review (Q2) (Cyber Essentials)** - Comprehensive user account and privilege audit [Access Control Policy](access-control.md)
  - **Automated Export & Reconciliation:** Export GitHub organisation members list and Northflank team members list; compare against Privileged Account Inventory for discrepancies
  - **Device Privileges:** Verify standard/admin account separation maintained on all devices
  - **Device Admin Credentials:** Verify device administrator credentials remain securely stored in password manager
  - **Admin Usage Verification:** Confirm admin accounts (device and cloud) not used for routine work activities
  - **Cloud Accounts:** Verify no orphaned or inactive accounts exist on GitHub and Northflank
  - **Role Alignment:** Confirm all current users are authorized with appropriate role assignments (Owner vs Member)
  - **Privilege Verification:** Verify account privileges match current role requirements and identify any 'privilege creep'
  - **Admin Controls:** Verify administrative privileges only assigned to designated administrative accounts
  - **Operational Restrictions:** Confirm operational accounts cannot perform security-critical operations
  - **Contractor Access:** Ensure subcontractors only retain access to active projects
  - **Leaver Verification:** Confirm any accounts belonging to departed staff have been fully removed
  - **Emergency Contacts:** Review emergency contacts and Unseal Key locations
  - **Documentation Check:** Verify Movers/Leavers Log is current and audit logs reviewed
- [ ] **Security Review & Firewall Audit (Bi-annual)** - Mid-year review [Security Review Log](security-review-log.md) and [Infrastructure Technical Change Log](infrastructure-technical-change-log.md)
  - Production ingress rules verification
  - Compare against authorized inbound rule register
  - **Device User Account Re-verification:** Confirm only necessary accounts on all devices
    - Guest accounts still DISABLED
    - Single user per device maintained
    - Admin/user separation maintained
  - **Device Security Re-verification (Cyber Essentials):** [Standard Build Specification](standard-build-specification.md)
    - Screen lock timers still configured (laptops ≤10min, mobile ≤2min)
    - Safari 'Open safe files after downloading' still disabled
    - Chrome auto-open preferences still cleared
    - Gatekeeper still active
    - Device firewalls enabled with stealth mode
    - FileVault encryption active
  - Cloud service account review
  - Document findings

### Ongoing Monthly (June)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## July 2026

### Week 1-4 (Jul 1-31)

- [ ] **Software Asset Register Reconciliation (Q3)** - Quarterly review [Software Assets](software-assets.md)
  - Verify all software in register matches actual deployments
  - Remove decommissioned tools from register
  - Update version numbers and support status
- [ ] **Mid-Year Training Refresh Check** - Verify no training expirations
- [ ] **Incident Response Plan Review** - Mid-year review and update if needed [Incident Response Plan](incident-response-plan.md)
- [ ] **Data Rights Request Tracker Review** - Verify no pending SARs [Data Rights Request Tracker](data-rights-request-tracker.md)

### Ongoing Monthly (July)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## August 2026

### Week 1-4 (Aug 1-31)

- [ ] **Tabletop Exercise (Q3)** - Cyber security simulation [Exercise Summary](exercise-summary-2025.md)
  - Based on NCSC threat intelligence
  - Test incident response procedures
  - Validate role clarity (SIRO/CTO)
  - Test technical access to emergency backups
  - Review communication templates
  - Document lessons learned
  - Update action log
- [ ] **Supplier Register Review** - Mid-year update
- [ ] **Information Asset Register (ROPA) Review** - Verify current processing activities

### Ongoing Monthly (August)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists (CTO) [Access Control Policy](access-control.md)
  - Flag any accounts inactive for >90 days for review/disabling (Access Control Policy Section 6.4)
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes (new hires, role changes, leavers) [Access Audit Logs](access-audit-logs.md)
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal) [External Service Authentication](external-service-authentication.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## September 2026

### Week 1-4 (Sep 1-30)

- [ ] **Quarterly Access Review (Q3) (Cyber Essentials)** - Comprehensive user account and privilege audit [Access Control Policy](access-control.md)
  - **Automated Export & Reconciliation:** Export GitHub organisation members list and Northflank team members list; compare against Privileged Account Inventory for discrepancies
  - **Device Privileges:** Verify standard/admin account separation maintained on all devices
  - **Device Admin Credentials:** Verify device administrator credentials remain securely stored in password manager
  - **Admin Usage Verification:** Confirm admin accounts (device and cloud) not used for routine work activities
  - **Cloud Accounts:** Verify no orphaned or inactive accounts exist on GitHub and Northflank
  - **Role Alignment:** Confirm all current users are authorized with appropriate role assignments (Owner vs Member)
  - **Privilege Verification:** Verify account privileges match current role requirements and identify any 'privilege creep'
  - **Admin Controls:** Verify administrative privileges only assigned to designated administrative accounts
  - **Operational Restrictions:** Confirm operational accounts cannot perform security-critical operations
  - **Contractor Access:** Ensure subcontractors only retain access to active projects
  - **Leaver Verification:** Confirm any accounts belonging to departed staff have been fully removed
  - **Emergency Contacts:** Review emergency contacts and Unseal Key locations
  - **Documentation Check:** Verify Movers/Leavers Log is current and audit logs reviewed
- [ ] **Access Audit Log Spot Check** - Bi-annual review of Data Custodian exports
- [ ] **Change Management Policy Review** - Verify compliance with procedures

### Ongoing Monthly (September)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## October 2026

### Week 1-4 (Oct 1-31)

- [ ] **Software Asset Register Reconciliation (Q4)** - Quarterly review [Software Assets](software-assets.md)
  - Verify all software in register matches actual deployments
  - Remove decommissioned tools from register
  - Update version numbers and support status
- [ ] **Annual Training Season Begins** - Initiate annual training renewals
  - NHS Data Security Awareness (Level 1) - All staff
  - GDPR Training refresher
  - Information Governance refresher
  - OWASP/Secure Development - Technical staff
- [ ] **Patch Management Strategy Review** - Annual review and update [Patch Management Strategy](patch-management-strategy.md)
- [ ] **Vulnerability Patch Log Review** - Audit trail verification

### Ongoing Monthly (October)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## November 2026

### Week 1-2 (Nov 1-15)

- [ ] **Internal Audit Spot Check** - Annual comprehensive audit [Internal Audit Spot Check Log](internal-audit-spot-check-log.md)
  - User access review
  - Encryption verification
  - Staff awareness test
  - Backup verification
  - Individual rights tracker review
- [ ] **Sovereign Security Review (Q4)** - Review against updated NCSC Cloud Security Guidance

### Week 3-4 (Nov 16-30)

- [ ] **Board Meeting - Annual Policy Review** - Review all policies for 2027
  - Review and approve Data Security & Protection policy suite
  - Sign Board minutes for DSPT evidence [Board Minutes](board-suite-minutes-dpst.md)
- [ ] **Annual Training Completion Verification** - Ensure 100% completion [Training Log](training.md)

### Ongoing Monthly (November)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## December 2026

### Week 1-2 (Dec 1-15)

- [ ] **Security Review & Firewall Audit** - Bi-annual review [Security Review Log](security-review-log.md)
  - Router ingress rules verification (BT Smart Hub 2)
  - Verify no port forwarding enabled
  - Verify DMZ disabled
  - Verify UPnP disabled
  - Document findings in Security Review Log
- [ ] **Quarterly Access Review (Q4) (Cyber Essentials)** - Comprehensive user account and privilege audit [Access Control Policy](access-control.md)
  - **Automated Export & Reconciliation:** Export GitHub organisation members list and Northflank team members list; compare against Privileged Account Inventory for discrepancies
  - **Device Privileges:** Verify standard/admin account separation maintained on all devices
  - **Device Admin Credentials:** Verify device administrator credentials remain securely stored in password manager
  - **Admin Usage Verification:** Confirm admin accounts (device and cloud) not used for routine work activities
  - **Cloud Accounts:** Verify no orphaned or inactive accounts exist on GitHub and Northflank
  - **Role Alignment:** Confirm all current users are authorized with appropriate role assignments (Owner vs Member)
  - **Privilege Verification:** Verify account privileges match current role requirements and identify any 'privilege creep'
  - **Admin Controls:** Verify administrative privileges only assigned to designated administrative accounts
  - **Operational Restrictions:** Confirm operational accounts cannot perform security-critical operations
  - **Contractor Access:** Ensure subcontractors only retain access to active projects
  - **Leaver Verification:** Confirm any accounts belonging to departed staff have been fully removed
  - **Emergency Contacts:** Review emergency contacts and Unseal Key locations
  - **Documentation Check:** Verify Movers/Leavers Log is current and audit logs reviewed
- [ ] **Year-End Risk Register Review** - Prepare for annual board review
- [ ] **Business Impact Assessment Review** - Annual update [Business Impact Assessment](business-impact-assessment.md)
  - Verify RTO/RPO targets
  - Update service criticality ratings
  - Review dependencies

### Week 3-4 (Dec 16-31)

- [ ] **Annual Compliance Documentation Review** - Prepare evidence portfolio for next DSPT cycle
  - Organize all logs and audit trails
  - Collect training certificates
  - Compile incident reports (if any)
  - Document all exercises and drills
- [ ] **Data Retention Policy Review** - Verify automated data governance processes
- [ ] **Year-End Board Report** - Summary of security posture for the year

### Ongoing Monthly (December)

- [ ] **Monthly Access Review** - GitHub and Northflank user lists
- [ ] **Privileged Account Inventory Update** - Update inventory with any account changes
- [ ] **Monthly MFA Compliance Check (Cyber Essentials)** - Verify MFA enabled on staff administrative accounts (CheckTick backend/admin portal)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## Continuous/Weekly Activities (All Year)

### Daily

- [ ] **Automated Security Scans** - GitHub Dependabot and pip-audit (06:00 UTC)
- [ ] **Automated Maintenance Tasks**
  - `process_data_governance` - GDPR data minimization
  - `process_recovery_time_delays` - Key recovery
  - `cleanup_survey_progress` - Session cleanup
- [ ] **Security Monitoring** - Review alerts from Northflank/GitHub

### Weekly

- [ ] **Vulnerability Management** - Review and triage Dependabot alerts
- [ ] **Patch Review** - Assess and plan patches for non-critical vulnerabilities
- [ ] **NHS Data Dictionary Sync** - Automated clinical data accuracy update
- [ ] **Backup Verification** - Confirm automated backups successful

### As Needed

- [ ] **Critical/Zero-Day Patching** - Emergency response within 48 hours (CVSS 9.0+)
- [ ] **Incident Response** - Follow Incident Response Plan for any security events
- [ ] **Data Subject Rights Requests** - Process within 30 days of receipt
- [ ] **Breach Notification** - ICO within 72 hours; customers without undue delay

---

## Quarterly Summary Schedule

### Q1 (Jan-Mar)

- Annual Security Validation
- Unused Software & Service Removal (Annual)
- Software Asset Register Reconciliation (Quarterly)
- Annual Infrastructure & Firewall Review (Cyber Essentials)
- External Service Authentication Review (Cyber Essentials)
- Device User Account Audit (Annual)
- Device Security Configuration Audit - AutoRun/Execution Controls (Bi-annual)
- DSPT Submission
- Disaster Recovery Drill
- Contract Reviews
- Asset Register Update

### Q2 (Apr-Jun)

- Software Asset Register Reconciliation (Quarterly)
- Device User Account Re-verification (Bi-annual)
- Device Security Configuration Re-verification - AutoRun/Execution Controls (Bi-annual)
- DPIA Reviews
- Mid-year Backup Test
- Semi-annual Internal Audit
- Firewall Audit

### Q3 (Jul-Sep)

- Software Asset Register Reconciliation (Quarterly)
- Tabletop Exercise
- Mid-year Reviews
- Incident Response Plan Review
- Supplier Register Update

### Q4 (Oct-Dec)

- Software Asset Register Reconciliation (Quarterly)
- Annual Training Renewals
- Policy Suite Review
- Board Approval & Minutes
- Year-end Compliance Documentation
- Business Impact Assessment

---

## Key Contacts & Escalation

**SIRO (Senior Information Risk Owner):** {{ siro_name }}
**CTO (Cyber Security Lead):** {{ cto_name }}
**DPO (Data Protection Officer):** {{ siro_name }}
**Caldicott Guardian:** {{ cto_name }}

### Emergency Response Times

- **Critical Incidents (P1):** Immediate response, containment within 4 hours
- **ICO Breach Notification:** Within 72 hours of awareness
- **Critical Patching:** Within 48 hours
- **Data Subject Rights:** Within 30 days

---

## Version History

| Date | Version | Changes | Approved By |
| :--- | :--- | :--- | :--- |
| 08/02/2026 | 1.0 | Initial 2026 checklist created | Pending |

---

## Notes

- This checklist is derived from the complete compliance documentation suite
- All activities support DSPT (Data Security & Protection Toolkit) requirements
- Review and update this checklist monthly during board meetings
- Document completion of each item with date and responsible person
- Any deviations must be documented in the Risk Register
- Failed or missed items escalate to board level within 48 hours

**Last Updated:** 08/02/2026
**Next Review:** Monthly at Board Meeting
