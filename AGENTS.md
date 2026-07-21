# AGENTS.md

This file is a quick start for AI coding agents working in this repository.
It signposts common workflows and links to the full docs instead of duplicating them.

## Primary References

- Project documentation index: `docs/README.md`
- Contributing guide: `CONTRIBUTING.md`
- CDN/SRI update process: `docs/cdn-libraries.md`
- Versioning and deployment policy: `docs/versioning-and-deployment.md`
- Testing guides: `docs/testing-webapp.md`, `docs/testing-api.md`, `docs/accessibility.md`

## Common Agent Workflows

### 1. Run tests (default for feature/bug-fix work)

- Use `s/test --no-a11y` for the default non-accessibility test suite.
- Use `s/test --a11y-only` for the Playwright/axe-core accessibility suite in the dedicated local Chromium container. Add `--serial` if you need simpler logs.
- If the Docker web container is not running, the script will start it automatically for non-accessibility tests.
- Accessibility tests use `Dockerfile.a11y` and `docker-compose.a11y.yml` because the normal web container intentionally does not include Chromium.

### 2. Test fallback when Docker is not running

- If the Docker web container is not running, the script will start it automatically.
- `s/test --no-a11y --host-fallback` runs via Poetry on the host, but **requires a local PostgreSQL instance on port 5432**. The Docker DB is not exposed to the host, so this will fail unless you have a separate local DB. The script will check and exit clearly if none is found.

### 3. Lint before commit

- Any feature or bug fix must be completed by running `s/lint` before committing.

### 4. Version bumps (CTO/maintainer workflow)

