---
title: Platform Admin Functionality Technical Implementation
category: development
priority: 4
---

This document describes the technical implementation of platform admin functionality, including access controls, scope-aware operations, billing/reconciliation tooling, and operational safeguards.

## Scope

This document focuses on platform admin implementation in:

1. Views, forms, and templates used by superusers.
2. Account provisioning and account-management operations.
3. Promotion and billing actions exposed through platform admin.
4. Security, rate limiting, and auditability requirements.

## Entry Points and Structure

Primary implementation files:

1. `checktick_app/core/views_platform_admin.py`
2. `checktick_app/core/urls.py`
3. `checktick_app/core/templates/core/platform_admin/*.html`

Primary navigation surfaces include:

1. Dashboard
2. Organisations
3. Statistics
4. Logs
5. Pricing
6. Billing
7. Promotions

## Access Control Model

Platform admin endpoints are superuser-only and protected by explicit controls:

1. `superuser_required` decorator for route protection.
2. `require_http_methods` for endpoint method constraints.
3. `django-ratelimit` on sensitive actions.
4. CSRF protection for state-changing form posts.

Design intent: administrative workflows are explicit, auditable, and fail-closed when authorization fails.

## Account and Billing Operations

Platform admin supports operational workflows across account types and tiers:

1. Organization administration and status management.
2. Pricing override management for supported tiers.
3. Billing timeline/reconciliation views.
4. Controlled refund actions linked to payment records.

Refund action constraints (hosted reference flow):

1. Full refund automation only.
2. Mandatory reason code.
3. Required free-text explanation for `other` reason.
4. Idempotent handling for repeated operator attempts.

## Promotions Operations

Platform admin promotions implementation supports:

1. Promotion creation and edit workflows.
2. Activate/deactivate/toggle operations.
3. Duplicate/revoke workflows for reuse and controlled shutdown.
4. Post-start immutability of billing-impacting terms.
5. Lifecycle processing and reconciliation alignment.

## Audit and Observability

Administrative actions and lifecycle outcomes are auditable using structured metadata.

Coverage includes:

1. Promotion lifecycle events.
2. Refund request and webhook-reconciled state transitions.
3. Operator attribution and references required for finance/audit traceability.

See also: [Audit Logging and Notifications](/docs/audit-logging-and-notifications/).

## Security and Abuse Controls

Relevant protections include:

1. Role-constrained admin actions.
2. Endpoint rate limiting on refund/billing operations.
3. Strict webhook signature verification and required webhook secret.
4. Defensive validation on refund amount/policy paths.

See also: [Security Overview](/docs/security-overview/).

## Testing Strategy (Platform Admin Slice)

Primary coverage areas:

1. Permissions and authorization boundaries.
2. Method restrictions and malformed request handling.
3. Promotion operation regressions.
4. Billing/refund policy enforcement and idempotency.
5. Webhook-reconciled billing state transitions.

Representative suites:

1. `tests/test_platform_admin_permissions.py`
2. `tests/test_platform_admin_regressions.py`
3. `tests/test_billing.py`
4. `tests/test_organisation_checkout.py`

## Self-Hosted Considerations

For `SELF_HOSTED=true` environments:

1. Billing is disabled by default.
2. Platform admin billing/refund flows depend on optional external provider integration.
3. Operators must configure webhook signing and provider-specific credentials before enabling billing actions.

## Related Technical Documentation

1. [Billing, Refunds, and Promotions Technical Overview](/docs/billing-refunds-promotions-technical-overview/)
2. [Account Tiers Implementation](/docs/account-tiers-implementation/)
3. [Billing and Subscriptions](/docs/billing-and-subscriptions/)
4. [Refund Policy](/docs/refund-policy/)
