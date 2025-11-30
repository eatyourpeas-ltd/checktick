---
title: Vault Integration (Developers)
category: api
priority: 5
---

# HashiCorp Vault Integration for CheckTick

This guide is for **developers** integrating with CheckTick's Vault-based encryption system.

For deployment instructions, see [Vault Setup](/docs/self-hosting-vault-setup/).
For administrative procedures, see [Key Management for Administrators](/docs/key-management-for-administrators/).

## Architecture Overview

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

## Security Model

### Split-Knowledge Security

The platform master key uses a **split-knowledge** design:

```
Platform Master Key = Vault Component ⊕ Custodian Component
```

- **Vault Component**: Stored in HashiCorp Vault (accessible to CheckTick application)
- **Custodian Component**: Stored offline by platform administrators
- **Neither component alone** can decrypt any data
- **Both components required** to reconstruct the full platform key

This ensures:
- Vault compromise alone cannot decrypt data
- CheckTick application compromise alone cannot decrypt data
- Platform administrators control recovery capability

### Key Hierarchy

1. **Platform Master Key** (64 bytes)
   - Split into vault + custodian components via XOR
   - Vault component: stored in Vault at `secret/platform/master-key`
   - Custodian component: stored offline by admins

2. **Organization Keys** (32 bytes)
   - Derived from: Platform Key + Organization Owner Passphrase
   - Formula: `PBKDF2-HMAC-SHA256(platform_key || owner_passphrase, iterations=200k)`
   - Not stored directly - derived on-demand
   - Reference stored in Vault at `secret/organizations/{org_id}/master-key`

3. **Team Keys** (32 bytes)
   - Derived from: Organization Key + Team ID
   - Formula: `PBKDF2-HMAC-SHA256(org_key, salt=team_id, iterations=200k)`
   - Not stored directly - derived on-demand
   - Reference stored in Vault at `secret/teams/{team_id}/team-key`

4. **Survey KEKs** (32 bytes)
   - Generated: Random 32 bytes per survey
   - Encrypted with: Organization/Team key OR user-specific key (AES-256-GCM)
   - Stored in: Vault at `secret/surveys/{survey_id}/kek` (org/team) OR `secret/users/{user_id}/surveys/{survey_id}/kek` (individual)
   - Used to encrypt: Survey patient data and responses

5. **Individual User Recovery Keys** (For ethical data recovery)
   - Purpose: **Prevent permanent data loss when user forgets password AND recovery phrase**
   - Generated: User's survey KEKs encrypted with platform-derived key
   - Stored in: Vault at `secret/users/{user_id}/surveys/{survey_id}/recovery-kek`
   - Access: Requires platform custodian component + user identity verification + audit trail
   - Ethical safeguard: User is custodian of patient data, not owner - platform must provide recovery

## Prerequisites

Before using this integration, you must:

1. **Deploy HashiCorp Vault**
   - Follow instructions in `vault/README.md`
   - Deploy to Northflank using `vault/northflank-deployment.yaml`
   - 3-node HA cluster with Raft storage

2. **Initialize Vault**
   - Run `vault operator init -key-shares=4 -key-threshold=3`
   - Securely store all 4 unseal keys and root token
   - Distribute keys: Admin 1, Admin 2, Physical Safe, Encrypted Backup

3. **Unseal Vault**
   - Connect to each pod: `kubectl exec -it vault-0 -- /bin/sh`
   - Unseal with 3 of 4 keys: `vault operator unseal <key>`
   - Repeat for all 3 pods (vault-0, vault-1, vault-2)

4. **Run Setup Script**
   - `python vault/setup_vault.py`
   - Save outputted credentials to `.env` file
   - **CRITICAL**: Store `PLATFORM_CUSTODIAN_COMPONENT` in multiple secure locations

## Installation

### 1. Install Dependencies

```bash
poetry add hvac
# or
pip install hvac==2.1.0
```

### 2. Configure Environment

