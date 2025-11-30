---
title: Vault Setup
category: self-hosting
priority: 5
---

# HashiCorp Vault Setup for Self-Hosters

This guide covers deploying HashiCorp Vault for CheckTick's encryption key management system.

## Overview

HashiCorp Vault provides:
- Secure storage for encryption key backups (key escrow)
- Audit logging for compliance
- AppRole authentication for application access
- Split-knowledge key management

## Deployment Options

| Option | Complexity | Best For |
|--------|------------|----------|
| **Northflank** | Low | Production, managed infrastructure |
| **Docker Compose** | Medium | Development, small deployments |
| **Kubernetes** | High | Large-scale, enterprise |

## Northflank Deployment

Northflank provides managed container hosting with persistent storage, ideal for Vault.

### Prerequisites

- Northflank account
- Project created
- Basic familiarity with Northflank UI

### Step 1: Create Volume Addon

1. Navigate to your project
2. Click **Add new** → **Addon**
3. Select **Volume**
4. Configure:
   - Name: `vault-data`
   - Size: 10GB (minimum, increase for large deployments)
   - Type: NVMe (recommended for performance)
5. Click **Create**

### Step 2: Create Vault Service

1. Click **Add new** → **Service**
2. Select **External Image**
3. Configure:
   - Service name: `vault`
   - Image: `hashicorp/vault:1.21.1`
   - Image pull policy: Always

### Step 3: Configure Ports

1. In service settings, go to **Ports**
2. Add port:
   - Port name: `vault`
   - Internal port: `8200`
   - Protocol: HTTP
   - Public: Yes (creates external URL)

### Step 4: Mount Volume

1. Go to **Volumes** tab
2. Click **Add Volume Mount**
3. Select your `vault-data` volume
4. Mount path: `/vault/file`

### Step 5: Configure Command Override

1. Go to **CMD override** section
2. Enable command override
3. Enter this command:

```bash
/bin/sh -c 'printf "ui = true\nlistener \"tcp\" {\n  address = \"0.0.0.0:8200\"\n  tls_disable = true\n}\nstorage \"file\" {\n  path = \"/vault/file\"\n}\napi_addr = \"http://127.0.0.1:8200\"\ncluster_addr = \"http://127.0.0.1:8201\"\n" > /vault/config/vault.hcl && vault server -config=/vault/config/vault.hcl'
```

**Important**: `tls_disable = true` is correct here because Northflank's load balancer handles TLS termination. External connections use HTTPS via the load balancer.

### Step 6: Set Environment Variables

1. Go to **Environment** tab
2. Add these variables:

| Variable | Value |
|----------|-------|
| `VAULT_ADDR` | `http://127.0.0.1:8200` |
| `VAULT_API_ADDR` | `http://127.0.0.1:8200` |
| `SKIP_CHOWN` | `true` |
| `SKIP_SETCAP` | `true` |

### Step 7: Deploy

1. Click **Create Service**
2. Wait for deployment to complete
3. Note your external URL (e.g., `https://p01--vault--xxxxx.code.run`)

### Step 8: Initialize Vault

Connect to your Vault container and initialize:

```bash
# In Northflank terminal or via SSH
export VAULT_ADDR=http://127.0.0.1:8200

# Initialize with 4 key shares, 3 required to unseal
vault operator init -key-shares=4 -key-threshold=3
```

**Save the output securely!** You'll see:
- 4 unseal keys (need 3 to unseal)
- 1 root token (for initial setup only)

### Step 9: Unseal Vault

```bash
# Enter 3 of 4 unseal keys
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Verify unsealed
vault status
# Should show: Sealed: false
```

### Step 10: Run Setup Script

From your CheckTick development environment:

```bash
# Set environment variables
export VAULT_ADDR=https://p01--vault--xxxxx.code.run  # Your external URL
export VAULT_TOKEN=<root-token>

# Run setup script
cd vault/
python setup_vault.py

# Save the output credentials to your .env file
```

### Step 11: Revoke Root Token

After setup is complete:

```bash
vault token revoke <root-token>
```

### Step 12: Configure CheckTick

Add to your `.env` file:

