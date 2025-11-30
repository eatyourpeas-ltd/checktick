# Deploying HashiCorp Vault on Northflank

This guide explains how to deploy the HashiCorp Vault cluster to Northflank.

## Deployment Options

Northflank supports two approaches:

### Option 1: Direct Kubernetes Manifest (Recommended)

Northflank has native Kubernetes support. You can deploy the YAML directly:

1. **Navigate to Your Project**
   - Go to your CheckTick project in Northflank dashboard
   - Click "Add" → "Add-on" or "Service"

2. **Create Vault Service**
   - Choose "Combined Service"
   - Select "Deploy from manifest"
   - Upload `vault/northflank-deployment.yaml`

3. **Important**: Before deploying, you **must** create the TLS secret first (see below)

### Option 2: Manual Service Creation (More Control)

Create the Vault service manually through Northflank UI:

1. **Create New Combined Service**
   - Name: `vault`
   - Image: `hashicorp/vault:1.15`
   - Port: `8200` (HTTP), `8201` (Cluster)

2. **Configure Replicas**
   - Set replicas to `3` for HA
   - Enable "StatefulSet" mode
   - Add anti-affinity rules (different hosts)

3. **Add Persistent Storage**
   - Mount path: `/vault/data`
   - Size: `10GB` per replica
   - Type: Block storage (SSD recommended)

4. **Configure Environment Variables**
   - `VAULT_ADDR=https://127.0.0.1:8200`
   - `SKIP_SETCAP=true`

5. **Add ConfigMap** (vault.hcl)
   - Create from `vault/northflank-deployment.yaml` ConfigMap section
   - Mount at `/vault/config`

6. **Add TLS Secret**
   - Generate certificates first (see below)
   - Mount at `/vault/tls`

## Prerequisites: Generate TLS Certificates

**Before deploying**, you must generate TLS certificates:

### Step 1: Generate Certificates Locally

```bash
cd vault
chmod +x generate-tls.sh
./generate-tls.sh
```

This creates:
- `vault-cert.pem` (public certificate)
- `vault-key.pem` (private key)

### Step 2: Create Northflank Secret

**Via Northflank Dashboard:**

1. Go to your project → Secrets
2. Click "Add Secret"
3. Name: `vault-tls`
4. Type: "File Secret" or "TLS Certificate"
5. Upload both files:
   - `tls.crt` → Upload `vault-cert.pem`
   - `tls.key` → Upload `vault-key.pem`

**Via kubectl (if you have Northflank kubeconfig):**

```bash
# Get Northflank kubeconfig
northflank kubeconfig get --project checktick > ~/.kube/northflank-config

# Set context
export KUBECONFIG=~/.kube/northflank-config

# Create TLS secret
kubectl create secret tls vault-tls \
  --cert=vault-cert.pem \
  --key=vault-key.pem \
  --namespace=checktick
```

## Deployment Steps (Recommended Path)

### 1. Prepare TLS Certificates

```bash
cd vault
./generate-tls.sh
```

### 2. Create TLS Secret in Northflank

Upload the generated certificates to Northflank Secrets (see above).

### 3. Deploy via Northflank CLI (Easiest)

If you have Northflank CLI installed:

```bash
# Install Northflank CLI
npm install -g @northflank/cli

# Login
northflank login

# Deploy manifest
northflank apply -f vault/northflank-deployment.yaml --project checktick
```

### 4. Deploy via Northflank Dashboard

1. Go to Northflank Dashboard → Your Project
2. Click "Add" → "Combined Service"
3. Choose "Deploy from manifest"
4. Upload `vault/northflank-deployment.yaml`
5. Review and click "Deploy"

### 5. Verify Deployment

```bash
# Check pods are running
northflank kubectl get pods -l app=vault

# Expected output:
# vault-0   0/1  Running  0  30s
# vault-1   0/1  Running  0  25s
# vault-2   0/1  Running  0  20s

# Check logs
northflank kubectl logs vault-0
```

You should see:
```
==> Vault server configuration:
             Api Address: https://10.x.x.x:8200
                     Cgo: disabled
         Cluster Address: https://10.x.x.x:8201
   Environment Variables: ...
              Go Version: go1.21.3
              Listener 1: tcp (addr: "0.0.0.0:8200", cluster address: "0.0.0.0:8201", ...)
               Log Level: info
                   Mlock: supported: true, enabled: false
           Recovery Mode: false
                 Storage: raft (HA available)
                 Version: Vault v1.15.0
```

## Post-Deployment: Initialize Vault

Once the pods are running, you need to **initialize** Vault (one-time only):

### 1. Connect to vault-0

```bash
# Via Northflank CLI
northflank kubectl exec -it vault-0 -- /bin/sh

# Or via Northflank Dashboard (Shell button)
```

### 2. Initialize Vault

```bash
vault operator init -key-shares=4 -key-threshold=3
```

**CRITICAL**: Save the output immediately:
```
Unseal Key 1: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Unseal Key 2: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Unseal Key 3: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Unseal Key 4: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Initial Root Token: hvs.xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Store these in:
- Password manager (Admin 1)
- Password manager (Admin 2)
- Physical safe (printed, sealed)
- Encrypted backup (separate location)

### 3. Unseal All Vault Pods

Vault starts **sealed** and cannot decrypt data. You must unseal with 3 of 4 keys:

```bash
# Unseal vault-0
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Exit and repeat for vault-1
exit
northflank kubectl exec -it vault-1 -- /bin/sh
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
exit

