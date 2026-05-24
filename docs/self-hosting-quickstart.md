---
title: Self-Hosting Quickstart
category: self-hosting
priority: 2
---

Get CheckTick running on your own infrastructure in minutes using pre-built Docker images.

## Overview

CheckTick can be self-hosted using Docker, similar to platforms like Discourse. You don't need to clone the repository or build anything - just pull the pre-built image and configure your deployment.

**Self-hosted deployments automatically include all Enterprise tier features:**

- Custom branding (logos, themes, fonts)
- No survey limits
- Full collaboration features
- SSO/OIDC integration support

**Branding Configuration:** Superusers can configure platform branding via:

- Web UI at `/branding/` (requires superuser account)
- CLI command: `python manage.py configure_branding`
- Django admin at `/admin/core/sitebranding/`

See [Configuration Guide](/docs/self-hosting-configuration/) for full setup details.

## Prerequisites

CheckTick requires the following infrastructure. Understand what you need before you start:

| Component | Requirement | Notes |
|---|---|---|
| **App container** | Docker image (pulled automatically) | Runs the Django application |
| **PostgreSQL** | Version 16+ | Primary data store for all survey data |
| **Volume: `vault-data`** | 1 GB minimum, **airgapped** | Vault Raft storage — must not be shared with any other service. See [Vault setup](vault.md) |
| **Volume: `snomed-data`** | 10 GB minimum | SNOMED CT SQLite database. Optional — required only for clinical terminology dropdowns |

> ⚠️ `vault-data` and `snomed-data` must be **separate volumes**. Vault uses Raft storage and cannot share its volume with other data.

**Host system requirements:**

- **Docker** 24.0+ and **Docker Compose** 2.0+
- **4 GB RAM** (8 GB recommended if running the SNOMED seeding process on the same host)
- **Domain name** with TLS certificate (required for production; optional for local dev)

## Environment Variables

All configuration is done via environment variables. Start from the provided template:

```bash
# Download the template
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/.env.example
mv .env.example .env
```

`.env.example` contains every supported variable with inline comments. Work through each section and fill in your values. Then copy those values into your hosting provider's secrets/credentials store — **never commit a populated `.env` to version control**.