Add to your `.env` file (values from `setup_vault.py` output):

```bash
VAULT_ADDR=https://vault.checktick.internal:8200
VAULT_ROLE_ID=your-vault-role-id
VAULT_SECRET_ID=your-vault-secret-id
PLATFORM_CUSTODIAN_COMPONENT=your-64-byte-hex-custodian-component
```

⚠️ **SECURITY WARNING**: The `PLATFORM_CUSTODIAN_COMPONENT` is critical for recovery. Store it in:
- Password manager (encrypted)
- Physical safe (printed, sealed)
- Encrypted cloud backup (with strong passphrase)

### 3. Test Connection

```bash
python manage.py test_vault_connection
```

Expected output:
```
Testing Vault Connection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Configuration:
  VAULT_ADDR: https://vault.checktick.internal:8200
  VAULT_ROLE_ID: ✓ Set
  VAULT_SECRET_ID: ✓ Set
  PLATFORM_CUSTODIAN_COMPONENT: ✓ Set

Connection Test:
  Initialized: ✓
  Sealed: ✓ Unsealed
  Standby: No
  Version: 1.15.0

Authentication Test:
  ✓ Successfully authenticated with AppRole

Platform Key Test:
  ✓ Platform master key reconstructed successfully
  Key length: 64 bytes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Vault Connection Test Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Usage

### Get Vault Client

```python
from checktick_app.surveys.vault_client import get_vault_client

vault = get_vault_client()
```

### Enable Organization Encryption

```python
# When organization owner sets up encryption for first time
def enable_organization_encryption(org_id: int, owner_passphrase: str):
    """Enable hierarchical encryption for organization."""
    vault = get_vault_client()

    # Get platform custodian component from settings
    custodian_component = bytes.fromhex(settings.PLATFORM_CUSTODIAN_COMPONENT)

    # Derive organization master key
    org_key = vault.derive_organization_key(
        org_id=org_id,
        org_owner_passphrase=owner_passphrase,
        platform_custodian_component=custodian_component
    )

    # Store reference in Vault
    vault.store_organization_key_reference(
        org_id=org_id,
        metadata={'enabled_at': timezone.now().isoformat()}
    )

    return org_key
```

### Encrypt Survey KEK

```python
# When creating a new survey with organization encryption
def create_encrypted_survey(survey, org_key: bytes):
    """Create survey and encrypt its KEK with org key."""

    # Generate survey's master encryption key
    survey_kek = os.urandom(32)

    # Encrypt and store KEK in Vault
    vault = get_vault_client()
    vault_path = vault.encrypt_survey_kek(
        survey_kek=survey_kek,
        hierarchy_key=org_key,
        vault_path=f'surveys/{survey.id}/kek'
    )

    # Store vault path in database
    survey.vault_key_path = vault_path
    survey.encryption_version = 2  # Hierarchical encryption
    survey.save()

    return survey_kek
```

### Decrypt Survey KEK

```python
# When unlocking a survey (e.g., team member accesses survey)
def unlock_survey_with_org_key(survey, org_owner_passphrase: str):
    """Unlock survey using organization key."""

    vault = get_vault_client()
    custodian_component = bytes.fromhex(settings.PLATFORM_CUSTODIAN_COMPONENT)

    # Derive org key
    org_key = vault.derive_organization_key(
        org_id=survey.organization.id,
        org_owner_passphrase=org_owner_passphrase,
        platform_custodian_component=custodian_component
    )

    # Decrypt survey KEK from Vault
    survey_kek = vault.decrypt_survey_kek(
        vault_path=survey.vault_key_path,
        hierarchy_key=org_key
    )

    return survey_kek
