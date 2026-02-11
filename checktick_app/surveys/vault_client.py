"""
HashiCorp Vault Integration for CheckTick

This module provides a secure interface to HashiCorp Vault for
hierarchical encryption key management.

Architecture:
    Platform Master Key (split-knowledge)
    └── Organisation Keys
        └── Team Keys
            └── Survey KEKs (Key Encryption Keys)

Security Model:
    - Platform master key = vault_component XOR custodian_component
    - Vault stores partial keys only
    - Custodian component required for organisation recovery
    - Each level in hierarchy can recover keys below it
"""

import logging
import os
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.utils import timezone
import hvac

logger = logging.getLogger(__name__)


class VaultConnectionError(Exception):
    """Raised when cannot connect to Vault."""

    pass


class VaultKeyNotFoundError(Exception):
    """Raised when key not found in Vault."""

    pass


class VaultClient:
    """
    HashiCorp Vault client for CheckTick encryption key management.

    Handles authentication, key storage/retrieval, and hierarchical
    key derivation.
    """

    def __init__(self):
        """Initialize Vault client with AppRole authentication."""
        self.vault_addr = settings.VAULT_ADDR
        self.role_id = settings.VAULT_ROLE_ID
        self.secret_id = settings.VAULT_SECRET_ID
        self._client = None

    def _get_client(self) -> hvac.Client:
        """Get authenticated Vault client (cached)."""
        if self._client is not None:
            # Check if token is still valid
            try:
                if self._client.is_authenticated():
                    return self._client
            except Exception:
                pass

        # Create new client and authenticate
        try:
            client = hvac.Client(url=self.vault_addr, verify=False)

            # Authenticate with AppRole
            auth_response = client.auth.approle.login(
                role_id=self.role_id, secret_id=self.secret_id
            )

            client.token = auth_response["auth"]["client_token"]

            if not client.is_authenticated():
                raise VaultConnectionError("Failed to authenticate with Vault")

            self._client = client
            logger.info("Successfully authenticated with Vault")
            return self._client

        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            raise VaultConnectionError(f"Vault connection failed: {e}")

    def health_check(self) -> dict:
        """Check Vault health status."""
        try:
            client = self._get_client()
            health = client.sys.read_health_status(method="GET")
            return {
                "initialized": health.get("initialized", False),
                "sealed": health.get("sealed", True),
                "standby": health.get("standby", False),
                "version": health.get("version", "unknown"),
            }
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return {"initialized": False, "sealed": True, "error": str(e)}

    def get_platform_master_key(self, custodian_component: bytes) -> bytes:
        """
        Reconstruct platform master key from vault and custodian components.

        Args:
            custodian_component: Custodian's component of platform key (64 bytes)

        Returns:
            Full 64-byte platform master key

        Raises:
            VaultKeyNotFoundError: If platform key not found in Vault
        """
        try:
            client = self._get_client()

            # Read vault component from Vault
            secret = client.secrets.kv.v2.read_secret_version(
                path="platform/master-key"
            )

            vault_component_hex = secret["data"]["data"]["vault_component"]
            vault_component = bytes.fromhex(vault_component_hex)

            # Reconstruct full key (XOR)
            platform_key = bytes(
                a ^ b for a, b in zip(vault_component, custodian_component)
            )

            logger.info("Successfully reconstructed platform master key")
            return platform_key

        except hvac.exceptions.InvalidPath:
            logger.error("Platform master key not found in Vault")
            raise VaultKeyNotFoundError("Platform master key not initialized")
        except Exception as e:
            logger.error(f"Failed to get platform master key: {e}")
            raise

    def derive_organization_key(
        self,
        org_id: int,
        org_owner_passphrase: str,
        platform_custodian_component: bytes,
    ) -> bytes:
        """
        Derive organization master key from platform key + owner passphrase.

        This implements split-knowledge: platform provides one component,
        organization owner provides another. Both required to derive org key.

        Args:
            org_id: Organization ID
            org_owner_passphrase: Organization owner's secret passphrase
            platform_custodian_component: Platform custodian component

        Returns:
            32-byte organization master key
        """
        # Get platform master key
        platform_key = self.get_platform_master_key(platform_custodian_component)

        # Derive org key from platform key + owner passphrase
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"checktick-org-{org_id}".encode("utf-8"),
            iterations=200_000,
        )

        # Combine platform key + passphrase
        combined_input = platform_key + org_owner_passphrase.encode("utf-8")
        org_key = kdf.derive(combined_input)

        logger.info(f"Derived organization key for org_id={org_id}")
        return org_key

    def store_organization_key_reference(self, org_id: int, metadata: dict = None):
        """
        Store organization key reference in Vault.

        Note: We don't store the actual org key, just metadata.
        The key is derived on-demand from platform + owner passphrase.

        Args:
            org_id: Organization ID
            metadata: Optional metadata about the organization
        """
        try:
            client = self._get_client()

            secret_data = {
                "org_id": org_id,
                "created_at": timezone.now().isoformat(),
                "key_derivation": "platform_key + owner_passphrase",
                "note": "Key derived on-demand, not stored",
            }

            if metadata:
                secret_data.update(metadata)

            client.secrets.kv.v2.create_or_update_secret(
                path=f"organizations/{org_id}/master-key", secret=secret_data
            )

            logger.info(f"Stored organization key reference for org_id={org_id}")

        except Exception as e:
            logger.error(f"Failed to store org key reference: {e}")
            raise

    def derive_team_key(self, team_id: int, org_key: bytes) -> bytes:
        """
        Derive team-specific key from organization key.

        Args:
            team_id: Team ID
            org_key: Organization master key (32 bytes)

        Returns:
            32-byte team key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"checktick-team-{team_id}".encode("utf-8"),
            iterations=200_000,
        )

        team_key = kdf.derive(org_key)

        logger.info(f"Derived team key for team_id={team_id}")
        return team_key

    def store_team_key_reference(self, team_id: int, org_id: int):
        """Store team key reference in Vault."""
        try:
            client = self._get_client()

            client.secrets.kv.v2.create_or_update_secret(
                path=f"teams/{team_id}/team-key",
                secret={
                    "team_id": team_id,
                    "org_id": org_id,
                    "created_at": timezone.now().isoformat(),
                    "key_derivation": "org_key + team_id",
                    "note": "Key derived on-demand from org key",
                },
            )

            logger.info(f"Stored team key reference for team_id={team_id}")

        except Exception as e:
            logger.error(f"Failed to store team key reference: {e}")
            raise

    def encrypt_survey_kek(
        self, survey_kek: bytes, hierarchy_key: bytes, vault_path: str
    ) -> str:
        """
        Encrypt survey KEK with hierarchical key and store in Vault.

        Args:
            survey_kek: Survey's master encryption key (32 bytes)
            hierarchy_key: Organization or team key (32 bytes)
            vault_path: Vault path (e.g., 'surveys/123/kek')

        Returns:
            Vault path where encrypted KEK is stored
        """
        try:
            # Derive encryption key from hierarchy key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=vault_path.encode("utf-8"),
                iterations=200_000,
            )
            encryption_key = kdf.derive(hierarchy_key)

            # Encrypt KEK with AES-GCM
            aesgcm = AESGCM(encryption_key)
            nonce = os.urandom(12)
            encrypted_kek = aesgcm.encrypt(nonce, survey_kek, None)

            # Store in Vault
            client = self._get_client()
            client.secrets.kv.v2.create_or_update_secret(
                path=vault_path,
                secret={
                    "encrypted_kek": (nonce + encrypted_kek).hex(),
                    "created_at": timezone.now().isoformat(),
                    "algorithm": "AES-256-GCM",
                },
            )

            logger.info(f"Stored encrypted survey KEK at {vault_path}")
            return vault_path

        except Exception as e:
            logger.error(f"Failed to encrypt and store survey KEK: {e}")
            raise

    def decrypt_survey_kek(self, vault_path: str, hierarchy_key: bytes) -> bytes:
        """
        Decrypt survey KEK from Vault using hierarchical key.

        Args:
            vault_path: Vault path where encrypted KEK is stored
            hierarchy_key: Organization or team key (32 bytes)

        Returns:
            Decrypted survey KEK (32 bytes)

        Raises:
            VaultKeyNotFoundError: If KEK not found at vault_path
        """
        try:
            client = self._get_client()

            # Read encrypted KEK from Vault
            secret = client.secrets.kv.v2.read_secret_version(path=vault_path)
            encrypted_kek_hex = secret["data"]["data"]["encrypted_kek"]
            encrypted_blob = bytes.fromhex(encrypted_kek_hex)

            # Extract nonce and ciphertext
            nonce = encrypted_blob[:12]
            ciphertext = encrypted_blob[12:]

            # Derive decryption key from hierarchy key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=vault_path.encode("utf-8"),
                iterations=200_000,
            )
            decryption_key = kdf.derive(hierarchy_key)

            # Decrypt KEK
            aesgcm = AESGCM(decryption_key)
            survey_kek = aesgcm.decrypt(nonce, ciphertext, None)

            logger.info(f"Decrypted survey KEK from {vault_path}")
            return survey_kek

        except hvac.exceptions.InvalidPath:
            logger.error(f"Survey KEK not found at {vault_path}")
            raise VaultKeyNotFoundError(f"Survey KEK not found: {vault_path}")
        except Exception as e:
            logger.error(f"Failed to decrypt survey KEK: {e}")
            raise

    def delete_survey_kek(self, vault_path: str):
        """
        Delete survey KEK from Vault.

        Args:
            vault_path: Vault path where KEK is stored
        """
        try:
            client = self._get_client()
            client.secrets.kv.v2.delete_metadata_and_all_versions(path=vault_path)
            logger.info(f"Deleted survey KEK at {vault_path}")
        except Exception as e:
            logger.error(f"Failed to delete survey KEK: {e}")
            raise

    # ===== Individual User Recovery Methods (Ethical Data Recovery) =====

    def derive_user_recovery_key(self, user_id: int, platform_key: bytes) -> bytes:
        """
        Derive user-specific recovery key from platform master key.

        This key is used to encrypt/decrypt the user's survey KEKs that are
        escrowed in Vault for ethical recovery purposes.

        Args:
            user_id: User ID
            platform_key: Platform master key (64 bytes)

        Returns:
            32-byte user recovery key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"checktick-user-recovery-{user_id}".encode("utf-8"),
            iterations=200_000,
        )

        user_recovery_key = kdf.derive(platform_key)

        logger.info(f"Derived user recovery key for user_id={user_id}")
        return user_recovery_key

    def escrow_user_survey_kek(
        self,
        user_id: int,
        survey_id: int,
        survey_kek: bytes,
        user_email: str,
        platform_custodian_component: bytes,
    ) -> str:
        """
        Escrow user's survey KEK in Vault for ethical recovery.

        This creates a third copy of the survey KEK (alongside password and
        recovery phrase paths) that can be recovered by platform admins after
        identity verification, preventing permanent data loss.

        Args:
            user_id: User ID
            survey_id: Survey ID
            survey_kek: Survey's master encryption key (32 bytes)
            user_email: User's email (encrypted for verification)
            platform_custodian_component: Platform custodian component

        Returns:
            Vault path where escrowed KEK is stored
        """
        try:
            # Get platform master key
            platform_key = self.get_platform_master_key(platform_custodian_component)

            # Derive user-specific recovery key
            user_recovery_key = self.derive_user_recovery_key(user_id, platform_key)

            # Encrypt user's email for identity verification
            email_kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=f"email-verification-{user_id}".encode("utf-8"),
                iterations=100_000,
            )
            email_key = email_kdf.derive(platform_key[:32])  # Use first 32 bytes

            aesgcm_email = AESGCM(email_key)
            email_nonce = os.urandom(12)
            encrypted_email = aesgcm_email.encrypt(
                email_nonce, user_email.encode("utf-8"), None
            )

            # Encrypt survey KEK with user recovery key
            vault_path = f"users/{user_id}/surveys/{survey_id}/recovery-kek"

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=vault_path.encode("utf-8"),
                iterations=200_000,
            )
            encryption_key = kdf.derive(user_recovery_key)

            aesgcm = AESGCM(encryption_key)
            nonce = os.urandom(12)
            encrypted_kek = aesgcm.encrypt(nonce, survey_kek, None)

            # Store in Vault
            client = self._get_client()
            client.secrets.kv.v2.create_or_update_secret(
                path=vault_path,
                secret={
                    "encrypted_kek": (nonce + encrypted_kek).hex(),
                    "encrypted_email": (email_nonce + encrypted_email).hex(),
                    "created_at": timezone.now().isoformat(),
                    "algorithm": "AES-256-GCM",
                    "requires_verification": True,
                    "purpose": "ethical-recovery",
                    "audit_trail": {
                        "created_by": "system",
                        "accessed_by": [],
                        "access_timestamps": [],
                    },
                },
            )

            logger.info(
                f"Escrowed survey KEK for user_id={user_id}, survey_id={survey_id}"
            )
            return vault_path

        except Exception as e:
            logger.error(f"Failed to escrow user survey KEK: {e}")
            raise

    def recover_user_survey_kek(
        self,
        user_id: int,
        survey_id: int,
        admin_id: int,
        verification_notes: str,
        platform_custodian_component: bytes,
    ) -> bytes:
        """
        Recover user's survey KEK from Vault escrow (admin operation).

        This should only be called after thorough identity verification.
        All access is logged for audit compliance.

        Args:
            user_id: User ID requesting recovery
            survey_id: Survey ID to recover
            admin_id: Admin performing recovery (for audit trail)
            verification_notes: Documentation of identity verification process
            platform_custodian_component: Platform custodian component

        Returns:
            Decrypted survey KEK (32 bytes)

        Raises:
            VaultKeyNotFoundError: If KEK not found in escrow
        """
        try:
            vault_path = f"users/{user_id}/surveys/{survey_id}/recovery-kek"
            client = self._get_client()

            # Read escrowed KEK from Vault
            secret = client.secrets.kv.v2.read_secret_version(path=vault_path)
            secret_data = secret["data"]["data"]
            encrypted_kek_hex = secret_data["encrypted_kek"]
            encrypted_blob = bytes.fromhex(encrypted_kek_hex)

            # Extract nonce and ciphertext
            nonce = encrypted_blob[:12]
            ciphertext = encrypted_blob[12:]

            # Get platform master key and derive user recovery key
            platform_key = self.get_platform_master_key(platform_custodian_component)
            user_recovery_key = self.derive_user_recovery_key(user_id, platform_key)

            # Derive decryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=vault_path.encode("utf-8"),
                iterations=200_000,
            )
            decryption_key = kdf.derive(user_recovery_key)

            # Decrypt KEK
            aesgcm = AESGCM(decryption_key)
            survey_kek = aesgcm.decrypt(nonce, ciphertext, None)

            # Update audit trail
            audit_trail = secret_data.get(
                "audit_trail", {"accessed_by": [], "access_timestamps": []}
            )
            audit_trail["accessed_by"].append(admin_id)
            audit_trail["access_timestamps"].append(timezone.now().isoformat())
            audit_trail["last_verification_notes"] = verification_notes

            # Write back with updated audit trail
            secret_data["audit_trail"] = audit_trail
            client.secrets.kv.v2.create_or_update_secret(
                path=vault_path, secret=secret_data
            )

            logger.warning(
                f"ADMIN RECOVERY: admin_id={admin_id} recovered survey KEK for "
                f"user_id={user_id}, survey_id={survey_id}. Verification: {verification_notes}"
            )

            return survey_kek

        except hvac.exceptions.InvalidPath:
            logger.error(
                f"Escrowed KEK not found for user_id={user_id}, survey_id={survey_id}"
            )
            raise VaultKeyNotFoundError(
                f"No escrowed KEK found for user {user_id}, survey {survey_id}"
            )
        except Exception as e:
            logger.error(f"Failed to recover user survey KEK: {e}")
            raise

    def verify_user_identity_email(
        self, user_id: int, claimed_email: str, platform_custodian_component: bytes
    ) -> bool:
        """
        Verify user's claimed email against encrypted email in Vault.

        Used during recovery process to confirm user identity.

        Args:
            user_id: User ID
            claimed_email: Email address user claims to own
            platform_custodian_component: Platform custodian component

        Returns:
            True if email matches, False otherwise
        """
        try:
            client = self._get_client()

            # Find any survey for this user (just need email verification)
            # In production, you'd query database for user's survey IDs

            # Read first available survey's recovery data
            # (All surveys for same user have same encrypted email)
            list_response = client.secrets.kv.v2.list_secrets(
                path=f"users/{user_id}/surveys/"
            )

            if not list_response or not list_response.get("data", {}).get("keys"):
                logger.error(f"No escrowed surveys found for user_id={user_id}")
                return False

            first_survey = list_response["data"]["keys"][0].rstrip("/")
            vault_path = f"users/{user_id}/surveys/{first_survey}/recovery-kek"

            secret = client.secrets.kv.v2.read_secret_version(path=vault_path)
            encrypted_email_hex = secret["data"]["data"]["encrypted_email"]
            encrypted_email_blob = bytes.fromhex(encrypted_email_hex)

            # Extract nonce and ciphertext
            email_nonce = encrypted_email_blob[:12]
            email_ciphertext = encrypted_email_blob[12:]

            # Derive email decryption key
            platform_key = self.get_platform_master_key(platform_custodian_component)

            email_kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=f"email-verification-{user_id}".encode("utf-8"),
                iterations=100_000,
            )
            email_key = email_kdf.derive(platform_key[:32])

            # Decrypt and compare
            aesgcm = AESGCM(email_key)
            decrypted_email = aesgcm.decrypt(
                email_nonce, email_ciphertext, None
            ).decode("utf-8")

            match = decrypted_email.lower() == claimed_email.lower()

            if match:
                logger.info(f"Email verification successful for user_id={user_id}")
            else:
                logger.warning(f"Email verification FAILED for user_id={user_id}")

            return match

        except Exception as e:
            logger.error(f"Failed to verify user email: {e}")
            return False


# Global Vault client instance
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get global Vault client instance (singleton)."""
    global _vault_client

    if _vault_client is None:
        _vault_client = VaultClient()

    return _vault_client
