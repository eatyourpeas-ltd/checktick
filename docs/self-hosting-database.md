---
title: Database Setup
category: self-hosting
priority: 4
---

Choose between included PostgreSQL or external managed database services.

## Overview

CheckTick supports two database deployment options:

1. **Included PostgreSQL** (Default) - Database runs in a Docker container
2. **External Managed Database** - Use AWS RDS, Azure Database, Google Cloud SQL, etc.

## Option 1: Included PostgreSQL (Default)

### Pros

- **Simple setup** - Everything in one docker-compose file
- **No additional costs** - No cloud database fees
- **Good for** - Small/medium deployments, single-server setups, testing

### Cons

- **Manual backups** required
- **Limited scalability** - Tied to single server
- **Your responsibility** - Database maintenance and monitoring

### Configuration

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

### Backups

See [Backup & Restore Guide](self-hosting-backup.md) for backup procedures.

## Option 2: External Managed Database

### Pros

- **Automatic backups** - Provider manages backups
- **High availability** - Built-in failover and redundancy
- **Scalability** - Easy to upgrade resources
- **Managed maintenance** - Automatic updates and patches
- **Good for** - Production deployments, high availability requirements

### Cons

- **Additional cost** - Cloud database fees
- **More complex setup** - Requires cloud account
- **Network latency** - Slight latency vs local database

### Supported Providers

CheckTick works with any PostgreSQL-compatible managed database service:

- **AWS RDS** for PostgreSQL
- **Azure Database** for PostgreSQL
- **Google Cloud SQL** for PostgreSQL
- **DigitalOcean Managed Databases**
- **Heroku Postgres**
- **Any PostgreSQL 12+** instance

## Setting Up External Database

### Step 1: Create Database Instance

Create a PostgreSQL database through your cloud provider:

**Minimum Requirements:**

- PostgreSQL 12 or higher (16 recommended)
- 2 vCPU, 4GB RAM minimum
- 20GB storage (SSD recommended)
- Automated backups enabled

**AWS RDS Example:**

```bash
# Using AWS CLI
aws rds create-db-instance \
  --db-instance-identifier checktick-db \
  --db-instance-class db.t3.small \
  --engine postgres \
  --engine-version 16.1 \
  --master-username checktick \
  --master-user-password <secure-password> \
  --allocated-storage 20 \
  --backup-retention-period 7 \
  --publicly-accessible
```

**Azure Database Example:**

```bash
# Using Azure CLI
az postgres server create \
  --resource-group checktick-rg \
  --name checktick-db \
  --location eastus \
  --admin-user checktick \
  --admin-password <secure-password> \
  --sku-name GP_Gen5_2 \
  --storage-size 51200 \
  --backup-retention 7
```

### Step 2: Configure Firewall

Allow connections from your CheckTick server:

**AWS RDS:**

- Add inbound rule in security group for PostgreSQL (port 5432)
- Allow your server's IP address

**Azure:**

```bash
az postgres server firewall-rule create \
  --resource-group checktick-rg \
  --server-name checktick-db \
  --name AllowCheckTickServer \
  --start-ip-address <your-server-ip> \
  --end-ip-address <your-server-ip>
```

### Step 3: Get Connection String

Your connection string format depends on the provider:

**AWS RDS:**

```
postgresql://checktick:password@checktick-db.abc123.us-east-1.rds.amazonaws.com:5432/checktick
```

**Azure Database:**

```
postgresql://checktick@checktick-db:password@checktick-db.postgres.database.azure.com:5432/checktick?sslmode=require
```

**Google Cloud SQL:**

```
postgresql://checktick:password@/checktick?host=/cloudsql/project-id:region:instance-name
```

### Step 4: Update CheckTick Configuration

Use the external database compose file:

```bash
# Download external database compose file
curl -O https://raw.githubusercontent.com/eatyourpeas/checktick/main/docker-compose.external-db.yml

# Update .env with your connection string
echo "DATABASE_URL=postgresql://user:pass@your-db-host:5432/checktick" >> .env

# Start CheckTick (without local database)
docker compose -f docker-compose.external-db.yml up -d
```

### Step 5: Run Initial Migration

```bash
# Migrations run automatically on startup
# But you can manually trigger if needed:
docker compose exec web python manage.py migrate

# Create admin user
docker compose exec web python manage.py createsuperuser
```

## Connection String Formats

### Standard Format