```

### Team-Level Encryption

```python
# Derive team key and encrypt survey KEK
def create_team_survey(survey, org_key: bytes, team_id: int):
    """Create survey encrypted with team key."""

    vault = get_vault_client()

    # Derive team key from org key
    team_key = vault.derive_team_key(
        team_id=team_id,
        org_key=org_key
    )

    # Store team reference
    vault.store_team_key_reference(
        team_id=team_id,
        org_id=survey.organization.id
    )

    # Generate and encrypt survey KEK
    survey_kek = os.urandom(32)
    vault_path = vault.encrypt_survey_kek(
        survey_kek=survey_kek,
        hierarchy_key=team_key,
        vault_path=f'surveys/{survey.id}/kek'
    )

    survey.vault_key_path = vault_path
    survey.save()

    return survey_kek
```

## Recovery Workflows

### Individual User (No Organization) - UPDATED ETHICAL RECOVERY

**Problem**: It's unethical to allow permanent data loss when users forget credentials. They are custodians of patient data, not owners.

**Solution**: Platform-escrowed recovery keys stored in Vault

#### Normal Operation (Triple-Path Encryption)

When a user creates a survey, their KEK is encrypted THREE ways:

1. **Password path**: KEK encrypted with password-derived key (stored in database)
2. **Recovery phrase path**: KEK encrypted with BIP39-derived key (stored in database
3. **Platform escrow path**: KEK encrypted with platform-derived key (stored in Vault)

#### Recovery Process (User Lost Password + Recovery Phrase)

**Eligibility Requirements:**

- User must verify identity (email/phone/video call/SSO re-authentication)
- User must have legitimate access rights to the data
- Audit trail created for regulatory compliance

**Recovery Steps:**

1. **User initiates recovery request**
   - Via "Lost all credentials" option on login page
   - Provides identity information (email, survey details, approx. creation date)

2. **Platform admin reviews request**
   - Verifies user identity (email confirmation, video call, or SSO re-authentication for OIDC users)
   - Checks audit logs for suspicious activity
   - Documents verification in audit system

3. **Platform admin initiates recovery** - Decrypts escrowed KEK using platform key

4. **User sets new credentials** - Creates new password and recovery phrase

5. **Audit trail recorded** - Full compliance documentation

**For OIDC Users:**

If user still has SSO access, re-authentication automatically decrypts via identity key (no admin needed).

### Team Member Recovery

If team member forgets password:

1. **Team admin provides org owner passphrase**
2. System derives org key → team key
3. System decrypts survey KEK from Vault
4. Team member sets new password
5. System re-encrypts KEK with new password

### Organization Member Recovery

If organization member loses access:

1. **Organization owner provides passphrase**
2. System derives org key
3. System decrypts survey KEK from Vault
4. User sets new password
5. System re-encrypts KEK with new password

### Catastrophic Recovery

If organization owner forgets passphrase:

1. **Platform admins retrieve custodian component** (from secure storage)
2. **Organization provides business verification** (legal documentation)
3. Platform admins reconstruct platform key
4. Platform admins derive org key using emergency process
5. Organization owner sets new passphrase
6. Keys re-derived with new passphrase

## Vault Paths

### Platform Level
```
secret/platform/master-key
  ├─ vault_component (hex string)
  ├─ created_at
  └─ algorithm
```

### Organization Level
```
secret/organizations/{org_id}/master-key
  ├─ org_id
  ├─ created_at
  ├─ key_derivation (metadata only, key not stored)
  └─ note
```

### Team Level
```
secret/teams/{team_id}/team-key
  ├─ team_id
  ├─ org_id
  ├─ created_at
  ├─ key_derivation (metadata only)
  └─ note
```

### Survey Level
```
secret/surveys/{survey_id}/kek
  ├─ encrypted_kek (nonce + ciphertext, hex)
  ├─ created_at
  └─ algorithm (AES-256-GCM)