```bash
VAULT_ADDR=https://p01--vault--xxxxx.code.run
VAULT_ROLE_ID=<from setup output>
VAULT_SECRET_ID=<from setup output>
PLATFORM_CUSTODIAN_COMPONENT=<from setup output - store securely offline!>
```

## Docker Compose Deployment

For development or small self-hosted deployments.

### docker-compose.vault.yml

```yaml
version: '3.8'

services:
  vault:
    image: hashicorp/vault:1.21.1
    container_name: vault
    ports:
      - "8200:8200"
    environment:
      VAULT_ADDR: http://127.0.0.1:8200
      VAULT_API_ADDR: http://127.0.0.1:8200
    cap_add:
      - IPC_LOCK
    volumes:
      - vault-data:/vault/file
      - ./vault/config:/vault/config
    command: vault server -config=/vault/config/vault.hcl
    restart: unless-stopped

volumes:
  vault-data:
```

### vault/config/vault.hcl

```hcl
ui = true

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true  # Enable TLS in production!
}

storage "file" {
  path = "/vault/file"
}

api_addr = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"
```

### Start Vault

```bash
docker compose -f docker-compose.vault.yml up -d

# Initialize
docker exec -it vault vault operator init -key-shares=4 -key-threshold=3

# Save keys securely, then unseal
docker exec -it vault vault operator unseal <key1>
docker exec -it vault vault operator unseal <key2>
docker exec -it vault vault operator unseal <key3>
```

## Production Hardening

### Enable TLS

For production without a load balancer:

```hcl
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file  = "/vault/certs/vault.key"
}
```

### Enable Audit Logging

```bash
# Login with root token (during setup only)
vault login <root-token>

# Enable file audit backend
vault audit enable file file_path=/vault/logs/audit.log

# Or enable syslog backend
vault audit enable syslog tag="vault" facility="AUTH"
```

### Configure Auto-Unseal (Enterprise)

For HashiCorp Vault Enterprise, configure auto-unseal with a cloud KMS:

```hcl
seal "awskms" {
  region     = "eu-west-2"
  kms_key_id = "alias/vault-unseal-key"
}
```

### High Availability (HA)

For production HA, use Consul or Raft storage backend:

```hcl
storage "raft" {
  path    = "/vault/raft"
  node_id = "vault-1"
}

cluster_addr = "https://vault-1.internal:8201"
```

## Elasticsearch SIEM Setup

For self-hosted audit logging and SIEM capabilities.

### Deploy Elasticsearch on Northflank

1. **Create Elasticsearch Service:**
   - Image: `docker.elastic.co/elasticsearch/elasticsearch:8.11.0`
   - Port: 9200 (internal)
   - Environment:
     - `discovery.type=single-node`
     - `xpack.security.enabled=false` (for dev, enable in prod)
     - `ES_JAVA_OPTS=-Xms512m -Xmx512m`

2. **Create Volume:**
   - Name: `elasticsearch-data`
   - Mount path: `/usr/share/elasticsearch/data`

3. **Create Kibana Service (optional):**
   - Image: `docker.elastic.co/kibana/kibana:8.11.0`
   - Port: 5601 (public for dashboard access)
   - Environment:
     - `ELASTICSEARCH_HOSTS=http://elasticsearch:9200`

### Configure Vault Audit to Elasticsearch

Option 1: **File audit + Filebeat**

```bash
# Enable file audit in Vault
vault audit enable file file_path=/vault/logs/audit.log

# Deploy Filebeat to ship logs to Elasticsearch
# Configure filebeat.yml to read /vault/logs/audit.log
```

Option 2: **Socket audit backend**

```bash
# Enable socket audit backend
vault audit enable socket address=elasticsearch:9200 socket_type=tcp
```

### Kibana Dashboard Setup

1. Access Kibana at your Kibana URL
2. Create index pattern: `vault-audit-*`
3. Import CheckTick dashboard (provided in `vault/kibana-dashboards/`)
4. Configure alerts for:
   - Recovery requests > 5/day
   - Failed authentication attempts
   - Policy violations

## Backup Procedures

### Automated Vault Backup

Create a backup script:

