"""
Tests for Vault-based key recovery functionality.

These tests verify the ethical data recovery flow using mocked Vault responses.
"""

import os
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
import pytest

from checktick_app.surveys.vault_client import VaultClient, VaultKeyNotFoundError

User = get_user_model()


class MockVaultStorage:
    """In-memory storage to simulate Vault KV store."""

    def __init__(self):
        self.secrets = {}

    def create_or_update_secret(self, path: str, secret: dict):
        """Store a secret."""
        self.secrets[path] = {"data": {"data": secret}}

    def read_secret_version(self, path: str):
        """Read a secret."""
        if path not in self.secrets:
            import hvac.exceptions

            raise hvac.exceptions.InvalidPath(f"No secret at {path}")
        return self.secrets[path]

    def list_secrets(self, path: str):
        """List secrets under a path."""
        # Normalize path - remove trailing slash for comparison
        normalized_path = path.rstrip("/") + "/"
        keys = []
        for secret_path in self.secrets.keys():
            if secret_path.startswith(normalized_path):
                # Extract the next path component after the prefix
                remainder = secret_path[len(normalized_path) :]
                if remainder:
                    # Get just the next directory/key
                    parts = remainder.split("/")
                    key = parts[0]
                    # Add trailing slash if it's a directory (has more parts)
                    if len(parts) > 1:
                        key = key + "/"
                    if key and key not in keys:
                        keys.append(key)
        return {"data": {"keys": keys}} if keys else {"data": {"keys": []}}

    def delete_metadata_and_all_versions(self, path: str):
        """Delete a secret."""
        if path in self.secrets:
            del self.secrets[path]


def create_mock_vault_client():
    """Create a VaultClient with mocked hvac client."""
    storage = MockVaultStorage()

    # Create mock hvac client
    mock_hvac = Mock()
    mock_hvac.is_authenticated.return_value = True
    mock_hvac.secrets.kv.v2.create_or_update_secret = storage.create_or_update_secret
    mock_hvac.secrets.kv.v2.read_secret_version = storage.read_secret_version
    mock_hvac.secrets.kv.v2.list_secrets = storage.list_secrets
    mock_hvac.secrets.kv.v2.delete_metadata_and_all_versions = (
        storage.delete_metadata_and_all_versions
    )

    return mock_hvac, storage


class TestVaultClientKeyDerivation(TestCase):
    """Tests for key derivation functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_hvac, self.storage = create_mock_vault_client()

        # Create a test platform key (64 bytes)
        self.platform_key = os.urandom(64)

        # Split into vault and custodian components
        self.vault_component = os.urandom(64)
        self.custodian_component = bytes(
            a ^ b for a, b in zip(self.platform_key, self.vault_component)
        )

        # Store vault component in mock storage
        self.storage.create_or_update_secret(
            "platform/master-key",
            {"vault_component": self.vault_component.hex()},
        )

    @patch("checktick_app.surveys.vault_client.settings")
    def test_derive_user_recovery_key(self, mock_settings):
        """Test user recovery key derivation is deterministic."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        user_id = 42

        # Derive key twice - should be identical
        key1 = client.derive_user_recovery_key(user_id, self.platform_key)
        key2 = client.derive_user_recovery_key(user_id, self.platform_key)

        assert key1 == key2, "Key derivation should be deterministic"
        assert len(key1) == 32, "Key should be 32 bytes"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_derive_user_recovery_key_different_users(self, mock_settings):
        """Test different users get different recovery keys."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        key_user1 = client.derive_user_recovery_key(1, self.platform_key)
        key_user2 = client.derive_user_recovery_key(2, self.platform_key)

        assert key_user1 != key_user2, "Different users should have different keys"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_get_platform_master_key(self, mock_settings):
        """Test platform master key reconstruction from components."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        reconstructed = client.get_platform_master_key(self.custodian_component)

        assert (
            reconstructed == self.platform_key
        ), "Key should be reconstructed correctly"


