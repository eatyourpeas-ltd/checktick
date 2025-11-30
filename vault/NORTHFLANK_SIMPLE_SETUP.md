# Simple Vault Setup for Northflank (No Kubernetes Access Needed)

Since Northflank doesn't expose direct Kubernetes API access, here's how to deploy Vault using Northflank's UI:

## Step 1: Upload TLS Certificates

1. Go to **Northflank Dashboard** → Your CheckTick Project
2. Click **Secrets** in the top navigation bar
3. Click **"Create Secret Group"**
4. Fill in:
   - **Name**: `vault-tls-certificates`
   - **Priority**: `0` (default)
   - **Scope**: Select **"Runtime"** (Vault needs certificates when running)
   - **Restrict secret group**: Leave **OFF** (unchecked) - makes it available to all services
5. Click **Create Secret Group**
6. Inside the new secret group, click **"Add Secret"**
7. Add the certificate:
   - **Type**: File
   - **Mount Path**: `/vault/tls/tls.crt`
   - **Content**: Copy and paste the entire contents of `vault/vault-cert.pem`
8. Click **"Add Secret"** again for the private key:
   - **Type**: File
   - **Mount Path**: `/vault/tls/tls.key`
   - **Content**: Copy and paste the entire contents of `vault/vault-key.pem`
9. Click **Save**

> **Note**: The certificates are currently in your local `vault/` directory on the `encryption-decryption` branch and are gitignored for security.

## Step 2: Create Volume for Vault Data

1. Go to **Addons** → **Create Addon**
2. Select **"Volume"**
3. Configure:
   - **Name**: `vault-data`
   - **Access Mode**: Single read/write
   - **Storage Type**: NVMe
   - **Size**: 10 GB (or 20 GB for production)
4. Click **Create**

> **Note**: This volume provides persistent storage. Without it, Vault data would be lost on pod restart.

## Step 3: Create Vault Service

**Recommended**: Start with single-node deployment. You can migrate to 3-node HA later once everything is working.

Since the YAML manifest requires Kubernetes-specific resources (StatefulSet, ConfigMap), we need to create the service manually:

### 3.1 Create Deployment Service

1. Go to **Services** → **Add Service**
2. Select **"Deployment"** (for Docker container from registry)
   - Note: "Combined" is for building from GitHub repos
3. Basic Settings:
   - **Name**: `vault`
   - **Image**: `hashicorp/vault:1.21.1`
   - **Registry**: Docker Hub (default)

### 3.2 Configure Deployment

**For Single-Node (Recommended to start):**

- **Deployment Type**: Standard Deployment
- **Replicas**: `1`

**For 3-Node HA (Advanced, can do later):**

- **Deployment Type**: StatefulSet (if available)
- **Replicas**: `3`

**Resources:**

- **CPU**: 0.2 vCPU (minimum available)
- **Memory**: 512 MB
- **Ephemeral Storage**: 2 GB (maximum available)
- **Note**: You'll need to add persistent volumes separately for actual data storage (see step 2.6)

**Ports:**

- Port 1: `8200` (HTTP/HTTPS - external)
- Port 2: `8201` (Cluster communication - internal)

### 3.3 Environment Variables

Add these environment variables:

```bash
VAULT_ADDR=http://127.0.0.1:8200
SKIP_SETCAP=true
```

**Note**: Use `http://` (not `https://`) because `tls_disable = true` - Northflank's load balancer handles TLS.

### 3.4 Configuration File (vault.hcl)

**For Single-Node Deployment:**

Create a **Config File** or **ConfigMap**:

**Path**: `/vault/config/vault.hcl`

**Content**:

```hcl
ui = true

storage "raft" {
  path = "/vault/data"
  node_id = "NODE_ID_PLACEHOLDER"

  autopilot {
    cleanup_dead_servers = true
    last_contact_threshold = "200ms"
    max_trailing_logs = 250
    min_quorum = 2
    server_stabilization_time = "10s"
  }
}

listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_disable = false
  tls_cert_file = "/vault/tls/tls.crt"
  tls_key_file = "/vault/tls/tls.key"
}

api_addr = "https://POD_IP:8200"
cluster_addr = "https://POD_IP:8201"

telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = false
}
```

### 3.5 Mount Secrets and Volumes

**Mount the TLS Secret Group:**

