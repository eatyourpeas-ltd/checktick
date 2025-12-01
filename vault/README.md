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
| `northflank-deployment.yaml` | Kubernetes manifest for Northflank deployments |
| `vault-tls.crt` / `vault-tls.key` | TLS certificates (if using custom TLS) |

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
