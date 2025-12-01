---
title: Vault Integration
category: api
priority: 5
---

# HashiCorp Vault Integration

CheckTick uses HashiCorp Vault for secure encryption key management and ethical data recovery. This guide covers deployment, configuration, and developer integration.

## Overview

Vault provides:
- **Key Escrow**: Secure storage for user encryption keys (enables recovery when users forget credentials)
- **Split-Knowledge Security**: Platform master key split between Vault and offline custodian
- **Audit Logging**: Immutable audit trail for compliance
- **AppRole Authentication**: Secure application access

### Why Vault?

Users are **custodians** of patient data, not owners. It's unethical to allow permanent data loss when users forget their password AND recovery phrase. Vault enables platform-assisted recovery while maintaining security through:

1. Dual-approval workflow (two admins required)
2. Mandatory time delays (users can cancel suspicious requests)
3. Identity verification requirements
4. Complete audit trail

## Quick Start (Docker Hub)

The simplest deployment uses the official Vault image from Docker Hub:

```bash
# Pull and run Vault
docker run -d --name vault \
  -p 8200:8200 \
  -e VAULT_ADDR=http://127.0.0.1:8200 \
  -v vault-data:/vault/file \
  hashicorp/vault:1.21.1 \
  vault server -dev

# Initialize (production mode)
docker exec -it vault vault operator init -key-shares=4 -key-threshold=3
```

