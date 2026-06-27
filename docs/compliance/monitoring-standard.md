---
title: "Security Monitoring & Logging Standard"
category: dspt-9-it-protection
---

# Security Monitoring & Logging Standard

## 1. Scope of Monitoring

{{ platform_name }} implements layered monitoring across infrastructure, application, and development systems to ensure security, availability, and compliance.

### 1.1 Infrastructure Layer

- Hosting platform logs and metrics (e.g. Northflank, Azure, AWS)
- Container health, restarts, and resource utilisation
- Network ingress and service availability checks

### 1.2 Application Layer

- Django runtime logs (structured JSON output)
- Authentication events (success, failure, lockout)
- Security-critical exceptions and system errors
- Audit logs stored in PostgreSQL (see Audit Policy)

### 1.3 Development & Supply Chain Layer

- GitHub audit logs
- Dependency scanning (Dependabot or equivalent)
- Secret scanning and repository security alerts

---

## 2. Detection Logic (Security Events)

| Event Type | Monitoring Tool | Response Action |
| :--- | :--- | :--- |
| **Brute Force Attacks** | `django-axes` | IP lockout + automated alerting + admin notification |
| **Authentication Failures** | Django logging + audit system | Logged + threshold-based alerting |
| **Secret Leakage Attempts** | GitHub Secret Scanning | Immediate alert + pull request block |
| **Service Downtime / Degradation** | Hosting health checks (Northflank / equivalent) | Critical alert + incident workflow trigger |
| **Dependency Vulnerabilities** | GitHub Dependabot | Automated PR + weekly security review |

---

## 3. Log Retention

Retention is split by system type:

### 3.1 Infrastructure & Application Logs

- Retained for a minimum of **90 days** by the hosting platform or configured log aggregation system
- Includes:
  - runtime logs
  - error logs
  - infrastructure events
  - authentication activity (non-audit form)

### 3.2 Audit Logs (Security Record)

- Stored in encrypted PostgreSQL database (`AuditLog` model)
- Retained for **minimum 12 months**
- Used for:
  - authentication history
  - security investigations
  - compliance reporting
  - forensic analysis

---

## 4. Alerting & Response Model

{{ platform_name }} uses a **hybrid automated alerting model** to ensure timely detection and response.

### 4.1 Automated Alerts

The following events trigger automatic notifications:

- Critical authentication events (e.g. account lockout)
- Repeated login failures beyond threshold
- System downtime or degraded health checks
- Security-related exceptions
- Dependency or supply-chain vulnerabilities

### 4.2 Notification Channels

- Email alerts (administrative mailbox)
- Hosting platform alerting (Northflank / equivalent)
- Optional external integrations (Slack or equivalent, if configured)

---

## 5. Mitigation of Monitoring Gaps

As a small engineering team, {{ platform_name }} does not rely on continuous manual monitoring.

Instead, we implement:

- **Automated alerting for all critical events**
- **Push-based notifications for urgent security issues**
- **Infrastructure-level health checks with failure detection**
- **Daily review of system health dashboards during active development**
- **Weekly security review of dependency and repository alerts**

---

## 6. Security Event Classification

### Critical Events

- Account lockouts
- Suspected brute-force attacks
- Authentication system failures
- Service downtime
- Privilege escalation attempts

### Warning Events

- Repeated failed login attempts
- Unusual access patterns
- Dependency vulnerabilities
- Non-critical system degradation

### Informational Events

- Successful logins
- Routine system operations
- Scheduled maintenance activities

---

## 7. Key Principle

> Monitoring is automated, event-driven, and risk-prioritised.

The system is designed to ensure that:

- Critical events are never reliant on manual observation
- Security signals are surfaced immediately via automated alerting
- Audit logs provide retrospective forensic capability
- Infrastructure logs provide operational observability

---
