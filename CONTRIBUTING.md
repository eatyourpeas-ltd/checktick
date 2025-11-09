# Contributing

We welcome contributions of all kinds—bug reports, feature requests, docs, and code. Before opening a new issue, please search the existing [Issues](https://github.com/eatyourpeas/checktick/issues) to avoid duplicates. If you plan to work on something, feel free to open an issue to discuss it first. Pull Requests are very welcome—small, focused PRs are easiest to review.

## Getting Help vs Reporting Issues

### 💬 Use Discussions for

- **General Questions**: "How do I set up multi-language surveys?"
- **Healthcare Use Cases**: Sharing how you use CheckTick in clinical practice
- **Deployment Help**: Getting assistance with self-hosting or configuration
- **Community Support**: Getting help from other CheckTick users
- **Ideas & Brainstorming**: Discussing potential features before formal requests
- **Show and Tell**: Sharing your CheckTick implementations
- **Announcements**: Updates from the team and community

### 🐛 Use Issues for

- **Bug Reports**: Something is broken or not working as expected
- **Feature Requests**: Specific, well-defined features you'd like to see
- **Documentation**: Corrections, improvements, or missing documentation
- **Security**: Non-sensitive security discussions (use private advisories for vulnerabilities)

### When in doubt

Start with **Discussions** - we can always convert a discussion to an issue if needed!

Please follow these guidelines to keep the codebase healthy and secure.

## Tests and dummy credentials

Secret scanners (e.g. GitGuardian, GitHub Secret Scanning, ggshield) run on this repo. To avoid false positives:

- Use non-secret-like dummy values in tests.
  - Prefer a low-entropy constant: `test-pass`
  - Avoid realistic patterns: long base64/hex, JWT-like strings (`xxx.yyy.zzz`), PEM blocks, cloud key prefixes, or "CorrectHorseBatteryStaple"-style phrases.
- If you need to construct tokens for parsing, break known signatures (shorten them, remove prefixes) so they don’t match detectors.
- If a finding still occurs, resolve it one of these ways (in this order):
  1. Refactor to a less-detectable string.
  2. Use a precise per-secret ignore via ggshield (CLI) tied to the signature.
  3. As a last resort, add an inline allowlist comment above the line if your team policy permits:
     - Python: `# pragma: allowlist secret`

## Commit hygiene

- Keep changes focused; write clear commit messages.
- Link issues/PRs where relevant.
- Run the test suite locally before pushing.

## Security practices

- Do not commit real secrets, keys, or tokens.
- Use `.env.example` as a template; never commit your real `.env`.
- Follow existing security patterns (CSP, CSRF, HSTS, rate limiting) when adding features.
- For convenience, before sending in a PR you can run `s/lint` which will run ruff, isort and black and fix any errors.

## Style

- Python: ruff/black-compatible; follow existing patterns.
- Frontend: Tailwind + DaisyUI; keep components consistent with the current design.

### Linting & formatting

We use three tools for Python code quality:

- Ruff: fast linter (the primary style/lint engine)
- Black: code formatter (opinionated, no config)
- isort: import sorting (configured to match Black)

Local usage (poetry-managed):

```sh
# Lint
poetry run ruff check .

# Format (apply changes)
poetry run black .
poetry run isort --profile black .

# Verify (no changes should be needed)
poetry run black --check .
poetry run isort --profile black --check-only .
```

Pre-commit (optional but recommended): install hooks once, then they run automatically on commits.

```sh
pip install pre-commit
pre-commit install
# To run on entire repo
pre-commit run --all-files
```

CI runs the following in the lint phase (see `.github/workflows/ci.yml`):

- `ruff check .`
- `black --check .`
- `isort --profile black --check-only .`

## Docs

- Update `docs/` when behavior or APIs change.
- Keep examples accurate and minimal.

## Pre-commit hooks (recommended with Poetry)

We run quick fixers and secret scans before code lands.

With Poetry-managed tools:

```sh
# Install dependencies
poetry install

# Install git hooks
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push

# Run across the repo once
poetry run pre-commit run --all-files
```

If you don’t use Poetry, install system-wide: `pipx install pre-commit` (or `pip install pre-commit`).

## Local environment quick start

```sh
# Python deps
poetry install

# Start services
docker compose up -d

# Tests
docker compose exec web python -m pytest -q

# Lint/format
poetry run ruff check .
poetry run black --check .
poetry run isort --check-only .
```

## Environment Variables

For local development, environment variables are configured in `docker-compose.yml` with sensible defaults. You don't need to create a `.env` file unless you want to override specific values.

### External Dataset API

If you're working on features that use external datasets (hospitals, NHS trusts, etc.), these are already configured:

- `EXTERNAL_DATASET_API_URL` - Defaults to RCPCH NHS Organisations API
- `EXTERNAL_DATASET_API_KEY` - Empty by default (RCPCH API is public)

These settings are in `docker-compose.yml` and will be picked up automatically when you run `./s/dev` or `docker compose up`.

### Production Deployment

For production environments (Northflank, Heroku, etc.), ensure these environment variables are set in your platform's configuration:

- `EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk/nhs-organisations/v1`
- `EXTERNAL_DATASET_API_KEY=` (leave empty unless using a private API)
- Plus standard Django variables: `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG=False`

See `docs/getting-started.md` for complete environment variable documentation.

## Secret scanning with GitGuardian (ggshield)

Authenticate once locally so scans run without prompts:

```sh
poetry run ggshield auth login
```

Typical local scans:

```sh
# Scan the staged diff (what you'd commit)
poetry run ggshield secret scan pre-commit --verbose

# Scan before pushing
poetry run ggshield secret scan pre-push --verbose

# Scan the full repository
poetry run ggshield secret scan repo --verbose
```

If ggshield flags a false positive in tests, prefer to refactor the test value to a low-entropy dummy. If that’s not possible, add a precise ignore via CLI which updates `.gitguardian.yaml`:

```sh
poetry run ggshield secret ignore add --occurrence <OCCURRENCE_ID>
# or
poetry run ggshield secret ignore add --sha <SECRET_SHA>
```

Avoid broad path ignores. All ignores should be reviewed in PRs.

## Testing in Production Mode

To verify that themes and static assets work correctly in production builds (not just development), use the production test environment:

### Quick Start

```sh
# Build and start production test environment (port 8001)
docker-compose -f docker-compose.prod-test.yml up --build

# Run in background
docker-compose -f docker-compose.prod-test.yml up --build -d
```

Access at **http://localhost:8001** (development remains on port 8000)

### What's Different from Development

- Uses production Dockerfile (CSS built at image build time)
- `DEBUG=False` with production Django settings
- Static files collected to `/staticfiles`
- Gunicorn WSGI server (4 workers)
- Separate database on port 5433

### Verifying Theme System

```sh
# Check CSS files built correctly
docker-compose -f docker-compose.prod-test.yml exec web-prod ls -lh /app/staticfiles/build/

# Verify all daisyUI themes included
docker-compose -f docker-compose.prod-test.yml exec web-prod grep -o '\[data-theme=[^]]*\]' /app/staticfiles/build/styles.css | sort | uniq

# View server logs
docker-compose -f docker-compose.prod-test.yml logs -f web-prod
```

### Testing Checklist

- [ ] All 32 daisyUI theme presets in CSS (20 light + 12 dark)
- [ ] Default themes: nord (light), business (dark)
- [ ] `data-theme` attribute on `<html>` element
- [ ] Theme toggle button switches themes
- [ ] Custom CSS overrides from SiteBranding appear
- [ ] Static files load correctly (check DevTools Network tab)

### Cleanup

```sh
# Stop containers
docker-compose -f docker-compose.prod-test.yml down

# Remove volumes (fresh database next time)
docker-compose -f docker-compose.prod-test.yml down -v
```

**Important**: CSS changes require rebuilding the image since CSS is built at image build time, not runtime.
