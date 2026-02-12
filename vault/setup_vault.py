#!/usr/bin/env python3
"""
HashiCorp Vault Setup Script for CheckTick

This script initializes Vault with the necessary configuration for
CheckTick's hierarchical encryption system.

Run this ONCE after Vault is initialized and unsealed.

Requirements:
    pip install hvac

Usage:
    export VAULT_ADDR=https://vault.checktick.internal:8200
    export VAULT_TOKEN=<root_token>
    python setup_vault.py
"""

from datetime import datetime
import os
import sys

import hvac


def check_vault_status(client):
    """Check if Vault is initialized and unsealed."""
    try:
        if client.sys.is_sealed():
            print("❌ Error: Vault is sealed. Please unseal Vault first.")
            print("\nTo unseal:")
            print("  vault operator unseal <key1>")
            print("  vault operator unseal <key2>")
            print("  vault operator unseal <key3>")
            sys.exit(1)

        if not client.sys.is_initialized():
            print("❌ Error: Vault is not initialized.")
            print("\nTo initialize:")
            print("  vault operator init -key-shares=4 -key-threshold=3")
            sys.exit(1)

        print("✅ Vault is initialized and unsealed")
        return True
    except Exception as e:
        print(f"❌ Error connecting to Vault: {e}")
        sys.exit(1)


def enable_secrets_engine(client):
    """Enable KV v2 secrets engine."""
    print("\n📦 Enabling secrets engine...")

    try:
        # Check if already enabled
        secrets_engines = client.sys.list_mounted_secrets_engines()
        if "secret/" in secrets_engines:
            print("  ℹ️  KV secrets engine already enabled at secret/")
        else:
            client.sys.enable_secrets_engine(
                backend_type="kv", path="secret", options={"version": "2"}
            )
            print("  ✅ Enabled KV v2 secrets engine at secret/")
    except Exception as e:
        print(f"  ⚠️  Warning: {e}")


def create_policies(client):
    """Create Vault policies for CheckTick."""
    print("\n🔐 Creating Vault policies...")

    # CheckTick application policy
    checktick_policy = """
# CheckTick Application Policy
# Allows CheckTick to manage encryption keys

# Platform master key (read-only)
path "secret/data/platform/master-key" {
  capabilities = ["read"]
}

# Organization keys (create, read, update)
path "secret/data/organizations/+/master-key" {
  capabilities = ["create", "read", "update", "list"]
}

path "secret/metadata/organizations/*" {
  capabilities = ["list"]
}

# Team keys (create, read, update)
path "secret/data/teams/+/team-key" {
  capabilities = ["create", "read", "update", "list"]
}

path "secret/metadata/teams/*" {
  capabilities = ["list"]
}

# Survey keys (create, read, update, delete)
path "secret/data/surveys/+/kek" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/surveys/*" {
  capabilities = ["list", "delete"]
}

# Token management
path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}
"""

    try:
        client.sys.create_or_update_policy(
            name="checktick-app", policy=checktick_policy
        )
        print("  ✅ Created checktick-app policy")
    except Exception as e:
        print(f"  ❌ Error creating policy: {e}")
        sys.exit(1)

    # Organization admin policy template
    org_admin_policy = """
# Organization Admin Policy
# Allows org admins to read their organization's keys

# Read own organization key
path "secret/data/organizations/{{identity.entity.metadata.org_id}}/master-key" {
  capabilities = ["read"]
}

# Read team keys within organization
path "secret/data/teams/{{identity.entity.metadata.org_id}}_+/team-key" {
  capabilities = ["read"]
}

# List surveys within organization
path "secret/metadata/surveys/{{identity.entity.metadata.org_id}}_+/*" {
  capabilities = ["list"]
}
"""

    try:
        client.sys.create_or_update_policy(name="org-admin", policy=org_admin_policy)
        print("  ✅ Created org-admin policy")
    except Exception as e:
        print(f"  ❌ Error creating org admin policy: {e}")


