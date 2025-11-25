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

- **Docker** 24.0+ and **Docker Compose** 2.0+
- **2GB RAM minimum** (4GB recommended)
- **10GB disk space** for database and media files
- **Domain name** (optional, but recommended for production)

## Quick Start

### 1. Download Deployment Files

```bash
# Create a directory for your deployment
mkdir checktick-app && cd checktick-app

# Download the compose file
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.registry.yml

# Download environment template
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/.env.selfhost
mv .env.selfhost .env
```

### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Generate a secure secret key
openssl rand -base64 50

# Edit configuration
nano .env
```

**Minimum required settings:**

```bash
Edit `.env` and configure at minimum:

```bash
# Security (REQUIRED)
SECRET_KEY=your-generated-secret-key
ALLOWED_HOSTS=yourdomain.com,localhost

# Database (REQUIRED - for included PostgreSQL)
POSTGRES_PASSWORD=secure-database-password
# REQUIRED - forms base url for emails
SITE_URL="https://yourdomain.com"

# Branding (OPTIONAL - has defaults)
BRAND_TITLE=Your Survey Platform
# Theme Configuration (OPTIONAL - has sensible defaults)
# Set deployment-level default themes - org admins can override in Profile
# Light theme: choose from 20 options (nord, cupcake, emerald, corporate, etc.)
# Dark theme: choose from 12 options (business, dark, night, forest, etc.)
# See docs/themes.md for full list and customization options
BRAND_THEME_PRESET_LIGHT=nord
BRAND_THEME_PRESET_DARK=business

# Email Provider (REQUIRED for functionality)
# Email is essential for user invitations, password resets, and notifications
# CheckTick will start without email configured, but users cannot be invited or reset passwords
DEFAULT_FROM_EMAIL=no-reply@yourdomain.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# External Datasets (REQUIRED)
# Get free API key from: https://api.rcpch.ac.uk
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk
EXTERNAL_DATASET_API_KEY=your-rcpch-api-key
```

> **Note**: Generate a strong `SECRET_KEY` with: `openssl rand -base64 50`
```

> **Note:** CheckTick will start without email configured, but users cannot be invited or reset passwords. Email setup is essential for a working system.

### 3. Start CheckTick

```bash
# Pull the latest image and start services
docker compose -f docker-compose.registry.yml up -d

# Check status
docker compose ps

# View logs
docker compose logs -f web
```

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

### 5. Access Your Instance

Visit `http://localhost:8000` (or your domain) and log in with your admin credentials.

## Next Steps

- [Scheduled Tasks](/docs/self-hosting-scheduled-tasks/) - **REQUIRED** for GDPR compliance and maintenance
- [Production Setup](/docs/self-hosting-production/) - SSL, nginx, security hardening
- [Database Options](/docs/self-hosting-database/) - External managed databases (AWS RDS, Azure, etc.)
- [Configuration Guide](/docs/self-hosting-configuration/) - Branding, authentication, email providers
- [Theming & UI Customization](/docs/themes/) - Theme presets, custom CSS, and daisyUI configuration
- [Backup & Restore](/docs/self-hosting-backup/) - Database backups and disaster recovery

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
