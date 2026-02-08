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

- [ ] **Business Continuity Plan Review** - Annual review and update [Business Continuity Plan](business-continuity-plan.md)
- [ ] **Risk Register Review** - Board-level annual review [Risk Register](risk-register.md)
- [ ] **Vulnerability Management Policy Review** - SIRO approval [Vulnerability Management Policy](vulnerability-management-policy.md)
- [ ] **Board Meeting - January** - Review all annual reports and approve policies for 2026
  - Data Security & Protection policies approval
  - DSPT preparation review
  - Document minutes for DSPT evidence

### Ongoing Monthly (January)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists (CTO) [Access Control Policy](access-control.md)
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## February 2026

### Week 1-2 (Feb 1-15)

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

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
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
- [ ] **Quarterly Access Review (Q1)** - Review emergency contacts and Unseal Key locations
- [ ] **Data Flow Mapping Review** - Verify current state matches documentation

### Ongoing Monthly (March)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## April 2026

### Week 1-4 (Apr 1-30)

- [ ] **DPIA Annual Review** - Review all existing DPIAs (minimum annually) [DPIA Procedure](dpia-procedure.md)
  - Survey Platform DPIA
  - Any new feature DPIAs from previous year
  - Update risk assessments
  - SIRO sign-off on residual risks
- [ ] **Privacy Notice Review** - Annual review and update if required
- [ ] **Terms of Service Review** - Annual review and update if required

### Ongoing Monthly (April)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
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

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
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

- [ ] **Quarterly Access Review (Q2)** - Review emergency contacts and Unseal Key locations
- [ ] **Security Review & Firewall Audit** - Bi-annual review [Security Review Log](security-review-log.md)
  - Production ingress rules verification
  - Compare against authorized inbound rule register
  - Document findings

### Ongoing Monthly (June)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## July 2026

### Week 1-4 (Jul 1-31)

- [ ] **Mid-Year Training Refresh Check** - Verify no training expirations
- [ ] **Incident Response Plan Review** - Mid-year review and update if needed [Incident Response Plan](incident-response-plan.md)
- [ ] **Data Rights Request Tracker Review** - Verify no pending SARs [Data Rights Request Tracker](data-rights-request-tracker.md)

### Ongoing Monthly (July)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
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

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## September 2026

### Week 1-4 (Sep 1-30)

- [ ] **Quarterly Access Review (Q3)** - Review emergency contacts and Unseal Key locations
- [ ] **Access Audit Log Spot Check** - Bi-annual review of Data Custodian exports
- [ ] **Change Management Policy Review** - Verify compliance with procedures

### Ongoing Monthly (September)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## October 2026

### Week 1-4 (Oct 1-31)

- [ ] **Annual Training Season Begins** - Initiate annual training renewals
  - NHS Data Security Awareness (Level 1) - All staff
  - GDPR Training refresher
  - Information Governance refresher
  - OWASP/Secure Development - Technical staff
- [ ] **Patch Management Strategy Review** - Annual review and update [Patch Management Strategy](patch-management-strategy.md)
- [ ] **Vulnerability Patch Log Review** - Audit trail verification

### Ongoing Monthly (October)

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
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

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
- [ ] **Monthly Risk Register Review** - Founders' Board meeting
- [ ] **Monthly Security Briefing** - Review logs, alerts, and policy updates

---

## December 2026

### Week 1-2 (Dec 1-15)

- [ ] **Quarterly Access Review (Q4)** - Review emergency contacts and Unseal Key locations
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

- [ ] **Monthly Access Review** - GitHub & Northflank user lists
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
- DSPT Submission
- Disaster Recovery Drill
- Contract Reviews
- Asset Register Update

### Q2 (Apr-Jun)

- DPIA Reviews
- Mid-year Backup Test
- Semi-annual Internal Audit
- Firewall Audit

### Q3 (Jul-Sep)

- Tabletop Exercise
- Mid-year Reviews
- Incident Response Plan Review
- Supplier Register Update

### Q4 (Oct-Dec)

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