# Repeat for vault-2
northflank kubectl exec -it vault-2 -- /bin/sh
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>
exit
```

### 4. Verify Unsealed

```bash
northflank kubectl exec -it vault-0 -- vault status
```

Expected output:
```
Key             Value
---             -----
Seal Type       shamir
Initialized     true
Sealed          false    # <-- Must be false
Total Shares    4
Threshold       3
```

## Run Setup Script

Now that Vault is unsealed, configure it for CheckTick:

### 1. Set Environment Variables

```bash
# Get vault-0 pod IP
VAULT_POD_IP=$(northflank kubectl get pod vault-0 -o jsonpath='{.status.podIP}')

export VAULT_ADDR="https://${VAULT_POD_IP}:8200"
export VAULT_TOKEN="<your-root-token-from-init>"
export VAULT_SKIP_VERIFY=true  # For self-signed cert
```

### 2. Run Setup Script

```bash
cd vault
python setup_vault.py
```

This will:
- Enable KV v2 secrets engine
- Create CheckTick policies
- Enable AppRole authentication
- Generate platform master key (split-knowledge)
- Create sample organization structure

### 3. Save Output

The script outputs:

```
=================================================
Vault Setup Complete!
=================================================

IMPORTANT: Add these to your .env file:

VAULT_ADDR=https://vault.checktick.internal:8200
VAULT_ROLE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VAULT_SECRET_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

PLATFORM_CUSTODIAN_COMPONENT=<64-byte-hex-string>

WARNING: Store PLATFORM_CUSTODIAN_COMPONENT in multiple secure locations!
This component is required for organization-level key recovery.
```

**Copy these values to your CheckTick `.env` file.**

### 4. Revoke Root Token

After setup, revoke the root token for security:

```bash
vault token revoke <root-token>
```

## Northflank-Specific Configuration

### Service Discovery

Northflank provides automatic service discovery. Update your CheckTick deployment:

**Environment Variable:**
```bash
VAULT_ADDR=https://vault.checktick.svc.cluster.local:8200
# Or if in same namespace:
VAULT_ADDR=https://vault:8200
```

### Network Policies

The YAML includes a NetworkPolicy that allows:
- ✅ CheckTick web pods → Vault (port 8200)
- ✅ Vault pods ↔ Vault pods (ports 8200, 8201)
- ❌ External traffic → Vault

Northflank should automatically apply this.

### Health Checks

Northflank will use the health probes defined in the YAML:

- **Readiness**: `vault status -tls-skip-verify` (every 5s)
- **Liveness**: `/v1/sys/health` HTTP endpoint (every 5s after 60s)

### Auto-Restart on Seal

If a Vault pod becomes sealed (after restart), you'll need to unseal it manually. Consider:

1. **Auto-unseal** (enterprise feature, requires cloud KMS)
2. **Monitoring alert** when `sealed=true`
3. **Documented unseal procedure** for on-call team

## Troubleshooting

### Pods Won't Start

**Check logs:**
```bash
northflank kubectl logs vault-0
```

**Common issues:**
- Missing TLS secret → Create `vault-tls` secret first
- Insufficient resources → Check Northflank quota
- ConfigMap not mounted → Verify ConfigMap exists

### TLS Certificate Errors

**Symptom:** `x509: certificate signed by unknown authority`

**Solutions:**
1. Use `VAULT_SKIP_VERIFY=true` for internal communication
2. Or add CA certificate to CheckTick trust store
3. Or use Northflank's built-in certificate management

### Can't Connect from CheckTick

**Check NetworkPolicy:**
```bash
northflank kubectl get networkpolicy vault-network-policy -o yaml
```

Ensure CheckTick pods have label `app: checktick-web`.

**Test connectivity:**
```bash
northflank kubectl exec -it <checktick-pod> -- nc -zv vault 8200
```

### Vault Sealed After Restart

**Expected behavior**: Vault seals on restart for security.

**Solution**: Unseal with 3 of 4 keys (see step 3 above)

**Long-term**: Consider Vault auto-unseal with cloud KMS (AWS KMS, Azure Key Vault, GCP KMS)

## Cost Considerations

### Northflank Resources

**Vault cluster (3 replicas):**
- CPU: 3 × 250m = 750m (0.75 cores)
- Memory: 3 × 256Mi = 768Mi
- Storage: 3 × 10Gi = 30Gi
- Network: Internal only (free)

**Estimated cost**: ~$30-50/month on Northflank (varies by plan)

### Optimization Tips

- Start with 1 replica (no HA) for development
- Use 3 replicas for production
- Monitor storage usage (Raft logs grow over time)
- Enable Vault autopilot for automatic cleanup

## Security Checklist

Before going to production:

- [ ] TLS certificates generated and mounted
- [ ] Unseal keys stored in 4 separate secure locations
- [ ] Root token revoked after setup
- [ ] VAULT_ROLE_ID and VAULT_SECRET_ID saved to .env
- [ ] PLATFORM_CUSTODIAN_COMPONENT backed up (3+ locations)
- [ ] NetworkPolicy applied (blocks external access)
- [ ] Audit logging enabled (in setup script)
- [ ] Health monitoring configured
- [ ] Unseal procedure documented for team
- [ ] Disaster recovery plan documented

## Next Steps

After Vault is deployed and configured:

1. **Test Connection**
   ```bash
   python manage.py test_vault_connection
   ```

2. **Enable Organization Encryption** (Phase 3)
   - Implement UI for org owners
   - Derive organization keys
   - Migrate existing surveys

3. **Set Up Monitoring**
   - Prometheus metrics (port 9090)
   - Alert on sealed pods
   - Alert on auth failures

4. **Document Procedures**
   - Unseal process for on-call team
   - Recovery workflows
   - Backup/restore procedures

## Support

- Northflank Docs: https://northflank.com/docs
- HashiCorp Vault Docs: https://developer.hashicorp.com/vault/docs
- CheckTick Vault Integration: `docs/vault-integration.md`
