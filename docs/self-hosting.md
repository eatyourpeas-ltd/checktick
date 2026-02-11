---
title: Self-Hosting Guide
category: self-hosting
priority: 1
---

Complete guide to deploying and maintaining your own CheckTick instance using Docker.

## Table of Contents

- [Quick Start](#quick-start) - Get running in 15 minutes
- [Production Deployment](#production-deployment) - SSL, nginx, security hardening
- [Database Options](#database-options) - PostgreSQL configurations
- [Configuration Reference](#configuration-reference) - All environment variables
- [Scheduled Tasks](#scheduled-tasks) - Data governance automation
- [Backup and Restore](#backup-and-restore) - Protecting your data
- [Customization](#customization) - Themes and branding

---

## Quick Start

Get CheckTick running on your own infrastructure in minutes using pre-built Docker images.

### Prerequisites

- **Docker** 24.0+ and **Docker Compose** 2.0+
- **2GB RAM minimum** (4GB recommended)
- **10GB disk space** for database and media files
- **Domain name** (optional, but recommended for production)

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
# Security (REQUIRED)
SECRET_KEY=your-very-long-random-secret-key-from-above
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database (change password!)
POSTGRES_PASSWORD=your-secure-database-password

# Email (for invitations and notifications)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### 3. Start Services

```bash
# Start containers
docker compose -f docker-compose.registry.yml up -d

# Watch logs
docker compose logs -f web
```

### 4. Create Superuser

```bash
# Run migrations (first time only)
docker compose exec web python manage.py migrate

# Create admin account
docker compose exec web python manage.py createsuperuser
```

### 5. Access CheckTick

- **Application**: http://localhost:8000
- **Admin**: http://localhost:8000/admin

**Next steps**: See [Production Deployment](#production-deployment) for SSL and production settings.

### Updating

```bash
# Pull latest image
docker compose pull

# Restart with new image
docker compose up -d

# Run any new migrations
docker compose exec web python manage.py migrate
```

---

## Production Deployment

Complete setup for production with SSL, nginx, and security hardening.

### Production Checklist

Before deploying to production:

- [ ] Domain name configured with DNS pointing to your server
- [ ] SSL certificate ready (Let's Encrypt recommended)
- [ ] Email service configured and tested
- [ ] Secure passwords generated for database and Django
- [ ] Firewall configured (ports 80, 443)
- [ ] Backup strategy planned
- [ ] Scheduled tasks configured (see [Scheduled Tasks](#scheduled-tasks))

### SSL and Nginx Setup

For production deployments, use nginx as a reverse proxy for SSL termination and static file serving.

#### 1. Download Nginx Configuration

```bash
# Download nginx compose overlay
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.nginx.yml

# Create nginx directory
mkdir -p nginx
cd nginx

# Download nginx configuration
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/nginx/nginx.conf

cd ..
```

#### 2. Get SSL Certificate

**Option A: Let's Encrypt (Recommended)**

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Stop any services using ports 80/443
docker compose down

# Get certificate
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com

# Certificates will be in: /etc/letsencrypt/live/yourdomain.com/
```

**Option B: Custom Certificate**

If you have your own certificate:

```bash
mkdir -p ssl
# Copy your certificate files:
# - fullchain.pem (certificate + intermediate)
# - privkey.pem (private key)
```

#### 3. Update Nginx Config

Edit `nginx/nginx.conf` to use your domain and SSL paths:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... rest of config
}
```

#### 4. Update Environment Variables

Edit `.env` for production:

```bash
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
SECURE_SSL_REDIRECT=True
```

#### 5. Start with Nginx

```bash
# Start all services including nginx
docker compose -f docker-compose.registry.yml -f docker-compose.nginx.yml up -d

# Check nginx logs
docker compose logs nginx
```

Your site should now be accessible at `https://yourdomain.com`

### SSL Certificate Renewal

Let's Encrypt certificates expire after 90 days. Set up automatic renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab for automatic renewal
sudo crontab -e

# Add this line (runs twice daily):
0 0,12 * * * certbot renew --quiet && docker compose exec nginx nginx -s reload
```

### Security Hardening

**Firewall Configuration:**

```bash
# Allow SSH (if needed)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

**Security Headers:**

Already configured in nginx config:
- HSTS (HTTP Strict Transport Security)
- X-Frame-Options
- X-Content-Type-Options
- CSP (Content Security Policy)

**Rate Limiting:**

Configure in `.env`:

```bash
# API rate limits (requests per hour)
API_RATE_LIMIT=100

# Login rate limit (attempts per hour)
LOGIN_RATE_LIMIT=5
```

### Health Monitoring

CheckTick provides a health endpoint:

```bash
# Check health
curl https://yourdomain.com/healthz

# Should return: ok
```

Set up monitoring (e.g., UptimeRobot, Pingdom) to check this endpoint every 5 minutes.

### Resource Requirements

**Minimum (1-100 users)**:
- 2GB RAM
- 2 CPU cores
- 20GB disk

**Recommended (100-1000 users)**:
- 4GB RAM
- 4 CPU cores
- 50GB disk

**Large deployment (1000+ users)**:
- 8GB+ RAM
- 8+ CPU cores
- 100GB+ disk
- Consider external database (see [Database Options](#database-options))

---

## Database Options

Choose between included PostgreSQL or external managed database services.

### Option 1: Included PostgreSQL (Default)

#### Pros

- **Simple setup** - Everything in one docker-compose file
- **No additional costs** - No cloud database fees
- **Good for** - Small/medium deployments, single-server setups, testing

#### Cons

- **Manual backups** required
- **Limited scalability** - Tied to single server
- **Your responsibility** - Database maintenance and monitoring

#### Configuration

Already configured in `docker-compose.registry.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - db_data:/var/lib/postgresql/data
```

In `.env`:

```bash
# Database credentials (change password!)
POSTGRES_DB=checktick
POSTGRES_USER=checktick
POSTGRES_PASSWORD=your-secure-password

# Connection string (used by web container)
DATABASE_URL=postgresql://checktick:your-secure-password@db:5432/checktick
```

### Option 2: External Managed Database

Use cloud-managed PostgreSQL from AWS RDS, Azure Database, Google Cloud SQL, etc.

#### Pros

- **Managed backups** - Automatic, point-in-time recovery
- **High availability** - Multi-AZ deployments
- **Scalability** - Easy to resize
- **Monitoring** - Built-in metrics and alerts
- **Good for** - Production deployments, high availability requirements

#### Cons

- **Additional cost** - Cloud database fees
- **Slightly more complex** - External service configuration

#### Setup

**1. Create managed PostgreSQL instance** (example: AWS RDS)

- Engine: PostgreSQL 16
- Instance size: db.t3.small (minimum)
- Storage: 20GB minimum
- **Important**: Enable automated backups

**2. Get connection details:**

- Endpoint: `your-db.region.rds.amazonaws.com`
- Port: `5432`
- Database: `checktick`
- Username: `checktick`
- Password: `your-password`

**3. Download external database compose file:**

```bash
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.external-db.yml
```

**4. Update `.env`:**

```bash
# Remove POSTGRES_* variables, use only:
DATABASE_URL=postgresql://checktick:your-password@your-db.region.rds.amazonaws.com:5432/checktick
```

**5. Start without local database:**

```bash
docker compose -f docker-compose.external-db.yml up -d
```

**6. Run migrations:**

```bash
docker compose exec web python manage.py migrate
```

#### Network Configuration

Ensure your database security group allows connections from your application server:

```
Inbound Rules:
Type: PostgreSQL
Port: 5432
Source: <your-server-ip>/32
```

### Database Performance Tuning

**Connection pooling** (for external databases):

```bash
# In .env
DATABASE_URL=postgresql://user:pass@host:5432/checktick?pool=true&max_conns=20
```

**PostgreSQL settings** (for included PostgreSQL):

Create `postgresql.conf.d/custom.conf`:

```ini
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
```

Mount in `docker-compose.yml`:

```yaml
services:
  db:
    volumes:
      - ./postgresql.conf.d:/etc/postgresql/conf.d
```

---

## Configuration Reference

Complete environment variable reference for customizing your CheckTick deployment.

### Required Settings

#### Database

```bash
# For included PostgreSQL
POSTGRES_DB=checktick
POSTGRES_USER=checktick
POSTGRES_PASSWORD=your-secure-password

# For external database (replaces above)
DATABASE_URL=postgresql://user:password@host:5432/checktick
```

#### Security

```bash
# Generate with: openssl rand -base64 50
SECRET_KEY=your-very-long-random-secret-key-here

# Never use DEBUG=True in production
DEBUG=False

# Your domain(s), comma-separated
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,localhost

# HTTPS origins for CSRF protection
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Force HTTPS redirects (True for production)
SECURE_SSL_REDIRECT=True
```

#### Email

CheckTick requires email for user invitations and notifications:

```bash
DEFAULT_FROM_EMAIL=surveys@yourdomain.com
SERVER_EMAIL=server@yourdomain.com

# Email provider settings (see providers section below)
```

### Optional Settings

#### Application Settings

```bash
# Site name (shown in UI and emails)
SITE_NAME=CheckTick

# Site URL (for links in emails)
SITE_URL=https://yourdomain.com

# Maximum upload file size (in MB)
MAX_UPLOAD_SIZE_MB=10

# Session timeout (in seconds, default 2 weeks)
SESSION_COOKIE_AGE=1209600
```

#### Rate Limiting

```bash
# API requests per hour per user
API_RATE_LIMIT=100

# Login attempts per hour per IP
LOGIN_RATE_LIMIT=5

# Survey responses per hour per IP (prevent spam)
RESPONSE_RATE_LIMIT=50
```

#### Data Governance

```bash
# Default retention period (months) for closed surveys
DEFAULT_RETENTION_MONTHS=6

# Maximum retention period (months)
MAX_RETENTION_MONTHS=24

# Enable deletion warning emails
ENABLE_DELETION_WARNINGS=True
```

#### Storage

```bash
# Media files location (default: ./media)
MEDIA_ROOT=/var/www/media

# Static files location (default: ./staticfiles)
STATIC_ROOT=/var/www/static

# Optional: Use S3 for media storage
USE_S3=True
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-east-1
```

#### Logging

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log to file
LOG_TO_FILE=True
LOG_FILE_PATH=/var/log/checktick/app.log
```

### Email Provider Configuration

#### Gmail

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password  # Not your regular password!
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

**Get App Password:** Google Account → Security → 2-Step Verification → App passwords

#### SendGrid

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

#### AWS SES

```bash
EMAIL_BACKEND=django_ses.SESBackend
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SES_REGION_NAME=us-east-1
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

#### Mailgun

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=postmaster@yourdomain.com
EMAIL_HOST_PASSWORD=your-mailgun-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### External Dataset API (Optional)

For features that fetch external datasets (e.g., NHS hospitals, trusts):

```bash
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk/nhs-organisations/v1
EXTERNAL_DATASET_API_KEY=  # Usually empty for public APIs
```

### OIDC Single Sign-On (Optional)

Configure OIDC for enterprise SSO:

```bash
# Enable OIDC
ENABLE_OIDC=True

# Provider details
OIDC_RP_CLIENT_ID=your-client-id
OIDC_RP_CLIENT_SECRET=your-client-secret
OIDC_OP_AUTHORIZATION_ENDPOINT=https://your-idp.com/auth
OIDC_OP_TOKEN_ENDPOINT=https://your-idp.com/token
OIDC_OP_USER_ENDPOINT=https://your-idp.com/userinfo
OIDC_OP_JWKS_ENDPOINT=https://your-idp.com/jwks

# Optional: Map OIDC claims to Django user fields
OIDC_USERNAME_ALGO=checktick_app.auth.generate_username
```

---

## Scheduled Tasks

CheckTick requires several scheduled tasks for proper operation and GDPR compliance.

### Required Tasks

CheckTick uses **five scheduled tasks**:

1. **Data Governance** (GDPR Required) - Daily deletion warnings and automatic survey cleanup
2. **Survey Progress Cleanup** (Recommended) - Remove expired incomplete survey sessions
3. **External Dataset Sync** (Recommended) - Update hospital lists and organisational data
4. **NHS Data Dictionary Sync** (Recommended) - Scrape standardized NHS codes and values
5. **Global Question Group Templates Sync** (Optional) - Import reusable question templates

### Quick Setup

The minimum required task for GDPR compliance:

```bash
# Add to crontab (runs daily at 2 AM UTC)
0 2 * * * cd /path/to/checktick && docker compose exec -T web python manage.py process_data_governance >> /var/log/checktick-cron.log 2>&1
```

**For complete setup instructions** including all five tasks with platform-specific guides (Northflank, Docker Compose, Kubernetes, AWS ECS, Heroku), see:

👉 **[Scheduled Tasks Documentation](/docs/self-hosting-scheduled-tasks/)**

This comprehensive guide covers:

- Detailed task descriptions and requirements
- Platform-specific setup (Northflank, Docker, Kubernetes, AWS, Heroku, Railway)
- Initial setup and maintenance commands
- Command reference with dry-run options
- Testing and monitoring procedures
- Troubleshooting tips

---

## Backup and Restore

Protect your CheckTick data with regular backups and disaster recovery procedures.

### Backup Strategy

A comprehensive backup strategy includes:

1. **Database backups** - Survey data, users, responses
2. **Media files** - Uploaded images, documents
3. **Configuration** - Environment variables, docker-compose files

### Database Backups

#### Manual Backup

**With included PostgreSQL:**

```bash
# Create backup
docker compose exec db pg_dump -U checktick checktick > checktick-backup-$(date +%Y%m%d-%H%M%S).sql

# Compress backup
gzip checktick-backup-*.sql

# Verify backup
ls -lh checktick-backup-*.sql.gz
```

**With external managed database:**

```bash
# Direct backup
pg_dump postgresql://user:pass@external-host:5432/checktick > checktick-backup-$(date +%Y%m%d).sql

# Or using connection details
PGPASSWORD=yourpassword pg_dump \
  -h external-host \
  -U checktick \
  -d checktick \
  -F c \
  -f checktick-backup-$(date +%Y%m%d).backup
```

#### Automated Backups

Create a backup script (`backup.sh`):

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups/checktick"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d-%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
docker compose exec -T db pg_dump -U checktick checktick | gzip > $BACKUP_DIR/db-$DATE.sql.gz

# Media files backup
tar czf $BACKUP_DIR/media-$DATE.tar.gz media/

# Configuration backup
cp .env $BACKUP_DIR/env-$DATE
cp docker-compose*.yml $BACKUP_DIR/

# Delete old backups
find $BACKUP_DIR -name "*.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "env-*" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
```

Make executable and schedule:

```bash
chmod +x backup.sh

# Add to crontab (daily at 3 AM)
crontab -e
0 3 * * * /path/to/backup.sh >> /var/log/checktick-backup.log 2>&1
```

#### Backup to Cloud Storage

**AWS S3:**

```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure

# Backup script with S3 upload
#!/bin/bash
DATE=$(date +%Y%m%d)
docker compose exec -T db pg_dump -U checktick checktick | gzip | aws s3 cp - s3://your-bucket/checktick-backups/db-$DATE.sql.gz
```

**Google Cloud Storage:**

```bash
# Install gsutil
# ... configure credentials

# Backup with GCS upload
docker compose exec -T db pg_dump -U checktick checktick | gzip | gsutil cp - gs://your-bucket/checktick-backups/db-$DATE.sql.gz
```

### Restore from Backup

#### Database Restore

**From compressed backup:**

```bash
# Stop web service
docker compose stop web

# Restore database
gunzip < checktick-backup-20250109.sql.gz | docker compose exec -T db psql -U checktick checktick

# Restart
docker compose start web
```

**From uncompressed backup:**

```bash
cat checktick-backup.sql | docker compose exec -T db psql -U checktick checktick
```

**Alternative: Drop and recreate:**

```bash
# Stop web
docker compose stop web

# Drop and recreate database
docker compose exec db psql -U checktick -c "DROP DATABASE checktick;"
docker compose exec db psql -U checktick -c "CREATE DATABASE checktick;"

# Restore
gunzip < backup.sql.gz | docker compose exec -T db psql -U checktick checktick

# Restart
docker compose start web
```

#### Media Files Restore

```bash
# Extract media backup
tar xzf media-20250109.tar.gz

# Verify files restored
ls -lh media/
```

### Disaster Recovery

Complete recovery procedure:

**1. Provision new server** (same specs as original)

**2. Install Docker:**

```bash
curl -fsSL https://get.docker.com | sh
```

**3. Restore configuration:**

```bash
mkdir checktick && cd checktick

# Copy backed up files
cp /path/to/backups/docker-compose.registry.yml .
cp /path/to/backups/env-20250109 .env
```

**4. Start database container:**

```bash
docker compose up -d db

# Wait for database to be ready
sleep 10
```

**5. Restore database:**

```bash
gunzip < /path/to/backups/db-20250109.sql.gz | docker compose exec -T db psql -U checktick checktick
```

**6. Restore media files:**

```bash
tar xzf /path/to/backups/media-20250109.tar.gz
```

**7. Start application:**

```bash
docker compose up -d
```

**8. Verify:**

```bash
# Check health
curl http://localhost:8000/healthz

# Check admin access
curl http://localhost:8000/admin/
```

### Testing Backups

Regularly test your backups:

```bash
# Monthly backup test procedure
# 1. Create test database
docker compose exec db psql -U checktick -c "CREATE DATABASE test_restore;"

# 2. Restore to test database
gunzip < latest-backup.sql.gz | docker compose exec -T db psql -U checktick test_restore

# 3. Verify data
docker compose exec db psql -U checktick test_restore -c "SELECT COUNT(*) FROM surveys_survey;"

# 4. Clean up
docker compose exec db psql -U checktick -c "DROP DATABASE test_restore;"
```

### Backup Best Practices

- **Test restores monthly** - Untested backups are useless
- **Store offsite** - Use cloud storage or separate physical location
- **Encrypt backups** - Especially if they contain sensitive data
- **Version control configs** - Keep docker-compose and .env in git (without secrets)
- **Document procedures** - Ensure team knows how to restore
- **Monitor backup jobs** - Alert if backups fail
- **Retention policy** - Keep daily for 7 days, weekly for 4 weeks, monthly for 12 months

---

## Customization

Customize the look and feel of your CheckTick instance.

### Themes and Branding

CheckTick uses DaisyUI themes. You can customize colors, fonts, and styling.

#### Default Themes

Built-in themes available:
- `checktick-light` (default light theme)
- `checktick-dark` (default dark theme)

Users can toggle between themes using the theme switcher in the UI.

#### Custom Branding

Create custom branding via Django admin:

1. Go to `/admin/`
2. Navigate to **Site Branding**
3. Configure:
   - **Site Name**: Your organisation name
   - **Logo**: Upload your logo (SVG recommended)
   - **Primary Color**: Main brand color (hex)
   - **Secondary Color**: Accent color (hex)
   - **Favicon**: Upload favicon

#### Custom CSS

For advanced customization, you can override CSS:

**1. Create custom CSS file:**

```css
/* custom.css */
:root {
  --primary-color: #your-color;
  --secondary-color: #your-color;
}

.survey-header {
  background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
}
```

**2. Mount in docker-compose:**

```yaml
services:
  web:
    volumes:
      - ./custom.css:/app/staticfiles/css/custom.css
```

**3. Reference in template override:**

Create `templates/base.html` override to include your CSS.

#### Logo and Favicon

**Via Admin** (recommended):
1. Go to `/admin/core/sitebranding/`
2. Upload logo and favicon
3. Changes apply immediately

**Via Static Files**:

```bash
# Create static override directory
mkdir -p static-override

# Add your files
cp your-logo.svg static-override/logo.svg
cp your-favicon.ico static-override/favicon.ico

# Mount in docker-compose
volumes:
  - ./static-override:/app/staticfiles/override
```

#### Email Templates

Customize email templates:

```bash
# Create templates override
mkdir -p templates/email

# Copy default template
docker compose cp web:/app/checktick_app/templates/email/invitation.html templates/email/

# Edit template
nano templates/email/invitation.html

# Mount in docker-compose
volumes:
  - ./templates:/app/templates/override
```

#### Translation

CheckTick supports 13 languages. To customize translations:

```bash
# Download translation file
docker compose exec web python manage.py dumpdata core.translation > translations.json

# Edit translations
nano translations.json

# Load back
docker compose exec web python manage.py loaddata translations.json
```

### White Label Deployment

For complete white-label deployment:

1. **Branding**: Set custom logo, colors, site name (via admin)
2. **Domain**: Use your own domain with SSL
3. **Email**: Send from your domain (configure email settings)
4. **Custom CSS**: Override all styling
5. **Remove references**: Set `SITE_NAME` and `DEFAULT_FROM_EMAIL`

Example `.env` for white label:

```bash
SITE_NAME=YourOrg Surveys
SITE_URL=https://surveys.yourorg.com
DEFAULT_FROM_EMAIL=noreply@yourorg.com
SERVER_EMAIL=server@yourorg.com
BRAND_PRIMARY_COLOR=#your-color
BRAND_LOGO_URL=https://yourorg.com/logo.svg
```

---

## Troubleshooting

### Common Issues

#### Container won't start

```bash
# Check logs
docker compose logs web

# Common issues:
# - Database not ready: Wait 30 seconds and retry
# - Port already in use: Change port in docker-compose.yml
# - Permission issues: Check volume permissions
```

#### Database connection errors

```bash
# Verify database is running
docker compose ps db

# Check database logs
docker compose logs db

# Test connection
docker compose exec web python manage.py dbshell
```

#### Static files not loading

```bash
# Collect static files
docker compose exec web python manage.py collectstatic --no-input

# Check nginx logs (if using nginx)
docker compose logs nginx
```

#### Email not sending

```bash
# Test email configuration
docker compose exec web python manage.py shell

from django.core.mail import send_mail
send_mail('Test', 'Body', 'from@example.com', ['to@example.com'])
```

### Performance Issues

#### Slow page loads

- Check database query performance
- Enable caching (Redis)
- Increase worker processes
- Check disk I/O

#### High memory usage

```bash
# Check container memory
docker stats

# Increase limits in docker-compose.yml:
services:
  web:
    mem_limit: 2g
```

### Getting Help

- **Documentation**: Read the full docs at `/docs/`
- **GitHub Issues**: [Report bugs](https://github.com/eatyourpeas/checktick/issues)
- **Discussions**: [Ask questions](https://github.com/eatyourpeas/checktick/discussions)
- **Logs**: Always check `docker compose logs` first

---

## Summary

You now have:
- ✅ CheckTick running with Docker
- ✅ Production deployment with SSL
- ✅ Database backup strategy
- ✅ Scheduled tasks configured
- ✅ Custom branding applied

**Next steps:**
- Configure [Data Governance](data-governance.md)
- Set up [Encryption](encryption.md)
- Explore [API Documentation](using-the-api.md)

For questions or support, see [Getting Help](getting-help.md).