```

### Individual User Level (NEW - Ethical Recovery)
```
secret/users/{user_id}/
  ├─ identity
  │  ├─ email (encrypted for verification)
  │  ├─ created_at
  │  └─ last_login
  └─ surveys/{survey_id}/
     └─ recovery-kek (platform-escrowed KEK for ethical recovery)
        ├─ encrypted_kek (nonce + ciphertext, hex)
        ├─ created_at
        ├─ algorithm (AES-256-GCM)
        ├─ requires_verification (true)
        └─ audit_trail
           ├─ created_by (system)
           ├─ accessed_by (list of admin IDs)
           └─ access_timestamps
```

**Key Difference**: Individual user survey KEKs are stored at `secret/users/{user_id}/surveys/{survey_id}/recovery-kek` NOT at `secret/surveys/{survey_id}/kek` (which is for org/team surveys).

## Monitoring

### Health Check Endpoint

Create a Django view for monitoring:

```python
from django.http import JsonResponse
from checktick_app.surveys.vault_client import get_vault_client

def vault_health(request):
    """Vault health check endpoint for monitoring."""
    vault = get_vault_client()
    health = vault.health_check()

    status = 200 if not health.get('sealed') and health.get('initialized') else 503

    return JsonResponse(health, status=status)
```

### Audit Logging

Vault audit logs are written to `/vault/logs/audit.log` inside each pod.

View audit logs:
```bash
kubectl exec -it vault-0 -- cat /vault/logs/audit.log | tail -n 100
```

Audit log includes:
- All key access attempts
- Authentication events
- Policy violations
- Timestamp and client IP

## Troubleshooting

### Connection Refused

**Symptom**: `Connection refused` when connecting to Vault

**Solutions**:
1. Check Vault pods are running: `kubectl get pods -l app=vault`
2. Check Vault is unsealed: `kubectl exec -it vault-0 -- vault status`
3. Verify network connectivity: `kubectl exec -it checktick-web-0 -- nc -zv vault 8200`
4. Check NetworkPolicy allows traffic

### Vault Sealed

**Symptom**: `sealed: true` in health check

**Solution**: Unseal all Vault pods
```bash
for pod in vault-0 vault-1 vault-2; do
  kubectl exec -it $pod -- vault operator unseal <key1>
  kubectl exec -it $pod -- vault operator unseal <key2>
  kubectl exec -it $pod -- vault operator unseal <key3>
done
```

### Authentication Failed

**Symptom**: `permission denied` or `authentication failed`

**Solutions**:
1. Verify VAULT_ROLE_ID and VAULT_SECRET_ID are correct
2. Check AppRole is enabled: `vault auth list`
3. Verify policy attachments: `vault read auth/approle/role/checktick-app`
4. Generate new secret_id if needed:
   ```bash
   vault write -f auth/approle/role/checktick-app/secret-id
   ```

### Key Not Found

**Symptom**: `VaultKeyNotFoundError: Platform master key not initialized`

**Solution**: Run setup script
```bash
python vault/setup_vault.py
```

## Security Best Practices

### Credential Management

✅ **DO**:
- Store `PLATFORM_CUSTODIAN_COMPONENT` in multiple secure locations
- Rotate `VAULT_SECRET_ID` periodically (90 days)
- Use strong, unique org owner passphrases (20+ characters)
- Audit Vault access logs regularly
- Keep unseal keys in separate physical locations

❌ **DON'T**:
- Commit `.env` file to version control
- Share custodian component via email/chat
- Use weak org owner passphrases
- Log decrypted keys
- Store unseal keys on the same system

### Network Security

- Vault should only be accessible from CheckTick application pods
- Use TLS for all Vault communication
- NetworkPolicy enforces pod-to-pod restrictions
- No external internet access to Vault

### Access Control

- CheckTick application: `checktick-app` policy (CRUD on keys)
- Organization admins: `org-admin` policy (read-only, identity-templated)
- No direct root token usage (rotate immediately after setup)

## Migration Path

### From Individual to Organization Encryption

1. User creates organization
2. Organization owner sets encryption passphrase
3. System derives org key
4. For each survey:
   - Unlock with existing password/recovery
   - Re-encrypt KEK with org key
   - Store in Vault
   - Update `encryption_version = 2`

### From Organization to Team Encryption

1. Create team within organization
2. System derives team key from org key
3. For each survey moved to team:
   - Decrypt KEK with org key
   - Re-encrypt KEK with team key
   - Update vault path
   - Update `team_id` association

## Performance Considerations

### Key Caching

The `VaultClient` caches authenticated connections to avoid repeated AppRole authentications.

**Token TTL**: 1 hour (configurable in AppRole)

### Vault HA

The 3-node Raft cluster provides:
- **High availability**: Tolerates 1 node failure
- **Read scalability**: Reads served by any active node
- **Write consistency**: Writes go through leader (auto-election)

### Expected Latency

- Platform key reconstruction: ~5ms
- Organization key derivation: ~200ms (PBKDF2 200k iterations)
- Team key derivation: ~200ms
- Survey KEK encrypt/decrypt: ~10ms (Vault + AES-GCM)

**Total unlock time**: ~420ms for team survey

## Further Reading

- [HashiCorp Vault Documentation](https://developer.hashicorp.com/vault/docs)
- [Vault AppRole Auth](https://developer.hashicorp.com/vault/docs/auth/approle)
- [Vault KV Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2)
- [Encryption for Users](/docs/encryption-for-users/) - User-facing encryption guide
- [Key Management for Administrators](/docs/key-management-for-administrators/) - Admin procedures
- [Vault Setup](/docs/self-hosting-vault-setup/) - Deployment guide
- [Business Continuity](/docs/business-continuity/) - Disaster recovery

## Recovery Implementation Examples

### Escrowing KEK During Survey Creation

```python
from checktick_app.surveys.vault_client import get_vault_client