def enable_approle_auth(client):
    """Enable and configure AppRole authentication for CheckTick."""
    print("\n🔑 Configuring AppRole authentication...")

    try:
        # Enable AppRole auth method
        auth_methods = client.sys.list_auth_methods()
        if "approle/" in auth_methods:
            print("  ℹ️  AppRole already enabled")
        else:
            client.sys.enable_auth_method(method_type="approle", path="approle")
            print("  ✅ Enabled AppRole auth method")

        # Create AppRole for CheckTick
        client.auth.approle.create_or_update_approle(
            role_name="checktick-app",
            token_policies=["checktick-app"],
            token_ttl="1h",
            token_max_ttl="8h",  # Reduced from 24h for security
            bind_secret_id=True,
            secret_id_ttl="90d",  # 90-day rotation policy
            token_num_uses=0,  # Unlimited uses
        )
        print("  ✅ Created checktick-app AppRole")

        # Get RoleID and SecretID
        role_id = client.auth.approle.read_role_id(role_name="checktick-app")["data"][
            "role_id"
        ]
        secret_id_response = client.auth.approle.generate_secret_id(
            role_name="checktick-app"
        )
        secret_id = secret_id_response["data"]["secret_id"]

        print("\n  📋 AppRole Credentials (save these in CheckTick .env):")
        print(f"  VAULT_ROLE_ID={role_id}")
        print(f"  VAULT_SECRET_ID={secret_id}")
        print("\n  ⚠️  These credentials allow CheckTick to authenticate to Vault.")
        print("  ⚠️  Store them securely in your environment configuration.\n")

        return role_id, secret_id

    except Exception as e:
        print(f"  ❌ Error configuring AppRole: {e}")
        sys.exit(1)


def enable_audit_logging(client):
    """Enable audit logging for Vault."""
    print("\n📝 Enabling audit logging...")

    try:
        audit_backends = client.sys.list_enabled_audit_devices()
        if "file/" in audit_backends:
            print("  ℹ️  File audit already enabled")
        else:
            client.sys.enable_audit_device(
                device_type="file", options={"file_path": "/vault/logs/audit.log"}
            )
            print("  ✅ Enabled file audit logging to /vault/logs/audit.log")

        # Verify audit log is writable
        print("\n  📋 Audit Log Verification:")
        print("     After deployment, verify:")
        print("     1. Log file exists and is writable")
        print("     2. Set up log rotation (logrotate or similar)")
        print("     3. Configure SIEM ingestion (Elasticsearch/Splunk)")
        print("     4. Set alerts for:")
        print("        - Excessive failed authentication (>5/min)")
        print("        - Recovery requests (>5/day)")
        print("        - Unusual access patterns")

    except Exception as e:
        print(f"  ⚠️  Warning: Could not enable audit logging: {e}")


def generate_platform_master_key(client):
    """
    Generate platform master key with split-knowledge design.

    Returns vault component and custodian component.
    Platform master key = vault_component XOR custodian_component
    """
    print("\n🔐 Generating platform master key...")

    import secrets

    # Generate 64-byte (512-bit) full key
    full_key = secrets.token_bytes(64)

    # Generate vault component (random)
    vault_component = secrets.token_bytes(64)

    # Derive custodian component (XOR)
    custodian_component = bytes(a ^ b for a, b in zip(full_key, vault_component))

    # Store vault component in Vault
    try:
        client.secrets.kv.v2.create_or_update_secret(
            path="platform/master-key",
            secret={
                "vault_component": vault_component.hex(),
                "created_at": datetime.utcnow().isoformat(),
                "algorithm": "XOR split-knowledge",
                "key_size": 512,
                "note": "Requires custodian component to reconstruct full key",
            },
        )
        print("  ✅ Stored vault component in Vault")
    except Exception as e:
        print(f"  ❌ Error storing platform key: {e}")
        sys.exit(1)

    print("\n  📋 Platform Custodian Component:")
    print(f"  {custodian_component.hex()}")
    print("\n  ⚠️  CRITICAL: Split this into Shamir shares before using in production!")
    print("\n  Next steps:")
    print("     1. Copy the hex string above")
    print("     2. Run: python manage.py split_custodian_component \\")
    print("                --custodian-component=<paste_hex_here>")
    print("     3. Distribute 4 shares to custodians (need 3 to recover)")
    print("     4. DO NOT add PLATFORM_CUSTODIAN_COMPONENT to .env")
    print("     5. Delete this output after splitting shares")
    print(
        "\n  ⚠️  For platform recovery, use: python manage.py execute_platform_recovery"
    )
    print("  ⚠️  Without custodian shares, platform recovery is impossible!\n")

    return vault_component.hex(), custodian_component.hex()


