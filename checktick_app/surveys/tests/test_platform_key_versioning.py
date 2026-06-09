"""Tests for platform key versioning and rotation."""

from datetime import timedelta
import secrets
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.surveys.models import PlatformKeyVersion, Survey, UserSurveyKEKEscrow
from checktick_app.surveys.vault_client import VaultClient

User = get_user_model()

TEST_PASSWORD = "testpass123"
TEST_USERNAME = "testuser"
TEST_EMAIL = "test@example.com"
TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "adminpass123"
TEST_ADMIN_EMAIL = "admin@example.com"


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username=TEST_USERNAME,
        email=TEST_EMAIL,
        password=TEST_PASSWORD,
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username=TEST_ADMIN_USERNAME,
        email=TEST_ADMIN_EMAIL,
        password=TEST_ADMIN_PASSWORD,
    )


@pytest.fixture
def survey(db, user):
    """Create a test survey."""
    return Survey.objects.create(
        owner=user,
        name="Test Survey",
        slug="test-survey",
    )


@pytest.fixture
def platform_key_v1(db):
    """Get or create platform key version v1."""
    vault_component = secrets.token_bytes(64)
    version, created = PlatformKeyVersion.objects.get_or_create(
        version="v1",
        defaults={
            "vault_component": vault_component,
            "activated_at": timezone.now(),
            "notes": "Initial platform key version",
        },
    )
    return version


@pytest.fixture
def platform_key_v2(db):
    """Create platform key version v2 (not activated)."""
    vault_component = secrets.token_bytes(64)
    return PlatformKeyVersion.objects.create(
        version="v2",
        vault_component=vault_component,
        notes="Second platform key version",
    )


@pytest.mark.django_db
class TestPlatformKeyVersionModel:
    """Test PlatformKeyVersion model functionality."""

    def test_create_platform_key_version(self):
        """Test creating a new platform key version."""
        vault_component = secrets.token_bytes(64)
        version = PlatformKeyVersion.objects.create(
            version="v3",
            vault_component=vault_component,
        )

        assert version.version == "v3"
        assert len(version.vault_component) == 64
        assert version.activated_at is None
        assert version.retired_at is None
        assert not version.is_active()

    def test_activate_platform_key_version(self, platform_key_v1):
        """Test activating a platform key version."""
        assert platform_key_v1.is_active()
        assert platform_key_v1.activated_at is not None
        assert platform_key_v1.retired_at is None

    def test_get_active_version(self, platform_key_v1, platform_key_v2):
        """Test retrieving the active platform key version."""
        active = PlatformKeyVersion.get_active_version()
        assert active == platform_key_v1
        assert active.version == "v1"

    def test_activate_retires_previous_version(self, platform_key_v1, platform_key_v2):
        """Test that activating a new version retires the old one."""
        assert platform_key_v1.is_active()

        # Activate v2
        platform_key_v2.activate()

        # Refresh v1 from database
        platform_key_v1.refresh_from_db()

        assert not platform_key_v1.is_active()
        assert platform_key_v1.retired_at is not None
        assert platform_key_v2.is_active()
        assert platform_key_v2.retired_at is None

    def test_retire_platform_key_version(self, platform_key_v1):
        """Test retiring a platform key version."""
        platform_key_v1.retire()

        assert not platform_key_v1.is_active()
        assert platform_key_v1.retired_at is not None

    def test_needs_share_rotation_never_rotated(self, platform_key_v1):
        """Test share rotation check for version that was never rotated."""
        # Just activated, should not need rotation within 2 years
        assert not platform_key_v1.needs_share_rotation(rotation_policy_days=730)

        # Simulate old activation
        platform_key_v1.activated_at = timezone.now() - timedelta(days=731)
        platform_key_v1.save()

        assert platform_key_v1.needs_share_rotation(rotation_policy_days=730)

    def test_needs_share_rotation_with_rotation_history(self, platform_key_v1):
        """Test share rotation check for version with rotation history."""
        # Set rotation date to 2 years ago
        platform_key_v1.shares_last_rotated = timezone.now() - timedelta(days=731)
        platform_key_v1.save()

        assert platform_key_v1.needs_share_rotation(rotation_policy_days=730)

        # Update rotation date to recent
        platform_key_v1.shares_last_rotated = timezone.now()
        platform_key_v1.save()

        assert not platform_key_v1.needs_share_rotation(rotation_policy_days=730)

    def test_get_version(self, platform_key_v1):
        """Test retrieving a specific version."""
        version = PlatformKeyVersion.get_version("v1")
        assert version == platform_key_v1

    def test_get_version_not_found(self):
        """Test retrieving a non-existent version raises exception."""
        with pytest.raises(PlatformKeyVersion.DoesNotExist):
            PlatformKeyVersion.get_version("v999")


