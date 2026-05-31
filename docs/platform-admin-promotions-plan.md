# Platform Admin Promotions: Current State Review and Implementation Plan

## Status Update (31 May 2026)

Implemented in code:

1. Promotion model, precedence resolver, billing integration, and public pricing/signup surfacing.
2. Platform admin promotions list/create/toggle flows.
3. Post-start promotion immutability for billing-impacting terms.
4. Platform admin edit, duplicate, and revoke flows for promotions.
5. Promotion lifecycle audit logging via the existing `AuditLog` model for create, update, toggle, and revoke actions.

Still future work:

1. Refund lifecycle completion and policy hardening:
   - webhook/event handling for provider-side refund states
   - customer notification after refund execution
   - explicit policy for partial refunds, credits, and reconciliation edge cases
2. Adjustment reporting for refunds and credits tied to promotions.

Recently completed since the original draft:

1. Provider-side refund creation support in `PaymentClient` for GoCardless refunds.
2. Platform admin refund actions from the billing timeline for confirmed GoCardless payments.
3. Tier account-list refund access, including choosing from multiple refundable payments per account.
4. Audit logging and safe return navigation for admin-initiated refunds.

## Scope

This document reviews the current billing and platform admin implementation and proposes a plan to add a promotions feature that can be granted by platform admins at:

1. Platform level (global)
2. Tier level (all users/accounts on a tier)
3. Individual account level (individual user, team, or organisation)

The plan assumes platform admin access remains superuser-only and keeps existing security controls.

## Current State Review

### 1) Billing service layer (`checktick_app/core/billing.py`)

Current capabilities:

1. `PaymentClient` wraps GoCardless API operations:
   - Redirect flows (create/complete)
   - Customer operations
   - Mandate operations
   - Subscription operations (create/get/cancel/pause/resume/update)
   - Payment listing/retrieval
2. User-level subscription helpers exist (`get_or_create_redirect_flow`, `complete_mandate_setup`, `create_subscription_for_user`).
3. Tier prices are computed from `PricingOverride.get_effective_tiers()` for overridable tiers.

Limitations for requested feature:

1. No promotion concept or rule resolution in billing logic.
2. No support for layered precedence (platform -> tier -> account) in price/tier decisions.
3. No audit model specifically for promotions granted/revoked by platform admins.

### 2) Organisation checkout flow (`checktick_app/surveys/views_organisation_billing.py`)

Current capabilities:

1. Public token-based org checkout flow with safeguards:
   - Token validity checks
   - Token expiry checks
   - Setup-completed checks
   - Session-bound checkout completion
   - Rate limiting (`django_ratelimit`)
   - Disabled under `SELF_HOSTED`
2. Pricing for organisations is calculated from organisation fields:
   - `per_seat`: `max_seats * price_per_seat`
   - `flat_rate`: `flat_rate_price`
   - VAT added using `VAT_RATE`
3. Checkout completion creates subscription and marks org setup complete.

Limitations for requested feature:

1. No promotion application for organisation checkout amount.
2. No explicit override path for temporary or permanent promotions.
3. No promotion metadata attached to resulting subscription.

### 3) Platform admin views (`checktick_app/core/views_platform_admin.py`)

Current capabilities:

1. Access control:
   - `superuser_required` decorator applied to platform admin views
   - View-level rate limiting
   - Method restrictions via `require_http_methods`
2. Dashboard and management features:
   - Organisation overview and attention list
   - Organisation CRUD, invite link generation, invite email
   - Active/inactive toggle
   - Organisation stats
   - Platform logs page
   - Pricing override page for selected tiers (`pro`, `team_small`, `team_medium`, `team_large`)
3. Navigation currently includes: Dashboard, Organisations, Statistics, Logs, Pricing.

Limitations for requested feature:

1. Dashboard focuses on organisations only; no first-class teams or individual accounts view.
2. No promotions tab or promotions workflows.
3. Pricing override is tier-price management, not scoped promotions with expiries/reasons/precedence.

### 4) Existing data models and related behavior

Relevant models:

1. `UserProfile` contains account tier and subscription fields.
2. `Organization` stores billing terms and payment subscription fields.
3. `Team` exists with size and subscription reference.
4. `PricingOverride` supports fixed per-tier price override for selected tiers.

Gap:

1. No unified promotion model spanning user/team/organisation and tier/global scope.

### 5) Existing test coverage (important baseline)

Current tests already validate key protections:

