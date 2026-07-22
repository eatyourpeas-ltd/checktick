# Annual Billing Implementation Plan

**Status:** Draft
**Date:** July 2026
**Author:** Engineering

## Context

CheckTick currently supports monthly billing only. Every tier in
`settings.SUBSCRIPTION_TIERS` hardcodes `"interval_unit": "monthly"` and
`"interval": 1`, and the checkout flow (`views_billing.start_checkout` →
`billing.create_subscription_for_user`) passes those values straight to
GoCardless with no billing-cycle option.

However, the product documentation already promises annual billing:

- `docs/refund-policy.md` §2.2: "Annual subscriptions are billed once per
  year, offering a discount over monthly billing"
- `docs/refund-policy.md` §4.5: defines the refund rules for annual
  subscriptions (14-day right to cancel, then discretionary pro-rata)
- `docs/billing-and-subscriptions.md`: "Pro-rated refunds for annual plans
  may be considered for exceptional circumstances"
- `docs/pricing-summary.md`: the Enterprise tier table already quotes
  annual figures

The `send_subscription_created_email` function already accepts a
`billing_cycle` parameter ("Monthly" / "Yearly"), and GoCardless natively
supports `interval_unit: "yearly"`. So the infrastructure is partially
scaffolded — the gap is in tier config, pricing calculation, the checkout
form, and the UI.

This plan describes how to add annual billing with a configurable discount,
flowing through to GoCardless in the same way monthly billing does, with
correct VAT treatment on the discounted annual amount.

## Goals

1. Customers can choose monthly or annual billing at checkout for Pro and
   Team tiers.
2. Annual billing applies a configurable discount (default 20% — effectively
   ~2.4 months free) off the equivalent monthly price × 12.
3. The discounted annual amount flows to GoCardless as a single yearly
   charge, with correct VAT computed on the discounted ex-VAT amount.
4. The pricing page, signup page, subscription portal, welcome email, and
   platform admin billing view all show the billing cycle and correct
   amounts.
5. The refund policy for annual subscriptions (14-day right to cancel,
   then discretionary pro-rata) is enforced by the existing refund flow —
   no new refund logic needed for the initial implementation.

## Non-goals

- **Organisation tier annual billing:** Organisation pricing is bespoke
  (per-contract). Annual contracts for organisations are handled
  out-of-band by sales. The platform admin can already set a per-org
  `price_per_seat`; annual org billing would be a separate enhancement.
- **Mid-cycle switches between monthly and annual:** Switching billing
  cycle on an existing subscription requires cancelling and re-subscribing.
  A seamless switch (with pro-rata credit) is a future enhancement.
- **Automatic annual discount as a promotion:** The annual discount is a
  pricing property, not a time-limited promotion. It will be modelled in
  the tier config, not as a `Promotion` record. (Promotions can still be
  stacked on top of annual billing at checkout, as they are today.)

## Design

### Tier config (`settings.py`)

Add a `billing_cycles` sub-dict to each fixed-price tier. The existing
`interval_unit` and `interval` fields at the top level become the default
(monthly) for backwards compatibility.

```python
"pro": {
    "name": "Pro",
    "seats": 1,
    "amount_ex_vat": BASE_SEAT_PRICE_EX_VAT,
    "currency": "GBP",
    "interval_unit": "monthly",  # default, backwards-compatible
    "interval": 1,
    "billing_cycles": {
        "monthly": {
            "interval_unit": "monthly",
            "interval": 1,
            "discount_percent": 0,
        },
        "annual": {
            "interval_unit": "yearly",
            "interval": 1,
            "discount_percent": ANNUAL_DISCOUNT_PERCENT,
        },
    },
    "description": "...",
},
```

New env-driven setting:

```python
# Annual billing discount, applied to (monthly price × 12).
# Default 20% — effectively ~2.4 months free.
ANNUAL_DISCOUNT_PERCENT = float(os.environ.get("ANNUAL_DISCOUNT_PERCENT", "20"))
```

### Pricing helper (`core/pricing.py`)

Add a `billing_cycle` parameter to `get_tier_amounts` and
`get_effective_tiers`:

```python
def get_tier_amounts(tier, *, billing_cycle="monthly", vat_rate=None) -> TierAmounts:
    """Return ex-VAT, inc-VAT, VAT-only amounts for a tier and billing cycle.

    For annual billing, the ex-VAT amount is:
        monthly_amount_ex_vat × 12 × (1 - discount_percent / 100)
    rounded to the nearest penny.
    """
```

