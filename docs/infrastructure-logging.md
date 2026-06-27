---
title: Infrastructure Logging
category: self-hosting
priority: 4
---

# Infrastructure Logging (Structured Logging)

## Overview

CheckTick uses structured logging to emit **machine-readable JSON logs to stdout**.

This design is platform-agnostic and works with any infrastructure that captures stdout logs, including:

- Northflank (primary reference implementation)
- Azure App Service / Application Insights
- AWS CloudWatch / ECS / EKS
- GCP Cloud Logging
- Self-hosted Docker / Kubernetes logging stacks (Fluent Bit, Vector, Promtail)

No external logging service is required.

---

## Logging Philosophy

CheckTick follows a **platform-first logging model**:

> The application writes structured logs to stdout.
> The infrastructure determines storage, retention, and indexing.

This means:

- No vendor-specific logging dependency
- No application-level log persistence
- No performance impact when log collectors are absent
- Logs are always emitted, regardless of environment

---

## Logging Pipeline

All application logs follow this pipeline:

```
Django logger
↓
LoggingContextFilter (adds request metadata)
↓
RedactionFilter (removes sensitive values)
↓
JSONFormatter (emits structured JSON)
↓
stdout
↓
Platform logging system (Northflank / Azure / AWS / etc.)
↓
Optional external log store (OpenObserve / Datadog / ELK / Loki)
```

---

## Logging Components

CheckTick uses three internal logging components:

### 1. LoggingContextFilter

Adds request-scoped metadata to every log record:

- `request_id`
- `user_id`
- `remote_addr`
- `project`
- `service`
- `environment`

This enables traceability across distributed systems and requests.

---

### 2. RedactionFilter

Removes or sanitises sensitive values from log messages.

It acts as a **defensive safety layer** in case sensitive values are accidentally logged.

#### Categories covered:

**Authentication & secrets**
- passwords
- tokens
- API keys
- session IDs
- cookies
- bearer tokens
- OAuth credentials

**Healthcare identifiers**
- NHS numbers
- hospital / MRN identifiers
- names (first/surname)
- email addresses (optional policy-based redaction)
- phone numbers

> Note: Survey payloads are not expected to be logged in plaintext due to encryption at rest.

---

### 3. JSONFormatter

All logs are emitted as structured JSON:

```json
{
  "timestamp": "2026-06-27T10:14:22.318Z",
  "level": "INFO",
  "logger": "checktick_app.core.auth",
  "message": "User logged in",
  "request_id": "abc123",
  "user_id": 42,
  "remote_addr": "81.2.69.142",
  "project": "checktick",
  "service": "django",
  "environment": "production",
  "module": "auth",
  "function": "login_view",
  "line": 184
}
```

This format is optimised for:

- structured search
- alerting
- filtering in log aggregation systems
- audit correlation

## Logging Configuration

CheckTick uses standard Django logging configuration with a single active sink: stdout.

## Console Handler (Primary Output)

```python
"console": {
    "class": "logging.StreamHandler",
    "formatter": "json",
    "filters": [
        "context_filter",
        "redaction_filter",
    ],
}
```

## Email Alerts

Django administrative email alerts remain enabled via:

`django.utils.log.AdminEmailHandler`

These are used for:

- uncaught 500 errors
- request failures
- critical system exceptions
- External Log Storage (Optional)

CheckTick does not require a logging backend, but supports integration via infrastructure-level log collectors.

### Option A — Platform Native Logging (Recommended)

If deployed on:

- Azure App Service
- AWS CloudWatch / ECS / EKS
- GCP Cloud Logging
- Northflank
- Kubernetes logging stacks

then:

Logs are automatically captured from stdout with no application changes required.

### Option B — External Log Aggregators

For long-term retention or advanced analytics:

- OpenObserve
- Datadog
- Elasticsearch / Kibana (ELK)
- Grafana Loki

These are connected via log shipping agents (Vector, Fluent Bit, etc.), not by the application.

### Does this work on Azure / AWS / other platforms?

Yes — fully.

> Azure
- stdout logs are automatically captured
- available in Application Insights and Log Analytics
- JSON improves queryability and filtering

> AWS
- CloudWatch captures container stdout logs
- JSON format improves CloudWatch Logs Insights queries
- Kubernetes

Compatible with:

- Fluent Bit
- Fluentd
- Vector
- Promtail
- Key Architecture Change
- Previous approach (exporter-based)
- Application pushed logs to a logging backend
- Tight coupling to a specific service
- Network requests from application process
- Current approach (stdout-based)
- Application writes structured logs only
- Infrastructure handles ingestion and storage
- Fully portable and vendor-neutral
- No network calls from logging layer
- Security Model

This system is designed for healthcare-grade workloads.

Guarantees
- No request bodies are logged by default
- No decrypted survey data is emitted in logs
- Sensitive fields are redacted at source
- Logs are safe for external aggregation (with proper infrastructure controls)

## Important Principle

Redaction is a safety net — not the primary control.

The primary control is:

- explicit structured logging via `JSONFormatter`
- no automatic dumping of request or object data

## Deployment Checklist

- Logs emit JSON to stdout
- Platform logging enabled (Azure/AWS/Northflank/etc.)
- LoggingContextFilter enabled
- RedactionFilter enabled
- No secrets logged via extra, `__dict__`, or request bodies
- Error logs visible in platform logging system
- Optional external log shipping configured if required

## Summary

CheckTick logging is:

Structured, portable, and infrastructure-agnostic

It replaces vendor-specific logging integrations with:

- JSON structured logs
- stdout-based transport
- infrastructure-managed persistence

This makes it:

- simpler to operate
- safer for healthcare environments
- portable across cloud providers
- compatible with both modern and traditional logging stacks
- Azure Compatibility Note

Yes — this works seamlessly on Azure.

Azure App Service and Azure Container Apps automatically:

- capture stdout logs
- persist them in Application Insights / Log Analytics
- support structured querying of JSON logs

No application-level changes are required.