```bash
#!/bin/bash
# vault-backup.sh

BACKUP_DIR=/backups/vault
DATE=$(date +%Y%m%d_%H%M%S)
VAULT_DATA=/vault/file

# Stop writes temporarily (optional for consistency)
# vault write sys/seal

# Create backup
tar -czf ${BACKUP_DIR}/vault-backup-${DATE}.tar.gz ${VAULT_DATA}

# Upload to cloud storage
aws s3 cp ${BACKUP_DIR}/vault-backup-${DATE}.tar.gz s3://your-bucket/vault-backups/

# Clean old local backups (keep 7 days)
find ${BACKUP_DIR} -name "vault-backup-*.tar.gz" -mtime +7 -delete

# Unseal if sealed
# vault operator unseal <keys>
```

### Backup Schedule

```bash
# Add to crontab
0 2 * * * /path/to/vault-backup.sh >> /var/log/vault-backup.log 2>&1
```

### Restore Procedure

```bash
# Stop Vault
docker stop vault

# Clear existing data
rm -rf /vault/file/*

# Restore from backup
tar -xzf /backups/vault/vault-backup-YYYYMMDD_HHMMSS.tar.gz -C /

# Start Vault
docker start vault

# Unseal (required after restart)
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
```

## Monitoring

### Health Check Endpoint

```bash
# Check Vault health
curl -s https://your-vault-url/v1/sys/health | jq

# Healthy unsealed response:
{
  "initialized": true,
  "sealed": false,
  "standby": false,
  "performance_standby": false,
  "replication_performance_mode": "disabled",
  "replication_dr_mode": "disabled",
  "server_time_utc": 1701356400,
  "version": "1.21.1"
}
```

### Prometheus Metrics

Enable Prometheus metrics:

```hcl
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}
```

Access metrics at `/v1/sys/metrics?format=prometheus`

### Alert Rules

```yaml
groups:
  - name: vault
    rules:
      - alert: VaultSealed
        expr: vault_core_unsealed == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Vault is sealed"

      - alert: VaultHighRequestLatency
        expr: vault_core_handle_request{quantile="0.99"} > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Vault request latency is high"
```

## Troubleshooting

### Vault Won't Start

1. **Check logs:**
   ```bash
   docker logs vault
   ```

2. **Common issues:**
   - Permission denied on data directory
   - Port 8200 already in use
   - Invalid configuration file

3. **Fix permissions:**
   ```bash
   chown -R 100:1000 /vault/file
   ```

### Can't Unseal

1. **Verify you have correct keys:**
   - Need 3 of 4 keys (threshold)
   - Keys are case-sensitive

2. **Check Vault status:**
   ```bash
   vault status
   ```

3. **If keys are lost:** See [Business Continuity](/docs/business-continuity/) for recovery options

### Connection Refused

1. **Check Vault is running:**
   ```bash
   docker ps | grep vault
   ```

2. **Check network:**
   ```bash
   curl -v http://localhost:8200/v1/sys/health
   ```

3. **For Northflank:** Use HTTPS external URL, not HTTP

### AppRole Authentication Fails

1. **Verify credentials:**
   ```bash
   vault write auth/approle/login \
     role_id=$VAULT_ROLE_ID \
     secret_id=$VAULT_SECRET_ID
   ```

2. **Check role exists:**
   ```bash
   vault read auth/approle/role/checktick
   ```

3. **Re-run setup script** if credentials are missing

## Security Checklist

Before going to production:

- [ ] TLS enabled (or behind TLS-terminating load balancer)
- [ ] Root token revoked
- [ ] Audit logging enabled
- [ ] Unseal keys stored securely (multiple locations)
- [ ] Custodian component stored offline
- [ ] Backup procedure tested
- [ ] Monitoring configured
- [ ] Alerts configured
- [ ] Access policies reviewed
- [ ] Network access restricted (firewall rules)

## Related Documentation

- [Key Management for Administrators](/docs/key-management-for-administrators/) - Admin procedures
- [Business Continuity](/docs/business-continuity/) - Disaster recovery
- [Vault Integration](/docs/vault-integration/) - Developer API reference
- [Self-Hosting Configuration](/docs/self-hosting-configuration/) - General self-hosting

## Getting Help

**For Vault deployment issues:**
- Email: support@checktick.uk
- Include: Vault version, deployment method, error logs

**For HashiCorp Vault questions:**
- HashiCorp Learn: https://learn.hashicorp.com/vault
- Vault Documentation: https://developer.hashicorp.com/vault/docs