**Required variables — the app will not start without these:**

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key. Generate with: `openssl rand -base64 50` |
| `ALLOWED_HOSTS` | Comma-separated domains/IPs, e.g. `yourdomain.com,localhost` |
| `CSRF_TRUSTED_ORIGINS` | Full HTTPS origins, e.g. `https://yourdomain.com` |
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgres://user:pass@host:5432/checktick` |
| `DEFAULT_FROM_EMAIL` | Sender address for all outbound email |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP credentials |
| `EXTERNAL_DATASET_API_URL` | Set to `https://api.rcpch.ac.uk` |
| `EXTERNAL_DATASET_API_KEY` | Free key from [api.rcpch.ac.uk](https://api.rcpch.ac.uk) — needed for NHS dropdown lists |
| `VAULT_ADDR` | URL of your Vault instance |
| `VAULT_ROLE_ID` / `VAULT_SECRET_ID` | AppRole credentials from Vault initialisation — see [Vault setup](vault.md) |

**Optional but recommended:**

| Variable | Description |
|---|---|
| `TRUD_API_KEY` | TRUD API key for SNOMED CT. Free from [isd.digital.nhs.uk/trud](https://isd.digital.nhs.uk/trud). Without this, SNOMED dropdown types are hidden |
| `SNOMED_DB_PATH` | Path on the `snomed-data` volume — default `/app/data/snomed.db` |
| `SITE_URL` | Base URL used in email links, e.g. `https://yourdomain.com` |
| `BRAND_TITLE` / `BRAND_THEME` | Branding customisation |
| `OIDC_RP_CLIENT_ID_*` / `OIDC_RP_CLIENT_SECRET_*` | Google or Azure SSO — see [SSO setup](oidc-sso-setup.md) |
| `LLM_URL` / `LLM_API_KEY` | AI-assisted survey generation |
| `HOSTING_API_TOKEN` / `HOSTING_API_BASE_URL` | Infrastructure log viewer in platform admin |

See [Configuration Guide](self-hosting-configuration.md) for the full reference including data governance, compliance roles, and advanced options.

## Quick Start

### 1. Download Deployment Files

```bash
# Create a directory for your deployment
mkdir checktick-app && cd checktick-app

# Download the compose file
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.registry.yml

# Download environment template
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/.env.example
mv .env.example .env
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your values (or use the download step above):

```bash
# Generate a secure secret key
openssl rand -base64 50

# Edit configuration
nano .env
```

At minimum, set:

```bash
# Security
SECRET_KEY=your-generated-secret-key
ALLOWED_HOSTS=yourdomain.com,localhost
CSRF_TRUSTED_ORIGINS=https://yourdomain.com

# Database
DATABASE_URL=postgres://checktick:password@db:5432/checktick
SITE_URL=https://yourdomain.com

# Email
DEFAULT_FROM_EMAIL=no-reply@yourdomain.com
EMAIL_HOST=smtp.eu.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@mg.yourdomain.com
EMAIL_HOST_PASSWORD=your-smtp-password

# External Datasets (free key from https://api.rcpch.ac.uk)
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk
EXTERNAL_DATASET_API_KEY=your-rcpch-api-key

# Vault (generated during vault initialisation — see vault.md)
VAULT_ADDR=https://vault.yourdomain.com:8200
VAULT_ROLE_ID=your-role-id
VAULT_SECRET_ID=your-secret-id

# SNOMED CT (optional — free key from https://isd.digital.nhs.uk/trud)
TRUD_API_KEY=your-trud-api-key
SNOMED_DB_PATH=/app/data/snomed.db
```

> **Note:** CheckTick will start without email configured, but users cannot be invited or reset passwords. Vault and email are essential for a working production system.

### 3. Start CheckTick

```bash
# Pull the latest image and start services
docker compose -f docker-compose.registry.yml up -d

# Check status
docker compose ps

# View logs
docker compose logs -f web
````

### 4. Create Superuser Account

**Important:** Superuser accounts have full administrative access including:

- Access to Django admin interface at `/admin/`
- Ability to configure platform branding at `/branding/`
- User management and system configuration
- Access to all surveys and data

```bash
# Create your first superuser account
docker compose exec web python manage.py createsuperuser

# Follow the prompts:
# - Username: (your admin username)
# - Email: (your admin email)
# - Password: (strong password)
```

**Creating Additional Superusers:**

After initial setup, you can create additional superuser accounts in two ways:

1. **Via Django Admin** (Recommended):
   - Log in to `/admin/` with your superuser account
   - Navigate to "Users" under "Authentication and Authorization"
   - Select a user and check "Superuser status"
   - Or create a new user and grant superuser status

2. **Via Command Line**:

   ```bash
   # Create a new superuser
   docker compose exec web python manage.py createsuperuser

   # Or promote an existing user to superuser
   docker compose exec web python manage.py shell
   >>> from django.contrib.auth import get_user_model
   >>> User = get_user_model()
   >>> user = User.objects.get(username='existing_username')
   >>> user.is_superuser = True
   >>> user.is_staff = True
   >>> user.save()
   >>> exit()
   ```

**Regular User Registration:**

Regular users (non-superusers) can sign up through the web interface at `/signup/` once your instance is running. They don't need command-line access.

**Demo Accounts for Testing (Development/Staging Only):**

For testing different account tiers without going through billing, use the demo accounts command:

```bash
# Create all demo accounts
docker compose exec web python manage.py create_demo_accounts

# Create only a specific tier
docker compose exec web python manage.py create_demo_accounts --tier team_small

# Reset and recreate all demo accounts
docker compose exec web python manage.py create_demo_accounts --reset
```

This creates 7 demo accounts with different tiers:

- `demo-free@example.com` - Free tier
- `demo-pro@example.com` - PRO tier with encryption
- `demo-team-small@example.com` - Team (5 members) with pre-created team
- `demo-team-medium@example.com` - Team (10 members) with pre-created team
- `demo-team-large@example.com` - Team (20 members) with pre-created team
- `demo-org@example.com` - Organization tier with pre-created organization
- `demo-enterprise@example.com` - Enterprise tier with custom branding

**Password for all accounts:** `demo123!pass`

All accounts require 2FA setup on first login (even though billing is bypassed).

> ⚠️ **SECURITY WARNING**: This command is for **development and staging only**. It is blocked in production by checking the `ENVIRONMENT` variable. Set `ENVIRONMENT=production` before going live to prevent creation of accounts with known passwords. Always run with `--reset` before going live to delete all demo accounts.

### 5. Access Your Instance

Visit `http://localhost:8000` (or your domain) and log in with your admin credentials.

## Next Steps

- [Scheduled Tasks](/docs/self-hosting-scheduled-tasks/) - **REQUIRED** for GDPR compliance and maintenance
- [Production Setup](/docs/self-hosting-production/) - SSL, nginx, security hardening
- [Database Options](/docs/self-hosting-database/) - External managed databases (AWS RDS, Azure, etc.)
- [Configuration Guide](/docs/self-hosting-configuration/) - Branding, authentication, email providers
- [Theming & UI Customization](/docs/themes/) - Theme presets, custom CSS, and daisyUI configuration
- [Backup & Restore](/docs/self-hosting-backup/) - Database backups and disaster recovery

## Before Going Live (Production Checklist)

When preparing to accept real users and go into production:

1. **Set environment variable:**

   ```bash
   ENVIRONMENT=production
   ```

   This disables demo account creation to prevent security vulnerabilities.

2. **Delete all demo accounts:**

   ```bash
   docker compose exec web python manage.py create_demo_accounts --reset
   ```

   This removes all `demo-*@example.com` accounts with known passwords.

3. **Review security settings:**
   - Ensure `DEBUG=False` in production
   - Verify `SECRET_KEY` is secure and not shared
   - Check `ALLOWED_HOSTS` is properly configured
   - Enable SSL/TLS (see [Production Setup](/docs/self-hosting-production/))

4. **Test authentication:**
   - Verify 2FA is working
   - Test password reset emails
   - Confirm email notifications are sending

## Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker compose logs web

# Common issues:
# - Missing required environment variables
# - Database connection failed
# - Port 8000 already in use
```

### Can't access the site

1. Check firewall allows port 8000
2. Verify `ALLOWED_HOSTS` includes your domain/IP
3. Check container is running: `docker compose ps`

### Database errors

```bash
# Ensure database is healthy
docker compose ps db

# Check database logs
docker compose logs db

# Reset database (WARNING: destroys all data)
docker compose down -v
docker compose up -d
```

### Email not sending

1. Verify email credentials in `.env`
2. For Gmail, use [App Passwords](https://support.google.com/accounts/answer/185833)
3. Check email service allows SMTP access
4. Test with: `docker compose exec web python manage.py sendtestemail your@email.com`

## Updating CheckTick

```bash
# Pull latest image
docker compose pull

# Restart with new image
docker compose up -d

# Migrations run automatically on startup
```

## Getting Help

- [Documentation](https://github.com/eatyourpeas/checktick/tree/main/docs) - Full guides
- [GitHub Issues](https://github.com/eatyourpeas/checktick/issues) - Report bugs or problems
- [GitHub Discussions](https://github.com/eatyourpeas/checktick/discussions) - Ask questions

## Architecture

Your deployment includes:

- **Web Application** - Django application serving CheckTick
- **PostgreSQL Database** - Data storage with persistent volume
- **Media Volume** - Uploaded files and user content

All data persists in Docker volumes even when containers are stopped or upgraded.
