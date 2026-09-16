# Manual Tier Upgrade & Expiry Lifecycle — Implementation Plan

## Problem

A platform admin can manually upgrade a free account to a paid tier (e.g. Pro) via `organization_create` in `checktick_app/core/views_platform_admin.py` (L843–858). The current flow sets `account_tier`, `subscription_status = ACTIVE`, and `tier_changed_at`, but:

- It does **not** set `subscription_current_period_end`, so the daily `process_expired_subscriptions` cron never matches the profile (its query filters on `subscription_current_period_end__lt=now`).
- There is no `payment_subscription_id`, so no GoCardless webhook will ever fire to renew or cancel.
- Net effect: a manually upgraded account stays on the paid tier **indefinitely** with no automatic review point, no audit trail in the billing view, and no expiry.

Separately, even for users whose subscriptions *do* expire naturally (paid subscription cancelled and period end reached), the only notification is a single email sent at the moment of downgrade (`send_subscription_expired_email` in `checktick_app/core/email_utils.py` L1030). On subsequent login there is no banner, flash message, or badge distinguishing a lapsed subscriber from a never-subscribed free user.

## Goals

1. Manual tier upgrades have a finite, operator-chosen validity period and auto-expire.
2. Users approaching expiry get a warning email before the cliff.
3. Users who have lapsed see a clear signpost on login and in the UI, distinct from never-subscribed free users.
4. Re-subscription after lapse re-opens auto-closed surveys where appropriate.
5. Platform admins have a dedicated UI for adding users and setting tier + validity in one workflow.

Non-goals: changing the GoCardless webhook-driven renewal path for self-serve paid subscriptions; changing the `Promotion` model; introducing a new billing provider.

## Existing Behaviour to Reuse

| Behaviour | Location | Notes |
|---|---|---|
| Auto-downgrade at period end | `process_expired_subscriptions` management command (`checktick_app/core/management/commands/process_expired_subscriptions.py` L94–193) | Queries `subscription_current_period_end__lt=now` + `subscription_status__in=[CANCELED, ACTIVE]` + `account_tier != FREE`. Reuse as-is. |
| Auto-close excess surveys on downgrade | `UserProfile.force_downgrade_tier()` (`checktick_app/core/models.py` L491–547) | Closes oldest surveys beyond free limit (3). Read-only, not deleted. Reuse as-is. |
| Expiry email | `send_subscription_expired_email()` (`checktick_app/core/email_utils.py` L1030) | Already called by the cron. Reuse as-is. |
| Manual upgrade write path | `organization_create` view (`views_platform_admin.py` L843–858) | Currently writes `account_tier`, `subscription_status`, `tier_changed_at`. Needs to also write `subscription_current_period_end`. |
| Login signal | `user_logged_in` receiver (`checktick_app/core/signals.py` L178–188) | Currently only writes an `AuditLog` row. Extension point for the login signpost. |
| Base template tier badge | `checktick_app/templates/base.html` L160 | Shows `get_account_tier_display|upper` as a ghost badge. Extension point for lapsed indicator. |
| Profile page status badge | `checktick_app/core/templates/core/profile.html` L211–219 | Already shows `subscription_status` badge ("Cancelled" = warning). No change needed, but worth linking from the new login banner. |

## Implementation Steps

### Step 1 — Set `subscription_current_period_end` on manual upgrade

**File:** `checktick_app/core/views_platform_admin.py` (`organization_create`, around L843–858).

Extend the manual-tier-account branch to accept a `valid_until` form field and write it to `subscription_current_period_end`. Keep `subscription_status = ACTIVE` (not `CANCELED`) so the existing cron's expired-subscriptions pass picks it up when the date passes.

```python
profile.account_tier = scope
profile.subscription_status = (
    UserProfile.SubscriptionStatus.NONE
    if scope == UserProfile.AccountTier.FREE
    else UserProfile.SubscriptionStatus.ACTIVE
)
profile.tier_changed_at = timezone.now()
profile.subscription_current_period_end = valid_until  # NEW
profile.save(update_fields=[
    "account_tier",
    "subscription_status",
    "tier_changed_at",
    "subscription_current_period_end",  # NEW
    "updated_at",
])
```

**Decision needed:** for tiers that don't make sense with expiry (e.g. `organization`, `enterprise`), should `valid_until` be optional/nullable? Recommend: required for `pro` and `team_*`, optional (defaults to `None` = no expiry) for `organization`/`enterprise`. Document this in the form.

**Audit:** add an `AuditLog` entry recording the actor, target user, old tier, new tier, and `valid_until`. The existing `organization_create` flow does not currently write an audit row for tier changes — this is a gap worth closing in the same change.

### Step 2 — Pre-expiry warning email

**File:** new pass in `process_expired_subscriptions.py`, or a new management command `process_expiring_subscriptions` (cleaner separation; recommend the latter).