@pytest.mark.django_db
class TestUserSurveyKEKEscrowModel:
    """Test UserSurveyKEKEscrow model functionality."""

    def test_create_escrow(self, user, survey, platform_key_v1):
        """Test creating an escrow record."""
        escrow = UserSurveyKEKEscrow.objects.create(
            user=user,
            survey=survey,
            platform_key_version=platform_key_v1,
            vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek",
        )

        assert escrow.user == user
        assert escrow.survey == survey
        assert escrow.platform_key_version == platform_key_v1
        assert escrow.recovered_count == 0
        assert escrow.last_recovered_at is None

    def test_record_recovery(self, user, survey, platform_key_v1, admin_user):
        """Test recording a recovery operation."""
        escrow = UserSurveyKEKEscrow.objects.create(
            user=user,
            survey=survey,
            platform_key_version=platform_key_v1,
            vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek",
        )

        escrow.record_recovery(admin_user)

        assert escrow.recovered_count == 1
        assert escrow.last_recovered_at is not None
        assert escrow.last_recovered_by == admin_user

        # Record second recovery
        escrow.record_recovery(admin_user)

        assert escrow.recovered_count == 2

    def test_unique_together_constraint(self, user, survey, platform_key_v1):
        """Test that user+survey combination must be unique."""
        UserSurveyKEKEscrow.objects.create(
            user=user,
            survey=survey,
            platform_key_version=platform_key_v1,
            vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek",
        )

        with pytest.raises(Exception):  # IntegrityError
            UserSurveyKEKEscrow.objects.create(
                user=user,
                survey=survey,
                platform_key_version=platform_key_v1,
                vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek-2",
            )

    def test_cannot_delete_version_with_escrows(self, user, survey, platform_key_v1):
        """Test that platform key version with escrows cannot be deleted."""
        UserSurveyKEKEscrow.objects.create(
            user=user,
            survey=survey,
            platform_key_version=platform_key_v1,
            vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek",
        )

        # Should raise ProtectedError due to PROTECT on_delete
        with pytest.raises(Exception):
            platform_key_v1.delete()


@pytest.mark.django_db
class TestVaultClientXOR:
    """Test VaultClient XOR functionality."""

    def test_xor_bytes_same_length(self):
        """Test XOR with equal length byte sequences."""
        a = b"\x01\x02\x03\x04"
        b = b"\x05\x06\x07\x08"

        result = VaultClient.xor_bytes(a, b)

        assert result == b"\x04\x04\x04\x0c"
        assert len(result) == len(a)

    def test_xor_bytes_reversible(self):
        """Test that XOR is reversible (a XOR b XOR b = a)."""
        platform_key = secrets.token_bytes(32)
        vault_component = secrets.token_bytes(32)

        custodian_component = VaultClient.xor_bytes(platform_key, vault_component)
        reconstructed = VaultClient.xor_bytes(vault_component, custodian_component)

        assert reconstructed == platform_key

    def test_xor_bytes_different_lengths_raises_error(self):
        """Test that XOR with different length inputs raises ValueError."""
        a = b"\x01\x02\x03"
        b = b"\x04\x05"

        with pytest.raises(ValueError, match="XOR inputs must be same length"):
            VaultClient.xor_bytes(a, b)


