# HashiCorp Vault - CheckTick Integration

This folder contains infrastructure files for HashiCorp Vault deployment.

## Documentation

**For complete documentation, see: [docs/vault.md](/docs/vault.md)**

The main documentation includes:
- Architecture and key hierarchy
- Deployment options (Northflank, Docker Compose, Kubernetes)
- Initialization and setup
- Developer integration guide
- Recovery workflows
- Troubleshooting

## Files in This Folder

| File | Purpose |
|------|---------|
| `setup_vault.py` | Vault initialization script (creates secrets engine, policies, AppRole) |
| `verify-production-security.sh` | Production security verification script (checks TLS, token config, audit logs) |
| `northflank-deployment.yaml` | Kubernetes manifest for Northflank deployments |
| `generate-tls.sh` | Generate self-signed TLS certificates for testing |
| `vault-cert.pem` / `vault-key.pem` | TLS certificates (if using custom TLS) |

## Quick Start

If you're pulling Vault from Docker Hub (recommended):

```bash
docker run -d --name vault \
  -p 8200:8200 \
  -v vault-data:/vault/file \
  hashicorp/vault:1.21.1 \
  vault server -dev
```

Then follow the [Initialization guide](/docs/vault.md#initialization) in the main docs.

## Setup Script

After Vault is running and initialized:

```bash
export VAULT_ADDR=https://your-vault-url:8200
export VAULT_TOKEN=<root-token>

python setup_vault.py
```

This configures:
- KV v2 secrets engine at `secret/`
- CheckTick policy with required permissions
- AppRole authentication for the application
- Split-knowledge platform master key

Save the output to your `.env` file.

## Production Security Verification

After setup, verify your production configuration:

```bash
export VAULT_ADDR=https://your-vault-url:8200
export VAULT_TOKEN=<approle-token>  # NOT root token

cd vault/
./verify-production-security.sh
```

This checks:
- Root token revoked
- TLS configuration
- Token TTL settings
- Audit logging enabled
- Platform master key exists
- SecretID rotation policy