Logic:
- Query `UserProfile.objects.filter(subscription_current_period_end__isnull=False)` where `subscription_current_period_end` is within the next 7 days and `subscription_status == ACTIVE` and `account_tier != FREE`.
- For each match, send a "Your [Tier] access ends on [date]" email via a new `send_subscription_expiring_email()` in `email_utils.py` (mirror `send_subscription_expired_email`).
- Idempotency: add a `last_expiry_warning_sent_at` field on `UserProfile` (or reuse a lightweight `NotificationLog` model if one exists — check `surveys/models.py` for an existing notification log before adding a new field). Only send once per expiry window.
- Schedule: daily, alongside `process_expired_subscriptions`. Document in `docs/self-hosting-scheduled-tasks.md`.

### Step 3 — Login-time signpost

**File:** `checktick_app/core/signals.py` (`user_logged_in` receiver, L178–188).

Extend the existing receiver to set a Django `messages.warning()` when the user's profile indicates a recent lapse. "Recent" = `subscription_status == CANCELED` AND `tier_changed_at` within the last 14 days AND `account_tier == FREE`. This avoids re-showing the banner forever; after 14 days the user is treated as a regular free user.

```python
@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    from django.contrib import messages
    from django.utils import timezone
    from datetime import timedelta

    # existing AuditLog write ...

    profile = getattr(user, "profile", None)
    if (
        profile
        and profile.subscription_status == UserProfile.SubscriptionStatus.CANCELED
        and profile.account_tier == UserProfile.AccountTier.FREE
        and profile.tier_changed_at
        and profile.tier_changed_at > timezone.now() - timedelta(days=14)
    ):
        messages.warning(
            request,
            "Your paid subscription has ended and your account has been "
            "downgraded to Free. Some surveys may have been closed. "
            "Upgrade again to restore full access.",
        )
```

Note: `messages.warning` requires the `django.contrib.messages` middleware and storage backend, which are already in use across the admin templates (see `platform_admin/base.html` L105–114 rendering `{% for message in messages %}`). Confirm the messages framework is enabled for the user-facing `base.html` (it is — L223–227 renders the same loop).

### Step 4 — Distinguish lapsed from never-subscribed in UI

**File:** `checktick_app/templates/base.html` (L160, the tier badge).

Currently:
```html
<span class="badge badge-xs badge-ghost">{{ user.profile.get_account_tier_display|upper }}</span>
```

Change to surface lapsed state when `subscription_status == CANCELED` and `tier_changed_at` is set (i.e. they used to be paid):
```html
{% if user.profile.subscription_status == 'canceled' and user.profile.tier_changed_at %}
  <span class="badge badge-xs badge-warning" title="Your paid subscription has ended">{% trans "LAPSED" %}</span>
{% else %}
  <span class="badge badge-xs badge-ghost">{{ user.profile.get_account_tier_display|upper }}</span>
{% endif %}
```

Keep the existing "Upgrade" button (L142–149) — it already shows for `account_tier == 'free'`, which covers lapsed users.

**Accessibility:** the `badge-warning` colour pair must meet WCAG 2.2 AA contrast against the navbar background. Verify with the accessibility test suite (`s/test --a11y-only`) after the change. Use `text-warning-content` if the default warning badge text contrast is insufficient.

### Step 5 — Re-open closed surveys on re-subscription

**Investigation first.** `force_downgrade_tier` closes surveys but I did not find a re-open path in `billing.create_subscription_for_user` or the `payments.confirmed` webhook handler. Confirm by reading:
- `checktick_app/core/billing.py` `create_subscription_for_user` (L617+) — does it touch `Survey.status`?
- The `payments.confirmed` webhook handler in `checktick_app/core/views_billing.py` (or wherever `handle_gocardless_payment_confirmed` lives).

**Proposed behaviour:** on re-subscription to a tier whose `max_surveys` is greater than the user's current active+closed count, automatically re-open the most recently closed surveys up to the new limit. Add a `reopened_count` to the welcome-back / checkout-success context.

**Scope guard:** only re-open surveys closed by the *previous* downgrade (track via a `closed_by_downgrade_at` timestamp on `Survey`, or a `SurveyClosureLog` model). Avoid re-opening surveys the user manually closed for their own reasons. This is the most complex step — consider deferring to a follow-up if the first four steps are time-boxed.

### Step 6 — Platform admin "Add user" UI workflow

**Files:**
- `checktick_app/core/views_platform_admin.py` — extend `organization_create` (or add a sibling `tier_account_create` view if the org/tier branching in `organization_create` is getting unwieldy; recommend extending in place to avoid route sprawl).
- `checktick_app/core/templates/core/platform_admin/organization_form.html` — add the new form fields.
- `checktick_app/core/urls.py` — no change if reusing the existing route.

**Form fields to add** (only shown when `create_tier_account` is true, i.e. `mode == tier` and `scope != organization`):