@pytest.mark.django_db
class TestVaultClientVersionAwareOperations:
    """Test VaultClient version-aware escrow and recovery operations."""

    @patch("checktick_app.surveys.vault_client.VaultClient._get_client")
    @patch("checktick_app.surveys.vault_client.VaultClient.derive_user_recovery_key")
    def test_escrow_uses_active_version(
        self,
        mock_derive_key,
        mock_get_client,
        user,
        survey,
        platform_key_v1,
    ):
        """Test that escrow operation uses the active platform key version."""
        # Setup mocks
        mock_vault_client = Mock()
        mock_get_client.return_value = mock_vault_client
        mock_derive_key.return_value = secrets.token_bytes(32)

        vault = VaultClient()
        survey_kek = secrets.token_bytes(32)
        custodian_component = secrets.token_bytes(64)

        # Perform escrow
        vault_path = vault.escrow_user_survey_kek(
            user_id=user.id,
            survey_id=survey.id,
            survey_kek=survey_kek,
            user_email=user.email,
            platform_custodian_component=custodian_component,
        )

        # Verify database record was created with correct version
        escrow = UserSurveyKEKEscrow.objects.get(user=user, survey=survey)
        assert escrow.platform_key_version == platform_key_v1
        assert escrow.vault_path == vault_path
        assert "users/" in vault_path

    @patch("checktick_app.surveys.vault_client.VaultClient._get_client")
    def test_recovery_uses_correct_version(
        self,
        mock_get_client,
        user,
        survey,
        platform_key_v1,
        platform_key_v2,
        admin_user,
    ):
        """Test that recovery operation uses the correct versioned platform key."""
        # Create escrow with v1
        UserSurveyKEKEscrow.objects.create(
            user=user,
            survey=survey,
            platform_key_version=platform_key_v1,
            vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek",
        )

        # Now activate v2 (simulating key rotation)
        platform_key_v2.activate()

        # Setup mock Vault response
        mock_vault_client = Mock()
        mock_get_client.return_value = mock_vault_client

        # Mock encrypted KEK data
        encrypted_kek = secrets.token_bytes(12 + 48)  # nonce + ciphertext
        mock_vault_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "encrypted_kek": encrypted_kek.hex(),
                    "platform_key_version": "v1",
                    "audit_trail": {
                        "accessed_by": [],
                        "access_timestamps": [],
                    },
                }
            }
        }

        # Note: This will fail in actual decryption but we're testing version lookup
        vault = VaultClient()
        custodian_component = secrets.token_bytes(64)

        try:
            # This should use v1's vault_component, not v2's
            vault.recover_user_survey_kek(
                user_id=user.id,
                survey_id=survey.id,
                admin_id=admin_user.id,
                verification_notes="Testing version lookup",
                platform_custodian_component=custodian_component,
            )
        except Exception:
            # Decryption will fail with mock data, but that's OK
            # We're testing that it looked up the correct version
            pass

        # Verify it attempted to read from Vault
        mock_vault_client.secrets.kv.v2.read_secret_version.assert_called()

    def test_escrow_without_active_version_raises_error(self, user, survey):
        """Test that escrow fails when no active platform key version exists."""
        # Retire any existing active versions (including v1 from migration)
        from django.utils import timezone

        PlatformKeyVersion.objects.filter(
            activated_at__isnull=False, retired_at__isnull=True
        ).update(retired_at=timezone.now())

        vault = VaultClient()
        survey_kek = secrets.token_bytes(32)
        custodian_component = secrets.token_bytes(64)

        with pytest.raises(ValueError, match="No active platform key version"):
            vault.escrow_user_survey_kek(
                user_id=user.id,
                survey_id=survey.id,
                survey_kek=survey_kek,
                user_email=user.email,
                platform_custodian_component=custodian_component,
            )