The function will:
1. Read the tier's `amount_ex_vat` (the monthly base).
2. If `billing_cycle == "annual"`, multiply by 12 and apply the discount.
3. Compute inc-VAT from the (possibly discounted) ex-VAT via `VAT_RATE`.

`get_effective_tiers` will accept `billing_cycle` and return the full tier
dict with amounts computed for that cycle.

### Checkout flow

**`views_billing.start_checkout`:**
- Accept a `billing_cycle` POST parameter (`"monthly"` or `"annual"`).
- Default to `"monthly"` if not provided (backwards-compatible).
- Store it in the session alongside `checkout_tier`.

**`billing.create_subscription_for_user`:**
- Accept a `billing_cycle` parameter.
- Pass it to `resolve_effective_pricing_for_user` (or `_for_team`).
- Read `interval_unit` / `interval` from the tier's
  `billing_cycles[billing_cycle]` config.
- Pass the resolved amount and the annual interval to
  `payment_client.create_subscription`.
- Cache `billing_cycle` on `UserProfile` alongside the existing
  `last_checkout_*` fields (new field: `last_checkout_billing_cycle`).

**`promotion_resolver.resolve_effective_pricing_for_user`:**
- Accept `billing_cycle` parameter.
- Use `get_effective_tier_amounts(tier, billing_cycle=billing_cycle)` for
  the base price.
- Promotions are applied on top of the annual-discounted base, same as
  they are today for monthly.

### Webhook / Payment record

**`handle_gocardless_payment_confirmed`:**
- Read `last_checkout_billing_cycle` from the profile.
- Pass it to `Payment.create_from_subscription` so the Payment record
  knows whether this is a monthly or annual charge.

**`Payment` model:**
- Add a `billing_cycle` field (`CharField`, choices `monthly` / `annual`,
  default `monthly`) for audit clarity and CSV export.
- `create_from_subscription` accepts `billing_cycle` and uses it to
  compute the correct amount via `get_tier_amounts(tier,
  billing_cycle=billing_cycle)` when no `resolved_amount_ex_vat` is
  provided (backwards-compat fallback).

### UI changes

**Pricing page (`pricing.html`):**
- Add a monthly/annual toggle at the top of the pricing cards section.
  Common pattern: a switch with "Monthly" / "Annual" labels and a
  "Save 20%" badge on the annual side.
- The toggle updates the displayed prices via JavaScript (the team-size
  selector already does this pattern — reuse it).
- The checkout form passes the selected `billing_cycle` as a hidden field.

**Signup page (`signup.html`):**
- Same toggle, same hidden field.

**Subscription portal (`subscription_portal.html`):**
- Show the current billing cycle (Monthly / Annual) next to the tier badge.
- Show the next renewal date (already available via
  `subscription_current_period_end`).

**Platform admin billing view (`billing.html`):**
- Add a "Billing Cycle" column to the payments table.

**Welcome email (`send_subscription_created_email`):**
- Already accepts `billing_cycle` — just pass the actual value from the
  webhook handler instead of the hardcoded `"monthly"`.

### Platform admin pricing overrides

The `PricingOverride` model and the `/platform-admin/pricing/` panel
currently override the monthly ex-VAT amount. For annual billing, the
override applies to the monthly base; the annual price is derived from
it via the discount. This keeps the admin UI simple — one override per
tier, and the annual price follows automatically.

If we later want separate monthly/annual overrides, that would be a
separate enhancement. For now, one override per tier is sufficient.

## Files to change