class TestVaultEscrowAndRecovery(TestCase):
    """Tests for KEK escrow and recovery flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_hvac, self.storage = create_mock_vault_client()

        # Create test platform key
        self.platform_key = os.urandom(64)
        self.vault_component = os.urandom(64)
        self.custodian_component = bytes(
            a ^ b for a, b in zip(self.platform_key, self.vault_component)
        )

        # Store vault component
        self.storage.create_or_update_secret(
            "platform/master-key",
            {"vault_component": self.vault_component.hex()},
        )

        # Test data
        self.user_id = 123
        self.survey_id = 456
        self.admin_id = 1
        self.user_email = "test.user@example.com"
        self.survey_kek = os.urandom(32)

    @patch("checktick_app.surveys.vault_client.settings")
    def test_escrow_user_survey_kek(self, mock_settings):
        """Test escrowing a user's survey KEK."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Escrow the KEK
        vault_path = client.escrow_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            survey_kek=self.survey_kek,
            user_email=self.user_email,
            platform_custodian_component=self.custodian_component,
        )

        expected_path = f"users/{self.user_id}/surveys/{self.survey_id}/recovery-kek"
        assert vault_path == expected_path

        # Verify data was stored
        stored = self.storage.secrets[expected_path]["data"]["data"]
        assert "encrypted_kek" in stored
        assert "encrypted_email" in stored
        assert stored["algorithm"] == "AES-256-GCM"
        assert stored["requires_verification"] is True
        assert stored["purpose"] == "ethical-recovery"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_recover_user_survey_kek(self, mock_settings):
        """Test recovering a user's survey KEK."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # First escrow the KEK
        client.escrow_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            survey_kek=self.survey_kek,
            user_email=self.user_email,
            platform_custodian_component=self.custodian_component,
        )

        # Now recover it
        recovered_kek = client.recover_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            admin_id=self.admin_id,
            verification_notes="Identity verified via video call and email confirmation",
            platform_custodian_component=self.custodian_component,
        )

        assert recovered_kek == self.survey_kek, "Recovered KEK should match original"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_recover_updates_audit_trail(self, mock_settings):
        """Test that recovery updates the audit trail."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Escrow and recover
        client.escrow_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            survey_kek=self.survey_kek,
            user_email=self.user_email,
            platform_custodian_component=self.custodian_component,
        )

        client.recover_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            admin_id=self.admin_id,
            verification_notes="Video call verification",
            platform_custodian_component=self.custodian_component,
        )

        # Check audit trail was updated
        vault_path = f"users/{self.user_id}/surveys/{self.survey_id}/recovery-kek"
        stored = self.storage.secrets[vault_path]["data"]["data"]
        audit_trail = stored["audit_trail"]

        assert self.admin_id in audit_trail["accessed_by"]
        assert len(audit_trail["access_timestamps"]) == 1
        assert audit_trail["last_verification_notes"] == "Video call verification"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_recover_nonexistent_kek_raises_error(self, mock_settings):
        """Test that recovering a non-existent KEK raises appropriate error."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        with pytest.raises(VaultKeyNotFoundError):
            client.recover_user_survey_kek(
                user_id=999,
                survey_id=999,
                admin_id=self.admin_id,
                verification_notes="Test",
                platform_custodian_component=self.custodian_component,
            )


class TestEmailVerification(TestCase):
    """Tests for email verification during recovery."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_hvac, self.storage = create_mock_vault_client()

        # Create test platform key
        self.platform_key = os.urandom(64)
        self.vault_component = os.urandom(64)
        self.custodian_component = bytes(
            a ^ b for a, b in zip(self.platform_key, self.vault_component)
        )

        # Store vault component
        self.storage.create_or_update_secret(
            "platform/master-key",
            {"vault_component": self.vault_component.hex()},
        )

        self.user_id = 123
        self.survey_id = 456
        self.user_email = "real.user@example.com"
        self.survey_kek = os.urandom(32)

    @patch("checktick_app.surveys.vault_client.settings")
    def test_verify_correct_email(self, mock_settings):
        """Test that correct email passes verification."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Escrow with email
        client.escrow_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            survey_kek=self.survey_kek,
            user_email=self.user_email,
            platform_custodian_component=self.custodian_component,
        )

        # Verify correct email
        result = client.verify_user_identity_email(
            user_id=self.user_id,
            claimed_email=self.user_email,
            platform_custodian_component=self.custodian_component,
        )

        assert result is True

    @patch("checktick_app.surveys.vault_client.settings")
    def test_verify_correct_email_case_insensitive(self, mock_settings):
        """Test that email verification is case-insensitive."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Escrow with lowercase email
        client.escrow_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            survey_kek=self.survey_kek,
            user_email="user@example.com",
            platform_custodian_component=self.custodian_component,
        )

        # Verify with different case
        result = client.verify_user_identity_email(
            user_id=self.user_id,
            claimed_email="USER@EXAMPLE.COM",
            platform_custodian_component=self.custodian_component,
        )

        assert result is True

    @patch("checktick_app.surveys.vault_client.settings")
    def test_verify_wrong_email_fails(self, mock_settings):
        """Test that wrong email fails verification."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Escrow with real email
        client.escrow_user_survey_kek(
            user_id=self.user_id,
            survey_id=self.survey_id,
            survey_kek=self.survey_kek,
            user_email=self.user_email,
            platform_custodian_component=self.custodian_component,
        )

        # Try to verify with wrong email
        result = client.verify_user_identity_email(
            user_id=self.user_id,
            claimed_email="attacker@evil.com",
            platform_custodian_component=self.custodian_component,
        )

        assert result is False

    @patch("checktick_app.surveys.vault_client.settings")
    def test_verify_email_no_escrowed_surveys(self, mock_settings):
        """Test that verification fails if user has no escrowed surveys."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Try to verify without any escrowed surveys
        result = client.verify_user_identity_email(
            user_id=999,  # Non-existent user
            claimed_email="nobody@example.com",
            platform_custodian_component=self.custodian_component,
        )

        assert result is False


