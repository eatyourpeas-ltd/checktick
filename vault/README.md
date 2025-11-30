# HashiCorp Vault Setup for CheckTick

This directory contains configuration for deploying HashiCorp Vault on Northflank for secure encryption key management.

## Architecture

```
CheckTick Application
       ↓
  Vault Cluster (3 nodes, HA)
       ↓
  Persistent Storage (Northflank Volume)
```

## Initial Setup

### 1. Deploy to Northflank

Use the configuration in `northflank-deployment.yaml` to create the Vault service.

### 2. Initialize Vault (One-Time)

After deployment, initialize Vault with Shamir's Secret Sharing:

```bash
# Connect to Vault pod
kubectl exec -it vault-0 -- /bin/sh

# Initialize with 4 key shares, requiring 3 to unseal
vault operator init -key-shares=4 -key-threshold=3
```

This will output:
```
Unseal Key 1: <key1>
Unseal Key 2: <key2>
Unseal Key 3: <key3>
Unseal Key 4: <key4>
Initial Root Token: <root_token>
```

### 3. Secure the Unseal Keys

**Critical: Store these keys immediately and securely!**

- **Admin 1**: Unseal Key 1 (password manager + printed backup)
- **Admin 2**: Unseal Key 2 (password manager + printed backup)
- **Physical Safe**: Unseal Key 3 (printed, sealed envelope)
- **Encrypted Backup**: Unseal Key 4 (password-protected file in secure cloud storage)

**Root Token**: Store in both admins' password managers

### 4. Unseal Vault

After Vault restarts, it needs to be unsealed (requires any 3 of 4 keys):

```bash
# Admin 1 unseals with their key
vault operator unseal <key1>

# Admin 2 unseals with their key
vault operator unseal <key2>

# Use safe or backup for third key
vault operator unseal <key3>
```

### 5. Configure Vault

Run the setup script:

```bash
cd vault/
python setup_vault.py
```

This creates:
- Secret engines
- Policies for CheckTick
- AppRole authentication
- Audit logging

## Environment Variables

Add to CheckTick `.env`:

```bash
# HashiCorp Vault Configuration
VAULT_ADDR=https://vault.checktick.internal:8200
VAULT_NAMESPACE=checktick
VAULT_ROLE_ID=<from_setup_script>
VAULT_SECRET_ID=<from_setup_script>

# Platform Custodian Component (CRITICAL - store securely!)
PLATFORM_CUSTODIAN_COMPONENT=<generated_during_platform_init>
```

## Maintenance

### Auto-Unseal Setup (Optional - Future)

Once established, configure AWS KMS or Azure Key Vault for auto-unseal:

```hcl
seal "awskms" {
  region     = "eu-west-2"
  kms_key_id = "arn:aws:kms:..."
}
```

### Backup Procedure

Vault data is stored in Northflank persistent volumes. Northflank handles:

- Automatic backups
- Point-in-time recovery
- Cross-region replication (if configured)

Manual backup:
```bash
vault operator raft snapshot save backup.snap
```

### Monitoring

Key metrics to monitor:

- Vault sealed status (should be unsealed)
- Token TTL and renewal
- Secret access audit logs
- Storage capacity

## Security Notes

1. **Never commit unseal keys or root token to git**
2. **Rotate root token regularly** (every 90 days recommended)
3. **Use AppRole for CheckTick** (not root token)
4. **Enable audit logging** to track all secret access
5. **Review Vault logs weekly** for suspicious activity

## Troubleshooting

### Vault is sealed after restart

This is normal. Unseal using procedure in step 4 above.

### Cannot connect to Vault

Check:
1. Vault service is running: `kubectl get pods | grep vault`
2. Network policy allows CheckTick → Vault traffic
3. TLS certificates are valid
4. VAULT_ADDR in environment is correct

### Lost unseal key

If you lose 2+ unseal keys, data is **permanently unrecoverable**. This is by design.

If you lose 1 unseal key, you still have 3 others - recover using the remaining keys.

## Production Checklist

Before going live:

- [ ] All 4 unseal keys stored in secure locations
- [ ] Root token stored in 2+ password managers
- [ ] Platform custodian component backed up offline
- [ ] Auto-unseal configured (optional but recommended)
- [ ] Monitoring and alerting set up
- [ ] Backup/restore procedure tested
- [ ] Vault access audit logs enabled
- [ ] Disaster recovery plan documented