| File | Change |
|------|--------|
| `checktick_app/settings.py` | Add `ANNUAL_DISCOUNT_PERCENT` env var; add `billing_cycles` sub-dict to each fixed-price tier |
| `checktick_app/core/pricing.py` | Add `billing_cycle` param to `get_tier_amounts`, `get_effective_tiers`, `get_effective_tier_amounts`; add annual price calculation |
| `checktick_app/core/models.py` | Add `billing_cycle` field to `Payment`; add `last_checkout_billing_cycle` to `UserProfile` |
| `checktick_app/core/billing.py` | `create_subscription_for_user` accepts `billing_cycle`; reads interval from `billing_cycles` config; caches on profile |
| `checktick_app/core/services/promotion_resolver.py` | `resolve_effective_pricing_for_user` / `_for_team` accept `billing_cycle` |
| `checktick_app/core/views_billing.py` | `start_checkout` accepts `billing_cycle` from POST; `handle_gocardless_payment_confirmed` passes cached cycle to Payment; `handle_gocardless_subscription_created` passes real cycle to email |
| `checktick_app/core/views.py` | `_get_public_pricing_context` provides both monthly and annual prices for the pricing page |
| `checktick_app/core/email_utils.py` | `send_subscription_created_email` uses cached billing cycle for invoice amounts |
| `checktick_app/core/templates/core/pricing.html` | Monthly/annual toggle; JS to switch displayed prices; hidden `billing_cycle` field in checkout forms |
| `checktick_app/templates/registration/signup.html` | Same toggle and hidden field |
| `checktick_app/core/templates/core/subscription_portal.html` | Show billing cycle badge |
| `checktick_app/core/templates/core/platform_admin/billing.html` | Add Billing Cycle column |
| `checktick_app/core/admin.py` | `PaymentAdmin` list_display / CSV export includes `billing_cycle` |
| `checktick_app/core/migrations/0025_*.py` | Add `billing_cycle` to Payment, `last_checkout_billing_cycle` to UserProfile |
| `tests/test_billing.py` | Tests for annual price calculation, annual checkout, annual VAT, annual + promotion |
| `tests/test_platform_admin_regressions.py` | Update checkout regression tests to pass `billing_cycle` |
| `docs/billing-and-subscriptions.md` | Document annual billing, discount, and refund policy |
| `docs/pricing-summary.md` | Add annual price columns to tier tables |
| `docs/refund-policy.md` | Already documents annual — verify it matches implementation |
| `AGENTS.md` | Document the `billing_cycles` config and `ANNUAL_DISCOUNT_PERCENT` env var |
| `.env.example` | Add `ANNUAL_DISCOUNT_PERCENT=20` |
| `.env.selfhost` | Add `ANNUAL_DISCOUNT_PERCENT` (commented) |

## Migration

Two new fields, both with defaults, so the migration is safe and
backwards-compatible:

- `Payment.billing_cycle` — `CharField(max_length=10, default="monthly")`
- `UserProfile.last_checkout_billing_cycle` — `CharField(max_length=10, default="monthly")`

No data migration needed — existing records default to `"monthly"`.

## Testing

### Unit tests (`tests/test_billing.py`)

1. `test_annual_price_calculation` — annual ex-VAT = monthly × 12 × 0.80
   (at 20% discount), inc-VAT computed from it.
2. `test_annual_price_with_zero_discount` — `ANNUAL_DISCOUNT_PERCENT=0`
   → annual = monthly × 12, no discount.
3. `test_annual_vat_correct` — VAT is 20% of the discounted annual
   ex-VAT, not the undiscounted amount.
4. `test_annual_with_percent_discount_promotion` — 25% annual discount +
   10% promotion → stacked correctly.
5. `test_annual_checkout_passes_yearly_interval_to_gocardless` —
   `create_subscription_for_user` with `billing_cycle="annual"` sends
   `interval_unit="yearly"` to GoCardless.
6. `test_monthly_checkout_still_works` — backwards compat.
7. `test_payment_record_stores_billing_cycle` — Payment record has
   `billing_cycle="annual"` for annual checkout.
8. `test_webhook_uses_cached_billing_cycle` — webhook handler reads
   `last_checkout_billing_cycle` and passes it to
   `create_from_subscription`.

### Regression tests

- All existing billing tests pass unchanged (monthly is the default).
- Platform admin pricing override tests pass (override applies to monthly
  base; annual is derived).

## Rollout

1. Merge code + migration.
2. Set `ANNUAL_DISCOUNT_PERCENT=20` in the hosted environment.
3. The pricing page immediately shows monthly/annual toggle.
4. Existing subscriptions are unaffected (monthly interval, no change).
5. New checkouts can choose monthly or annual.

## Open questions

1. **Default annual discount:** 20% is proposed (≈2.4 months free, a
   common SaaS convention). Confirm or adjust.
2. **Annual on Team tiers:** Should all three Team tiers (Small/Medium/
   Large) support annual, or just Pro? (Proposal: all three, since they're
   fixed-price.)
3. **Annual discount visibility on pricing page:** Show the annual
   per-month-equivalent price (e.g. "£16/mo billed annually") or the
   full annual amount (e.g. "£192/year")? (Proposal: show both — the
   per-month-equivalent as the headline, with "billed annually" as a
   subtitle, matching common SaaS pricing page patterns.)
4. **Proration for upgrades:** If a monthly subscriber upgrades to
   annual mid-cycle, do we pro-rate the remaining monthly period?
   (Proposal: no — require cancellation of monthly and fresh annual
   checkout. Pro-rated upgrades are a future enhancement.)