class TestOrganizationKeyDerivation(TestCase):
    """Tests for organization key derivation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_hvac, self.storage = create_mock_vault_client()

        # Create test platform key
        self.platform_key = os.urandom(64)
        self.vault_component = os.urandom(64)
        self.custodian_component = bytes(
            a ^ b for a, b in zip(self.platform_key, self.vault_component)
        )

        # Store vault component
        self.storage.create_or_update_secret(
            "platform/master-key",
            {"vault_component": self.vault_component.hex()},
        )

    @patch("checktick_app.surveys.vault_client.settings")
    def test_derive_organization_key(self, mock_settings):
        """Test organization key derivation."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        org_id = 1
        org_passphrase = "secret-org-passphrase"

        org_key = client.derive_organization_key(
            org_id=org_id,
            org_owner_passphrase=org_passphrase,
            platform_custodian_component=self.custodian_component,
        )

        assert len(org_key) == 32, "Organization key should be 32 bytes"

        # Verify deterministic
        org_key2 = client.derive_organization_key(
            org_id=org_id,
            org_owner_passphrase=org_passphrase,
            platform_custodian_component=self.custodian_component,
        )

        assert org_key == org_key2, "Key derivation should be deterministic"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_derive_organization_key_different_passphrases(self, mock_settings):
        """Test that different passphrases produce different org keys."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        org_id = 1

        key1 = client.derive_organization_key(
            org_id=org_id,
            org_owner_passphrase="passphrase-one",
            platform_custodian_component=self.custodian_component,
        )

        key2 = client.derive_organization_key(
            org_id=org_id,
            org_owner_passphrase="passphrase-two",
            platform_custodian_component=self.custodian_component,
        )

        assert key1 != key2, "Different passphrases should produce different keys"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_derive_team_key_from_org_key(self, mock_settings):
        """Test team key derivation from organization key."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # First derive org key
        org_key = client.derive_organization_key(
            org_id=1,
            org_owner_passphrase="org-passphrase",
            platform_custodian_component=self.custodian_component,
        )

        # Then derive team key
        team_key = client.derive_team_key(team_id=10, org_key=org_key)

        assert len(team_key) == 32, "Team key should be 32 bytes"

        # Verify deterministic
        team_key2 = client.derive_team_key(team_id=10, org_key=org_key)
        assert team_key == team_key2, "Team key derivation should be deterministic"

        # Different teams get different keys
        team_key_other = client.derive_team_key(team_id=20, org_key=org_key)
        assert team_key != team_key_other, "Different teams should have different keys"