- The Python package version lives in `pyproject.toml` (not `package.json`).
- When `pyproject.toml` version is bumped and merged to `main`, GitHub Actions automatically:
  - Updates the version badge in `README.md`
  - Enables versioned container publishing via the Docker publish workflow rules
  - These appear in the [GitHub Packages Registry](https://github.com/eatyourpeas-ltd/checktick/pkgs/container/checktick)
- See `docs/versioning-and-deployment.md` for full trigger and tagging rules.
- Typically bumped by CTO; agents should follow semver conventions if contributing version changes.

## Accessibility and Theming

- CheckTick is designed to support and tested against **WCAG 2.2 AA**. See `docs/accessibility.md` and `docs/testing-webapp.md` for the full posture and test workflow.
- Automated accessibility tests live in `tests/test_accessibility.py` and use Playwright plus axe-core WCAG tags, including `wcag22aa`.
- The dashboard custom-theme tester is `checktick_app/static/js/accessibility-test.js`; it loads the self-hosted axe-core asset and should stay aligned with the automated WCAG tag set.
- Theming uses Tailwind CSS v4 and daisyUI v5.6 presets from `checktick_app/static/css/daisyui_themes.css`; details are in `docs/themes.md` and `docs/self-hosting-themes.md`.
- Prefer daisyUI semantic colour pairs such as `bg-primary` with `text-primary-content`, `bg-info` with `text-info-content`, and `bg-base-*` with `text-base-content`. Avoid standalone accent text classes on base backgrounds unless contrast has been checked.

## CDN / Self-Hosted JS Dependencies

- **Single source of truth:** `checktick_app/cdn_assets.json` holds the version, SRI hash, npm package name, static file path, and source path for every self-hosted CDN asset.
- Templates read SRI and file path from this manifest via the `cdn_assets` template context variable (injected by `checktick_app/context_processors.py` → `checktick_app/cdn_assets.py`). **Do not hardcode SRI hashes or static file paths in templates.**
- To update a CDN dependency, run `s/update-cdn-assets`. This downloads the asset from npm, copies it into `checktick_app/static/`, updates the manifest version and SRI, regenerates `docs/cdn-libraries.md`, and appends a compliance log entry.
- Useful flags:
  - `s/update-cdn-assets --dry-run` — preview only.
  - `s/update-cdn-assets --yes --key axe_core` — non-interactive update of a specific asset.
  - `s/update-cdn-assets --sync-docs` — regenerate docs from the manifest without downloading anything.
- `s/sync-cdn-docs` (also called automatically by the updater) regenerates the auto-generated table and SRI sections inside `docs/cdn-libraries.md` from the manifest.
- The GitHub Actions workflow (`.github/workflows/update-cdn-libraries.yml`) reads pinned versions from the manifest (not from `env:` variables) and writes updated SRI hashes back to the manifest via `jq`.
- **When bumping a CDN library version, only two things are needed:**
  1. Run `s/update-cdn-assets` (handles manifest, static file, docs, and compliance log).
  2. If the update is security-driven, also add a row to `docs/compliance/vulnerability-patch-log.md`.
- See `docs/cdn-libraries.md` for the full architecture and troubleshooting guide.

## Other Dependencies

- Python dependencies are managed via Poetry (`pyproject.toml` / `poetry.lock`).

## Billing / Pricing

- **Canonical source:** `checktick_app/core/pricing.py` is the single source of truth for converting ex-VAT tier prices into inc-VAT amounts using `settings.VAT_RATE`.
- **Env-driven VAT:** Only `amount_ex_vat` is stored in `settings.SUBSCRIPTION_TIERS`. The inc-VAT `amount` is computed at runtime via `pricing.get_tier_amounts()` / `pricing.get_effective_tiers()`. **Never hardcode inc-VAT `amount` values in `SUBSCRIPTION_TIERS` or in templates/tests** — always read them through the pricing helpers so changing `VAT_RATE` flows through.
- **Per-seat base:** `settings.BASE_SEAT_PRICE_EX_VAT` (env: `BASE_SEAT_PRICE_EX_VAT`, default £20.00) is the building block for Pro and Team tiers and the default for Organisation per-seat billing.
- **Precedence chain:** `settings.SUBSCRIPTION_TIERS` (base) → `PricingOverride` rows (Platform Admin overrides, replace `amount_ex_vat`) → `Promotion` records (account > tier > platform scope, applied at checkout).
- **PricingOverride model:** `amount_ex_vat` is canonical; `amount` is auto-derived in `save()` from `amount_ex_vat` and `VAT_RATE`.
- **Promotion-discounted VAT:** When a promotion reduces the charged amount, VAT is computed on the **discounted** ex-VAT amount, not the base tier price. At checkout, `billing.create_subscription_for_user` caches the resolved pricing on `UserProfile` (`last_checkout_amount_ex_vat`, `last_checkout_applied_promotion`, `last_checkout_effective_tier`). The `payments.confirmed` webhook handler passes these into `Payment.create_from_subscription` via the `resolved_amount_ex_vat` / `applied_promotion` / `effective_tier` kwargs. The `Payment` record stores the discounted amounts plus a FK to the applied `Promotion` for audit and VAT returns.
- **Public pricing page:** `views._get_public_pricing_context` reads from `PricingOverride.get_effective_tiers()` (which delegates to `pricing.get_effective_tiers`). Templates must read `tier_display` / `tier_pounds` / `subscription_tiers` from that context — never hardcode £ amounts. Note: the headline price on the public pricing page shows the base/override price, not the promotion-discounted price; promotions are surfaced as short-text notes only. The discounted amount is computed at checkout.
- **Platform Admin billing view** (`/platform-admin/billing/`) shows per-payment ex-VAT / VAT / inc-VAT columns and the applied promotion. The Django admin CSV export (`PaymentAdmin.export_to_csv`) includes the same breakdown plus the promotion name, suitable for HMRC VAT returns.
- **User-facing upgrade messages** in `tier_limits.py` use `_tier_price_pounds(tier)` so they stay in sync with `VAT_RATE` and `BASE_SEAT_PRICE_EX_VAT`.
- **Docs:** `docs/billing-and-subscriptions.md` and `docs/pricing-summary.md` describe the default prices (assuming `VAT_RATE=0.20` and `BASE_SEAT_PRICE_EX_VAT=20`). Update both whenever the defaults change.
- **Env files:** `.env.example` and `.env.selfhost` document `VAT_RATE`, `BASE_SEAT_PRICE_EX_VAT`, `VAT_NUMBER`, `COMPANY_NAME`, `COMPANY_ADDRESS`, `COMPANY_REGISTRATION_NUMBER`.

## Notes

- Keep changes minimal and scoped to the request.
- Prefer existing scripts in `s/` over ad-hoc commands when available.

## Logging

This is a medical application so never log patient data or sensitive credentials.
Never log request bodies.
Never log decrypted survey objects.
Never log ORM models directly.
The JSON formatter will catch some of these but it's better to avoid logging them altogether.

For example, instead of:

```python
logger.debug(settings.__dict__)
```

or

```python
logger.info(os.environ)
```

always log only the specific configuration values you're interested in:

```python
logger.info(
    "Vault configured",
    extra={
        "vault_enabled": settings.VAULT_ENABLED,
        "vault_url": settings.VAULT_ADDR,
    },
)
```