1. `tests/test_platform_admin_permissions.py` verifies superuser-only access, method restrictions, and pricing override behavior.
2. `tests/test_organisation_checkout.py` verifies token security, session validation, rate-limited workflow behavior, VAT calculation, and payment error handling.

This is a strong foundation for adding promotions safely.

## Proposed Feature Design

## Promotion model and precedence

Introduce a dedicated promotions domain model (suggested names, can be adjusted):

1. `Promotion`
   - `name`, `code` (optional), `description`
   - `scope_type` enum: `platform`, `tier`, `account`
   - `target_tier` (nullable, for tier scope)
   - `target_user` (nullable)
   - `target_team` (nullable)
   - `target_organization` (nullable)
   - `effect_type` enum: `percent_discount`, `fixed_discount`, `set_price`, `tier_upgrade`, `tier_override`
   - `effect_value` (decimal/int depending on effect)
   - `is_active`, `starts_at`, `ends_at`
   - `created_by`, `updated_by`
   - `reason`, `internal_notes`
2. `PromotionAuditLog` (or extend existing audit logging)
   - Who changed what, when, old/new values, action (`create`, `activate`, `deactivate`, `revoke`, `expire`)

Recommended deterministic precedence for conflicting promotions:

1. Account-level promotion (most specific)
2. Tier-level promotion
3. Platform-level promotion (least specific)
4. Then existing default pricing logic

If multiple promotions exist in same scope, enforce one of:

1. Highest priority field (`priority` int), then most recent active
2. Or hard rule: max one active promotion per scope/target combination

## Promotion evaluation service

Add a central resolver service, for example:

1. `checktick_app/core/services/promotion_resolver.py`
2. Public methods:
   - `resolve_effective_pricing_for_user(user)`
   - `resolve_effective_pricing_for_team(team)`
   - `resolve_effective_pricing_for_organization(org)`
3. Returns structured result with:
   - Base price/tier
   - Applied promotion (if any)
   - Effective price/tier
   - Explanation metadata for audit/debug

This avoids duplicating promotion logic across views.

## Platform admin UX changes

Introduce a scoped platform admin model with a global scope selector to make operational pages consistent across tiers.

### Scope selector model

Add a top-level scope selector in platform admin header:

1. `All`
2. `free`
3. `pro`
4. `team_small`
5. `team_medium`
6. `team_large`
7. `organization`
8. `enterprise`

Pages that should respect selected scope:

1. Dashboard / Overview
2. Statistics
3. Logs
4. Billing
5. Accounts list and detail views

Page that remains platform-global:

1. Pricing (baseline platform-level tier pricing and controls)

### Navigation and tabs

Extend platform admin navigation with:

1. Accounts (aggregated users/teams/orgs)
2. Promotions

Recommended navigation split:

1. Scoped tabs: Overview, Billing, Accounts, Logs
2. Global tabs: Pricing, Promotions

### Dashboard extension

Enhance dashboard summary cards and tables to include:

1. Individual accounts by tier and subscription status
2. Teams by size/tier and subscription presence
3. Organisations (existing)
4. Promotion summary:
   - Active platform promotions
   - Active tier promotions
   - Active account-specific promotions
   - Promotions expiring soon
5. Billing summary for selected scope:
   - gross
   - ex VAT
   - VAT
   - refunds/adjustments
   - period trend

### Billing tab (new)

Add a dedicated platform admin billing tab scoped by selected tier:

1. Summary cards
2. Transaction table
3. Filters (date range, status, account type)
4. Export tools for finance and audit
5. Drill-through into account billing timeline

Per-customer billing timeline requirements:

1. Show full charge/failure/cancellation/refund history for that account.
2. Include a controlled refund workflow action from the customer timeline view.
3. Require reason code, amount validation, and confirmation before execution.
4. Record operator, timestamp, provider reference, and internal notes for audit.
5. Send customer notification email after refund decision/execution.

Initial source strategy:

1. Use existing `Payment` records where available.
2. For gaps, add reconciliation ingestion from provider APIs/webhooks.

### Promotions tab

Create promotion management screens for superusers:

1. Promotion list with filters:
   - scope
   - status (active/scheduled/expired)
   - target type
2. Create/edit form:
   - scope selection
   - target selection (tier/user/team/org)
   - effect type/value
   - validity window
   - reason/internal notes
3. Quick actions:
   - activate/deactivate
   - revoke
   - duplicate
4. Safety confirmations for destructive actions.

## Account provisioning across tiers

Current platform admin supports organisation creation. In the redesigned model, provisioning should be extended to all tier families using a unified admin flow.