- Secret Group: `vault-tls-certificates`
- This will mount the files at the paths specified when creating the secrets:
  - `/vault/tls/tls.crt` (certificate)
  - `/vault/tls/tls.key` (private key)
- Make sure "Link Secret Group" or "Attach Secret Group" option is enabled

**Mount the Volume:**

- Volume: `vault-data` (the addon you created in Step 2)
- Mount Path: `/vault/file`
- This provides persistent storage for Vault's data

### 3.6 Command Override

**Command:**

```bash
vault server -config=<(printf 'ui = true\n\nstorage "file" {\n  path = "/vault/file"\n}\n\nlistener "tcp" {\n  address = "0.0.0.0:8200"\n  tls_disable = true\n  proxy_protocol_behavior = "use_always"\n  x_forwarded_for_authorized_addrs = "0.0.0.0/0"\n}\n\napi_addr = "https://p01--vault--xyf5mw4dvp5r.code.run"\ndisable_mlock = true\n')
```

**Important Notes:**

- `tls_disable = true` - Northflank's load balancer handles SSL termination
- `proxy_protocol_behavior = "use_always"` - Properly handle proxied connections
- No TLS certificates needed in Vault config (load balancer manages this)

### 3.7 Health Checks

**Readiness Probe:**

- Type: Command
- Command: `vault status -tls-skip-verify`
- Initial Delay: 5 seconds
- Period: 5 seconds

**Liveness Probe:**

- Type: HTTP
- Path: `/v1/sys/health?standbyok=true&sealedcode=204&uninitcode=204`
- Port: 8200
- Scheme: HTTPS
- Initial Delay: 60 seconds
- Period: 5 seconds

## Quick Reference: Single-Node Configuration Summary

If you followed Steps 1-3 above for single-node, here's a quick checklist:

1. **Service Type**: Deployment (Docker container from registry)
2. **Image**: `hashicorp/vault:1.21.1`
3. **Registry**: Docker Hub
4. **Replicas**: `1`
5. **Resources**: CPU 0.2, Memory 512 MB, Ephemeral Storage 2 GB
6. **Ports**: `8200` (external, HTTPS)
7. **Environment Variables**:

   ```bash
   VAULT_ADDR=http://127.0.0.1:8200
   SKIP_SETCAP=true
   ```

8. **Persistent Volume**: Add a 10 GB volume mounted at `/vault/file` (required for data persistence)
9. **TLS Secret**: Link the `vault-tls-certificates` secret group (files will be mounted at `/vault/tls/tls.crt` and `/vault/tls/tls.key`)
10. **TLS Secret**: ~~Link the `vault-tls-certificates` secret group~~ - **NOT NEEDED** (Northflank handles SSL)
11. **Command**:

   ```bash
   vault server -config=<(printf 'ui = true\n\nstorage "file" {\n  path = "/vault/file"\n}\n\nlistener "tcp" {\n  address = "0.0.0.0:8200"\n  tls_disable = true\n  proxy_protocol_behavior = "use_always"\n  x_forwarded_for_authorized_addrs = "0.0.0.0/0"\n}\n\napi_addr = "https://p01--vault--xyf5mw4dvp5r.code.run"\ndisable_mlock = true\n')
   ```

**Note**: TLS is disabled in Vault because Northflank's load balancer handles SSL termination.

## Step 4: Initialize Vault

Once the service is deployed and running:

### 4.1 Access Vault Pod

In Northflank Dashboard:
1. Go to **Services** → **vault**
2. Click **"Shell"** or **"Console"** button
3. This opens a terminal in the Vault container

### 4.2 Initialize Vault

In the shell:
```bash
export VAULT_ADDR=http://127.0.0.1:8200

# Initialize with 4 keys, 3 needed to unseal
vault operator init -key-shares=4 -key-threshold=3
```

**Note**: Use `http://` (not `https://`) because Vault's listener has `tls_disable = true` - the load balancer handles TLS externally.

**CRITICAL**: Save all 4 unseal keys and the root token immediately!

### 4.3 Unseal Vault

Still in the shell (with `VAULT_ADDR=http://127.0.0.1:8200` set):

```bash
# Unseal with 3 of the 4 keys
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Verify unsealed
vault status
# Should show "Sealed: false"
```

If you have 3 replicas, repeat unseal for vault-1 and vault-2 pods.

## Step 5: Configure Vault