| Field | Type | Validation |
|---|---|---|
| `tier` | `<select>` dropdown | Required. Options: `free`, `pro`, `team_small`, `team_medium`, `team_large`. Reuse `UserProfile.AccountTier.choices` (filtered to exclude `organization`/`enterprise` which are provisioned via the org flow). Pre-selected from the current `scope` query param. |
| `validity_preset` | Radio/toggle buttons | `1_year` / `2_years` / `5_years` / `custom`. Default `1_year`. Selecting `custom` reveals the `valid_until` date picker. |
| `valid_until` | `<input type="date">` | Required when `validity_preset == custom`, or when preset is selected (computed client-side, submitted as the canonical value). Must be in the future. Optional/blank when tier is `free` (free has no expiry). |

**Client-side behaviour (small JS snippet in the template):**
- When a preset button is clicked, compute `valid_until = today + N years` and populate the hidden/submitted `valid_until` field. Show the computed date as read-only text next to the toggle so the admin sees the actual date.
- When `custom` is clicked, enable the date picker and clear the preset-derived value.
- When `tier == free`, disable and hide the validity controls (free has no expiry).

**Server-side handling** (in `organization_create`, tier-account branch):
- Parse `valid_until` from the POST data. If a preset was selected, the JS should have already filled `valid_until`; treat the submitted `valid_until` as canonical.
- Validate: required for non-free tiers; must parse as a date; must be `> today`; must be `<= today + 10 years` (sanity cap).
- Pass to the profile write in Step 1.

**Audit entry:** record `valid_until` in the `AuditLog` row added in Step 1 so there's a trace of when the admin intended the access to lapse.

**Edge cases:**
- Admin edits an existing user (the `account = User.objects.filter(...).first()` branch at L823). The same form should let them *extend* or *shorten* `valid_until` on an already-upgraded account. The write path is the same; just make sure the form is populated with the current `subscription_current_period_end` when editing.
- Admin downgrades a paid user to free via the same form. Set `valid_until = None`, `subscription_status = NONE`, and call `force_downgrade_tier(FREE)` to close excess surveys immediately (don't wait for the cron).

## Testing

Add to `tests/test_billing.py` (alongside the existing `TestSubscriptionExpiryCommand` class):

1. **Manual upgrade with `valid_until`** — admin upgrades free user to pro with `valid_until = now + 365 days`; assert `subscription_current_period_end` is set, `subscription_status == ACTIVE`, audit log row exists.
2. **Expiry fires** — set `subscription_current_period_end` to past; run `process_expired_subscriptions`; assert downgrade to free, surveys closed, expiry email sent.
3. **Pre-expiry warning** — set `subscription_current_period_end` to 5 days from now; run the new `process_expiring_subscriptions` command; assert warning email sent; run again; assert no duplicate (idempotency).
4. **Login signpost** — lapsed user (CANCELED + `tier_changed_at` 3 days ago) logs in; assert `messages.warning` present. Lapsed user 20 days ago logs in; assert no warning.
5. **Lapsed badge** — render `base.html` for a lapsed user; assert `badge-warning` with "LAPSED". Render for never-subscribed free user; assert `badge-ghost` with "FREE".
6. **Form validation** — POST `valid_until` in the past; assert form re-renders with error. POST `validity_preset=custom` with blank `valid_until`; assert error. POST `tier=free` with `valid_until` set; assert it's ignored (free has no expiry).
7. **Re-open on re-subscription** (if Step 5 is in scope) — downgrade closes 2 surveys; re-subscribe; assert the 2 most recently closed surveys are re-opened, manually-closed surveys remain closed.

Run `s/test --no-a11y` for the functional suite and `s/test --a11y-only --serial` for the new badge contrast check. Run `s/lint` before commit.

## Documentation Updates

- `docs/billing-and-subscriptions.md` — add a section "Manual tier upgrades and expiry" describing the `valid_until` field, the cron-driven expiry, and the pre-expiry warning.
- `docs/platform-admin-functionality-technical-implementation.md` — document the new form fields in the Account and Billing Operations section.
- `docs/self-hosting-scheduled-tasks.md` — add the new `process_expiring_subscriptions` command to the cron list.
- `docs/billing-refunds-promotions-technical-overview.md` — add a short "Manual upgrades" subsection cross-linking to the above.
- `AGENTS.md` — add a bullet under Billing / Pricing noting that manual upgrades set `subscription_current_period_end` and expire via the existing cron.

## Open Questions

1. **Default validity for `organization`/`enterprise` tiers** — recommend no expiry (admin sets explicitly if needed). Confirm with CTO.
2. **Pre-expiry warning window** — 7 days recommended. Could also add a 30-day warning for annual subscriptions. Decide before implementing Step 2.
3. **Re-open-on-resubscribe scope** — Step 5 is the most complex and least coupled to the rest. Acceptable to ship Steps 1–4 + 6 first and defer Step 5 to a follow-up?
4. **Idempotency storage for the warning email** — new `last_expiry_warning_sent_at` field on `UserProfile` (migration) vs. a generic `NotificationLog` model. Check whether `surveys/models.py` already has a notification log to reuse.
5. **Sanity cap on `valid_until`** — 10 years recommended. Confirm.