### Should creation be extended beyond organisations?

Yes. Extend platform admin provisioning to support:

1. Individual paid accounts (for `pro` and enterprise-like direct contracts)
2. Team accounts (`team_small`, `team_medium`, `team_large`)
3. Organisation accounts (existing flow)

### Provisioning model

Use a common “Create Account” entry point with account type and tier selection:

1. Account type:
   - user
   - team
   - organization
2. Target tier
3. Billing mode:
   - standard checkout
   - admin-assisted/manual
4. Optional promotion pre-assignment
5. Invite/start email trigger

Design principle:

1. Do not force free-tier-first onboarding.
2. Allow direct promoted or direct paid provisioning at creation time.
3. Keep free-tier onboarding as an optional path.

### Billing implications during provisioning

1. If billing is required, create/collect via checkout at effective resolved amount.
2. If admin-assisted/manual billing, mark status and require explicit activation path.
3. Always store who provisioned account, chosen tier, and applied pricing/promotion metadata.

## Billing integration points

Apply promotion resolver before subscription amount/tier decisions in:

1. User subscription creation path in `checktick_app/core/billing.py`
2. Organisation checkout completion in `checktick_app/surveys/views_organisation_billing.py`
3. Any other billing or upgrade endpoints that compute effective tier/price.

Include applied promotion metadata in payment subscription metadata where possible for traceability.

## Email and communications lifecycle

Promotions with billing impact should include explicit customer communications in addition to existing subscription emails.

Recommended additional email events:

1. Promotion activated
   - Sent when a promotion starts affecting a user/team/organisation.
   - Include scope, effective amount/tier, start date, and end date (if time-limited).
2. Promotion ending soon
   - Sent before expiry for time-limited promotions.
   - Include expected post-promotion amount/tier and effective date.
3. Promotion expired/reverted
   - Sent when pricing/tier returns to standard terms.
4. Promotion-related billing adjustment notice
   - Sent when a refund or credit is applied following promotion changes.

Implementation note:

1. Keep existing billing emails (`subscription created`, `payment failed`, `subscription cancelled`) and add promotion-specific templates/functions for transparency.

## GoCardless promotion behavior

GoCardless in this project is amount-based subscription billing. Promotions are therefore enforced in application logic, then persisted to GoCardless subscription amounts.

### Existing account with active subscription

1. Resolve effective promotion using precedence rules.
2. If promotional amount differs, call subscription update to set new amount.
3. Store promotion metadata for audit and support diagnostics.
4. On promotion expiry, update subscription amount back to baseline.

### New account onboarding with promotion

1. Resolve promotion before subscription creation.
2. Create mandate and subscription directly at promotional amount.
3. Persist promotion metadata on creation.

Important product decision:

1. Do not require users to register on a free tier before receiving a promotion.
2. Support direct promoted checkout for new users and admin-provisioned accounts.
3. Free-tier-first remains optional, not required.

### Money movement semantics

1. Collected amount is whatever is configured on the GoCardless subscription at charge time.
2. Subscription amount updates affect future charges, not already-collected funds.
3. Backdated corrections need a separate financial adjustment path (refund and/or manual credit policy).

## Refund and credit adjustment pathway

Because promotion changes can happen after a charge is collected, define a controlled adjustment path.

Recommended approach:

1. Add internal billing adjustment workflow in platform admin:
   - reason code (promotion backdate, support goodwill, billing error)
   - amount
   - linkage to promotion and payment record
2. For over-collection due to timing mismatch:
   - support a refund action (full/partial) where provider and policy allow
   - optionally support account credit tracking for next invoice/charge where refund is not preferred
3. Add audit logging for every adjustment decision and execution.
4. Notify customer via dedicated adjustment email.
5. Surface refund workflow directly within per-customer billing timeline for support/admin operations.

If GoCardless API capabilities or operational policy constrain automated refunds, keep a manual refund runbook and capture reference IDs in the audit trail.

## Security and compliance requirements

Keep or extend existing protections:

1. Superuser-only promotion management endpoints (`superuser_required`)
2. CSRF protection for all POST actions
3. Tight `require_http_methods` usage
4. Rate limits on sensitive endpoints
5. Audit logging for create/update/delete/activate/revoke actions
6. Server-side validation for scope-target compatibility (for example, account scope must target exactly one of user/team/org)
7. Time window validation (`starts_at < ends_at` when both set)
8. Guardrails against invalid negative pricing unless explicitly allowed and documented

