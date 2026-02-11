---
title: Production Deployment
category: self-hosting
priority: 8
---

Complete guide for deploying CheckTick in production with SSL, nginx, and security hardening.

## Production Checklist

Before deploying to production:

- [ ] Domain name configured with DNS pointing to your server
- [ ] SSL certificate ready (Let's Encrypt recommended)
- [ ] Email service configured and tested
- [ ] Secure passwords generated for database and Django
- [ ] Firewall configured (ports 80, 443)
- [ ] Backup strategy planned

## SSL and Nginx Setup

For production deployments, use nginx as a reverse proxy for SSL termination and static file serving.

### 1. Download Nginx Configuration

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

### 2. Get SSL Certificate

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

# Copy certificates
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/fullchain.pem
sudo chmod 600 nginx/ssl/privkey.pem
```

**Option B: Existing Certificate**

```bash
# Copy your certificates
mkdir -p nginx/ssl
cp /path/to/fullchain.pem nginx/ssl/
cp /path/to/privkey.pem nginx/ssl/
chmod 644 nginx/ssl/fullchain.pem
chmod 600 nginx/ssl/privkey.pem
```

### 3. Configure Your Domain

Edit `nginx/nginx.conf` and replace `yourdomain.com`:

```bash
sed -i 's/yourdomain.com/your-actual-domain.com/g' nginx/nginx.conf
```

Or manually edit:

```nginx
server_name your-actual-domain.com www.your-actual-domain.com;
```

### 4. Update Environment Variables

Edit `.env`:

```bash
ALLOWED_HOSTS=your-actual-domain.com,www.your-actual-domain.com
CSRF_TRUSTED_ORIGINS=https://your-actual-domain.com,https://www.your-actual-domain.com
SECURE_SSL_REDIRECT=True
```

### 5. Start with Nginx

```bash
# Start both base and nginx services
docker compose -f docker-compose.registry.yml -f docker-compose.nginx.yml up -d

# Verify nginx is running
docker compose ps nginx

# Check nginx configuration
docker compose exec nginx nginx -t

# View logs
docker compose logs nginx
```

### 6. Set Up Auto-Renewal

For Let's Encrypt certificates:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab
(crontab -l 2>/dev/null; echo "0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/*.pem /path/to/checktick/nginx/ssl/ && docker compose restart nginx") | crontab -
```

## Security Hardening

### Change Default Database Password

In `.env`:

```bash
# Generate secure password
openssl rand -base64 32

# Update in .env
POSTGRES_PASSWORD=your-generated-password
DATABASE_URL=postgresql://checktick:your-generated-password@db:5432/checktick
```

### Enable CAPTCHA

Prevent spam signups:

1. Get free keys from [hCaptcha](https://hcaptcha.com)
2. Add to `.env`:

```bash
HCAPTCHA_SITEKEY=your-site-key
HCAPTCHA_SECRET=your-secret-key
```

### Configure Email Sending Limits

In `nginx/nginx.conf`, rate limits are already configured:

```nginx
# Signup/login: 5 requests per minute
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

# General API: 10 requests per second
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
```

Adjust these values based on your needs.

### Firewall Configuration

```bash
# Allow SSH (if you're using it)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Regular Updates

```bash
# Update CheckTick
docker compose pull
docker compose up -d

# Update system packages
sudo apt-get update
sudo apt-get upgrade
```

## Performance Optimization

### Increase Workers

For better performance with multiple users, increase Gunicorn workers:

Edit `docker-compose.registry.yml` and override the CMD:

```yaml
services:
  web:
    command: >
      sh -c "python manage.py migrate --noinput &&
             python manage.py collectstatic --noinput &&
             gunicorn checktick_app.wsgi:application
             --bind 0.0.0.0:8000
             --workers 8
             --timeout 120"
```

**Workers calculation:** `(2 × CPU cores) + 1`

### Enable Database Connection Pooling

For high-traffic deployments, add to `.env`:

```bash
# Connection pooling (requires pgbouncer)
DATABASE_URL=postgresql://checktick:password@pgbouncer:6432/checktick
```

### Static File Caching

Nginx already configures aggressive caching for static files:

```nginx
location /static/ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

## Monitoring

### Health Checks

CheckTick includes a health check endpoint:

```bash
# Check application health
curl http://localhost:8000/api/health

# Expected response: 200 OK
```

### Container Logs

```bash
# View all logs
docker compose logs

# Follow web logs
docker compose logs -f web

# View nginx access logs
docker compose logs nginx | grep -v health
```

### Database Monitoring

```bash
# Check database size
docker compose exec db psql -U checktick -c "SELECT pg_size_pretty(pg_database_size('checktick'));"

# Active connections
docker compose exec db psql -U checktick -c "SELECT count(*) FROM pg_stat_activity;"
```

## Scaling Considerations

### Multiple Web Servers

For high availability, run multiple web containers behind a load balancer:

```yaml
services:
  web:
    deploy:
      replicas: 3
```

### External Database

For production, use a managed database service. See [Database Options](self-hosting-database.md).

### Redis for Caching

Future enhancement - not currently required but can improve performance.

## Troubleshooting Production Issues

### 502 Bad Gateway

```bash
# Check web container is running
docker compose ps web

# Check web logs
docker compose logs web

# Restart web container
docker compose restart web
```

### SSL Certificate Issues

```bash
# Verify certificate files exist
ls -la nginx/ssl/

# Check nginx configuration
docker compose exec nginx nginx -t

# View nginx error log
docker compose logs nginx | grep error
```

### High Memory Usage

```bash
# Check container memory
docker stats

# Restart services to free memory
docker compose restart
```

### Slow Performance

1. Check worker count matches CPU cores
2. Monitor database connections
3. Review nginx rate limits
4. Consider external database for high traffic

## Production Environment Variables

Required for production:

```bash
# Security
SECRET_KEY=<long-random-string>
DEBUG=False
SECURE_SSL_REDIRECT=True

# Hosts
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
POSTGRES_PASSWORD=<secure-password>

# Email (required for user management)
EMAIL_HOST=<smtp-server>
EMAIL_HOST_USER=<username>
EMAIL_HOST_PASSWORD=<password>
DEFAULT_FROM_EMAIL=<from-address>
```

Optional but recommended:

```bash
# Spam protection
HCAPTCHA_SITEKEY=<key>
HCAPTCHA_SECRET=<secret>

# SSO (for organisation encryption features)
OIDC_RP_CLIENT_ID_GOOGLE=<id>
OIDC_RP_CLIENT_SECRET_GOOGLE=<secret>
```

## Next Steps

- **[Database Options](self-hosting-database.md)** - External managed databases
- **[Backup Strategy](self-hosting-backup.md)** - Protect your data
- **[Configuration](self-hosting-configuration.md)** - Customize your instance