def create_survey_with_escrow(survey, user, user_password):
    """Create survey with triple-path encryption (password + recovery + escrow)."""
    vault = get_vault_client()

    # Generate survey KEK
    survey_kek = os.urandom(32)

    # Path 1: Encrypt with password-derived key (stored in database)
    password_encrypted_kek = encrypt_with_password(survey_kek, user_password)
    survey.encrypted_kek = password_encrypted_kek

    # Path 2: Encrypt with recovery phrase (stored in database)
    recovery_encrypted_kek = encrypt_with_recovery_phrase(survey_kek, user.recovery_phrase_hash)
    survey.recovery_encrypted_kek = recovery_encrypted_kek

    # Path 3: Escrow with platform key (stored in Vault)
    vault_path = vault.escrow_survey_kek(
        user_id=user.id,
        survey_id=survey.id,
        survey_kek=survey_kek
    )
    survey.vault_recovery_path = vault_path

    survey.save()

    # Log escrow creation
    audit_log.create(
        action='kek_escrowed',
        user_id=user.id,
        survey_id=survey.id,
        vault_path=vault_path
    )

    return survey_kek
```

### Recovering KEK for Individual User

```python
from checktick_app.surveys.vault_client import get_vault_client
from checktick_app.core.models import RecoveryRequest

def execute_platform_recovery(recovery_request_id: int, admin_user):
    """Execute platform recovery after dual authorization + time delay."""

    request = RecoveryRequest.objects.get(id=recovery_request_id)

    # Verify dual authorization complete
    if not request.primary_approval or not request.secondary_approval:
        raise PermissionError("Dual authorization required")

    # Verify time delay has passed
    if timezone.now() < request.time_delay_until:
        remaining = request.time_delay_until - timezone.now()
        raise PermissionError(f"Time delay not complete. {remaining} remaining.")

    # Get custodian component (retrieved from offline storage)
    custodian_component = get_custodian_component_from_secure_storage()

    vault = get_vault_client()

    # Recover KEK using platform key
    survey_kek = vault.recover_escrowed_kek(
        user_id=request.user_id,
        survey_id=request.survey_id,
        platform_custodian_component=custodian_component
    )

    # Log recovery execution
    audit_log.create(
        action='platform_recovery_executed',
        admin_id=admin_user.id,
        user_id=request.user_id,
        survey_id=request.survey_id,
        request_id=recovery_request_id,
        primary_approver=request.primary_approval.admin_id,
        secondary_approver=request.secondary_approval.admin_id,
        time_delay_hours=(request.time_delay_until - request.approved_at).total_seconds() / 3600
    )

    # Update request status
    request.status = 'completed'
    request.completed_at = timezone.now()
    request.completed_by = admin_user
    request.save()

    # Notify user
    send_recovery_completion_email(request.user, request.survey)

    return survey_kek