### 5.1 Set Environment Variables Locally

On your local machine:

```bash
# Get the Vault service URL from Northflank (should be something like)
export VAULT_ADDR=https://vault-yourproject.northflank.app:8200
export VAULT_TOKEN=<your-root-token-from-init>
export VAULT_SKIP_VERIFY=true  # For self-signed cert
```

### 5.2 Run Setup Script

```bash
cd vault
python setup_vault.py
```

This will:

- Enable KV secrets engine
- Create policies
- Set up AppRole authentication
- Generate platform master key with split-knowledge
- Output credentials for your `.env` file

### 5.3 Save Credentials

Copy the output from setup_vault.py to your CheckTick `.env` file:

```bash
VAULT_ADDR=https://vault-yourproject.northflank.app:8200
VAULT_ROLE_ID=<from-setup-output>
VAULT_SECRET_ID=<from-setup-output>
PLATFORM_CUSTODIAN_COMPONENT=<from-setup-output>
```

### 5.4 Revoke Root Token

For security:

```bash
vault token revoke $VAULT_TOKEN
```

## Step 6: Test from CheckTick

```bash
python manage.py test_vault_connection
```

Should show:

```
✓ Vault Connection Test Complete
✓ Successfully authenticated with AppRole
✓ Platform master key reconstructed successfully
```

## Connecting CheckTick to Vault

In your CheckTick deployment service environment variables, add:

```
VAULT_ADDR=https://vault:8200  # Internal service name
VAULT_ROLE_ID=<from-setup-output>
VAULT_SECRET_ID=<from-setup-output>
PLATFORM_CUSTODIAN_COMPONENT=<from-setup-output>
```

**Note**: Use internal service name `vault` if both services are in the same Northflank project. Northflank provides automatic service discovery.

## Troubleshooting

### Can't Access Vault Shell

If Northflank doesn't show a Shell button:

- Check the pod is running (Status = Running)
- Try restarting the service
- Check logs for startup errors

### Vault Won't Start

Common issues:

- TLS secret not mounted correctly
- Config file syntax error
- Insufficient resources (increase CPU/memory)

Check logs in Northflank Dashboard → Services → vault → Logs

### Can't Connect from CheckTick

1. Check Vault is unsealed: Access shell and run `vault status`
2. Verify internal DNS: `vault` should resolve to Vault service
3. Check network policies aren't blocking traffic
4. Try using HTTPS external URL first to test, then switch to internal

### Lost Unseal Keys

⚠️ **Without unseal keys, you cannot access Vault after restart!**

Recovery:

1. If you have 3+ of 4 keys: Unseal manually
2. If you lost all keys: You must re-initialize (loses all data)
3. Prevention: Store keys in password manager + physical safe + encrypted backup

## Security Checklist

Before production:

- [ ] TLS certificates created and uploaded
- [ ] Vault initialized (keys saved securely)
- [ ] All 3 replicas unsealed (if using HA)
- [ ] Setup script run (credentials saved)
- [ ] Root token revoked
- [ ] AppRole credentials in CheckTick .env
- [ ] Platform custodian component backed up (3+ locations)
- [ ] Unseal keys stored separately (4 different locations)
- [ ] Test connection from CheckTick successful
- [ ] Logs show no errors

## Recommendations

### For Development (Now)

- Single-node Vault (simpler, easier to manage)
- 1 replica, file storage backend
- Can always migrate to HA later

### For Production (Later)

- 3-node HA cluster (StatefulSet with Raft)
- Auto-unseal with cloud KMS (optional)
- Monitoring and alerting
- Documented unseal procedures
- Disaster recovery plan

## Next Steps After Vault Is Running

1. **Test connection**: `python manage.py test_vault_connection`
2. **Implement Phase 3**: Django integration for user recovery UI
3. **Update Survey model**: Add vault_recovery_path field
4. **Create recovery views**: Admin panel for identity verification
5. **Test recovery flow**: With test users
6. **Document procedures**: For admin team
7. **Go live**: Start escrowing user keys 🚀

## Questions?

See also:

- `vault/README.md` - Vault architecture and concepts
- `vault/NORTHFLANK_DEPLOYMENT.md` - Full Kubernetes deployment (advanced)
- `docs/vault-integration.md` - Integration guide
- `docs/INDIVIDUAL_USER_RECOVERY.md` - Ethical recovery explanation