For production, see [Deployment Options](#deployment-options) below.

---

## Architecture

```
Platform Master Key (split-knowledge: Vault + Custodian)
├─ Organization Keys (derived from platform key + org owner passphrase)
│  ├─ Team Keys (derived from org key)
│  │  └─ Survey KEKs (encrypted with team key)
│  └─ Direct Survey KEKs (for org-level surveys)
└─ Individual User Keys (ALL stored in Vault for recovery)
   ├─ Username/Password Users → Survey KEK encrypted in Vault
   ├─ SSO (OIDC) Users → Survey KEK encrypted with identity key
   └─ Recovery Phrase → Always available as fallback
```

### Split-Knowledge Security

The platform master key uses a **split-knowledge** design:

```
Platform Master Key = Vault Component ⊕ Custodian Component
```

- **Vault Component**: Stored in HashiCorp Vault (accessible to CheckTick)
- **Custodian Component**: Stored offline by platform administrators
- **Neither component alone** can decrypt data
- **Both required** to reconstruct the full platform key

### Key Hierarchy

| Level | Key Size | Storage | Purpose |
|-------|----------|---------|---------|
| Platform Master | 64 bytes | Split (Vault + Offline) | Root of all derivation |
| Organization | 32 bytes | Derived on-demand | Org-level encryption |
| Team | 32 bytes | Derived on-demand | Team-level encryption |
| Survey KEK | 32 bytes | Vault (encrypted) | Encrypts survey data |
| User Recovery | 32 bytes | Vault (escrowed) | Emergency recovery |

### Vault Paths

```
secret/platform/master-key          # Vault component of platform key
secret/organizations/{id}/master-key  # Org key metadata
secret/teams/{id}/team-key          # Team key metadata
secret/surveys/{id}/kek             # Org/team survey KEKs
secret/users/{id}/surveys/{id}/recovery-kek  # Individual user recovery keys
```

---

## Deployment Options

### Option 1: Northflank (Recommended for Production)

Northflank provides managed container hosting with persistent storage.

#### Step 1: Create Volume

1. Navigate to your project → **Add new** → **Addon** → **Volume**
2. Configure:
   - Name: `vault-data`
   - Size: 10GB
   - Type: NVMe

#### Step 2: Create Service

1. **Add new** → **Service** → **External Image**
2. Configure:
   - Service name: `vault`
   - Image: `hashicorp/vault:1.21.1`
   - Port: `8200` (HTTP, Public)

#### Step 3: Mount Volume

- Volume: `vault-data`
- Mount path: `/vault/file`

#### Step 4: Command Override

```bash
/bin/sh -c 'printf "ui = true\nlistener \"tcp\" {\n  address = \"0.0.0.0:8200\"\n  tls_disable = true\n}\nstorage \"file\" {\n  path = \"/vault/file\"\n}\napi_addr = \"http://127.0.0.1:8200\"\n" > /vault/config/vault.hcl && vault server -config=/vault/config/vault.hcl'
```

> **Note**: `tls_disable = true` is correct—Northflank's load balancer handles TLS termination.

#### Step 5: Environment Variables

| Variable | Value |
|----------|-------|
| `VAULT_ADDR` | `http://127.0.0.1:8200` |
| `SKIP_CHOWN` | `true` |
| `SKIP_SETCAP` | `true` |

#### Step 6: Deploy and Initialize

See [Initialization](#initialization) below.

### Option 2: Docker Compose (Development)

Create `docker-compose.vault.yml`:

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
    cap_add:
      - IPC_LOCK
    volumes:
      - vault-data:/vault/file
    command: >
      vault server -dev-root-token-id="dev-token"
    restart: unless-stopped

volumes:
  vault-data:
```

For production Docker Compose, use file storage instead of dev mode:

```yaml
command: >
  sh -c "vault server -config=/vault/config/vault.hcl"
```

### Option 3: Kubernetes (Enterprise)

For large-scale deployments, use the official Helm chart:

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault \
  --set server.ha.enabled=true \
  --set server.ha.replicas=3
```

---

## Initialization

After deployment, initialize Vault (one-time only):

### Step 1: Connect to Vault

```bash
# Docker
docker exec -it vault /bin/sh

# Northflank: Use Shell button in dashboard
# Kubernetes: kubectl exec -it vault-0 -- /bin/sh
```

### Step 2: Initialize

```bash
export VAULT_ADDR=http://127.0.0.1:8200

# Initialize with Shamir's Secret Sharing
vault operator init -key-shares=4 -key-threshold=3
```

**Output (save immediately!):**
```
Unseal Key 1: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Unseal Key 2: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Unseal Key 3: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Unseal Key 4: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Initial Root Token: hvs.xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 3: Store Keys Securely

| Key | Storage Location |
|-----|------------------|
| Unseal Key 1 | Admin 1's password manager |
| Unseal Key 2 | Admin 2's password manager |
| Unseal Key 3 | Physical safe (printed, sealed) |
| Unseal Key 4 | Encrypted cloud backup |
| Root Token | Both admins' password managers (temporary) |

### Step 4: Unseal

Vault starts sealed and requires 3 of 4 keys to unseal:

```bash
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Verify
vault status
# Should show: Sealed: false
```

### Step 5: Run Setup Script

From your CheckTick environment:

```bash
# Set environment
export VAULT_ADDR=https://your-vault-url:8200
export VAULT_TOKEN=<root-token>

# Run setup
cd vault/
python setup_vault.py
```

This creates:
- KV v2 secrets engine
- CheckTick policies
- AppRole authentication
- Platform master key (split-knowledge)

**Save the output** to your `.env` file:

```bash
VAULT_ADDR=https://your-vault-url:8200
VAULT_ROLE_ID=<from-setup-output>
VAULT_SECRET_ID=<from-setup-output>
PLATFORM_CUSTODIAN_COMPONENT=<from-setup-output>
```

### Step 6: Revoke Root Token

```bash
vault token revoke <root-token>
```

### Step 7: Test Connection

```bash
python manage.py test_vault_connection
```

---

## Developer Integration

### Get Vault Client

```python
from checktick_app.surveys.vault_client import get_vault_client

vault = get_vault_client()
```

### Escrow Survey KEK (During Survey Creation)

```python
def create_survey_with_escrow(survey, user, user_password):
    """Create survey with triple-path encryption."""
    vault = get_vault_client()

    # Generate survey KEK
    survey_kek = os.urandom(32)

    # Path 1: Password-encrypted (database)
    survey.encrypted_kek = encrypt_with_password(survey_kek, user_password)

    # Path 2: Recovery phrase (database)
    survey.recovery_encrypted_kek = encrypt_with_recovery(survey_kek, user.recovery_phrase)

    # Path 3: Platform escrow (Vault)
    vault_path = vault.escrow_user_survey_kek(
        user_id=user.id,
        survey_id=survey.id,
        survey_kek=survey_kek
    )
    survey.vault_recovery_path = vault_path
    survey.save()

    return survey_kek
```

### Recover Escrowed KEK

```python
def execute_platform_recovery(recovery_request, admin_user):
    """Execute recovery after dual authorization + time delay."""

    # Get custodian component (from secure offline storage)
    custodian_component = bytes.fromhex(settings.PLATFORM_CUSTODIAN_COMPONENT)

    vault = get_vault_client()

    # Recover KEK
    survey_kek = vault.recover_user_survey_kek(
        user_id=recovery_request.user_id,
        survey_id=recovery_request.survey_id,
        admin_id=admin_user.id,
        verification_notes="Recovery request approved",
        platform_custodian_component=custodian_component
    )

    return survey_kek
```

### Organization/Team Key Derivation

```python
# Derive organization key
org_key = vault.derive_organization_key(
    org_id=org.id,
    org_owner_passphrase=passphrase,
    platform_custodian_component=custodian_component
)

# Derive team key from org key
team_key = vault.derive_team_key(
    team_id=team.id,
    org_key=org_key
)

# Encrypt survey KEK with hierarchy key
vault.encrypt_survey_kek(
    survey_kek=survey_kek,
    hierarchy_key=team_key,
    vault_path=f'surveys/{survey.id}/kek'
)
```

### VaultClient Methods

| Method | Purpose |
|--------|---------|
| `get_platform_master_key()` | Reconstruct platform key from split components |
| `derive_organization_key()` | Derive org key from platform key + passphrase |
| `derive_team_key()` | Derive team key from org key |
| `escrow_user_survey_kek()` | Store user's KEK for recovery |
| `recover_user_survey_kek()` | Recover KEK (requires custodian component) |
| `encrypt_survey_kek()` | Encrypt KEK with hierarchy key |
| `decrypt_survey_kek()` | Decrypt KEK from Vault |
| `health_check()` | Check Vault connectivity and status |

---

## Recovery Workflows

### Individual User Recovery

When a user forgets both password AND recovery phrase:

1. **User submits recovery request** via UI
2. **Admin reviews** and verifies identity (email, video call, etc.)
3. **Primary admin approves** the request
4. **Secondary admin approves** (dual authorization)
5. **Time delay starts** (e.g., 24 hours)
6. **User notified** and can cancel if suspicious
7. **After delay**, admin executes recovery with new password
8. **KEK re-encrypted** with user's new password
9. **Audit trail** recorded for compliance

### Organization Member Recovery

If org member loses access:

1. Organization owner provides passphrase
2. System derives org key
3. System decrypts survey KEK
4. User sets new password
5. KEK re-encrypted with new password

### Catastrophic Recovery

If organization owner forgets passphrase:

1. Platform admins retrieve custodian component
2. Business verification (legal documentation)
3. Platform admins derive org key via emergency process
4. Owner sets new passphrase
5. Keys re-derived

---

## Monitoring

### Health Check Endpoint

```python
from django.http import JsonResponse
from checktick_app.surveys.vault_client import get_vault_client

def vault_health(request):
    vault = get_vault_client()
    health = vault.health_check()
    status = 200 if not health.get('sealed') and health.get('initialized') else 503
    return JsonResponse(health, status=status)
```

### CLI Health Check

```bash
curl -s https://your-vault-url/v1/sys/health | jq
```

### Key Metrics

- `vault_core_unsealed` - Should be `1` (unsealed)
- `vault_token_count` - Active tokens
- `vault_audit_log_request_total` - Audit events

### Alerts

Configure alerts for:
- Vault sealed (`vault_core_unsealed == 0`)
- High request latency (> 1s at p99)
- Authentication failures
- Recovery requests > 5/day (suspicious activity)

---

## Backup & Recovery

### Automated Backup

```bash
#!/bin/bash
# vault-backup.sh

BACKUP_DIR=/backups/vault
DATE=$(date +%Y%m%d_%H%M%S)

# Raft snapshot (for HA deployments)
vault operator raft snapshot save ${BACKUP_DIR}/vault-${DATE}.snap

# Or file storage backup
tar -czf ${BACKUP_DIR}/vault-${DATE}.tar.gz /vault/file

# Upload to cloud storage
aws s3 cp ${BACKUP_DIR}/vault-${DATE}.* s3://your-bucket/vault-backups/

# Cleanup old backups (keep 30 days)
find ${BACKUP_DIR} -mtime +30 -delete
```

### Restore Procedure

```bash
# Stop Vault
docker stop vault

# Restore data
tar -xzf vault-backup.tar.gz -C /

# Start Vault
docker start vault

# Unseal (required after restart)
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
```

---

## Security Best Practices

### ✅ Do

- Store `PLATFORM_CUSTODIAN_COMPONENT` in multiple offline locations
- Rotate `VAULT_SECRET_ID` every 90 days
- Use strong org owner passphrases (20+ characters)
- Audit Vault access logs regularly
- Keep unseal keys in separate physical locations
- Enable TLS in production (or use TLS-terminating load balancer)
- Revoke root token after initial setup

### ❌ Don't

- Commit `.env` file to version control
- Share custodian component via email/chat
- Use weak passphrases
- Log decrypted keys
- Store all unseal keys in one location
- Use root token for application access

---

## Troubleshooting

### Connection Refused

1. Check Vault is running: `docker ps | grep vault`
2. Check port: `curl -v http://localhost:8200/v1/sys/health`
3. For Northflank: Use HTTPS external URL

### Vault Sealed

Vault seals on restart (security feature). Unseal with 3 of 4 keys:

```bash
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
```

### Authentication Failed

1. Verify `VAULT_ROLE_ID` and `VAULT_SECRET_ID`
2. Check AppRole exists: `vault read auth/approle/role/checktick-app`
3. Generate new secret_id if expired:
   ```bash
   vault write -f auth/approle/role/checktick-app/secret-id
   ```

### Key Not Found

Run setup script:
```bash
python vault/setup_vault.py
```

---

## Production Checklist

Before going live:

- [ ] Vault deployed and unsealed
- [ ] TLS enabled (or behind TLS load balancer)
- [ ] Root token revoked
- [ ] Unseal keys stored in 4 separate locations
- [ ] Custodian component stored offline (3+ locations)
- [ ] AppRole credentials in `.env`
- [ ] Audit logging enabled
- [ ] Backup procedure tested
- [ ] Monitoring and alerts configured
- [ ] Network access restricted
- [ ] `test_vault_connection` passes

---

## Performance

### Expected Latency

| Operation | Latency |
|-----------|---------|
| Platform key reconstruction | ~5ms |
| Organization key derivation | ~200ms (PBKDF2 200k iterations) |
| Team key derivation | ~200ms |
| Survey KEK encrypt/decrypt | ~10ms |
| **Total unlock (team survey)** | **~420ms** |

### Caching

The `VaultClient` caches authenticated connections. Token TTL: 1 hour (configurable).

---

## Related Documentation

- [Encryption Overview](/docs/encryption/) - How CheckTick encrypts data
- [Self-Hosting Configuration](/docs/self-hosting-configuration/) - General self-hosting
- [Data Governance](/docs/data-governance/) - Compliance and retention

## Getting Help

- **Integration questions**: support@checktick.uk
- **Security reviews**: security@checktick.uk
- **HashiCorp Vault docs**: https://developer.hashicorp.com/vault/docs
