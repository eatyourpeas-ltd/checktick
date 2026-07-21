---
title: Billing, Refunds, and Promotions Technical Overview
category: development
priority: 3
---

This document provides the technical implementation overview for billing, refund, and promotions behavior in the hosted reference deployment.

## Scope

This overview covers:

1. Promotion data model and precedence resolution.
2. Billing integration points where promotions affect price/tier behavior.
3. Refund lifecycle processing, adjustment reconciliation, and audit coverage.
4. Security controls and policy guardrails applied to billing/refund actions.

This is an implementation overview, not a product roadmap. Future enhancements should be tracked as separate technical proposals.

## Architecture Overview

Core implementation areas:

1. Domain and resolver
   - `checktick_app/core/models.py`
   - `checktick_app/core/services/promotion_resolver.py`
2. Billing/provider integration
   - `checktick_app/core/billing.py`
   - `checktick_app/core/views_billing.py`
3. Platform admin billing/refund operations
   - `checktick_app/core/views_platform_admin.py`
   - `checktick_app/core/templates/core/platform_admin/billing.html`
4. Public pricing/signup surfacing
   - `checktick_app/core/views.py`
   - `checktick_app/core/templates/core/home.html`
   - `checktick_app/core/templates/core/pricing.html`
5. Lifecycle operations and notifications
   - `checktick_app/core/management/commands/process_promotion_lifecycle.py`
   - `checktick_app/core/email_utils.py`

## Promotions: Model and Resolution

## Promotion model

Promotions are represented as first-class records with:

1. Scope (`platform`, `tier`, `account`) and target metadata.
2. Effect type/value for discounting or tier override behavior.
3. Activation window (`starts_at`, `ends_at`) and active flag.
4. Priority and audit metadata for deterministic selection and traceability.

## Deterministic precedence

Effective promotion resolution is deterministic:

1. Account-scoped promotions (most specific).
2. Tier-scoped promotions.
3. Platform-scoped promotions.
4. Baseline pricing/tier behavior when no promotion applies.

Within a scope, priority and recency determine the winner.

## Public pricing/signup integration

Public pages surface resolved active offers for eligible tiers while preserving baseline pricing as canonical fallback.

## Billing Integration

## Price and tier evaluation

Billing flows integrate promotion resolution before provider-side amounts are prepared.

Key rules:

1. Applied promotion metadata is carried with billing records for traceability.
2. Promotion outputs are bounded by business constraints (for example, no negative charge amounts).
3. Effective tier/price decisions are reproducible from persisted metadata.

## VAT on discounted checkouts

When a promotion reduces the charged amount, VAT is computed on the **discounted** ex-VAT amount, not the base tier price. The flow is:

1. At checkout, `billing.create_subscription_for_user` resolves the effective pricing via `promotion_resolver.resolve_effective_pricing_for_user` (or `_for_team`), which returns `effective_amount_ex_vat_pence` and `effective_amount_pence` after applying any promotion.
2. The resolved ex-VAT amount, applied promotion, and effective tier are cached on `UserProfile` (`last_checkout_amount_ex_vat`, `last_checkout_applied_promotion`, `last_checkout_effective_tier`) so the webhook handler can retrieve them when the payment confirms.
3. When the `payments.confirmed` webhook fires, `handle_gocardless_payment_confirmed` passes the cached pricing into `Payment.create_from_subscription` via the `resolved_amount_ex_vat` / `applied_promotion` / `effective_tier` keyword arguments.
4. `Payment.create_from_subscription` uses the resolved ex-VAT amount as canonical and computes VAT from it via `settings.VAT_RATE` (see `checktick_app/core/pricing.py`). The `Payment` record stores the discounted ex-VAT, VAT, and inc-VAT amounts, plus a FK to the applied `Promotion`.

This ensures VAT returns generated from the Platform Admin billing view and the Django admin CSV export reflect the actually-charged amounts, with promotion attribution for audit.

## Organization checkout

Organization checkout applies effective pricing with the same guardrails used across other billing entry points.

## Refund Lifecycle and Reconciliation

## Admin-initiated refunds

Platform admin billing supports operator-initiated refund actions with policy constraints:

1. Hosted reference flow automates full refunds only.
2. Reason code is mandatory.
3. Additional free-text reason is required when reason code is `other`.

## Webhook-driven lifecycle states

Refund lifecycle transitions are processed from signed provider webhooks (for example: `created`, `paid`, `failed`, `funds_returned`, `refund_settled`), with idempotent reconciliation.

## Adjustment reporting

Promotion-linked adjustments are summarized in platform admin billing reporting with bounded query windows and structured metadata for finance and audit workflows.

## Audit and Notifications

Audit coverage includes:

1. Promotion create/update/toggle/revoke lifecycle events.
2. Refund request and reconciliation metadata.
3. Operator attribution and provider reference fields.

Notification coverage includes customer-facing refund processed messaging and promotion lifecycle notifications where configured.

## Security Controls

Security controls in this implementation include:

1. Superuser-only access for platform admin billing/promotion actions.
2. Strict HTTP method controls for sensitive endpoints.
3. Rate limiting on billing and admin operations.
4. Webhook signature verification with required webhook secret.
5. CSRF protection on administrative form actions.

## Self-Hosted Behavior

For `SELF_HOSTED=true` deployments, billing is disabled by default. Promotion and refund integrations are only applicable where operators explicitly implement and configure an external billing provider.

## Related Technical Documentation

1. [Platform Admin Functionality Technical Implementation](/docs/platform-admin-functionality-technical-implementation/)
2. [Billing and Subscriptions](/docs/billing-and-subscriptions/)
3. [Refund Policy](/docs/refund-policy/)
4. [Security Overview](/docs/security-overview/)
5. [Audit Logging and Notifications](/docs/audit-logging-and-notifications/)