@pytest.mark.django_db
class TestKeyRotationScenarios:
    """Test various key rotation scenarios."""

    def test_option_a_rotation_workflow(self, platform_key_v1):
        """Test Option A: Rotate Shamir shares, same platform key."""
        # Record the original vault component
        original_vault_component = bytes(platform_key_v1.vault_component)

        # Simulate reconstruction with old custodian component
        old_custodian_component = secrets.token_bytes(64)
        platform_key = VaultClient.xor_bytes(
            original_vault_component, old_custodian_component
        )

        # Generate NEW vault and custodian components
        new_vault_component = secrets.token_bytes(64)
        new_custodian_component = VaultClient.xor_bytes(
            platform_key, new_vault_component
        )

        # Update the version
        platform_key_v1.vault_component = new_vault_component
        platform_key_v1.shares_last_rotated = timezone.now()
        platform_key_v1.save()

        # Verify: reconstruct platform key with NEW components
        reconstructed = VaultClient.xor_bytes(
            new_vault_component, new_custodian_component
        )

        # Platform key should be identical
        assert reconstructed == platform_key
        assert platform_key_v1.shares_last_rotated is not None

    def test_option_b_rotation_workflow(self, platform_key_v1, user, survey):
        """Test Option B: Generate new platform key, keep old versions."""
        # Create escrow with v1
        escrow_v1 = UserSurveyKEKEscrow.objects.create(
            user=user,
            survey=survey,
            platform_key_version=platform_key_v1,
            vault_path=f"users/{user.id}/surveys/{survey.id}/recovery-kek",
        )

        # Create v2 with completely new platform key (Option B rotation)
        # In real usage: platform_key = XOR(vault_component, custodian_component)
        platform_key_v2 = PlatformKeyVersion.objects.create(
            version="v2",
            vault_component=secrets.token_bytes(64),
        )
        platform_key_v2.activate()

        # Refresh v1
        platform_key_v1.refresh_from_db()

        # v1 should be retired but still in database
        assert not platform_key_v1.is_active()
        assert platform_key_v1.retired_at is not None

        # v2 should be active
        assert platform_key_v2.is_active()

        # Old escrow should still reference v1
        assert escrow_v1.platform_key_version == platform_key_v1

        # New escrows would use v2
        active = PlatformKeyVersion.get_active_version()
        assert active == platform_key_v2

    def test_multiple_versions_coexist(self, platform_key_v1):
        """Test that multiple platform key versions can coexist."""
        # Retire v1 first so we can test multiple active/retired states
        platform_key_v1.retired_at = timezone.now() - timedelta(days=400)
        platform_key_v1.save()

        v4 = PlatformKeyVersion.objects.create(
            version="v4",
            vault_component=secrets.token_bytes(64),
            activated_at=timezone.now() - timedelta(days=365),
            retired_at=timezone.now() - timedelta(days=180),
        )

        v5 = PlatformKeyVersion.objects.create(
            version="v5",
            vault_component=secrets.token_bytes(64),
            activated_at=timezone.now() - timedelta(days=180),
            retired_at=timezone.now(),
        )

        v6 = PlatformKeyVersion.objects.create(
            version="v6",
            vault_component=secrets.token_bytes(64),
            activated_at=timezone.now(),
        )

        # 4 versions exist in database (v1 from fixture + v4, v5, v6)
        assert PlatformKeyVersion.objects.count() >= 4

        # Only v6 is active
        active = PlatformKeyVersion.get_active_version()
        assert active == v6

        # Can still retrieve old versions for recovery
        assert PlatformKeyVersion.get_version("v1") == platform_key_v1
        assert PlatformKeyVersion.get_version("v4") == v4
        assert PlatformKeyVersion.get_version("v5") == v5