```
postgresql://username:password@hostname:5432/database_name
```

### With SSL (Recommended for cloud)

```
postgresql://username:password@hostname:5432/database_name?sslmode=require
```

### With Connection Pooling

```
postgresql://username:password@hostname:5432/database_name?sslmode=require&pool_size=10
```

### Unix Socket (Google Cloud SQL)

```
postgresql://username:password@/database_name?host=/cloudsql/project:region:instance
```

## Database Configuration Best Practices

### Connection Limits

Set appropriate connection limits in your database:

**For included PostgreSQL:**

- Default: 100 connections (sufficient for most deployments)

**For external database:**

- Small: 100 connections
- Medium: 200 connections
- Large: 500+ connections

### SSL/TLS

Always use SSL for external databases:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

SSL modes:

- `disable` - No SSL (only for local development)
- `require` - SSL required, don't verify certificate
- `verify-ca` - SSL required, verify certificate
- `verify-full` - SSL required, verify certificate and hostname

### Performance Settings

Recommended PostgreSQL settings for CheckTick:

```sql
-- Connection settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

-- Write performance
wal_buffers = 16MB
checkpoint_completion_target = 0.9

-- Query performance
random_page_cost = 1.1  # For SSD storage
effective_io_concurrency = 200
```

## Migrating Between Options

### From Included to External

```bash
# 1. Backup existing data
docker compose exec db pg_dump -U checktick checktick > backup.sql

# 2. Create external database (see above)

# 3. Restore data
psql postgresql://user:pass@external-host:5432/checktick < backup.sql

# 4. Update .env with new DATABASE_URL

# 5. Switch to external-db compose file
docker compose -f docker-compose.external-db.yml up -d
```

### From External to Included

```bash
# 1. Backup from external database
pg_dump postgresql://user:pass@external-host:5432/checktick > backup.sql

# 2. Update .env (remove DATABASE_URL or use local connection)

# 3. Start with included database
docker compose -f docker-compose.registry.yml up -d

# 4. Wait for database to be ready
docker compose exec db pg_isready

# 5. Restore data
cat backup.sql | docker compose exec -T db psql -U checktick checktick
```

## Monitoring External Databases

### AWS RDS

```bash
# View metrics
aws rds describe-db-instances \
  --db-instance-identifier checktick-db \
  --query 'DBInstances[0].[DBInstanceStatus,AllocatedStorage,Endpoint]'

# Enable enhanced monitoring in AWS Console
```

### Azure Database

```bash
# Check metrics
az monitor metrics list \
  --resource /subscriptions/<sub>/resourceGroups/checktick-rg/providers/Microsoft.DBforPostgreSQL/servers/checktick-db \
  --metric cpu_percent \
  --interval PT1M
```

### Connection Testing

```bash
# Test database connection
docker compose exec web python manage.py dbshell

# Should connect successfully and show postgres prompt
```

## Cost Optimization

### Right-Sizing

Start small and scale up:

1. **Development:** db.t3.micro (AWS) or Basic (Azure)
2. **Small Production:** db.t3.small / General Purpose B1ms
3. **Medium Production:** db.t3.medium / GP_Gen5_2
4. **Large Production:** db.m5.large / GP_Gen5_4

### Storage

- Start with 20GB, expand as needed
- Use automated storage expansion features
- Monitor IOPS usage

### Backup Retention

- 7 days for most deployments
- 30 days for compliance requirements
- Point-in-time restore if needed

## Troubleshooting

### Connection Refused

1. Check firewall rules allow your server's IP
2. Verify connection string is correct
3. Ensure database is publicly accessible (or use VPN/private network)
4. Check security group/firewall settings

### SSL Errors

```bash
# If SSL certificate verification fails, use require mode:
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# NOT verify-full (which requires matching hostname)
```

### Performance Issues

1. Check database metrics (CPU, memory, connections)
2. Enable slow query logging
3. Review and optimize indexes
4. Consider scaling up instance size

### Migration Failures

```bash
# View migration status
docker compose exec web python manage.py showmigrations

# Run specific migration
docker compose exec web python manage.py migrate app_name migration_number

# Check for errors
docker compose logs web | grep -i migrate
```

## Next Steps

- **[Backup & Restore](self-hosting-backup.md)** - Protect your data
- **[Production Setup](self-hosting-production.md)** - SSL and security
- **[Quick Start](self-hosting-quickstart.md)** - Get started