class TestSurveyKEKEncryption(TestCase):
    """Tests for survey KEK encryption with hierarchical keys."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_hvac, self.storage = create_mock_vault_client()

        # Create test platform key
        self.platform_key = os.urandom(64)
        self.vault_component = os.urandom(64)
        self.custodian_component = bytes(
            a ^ b for a, b in zip(self.platform_key, self.vault_component)
        )

        # Store vault component
        self.storage.create_or_update_secret(
            "platform/master-key",
            {"vault_component": self.vault_component.hex()},
        )

        self.survey_kek = os.urandom(32)

    @patch("checktick_app.surveys.vault_client.settings")
    def test_encrypt_and_decrypt_survey_kek(self, mock_settings):
        """Test encrypting and decrypting survey KEK with hierarchy key."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Derive org key
        org_key = client.derive_organization_key(
            org_id=1,
            org_owner_passphrase="test-passphrase",
            platform_custodian_component=self.custodian_component,
        )

        # Encrypt survey KEK
        vault_path = "surveys/123/kek"
        stored_path = client.encrypt_survey_kek(
            survey_kek=self.survey_kek,
            hierarchy_key=org_key,
            vault_path=vault_path,
        )

        assert stored_path == vault_path

        # Decrypt survey KEK
        decrypted_kek = client.decrypt_survey_kek(
            vault_path=vault_path,
            hierarchy_key=org_key,
        )

        assert decrypted_kek == self.survey_kek, "Decrypted KEK should match original"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_decrypt_with_wrong_key_fails(self, mock_settings):
        """Test that decrypting with wrong hierarchy key fails."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Derive correct org key
        correct_key = client.derive_organization_key(
            org_id=1,
            org_owner_passphrase="correct-passphrase",
            platform_custodian_component=self.custodian_component,
        )

        # Derive wrong org key
        wrong_key = client.derive_organization_key(
            org_id=1,
            org_owner_passphrase="wrong-passphrase",
            platform_custodian_component=self.custodian_component,
        )

        # Encrypt with correct key
        vault_path = "surveys/456/kek"
        client.encrypt_survey_kek(
            survey_kek=self.survey_kek,
            hierarchy_key=correct_key,
            vault_path=vault_path,
        )

        # Try to decrypt with wrong key - should raise exception
        with pytest.raises(Exception):  # Will raise InvalidTag from AES-GCM
            client.decrypt_survey_kek(
                vault_path=vault_path,
                hierarchy_key=wrong_key,
            )

    @patch("checktick_app.surveys.vault_client.settings")
    def test_delete_survey_kek(self, mock_settings):
        """Test deleting survey KEK from Vault."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        org_key = os.urandom(32)

        # Store KEK
        vault_path = "surveys/789/kek"
        client.encrypt_survey_kek(
            survey_kek=self.survey_kek,
            hierarchy_key=org_key,
            vault_path=vault_path,
        )

        # Verify it exists
        assert vault_path in self.storage.secrets

        # Delete it
        client.delete_survey_kek(vault_path)

        # Verify it's gone
        assert vault_path not in self.storage.secrets