```

### Audit Logging to Vault

```python
def log_to_vault_audit(action: str, details: dict):
    """Write audit entry to Vault for immutable logging."""
    vault = get_vault_client()

    audit_entry = {
        'timestamp': timezone.now().isoformat(),
        'action': action,
        'details': details,
        'source_ip': get_client_ip(),
        'user_agent': get_user_agent()
    }

    # Write to Vault audit path
    vault.write_audit_entry(
        path=f"audit/recovery/{details.get('user_id')}/{uuid.uuid4()}",
        data=audit_entry
    )

    # Also forward to SIEM if configured
    if settings.SIEM_ENABLED:
        forward_to_siem(audit_entry)
```

### VaultClient Methods for Recovery

```python
class VaultClient:
    """Extended VaultClient with recovery methods."""

    def escrow_survey_kek(self, user_id: int, survey_id: int, survey_kek: bytes) -> str:
        """
        Escrow survey KEK encrypted with platform key.

        Returns vault path where escrowed key is stored.
        """
        # Reconstruct platform key
        platform_key = self.get_platform_master_key()

        # Derive user-specific escrow key from platform key
        escrow_key = self._derive_escrow_key(platform_key, user_id)

        # Encrypt KEK
        nonce = os.urandom(12)
        cipher = Cipher(algorithms.AES(escrow_key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(survey_kek) + encryptor.finalize()

        # Store in Vault
        vault_path = f"secret/users/{user_id}/surveys/{survey_id}/recovery-kek"
        self.client.secrets.kv.v2.create_or_update_secret(
            path=vault_path,
            secret={
                'encrypted_kek': (nonce + ciphertext + encryptor.tag).hex(),
                'algorithm': 'AES-256-GCM',
                'created_at': timezone.now().isoformat(),
                'requires_verification': True
            }
        )

        return vault_path

    def recover_escrowed_kek(
        self,
        user_id: int,
        survey_id: int,
        platform_custodian_component: bytes
    ) -> bytes:
        """
        Recover escrowed KEK using platform key.

        Requires custodian component (offline storage).
        """
        # Reconstruct platform key with custodian component
        vault_component = self._get_vault_component()
        platform_key = bytes(a ^ b for a, b in zip(vault_component, platform_custodian_component))

        # Derive user-specific escrow key
        escrow_key = self._derive_escrow_key(platform_key, user_id)

        # Read from Vault
        vault_path = f"secret/users/{user_id}/surveys/{survey_id}/recovery-kek"
        secret = self.client.secrets.kv.v2.read_secret_version(path=vault_path)

        # Decrypt KEK
        encrypted_data = bytes.fromhex(secret['data']['data']['encrypted_kek'])
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:-16]
        tag = encrypted_data[-16:]

        cipher = Cipher(algorithms.AES(escrow_key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()
        survey_kek = decryptor.update(ciphertext) + decryptor.finalize()

        return survey_kek

    def _derive_escrow_key(self, platform_key: bytes, user_id: int) -> bytes:
        """Derive user-specific escrow key from platform key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"escrow:{user_id}".encode(),
            iterations=200_000,
        )
        return kdf.derive(platform_key)
```

## Getting Help

**For integration questions:**
- Email: support@checktick.uk
- Include: Code snippets, error messages, Vault version

**For security reviews:**
- Email: security@checktick.uk