def create_sample_organization_key(client):
    """Create a sample organization key structure (for testing)."""
    print("\n🏢 Creating sample organization key structure...")

    try:
        client.secrets.kv.v2.create_or_update_secret(
            path="organizations/1/master-key",
            secret={
                "note": "Example organization key structure",
                "created_at": datetime.utcnow().isoformat(),
                "org_key_vault_part": "will_be_generated_on_org_creation",
            },
        )
        print("  ✅ Created sample organization key at organizations/1/")
    except Exception as e:
        print(f"  ⚠️  Warning: {e}")


def main():
    """Main setup routine."""
    print("=" * 70)
    print("  HashiCorp Vault Setup for CheckTick")
    print("  Hierarchical Encryption Key Management")
    print("=" * 70)

    # Get Vault connection details from environment
    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")

    if not vault_addr:
        print("\n❌ Error: VAULT_ADDR environment variable not set")
        print("   export VAULT_ADDR=https://vault.checktick.internal:8200")
        sys.exit(1)

    if not vault_token:
        print("\n❌ Error: VAULT_TOKEN environment variable not set")
        print("   export VAULT_TOKEN=<root_token>")
        sys.exit(1)

    print(f"\n🔗 Connecting to Vault at {vault_addr}...")

    # Initialize Vault client with explicit HTTPS
    # Northflank routes through port 443, not 8200
    # TLS verification: disable only for initial setup with self-signed certs
    verify_tls = os.getenv("VAULT_TLS_VERIFY_SETUP", "false").lower() == "true"
    client = hvac.Client(
        url=vault_addr, token=vault_token, verify=verify_tls, namespace=None
    )

    # Check Vault status
    check_vault_status(client)

    # Setup steps
    enable_secrets_engine(client)
    create_policies(client)
    role_id, secret_id = enable_approle_auth(client)
    enable_audit_logging(client)
    vault_comp, custodian_comp = generate_platform_master_key(client)
    create_sample_organization_key(client)

    # Summary
    print("\n" + "=" * 70)
    print("  ✅ Vault Setup Complete!")
    print("=" * 70)

    print("\n📋 Next Steps:")
    print("\n1. Add to CheckTick .env file:")
    print(f"   VAULT_ADDR={vault_addr}")
    print("   VAULT_NAMESPACE=checktick")
    print(f"   VAULT_ROLE_ID={role_id}")
    print(f"   VAULT_SECRET_ID={secret_id}")

    print("\n2. Split the custodian component into Shamir shares:")
    print("   python manage.py split_custodian_component \\")
    print(f"     --custodian-component={custodian_comp}")
    print("\n   This creates 4 shares (need 3 to reconstruct).")
    print("   Distribute to same people who have Vault unseal keys:")
    print("   - Share 1 → Admin 1's password manager")
    print("   - Share 2 → Admin 2's password manager")
    print("   - Share 3 → Physical safe")
    print("   - Share 4 → Encrypted cloud backup")

    print("\n3. DO NOT add PLATFORM_CUSTODIAN_COMPONENT to .env file!")
    print("   This is a security measure. Use shares via management command only.")

    print("\n4. Test Vault connection from CheckTick:")
    print("   python manage.py test_vault_connection")

    print("\n5. Revoke root token (recommended after setup):")
    print(f"   vault token revoke {vault_token}")
    print("   (CheckTick will use AppRole credentials instead)")

    print("\n6. Verify production security:")
    print("   cd vault/")
    print("   chmod +x verify-production-security.sh")
    print("   export VAULT_ADDR=<your-vault-url>")
    print("   export VAULT_TOKEN=<approle-token>  # Use AppRole, not root")
    print("   ./verify-production-security.sh")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