class TestFullRecoveryWorkflow(TestCase):
    """Integration tests for the complete recovery workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_hvac, self.storage = create_mock_vault_client()

        # Create test platform key
        self.platform_key = os.urandom(64)
        self.vault_component = os.urandom(64)
        self.custodian_component = bytes(
            a ^ b for a, b in zip(self.platform_key, self.vault_component)
        )

        # Store vault component
        self.storage.create_or_update_secret(
            "platform/master-key",
            {"vault_component": self.vault_component.hex()},
        )

    @patch("checktick_app.surveys.vault_client.settings")
    def test_complete_individual_user_recovery_flow(self, mock_settings):
        """
        Test complete recovery flow for individual user:
        1. User creates survey with encryption
        2. Survey KEK is escrowed
        3. User forgets password and recovery phrase
        4. Admin verifies identity
        5. Admin recovers KEK
        """
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Step 1 & 2: User creates encrypted survey, KEK is escrowed
        user_id = 100
        survey_id = 200
        user_email = "dr.smith@hospital.nhs.uk"
        original_kek = os.urandom(32)

        client.escrow_user_survey_kek(
            user_id=user_id,
            survey_id=survey_id,
            survey_kek=original_kek,
            user_email=user_email,
            platform_custodian_component=self.custodian_component,
        )

        # Step 3: User forgets credentials (simulated - they can't decrypt)

        # Step 4: Admin verifies identity via email
        email_verified = client.verify_user_identity_email(
            user_id=user_id,
            claimed_email=user_email,
            platform_custodian_component=self.custodian_component,
        )

        assert email_verified is True, "Email should be verified"

        # Step 5: Admin recovers KEK
        admin_id = 1
        recovered_kek = client.recover_user_survey_kek(
            user_id=user_id,
            survey_id=survey_id,
            admin_id=admin_id,
            verification_notes="Identity confirmed via NHS email + video call showing ID badge",
            platform_custodian_component=self.custodian_component,
        )

        assert recovered_kek == original_kek, "Recovered KEK should match original"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_organization_level_recovery_flow(self, mock_settings):
        """
        Test organization-level recovery:
        1. Organization sets up keys
        2. Team member creates encrypted survey
        3. Survey KEK is encrypted with org key
        4. Organization owner can recover
        """
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        # Step 1: Organization sets up (owner knows passphrase)
        org_id = 10
        org_passphrase = "secure-org-master-password-2024"

        org_key = client.derive_organization_key(
            org_id=org_id,
            org_owner_passphrase=org_passphrase,
            platform_custodian_component=self.custodian_component,
        )

        # Step 2: Team member creates encrypted survey
        survey_kek = os.urandom(32)
        survey_id = 500
        vault_path = f"organizations/{org_id}/surveys/{survey_id}/kek"

        # Step 3: Survey KEK encrypted with org key
        client.encrypt_survey_kek(
            survey_kek=survey_kek,
            hierarchy_key=org_key,
            vault_path=vault_path,
        )

        # Step 4: Organization owner recovers (they know the passphrase)
        # Re-derive org key (simulating different session)
        recovered_org_key = client.derive_organization_key(
            org_id=org_id,
            org_owner_passphrase=org_passphrase,
            platform_custodian_component=self.custodian_component,
        )

        recovered_kek = client.decrypt_survey_kek(
            vault_path=vault_path,
            hierarchy_key=recovered_org_key,
        )

        assert (
            recovered_kek == survey_kek
        ), "Org owner should be able to recover survey KEK"

    @patch("checktick_app.surveys.vault_client.settings")
    def test_multiple_surveys_same_user(self, mock_settings):
        """Test that multiple surveys for same user can be recovered independently."""
        mock_settings.VAULT_ADDR = "https://vault.example.com"
        mock_settings.VAULT_ROLE_ID = "test-role"
        mock_settings.VAULT_SECRET_ID = "test-secret"

        client = VaultClient()
        client._client = self.mock_hvac

        user_id = 42
        user_email = "user@example.com"

        # Create multiple surveys with different KEKs
        survey_keks = {
            1001: os.urandom(32),
            1002: os.urandom(32),
            1003: os.urandom(32),
        }

        # Escrow all KEKs
        for survey_id, kek in survey_keks.items():
            client.escrow_user_survey_kek(
                user_id=user_id,
                survey_id=survey_id,
                survey_kek=kek,
                user_email=user_email,
                platform_custodian_component=self.custodian_component,
            )

        # Recover each survey independently
        for survey_id, original_kek in survey_keks.items():
            recovered_kek = client.recover_user_survey_kek(
                user_id=user_id,
                survey_id=survey_id,
                admin_id=1,
                verification_notes=f"Recovery test for survey {survey_id}",
                platform_custodian_component=self.custodian_component,
            )

            assert recovered_kek == original_kek, f"Survey {survey_id} KEK should match"