## Implementation Plan (Phased)

### Phase 1: Data model and resolver foundation

1. Add migration(s) for promotion entities and indexes.
2. Implement promotion resolver service with precedence rules.
3. Add unit tests for resolver behavior and conflict handling.

### Phase 2: Platform admin promotions UI/API

1. Add routes in `checktick_app/core/urls.py` for promotions list/create/edit/toggle.
2. Add views in `checktick_app/core/views_platform_admin.py` (or a dedicated `views_platform_admin_promotions.py` if preferred).
3. Add templates under `checktick_app/core/templates/core/platform_admin/`.
4. Add scoped selector infrastructure and scoped tabs (Overview/Billing/Accounts/Logs).
5. Add unified account provisioning flows for user/team/organization creation.
6. Update platform admin base navigation and dashboard widgets.
7. Add permission, method, and form validation tests.

### Phase 3: Billing flow integration

1. Integrate resolver into user billing path.
2. Integrate resolver into organisation checkout completion amount calculation.
3. Persist promotion metadata on payment subscription creation.
4. Add integration tests covering promotion application and fallback behavior.
5. Add promotion lifecycle emails (activated, ending soon, expired/reverted).
6. Add refund/credit adjustment hooks and policy enforcement points.

### Phase 4: Observability and operational controls

1. Add audit log entries for promotion lifecycle events.
2. Add dashboard tiles for active/expiring promotions.
3. Add optional management command for expiring/cleanup or status reconciliation if needed.
4. Add scheduled reconciliation to catch expired promotions and revert subscription amounts.
5. Add adjustment/reconciliation reporting for refunds and credits tied to promotions.

## Test Plan

## A) Model and resolver tests

1. Platform-level promotion applies when no more specific match exists.
2. Tier-level overrides platform-level for matching tier.
3. Account-level overrides both tier and platform.
4. Inactive, scheduled-future, and expired promotions are ignored.
5. Invalid effects are rejected.
6. Multiple promotions in same scope obey deterministic policy.

## B) Platform admin permission/security tests

Add to `tests/test_platform_admin_permissions.py` or split into dedicated promotion test module:

1. Anonymous, regular, staff, org-admin denied for promotions endpoints.
2. Superuser can access/manage promotions.
3. GET/POST restrictions enforced per endpoint.
4. Invalid payloads return safe errors and do not persist partial state.

## C) Billing and checkout integration tests

Extend `tests/test_organisation_checkout.py` and billing tests:

1. Org checkout amount uses active applicable promotion.
2. Fallback to base pricing when no promotion applies.
3. Promotion metadata passed into subscription creation.
4. Session and token protections continue to work unchanged with promotions enabled.
5. Payment API errors still handled correctly when promotions are present.
6. Existing active subscription amount is updated correctly when promotion starts.
7. Subscription amount is reverted correctly when promotion expires.
8. New account can complete direct promoted checkout without a free-tier prerequisite.

## D) Refund/credit adjustment tests

1. Over-collection scenario creates a valid adjustment record.
2. Refund action validates amount bounds and audit fields.
3. Adjustment notification email is sent.
4. Idempotency protections prevent duplicate adjustments for same trigger.
5. Per-customer billing timeline exposes refund action only to permitted superusers.
6. Refund actions from per-customer timeline persist provider and audit references.

## E) Dashboard/data visibility tests

1. Dashboard displays team and individual account metrics correctly.
2. Promotions summary counts are correct for active/scheduled/expired.
3. Large result sets paginate/filter correctly.
4. Scope selector correctly filters Overview, Billing, Accounts, and Logs.
5. `All` scope returns platform-wide aggregates without double counting.

## F) Provisioning workflow tests

1. Superuser can provision user/team/organization accounts from unified flow.
2. Tier validation blocks incompatible account type selections.
3. Optional promotion at creation is persisted and applied at checkout/billing.
4. Free-tier-first is not required for direct paid/promo onboarding.
5. Audit trail captures provisioning actor and selected billing mode.

## G) Regression tests

1. Existing pricing override behavior remains intact where intended.
2. Existing platform admin pages continue to render and enforce permissions.
3. Existing organisation checkout security tests still pass.

## Suggested initial delivery slice

To reduce risk, implement in this order:

1. Read-only promotions list and resolver with tests
2. Promotion create/edit/activate flows (superuser-only)
3. Organisation checkout integration
4. User/team billing integration
5. Dashboard expansion for teams/individual accounts

This approach gets secure core behavior in place before broad UI/reporting expansion.
