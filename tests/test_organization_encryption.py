"""
Tests for organization-level encryption (Option 1: Key Escrow).

This tests the implementation of organization master key encryption
where organization owners/admins can recover surveys from their members.
"""

import os

from django.contrib.auth import get_user_model
import pytest

from checktick_app.surveys.models import (
    AuditLog,
    Organization,
    OrganizationMembership,
    Survey,
)
from checktick_app.surveys.utils import (
    decrypt_kek_with_org_key,
    encrypt_kek_with_org_key,
)

User = get_user_model()


@pytest.fixture
def org_with_master_key():
    """Create an organization with a master key."""
    owner = User.objects.create_user(username="org_owner", email="owner@example.com")
    org = Organization.objects.create(name="Test Org", owner=owner)
    # Generate a 32-byte master key for the organization
    org.encrypted_master_key = os.urandom(32)
    org.save()
    return org


@pytest.fixture
def member_user(org_with_master_key):
    """Create a regular member of the organization."""
    user = User.objects.create_user(username="member", email="member@example.com")
    OrganizationMembership.objects.create(
        organization=org_with_master_key,
        user=user,
        role=OrganizationMembership.Role.CREATOR,
    )
    return user


@pytest.fixture
def admin_user(org_with_master_key):
    """Create an admin member of the organization."""
    user = User.objects.create_user(username="admin", email="admin@example.com")
    OrganizationMembership.objects.create(
        organization=org_with_master_key,
        user=user,
        role=OrganizationMembership.Role.ADMIN,
    )
    return user


@pytest.fixture
def non_member_user():
    """Create a user who is NOT a member of the organization."""
    return User.objects.create_user(username="outsider", email="outsider@example.com")


@pytest.mark.django_db
class TestOrganizationEncryptionUtils:
    """Test organization encryption utility functions."""

    def test_encrypt_and_decrypt_with_org_key(self):
        """Test round-trip encryption/decryption with organization key."""
        # Generate test KEK and organization master key
        kek = os.urandom(32)
        org_key = os.urandom(32)

        # Encrypt KEK with organization key
        encrypted_blob = encrypt_kek_with_org_key(kek, org_key)

        # Verify it's different from original
        assert encrypted_blob != kek
        assert len(encrypted_blob) > 32  # Should include nonce + ciphertext

        # Decrypt and verify we get the original KEK back
        decrypted_kek = decrypt_kek_with_org_key(encrypted_blob, org_key)
        assert decrypted_kek == kek

    def test_decrypt_with_wrong_org_key_fails(self):
        """Test that decryption fails with wrong organization key."""
        from cryptography.exceptions import InvalidTag

        kek = os.urandom(32)
        org_key = os.urandom(32)
        wrong_key = os.urandom(32)

        encrypted_blob = encrypt_kek_with_org_key(kek, org_key)

        with pytest.raises(InvalidTag):
            decrypt_kek_with_org_key(encrypted_blob, wrong_key)

    def test_org_key_must_be_32_bytes(self):
        """Test that organization key must be exactly 32 bytes."""
        kek = os.urandom(32)
        short_key = os.urandom(16)  # Too short

        with pytest.raises(ValueError, match="must be 32 bytes"):
            encrypt_kek_with_org_key(kek, short_key)


@pytest.mark.django_db
class TestSurveyOrganizationEncryption:
    """Test Survey model organization encryption methods."""

    def test_set_org_encryption(self, org_with_master_key, member_user):
        """Test setting up organization encryption on a survey."""
        # Create a survey belonging to the organization
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        # Generate a KEK
        kek = os.urandom(32)

        # Set up organization encryption
        survey.set_org_encryption(kek, org_with_master_key)

        # Verify encrypted_kek_org is set
        assert survey.encrypted_kek_org is not None
        assert len(survey.encrypted_kek_org) > 32  # nonce + ciphertext

        # Verify it's encrypted (not the same as original KEK)
        assert bytes(survey.encrypted_kek_org) != kek

    def test_set_org_encryption_requires_master_key(self, member_user):
        """Test that organization must have a master key."""
        # Create organization without master key
        owner = User.objects.create_user(
            username="no_key_owner", email="nokey@example.com"
        )
        org_no_key = Organization.objects.create(name="No Key Org", owner=owner)

        survey = Survey.objects.create(
            owner=member_user,
            organization=org_no_key,
            name="Test Survey",
            slug="test-survey",
        )

        kek = os.urandom(32)

        with pytest.raises(ValueError, match="does not have a master key"):
            survey.set_org_encryption(kek, org_no_key)

    def test_has_org_encryption(self, org_with_master_key, member_user):
        """Test has_org_encryption() method."""
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Test Survey",
            slug="test-survey",
        )

        # Initially should be False
        assert survey.has_org_encryption() is False

        # After setting up encryption
        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        assert survey.has_org_encryption() is True

    def test_unlock_with_org_key(self, org_with_master_key, member_user):
        """Test unlocking survey with organization master key."""
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Test Survey",
            slug="test-survey",
        )

        # Set up encryption
        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Unlock with organization key
        unlocked_kek = survey.unlock_with_org_key(org_with_master_key)

        # Verify we got the original KEK back
        assert unlocked_kek == kek

    def test_unlock_with_org_key_wrong_organization(
        self, org_with_master_key, member_user
    ):
        """Test that unlock fails if survey doesn't belong to organization."""
        # Create survey in org_with_master_key
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Test Survey",
            slug="test-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Create a different organization
        other_owner = User.objects.create_user(
            username="other_owner", email="other@example.com"
        )
        other_org = Organization.objects.create(name="Other Org", owner=other_owner)
        other_org.encrypted_master_key = os.urandom(32)
        other_org.save()

        # Try to unlock with wrong organization
        unlocked_kek = survey.unlock_with_org_key(other_org)

        # Should return None
        assert unlocked_kek is None

    def test_unlock_without_org_encryption_returns_none(
        self, org_with_master_key, member_user
    ):
        """Test that unlock returns None if survey has no org encryption."""
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Test Survey",
            slug="test-survey",
        )

        # Don't set up org encryption

        # Try to unlock
        unlocked_kek = survey.unlock_with_org_key(org_with_master_key)

        assert unlocked_kek is None


@pytest.mark.django_db
class TestOrganizationEncryptionIntegration:
    """Integration tests for organization encryption in survey creation."""

    def test_survey_creation_with_org_encryption(
        self, org_with_master_key, member_user, client
    ):
        """Test that surveys get organization encryption on creation."""
        # Log in as member
        client.force_login(member_user)

        # Create a survey with encryption
        from checktick_app.surveys.utils import generate_bip39_phrase

        kek = os.urandom(32)
        password = "test_password_123"
        recovery_words = generate_bip39_phrase(12)

        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        # Set up dual encryption (simulating survey creation)
        survey.set_dual_encryption(kek, password, recovery_words)

        # Set up organization encryption
        survey.set_org_encryption(kek, org_with_master_key)

        # Verify all three encryption methods are set
        assert survey.has_dual_encryption() is True
        assert survey.has_org_encryption() is True

        # Verify organization owner can unlock
        unlocked_kek = survey.unlock_with_org_key(org_with_master_key)
        assert unlocked_kek == kek

        # Verify member can unlock with password
        password_unlocked = survey.unlock_with_password(password)
        assert password_unlocked == kek

        # Verify member can unlock with recovery phrase
        recovery_phrase = " ".join(recovery_words)
        recovery_unlocked = survey.unlock_with_recovery(recovery_phrase)
        assert recovery_unlocked == kek

    def test_multiple_surveys_in_same_org(self, org_with_master_key, member_user):
        """Test that multiple surveys can use the same org master key."""
        kek1 = os.urandom(32)
        kek2 = os.urandom(32)

        survey1 = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Survey 1",
            slug="survey-1",
        )
        survey1.set_org_encryption(kek1, org_with_master_key)

        survey2 = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Survey 2",
            slug="survey-2",
        )
        survey2.set_org_encryption(kek2, org_with_master_key)

        # Both should be unlockable with org key
        assert survey1.unlock_with_org_key(org_with_master_key) == kek1
        assert survey2.unlock_with_org_key(org_with_master_key) == kek2

        # Each should unlock to its own KEK
        assert kek1 != kek2


@pytest.mark.django_db
class TestOrganizationMasterKeyFields:
    """Test the new Survey model fields for organization encryption."""

    def test_survey_has_org_encryption_fields(self):
        """Test that Survey model has the new organization encryption fields."""
        owner = User.objects.create_user(username="owner", email="owner@example.com")
        survey = Survey.objects.create(
            owner=owner,
            name="Test Survey",
            slug="test-survey",
        )

        # Check that all fields exist and are None/blank by default
        assert hasattr(survey, "encrypted_kek_org")
        assert hasattr(survey, "recovery_threshold")
        assert hasattr(survey, "recovery_shares_count")

        assert survey.encrypted_kek_org is None
        assert survey.recovery_threshold is None
        assert survey.recovery_shares_count is None

    def test_organization_has_master_key_field(self):
        """Test that Organization model has encrypted_master_key field."""
        owner = User.objects.create_user(username="owner", email="owner@example.com")
        org = Organization.objects.create(name="Test Org", owner=owner)

        assert hasattr(org, "encrypted_master_key")
        assert org.encrypted_master_key is None

        # Set a master key
        org.encrypted_master_key = os.urandom(32)
        org.save()

        # Reload and verify it persisted
        org.refresh_from_db()
        assert org.encrypted_master_key is not None
        assert len(org.encrypted_master_key) == 32


@pytest.mark.django_db
class TestAuditLogKeyRecovery:
    """Test audit logging for organization key recovery."""

    def test_audit_log_has_key_recovery_action(self):
        """Test that AuditLog.Action has KEY_RECOVERY option."""
        assert hasattr(AuditLog.Action, "KEY_RECOVERY")
        assert AuditLog.Action.KEY_RECOVERY == "key_recovery"


@pytest.mark.django_db
class TestOrganizationKeyRecoveryView:
    """Test the organization key recovery view."""

    def test_org_owner_can_access_recovery_page(
        self, org_with_master_key, member_user, client
    ):
        """Test that organisation owner can access the recovery page."""
        # Create a survey belonging to a member
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        # Set up organization encryption
        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        assert response.status_code == 200
        assert "Organisation Key Recovery" in response.content.decode()
        assert survey.owner.username in response.content.decode()


@pytest.mark.django_db
class TestOrganizationKeyRecoverySecurityChecks:
    """Test security protections for organization key recovery."""

    def test_regular_member_cannot_access_recovery(
        self, org_with_master_key, member_user, client
    ):
        """Test that regular organisation members cannot perform key recovery."""
        # Create a second member (not owner, not admin)
        other_member = User.objects.create_user(
            username="other_member", email="other@example.com"
        )
        OrganizationMembership.objects.create(
            organization=org_with_master_key,
            user=other_member,
            role=OrganizationMembership.Role.CREATOR,  # Regular member role
        )

        # Create a survey by first member
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as other_member (regular member, not admin)
        client.force_login(other_member)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should be blocked
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any("Only organization owners and admins" in str(m) for m in messages)

        # Verify no audit log was created
        assert (
            AuditLog.objects.filter(
                action=AuditLog.Action.KEY_RECOVERY, survey=survey
            ).count()
            == 0
        )

    def test_viewer_role_cannot_access_recovery(
        self, org_with_master_key, member_user, client
    ):
        """Test that organization viewers cannot perform key recovery."""
        # Create a viewer (lowest permission level)
        viewer = User.objects.create_user(username="viewer", email="viewer@example.com")
        OrganizationMembership.objects.create(
            organization=org_with_master_key,
            user=viewer,
            role=OrganizationMembership.Role.VIEWER,
        )

        # Create a survey
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as viewer
        client.force_login(viewer)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should be blocked
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any("Only organization owners and admins" in str(m) for m in messages)

    def test_user_from_different_org_cannot_access_recovery(
        self, org_with_master_key, member_user, client
    ):
        """Test that admins from different organizations cannot perform key recovery."""
        # Create a different organization with its own owner
        other_owner = User.objects.create_user(
            username="other_org_owner", email="other_owner@example.com"
        )
        other_org = Organization.objects.create(name="Other Org", owner=other_owner)
        other_org.encrypted_master_key = os.urandom(32)
        other_org.save()

        # Create a survey in the FIRST organization
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as owner of DIFFERENT organization
        client.force_login(other_owner)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should be blocked
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any("Only organization owners and admins" in str(m) for m in messages)

    def test_non_authenticated_user_redirected(
        self, org_with_master_key, member_user, client
    ):
        """Test that unauthenticated users are redirected to login."""
        # Create a survey
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Don't log in - try to access as anonymous user
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should redirect to login page
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_cannot_recover_survey_without_org_encryption(
        self, org_with_master_key, member_user, client
    ):
        """Test that recovery is blocked if survey doesn't have org encryption."""
        # Create survey WITHOUT org encryption
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should be blocked
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any(
            "does not have organization-level encryption" in str(m) for m in messages
        )

    def test_cannot_perform_recovery_without_confirmation_text(
        self, org_with_master_key, member_user, client
    ):
        """Test that POST requests require exact confirmation text."""
        # Create and encrypt survey
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Try various incorrect confirmations
        for wrong_confirm in ["", "yes", "confirm", "RECOVER", "Recover", "rec"]:
            response = client.post(
                f"/surveys/{survey.slug}/organization-recovery/",
                {"confirm": wrong_confirm},
            )

            # Should stay on same page with error
            assert response.status_code == 200

            # No audit log should be created
            assert (
                AuditLog.objects.filter(
                    action=AuditLog.Action.KEY_RECOVERY, survey=survey
                ).count()
                == 0
            )

        # Only exact "recover" should work
        response = client.post(
            f"/surveys/{survey.slug}/organization-recovery/",
            {"confirm": "recover"},
        )
        assert response.status_code == 302  # Redirect on success
        assert (
            AuditLog.objects.filter(
                action=AuditLog.Action.KEY_RECOVERY, survey=survey
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestOrganizationKeyRecoveryAuditTrail:
    """Test audit logging for organization key recovery."""

    def test_audit_log_records_all_details(
        self, org_with_master_key, member_user, client
    ):
        """Test that audit log captures all important details."""
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Perform recovery as owner
        client.force_login(org_with_master_key.owner)
        client.post(
            f"/surveys/{survey.slug}/organization-recovery/",
            {"confirm": "recover"},
        )

        # Check audit log details
        audit_log = AuditLog.objects.get(
            action=AuditLog.Action.KEY_RECOVERY, survey=survey
        )

        assert audit_log.actor == org_with_master_key.owner
        assert audit_log.scope == AuditLog.Scope.SURVEY
        assert audit_log.organization == org_with_master_key
        assert audit_log.target_user == member_user
        assert audit_log.metadata["recovery_method"] == "organization_master_key"
        assert audit_log.metadata["survey_owner"] == member_user.username
        assert audit_log.metadata["org_role"] == "owner"
        assert audit_log.created_at is not None

    def test_admin_recovery_logged_with_admin_role(
        self, org_with_master_key, member_user, admin_user, client
    ):
        """Test that admin recoveries are logged with correct role."""
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Perform recovery as admin (not owner)
        client.force_login(admin_user)
        client.post(
            f"/surveys/{survey.slug}/organization-recovery/",
            {"confirm": "recover"},
        )

        # Check audit log shows admin role
        audit_log = AuditLog.objects.get(
            action=AuditLog.Action.KEY_RECOVERY, survey=survey
        )

        assert audit_log.actor == admin_user
        assert audit_log.metadata["org_role"] == "admin"


@pytest.mark.django_db
class TestOrganizationKeyRecoveryIntegration:
    """Integration tests for organization key recovery view."""

    def test_org_admin_can_access_recovery_page(
        self, org_with_master_key, member_user, admin_user, client
    ):
        """Test that organisation admin can access the recovery page."""
        # Create a survey belonging to a member
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        # Set up organization encryption
        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as organization admin
        client.force_login(admin_user)

        # Access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        assert response.status_code == 200
        assert "Organisation Admin" in response.content.decode()

    def test_non_admin_cannot_access_recovery_page(
        self, org_with_master_key, member_user, non_member_user, client
    ):
        """Test that non-admin users cannot access recovery page."""
        # Create a survey
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as non-member
        client.force_login(non_member_user)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should redirect with error
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any("Only organization owners and admins" in str(m) for m in messages)

    def test_survey_owner_redirected_to_regular_unlock(
        self, org_with_master_key, member_user, client
    ):
        """Test that survey owner is redirected to regular unlock page."""
        # Create a survey owned by the logged-in user
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="My Survey",
            slug="my-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as survey owner (who is also a member)
        client.force_login(member_user)

        # Try to access recovery page for own survey
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should redirect (either to unlock or dashboard)
        assert response.status_code == 302
        # Should have a redirect message (but we don't need to check exact text)
        # The view redirects survey owners to the unlock page

    def test_successful_organization_key_recovery(
        self, org_with_master_key, member_user, client
    ):
        """Test successful organization key recovery with audit logging."""
        # Create and encrypt survey
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Perform recovery
        response = client.post(
            f"/surveys/{survey.slug}/organization-recovery/",
            {"confirm": "recover"},
        )

        # Should redirect to dashboard
        assert response.status_code == 302
        assert response.url == f"/surveys/{survey.slug}/dashboard/"

        # Check audit log was created
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.Action.KEY_RECOVERY,
            survey=survey,
            actor=org_with_master_key.owner,
        )
        assert audit_logs.count() == 1

        audit_log = audit_logs.first()
        assert audit_log.organization == org_with_master_key
        assert audit_log.target_user == member_user
        assert audit_log.metadata["recovery_method"] == "organization_master_key"
        assert audit_log.metadata["survey_owner"] == member_user.username
        assert audit_log.metadata["org_role"] == "owner"

        # Check session contains recovery credentials
        session = client.session
        assert session.get("unlock_method") == "organization_recovery"
        assert session.get("unlock_survey_slug") == survey.slug

    def test_recovery_requires_confirmation_text(
        self, org_with_master_key, member_user, client
    ):
        """Test that recovery requires typing 'recover' to confirm."""
        # Create and encrypt survey
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Try to recover without correct confirmation
        response = client.post(
            f"/surveys/{survey.slug}/organization-recovery/",
            {"confirm": "wrong"},
        )

        # Should stay on same page with error
        assert response.status_code == 200
        messages = list(response.wsgi_request._messages)
        assert any('type "recover"' in str(m) for m in messages)

        # No audit log should be created
        assert (
            AuditLog.objects.filter(
                action=AuditLog.Action.KEY_RECOVERY, survey=survey
            ).count()
            == 0
        )

    def test_recovery_fails_without_org_encryption(
        self, org_with_master_key, member_user, client
    ):
        """Test that recovery fails if survey doesn't have org encryption."""
        # Create survey without org encryption
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should redirect with error
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any(
            "does not have organization-level encryption" in str(m) for m in messages
        )

    def test_recovery_fails_for_non_org_survey(
        self, org_with_master_key, member_user, client
    ):
        """Test that recovery fails if survey doesn't belong to organization."""
        # Create survey without organization
        survey = Survey.objects.create(
            owner=member_user, name="Personal Survey", slug="personal-survey"
        )

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Try to access recovery page
        response = client.get(f"/surveys/{survey.slug}/organization-recovery/")

        # Should redirect with error
        assert response.status_code == 302
        messages = list(response.wsgi_request._messages)
        assert any("does not belong to an organization" in str(m) for m in messages)

    def test_recovered_survey_can_be_accessed(
        self, org_with_master_key, member_user, client
    ):
        """Test that after recovery, survey data can be accessed."""
        from checktick_app.surveys.utils import generate_bip39_phrase

        # Create survey with full encryption
        survey = Survey.objects.create(
            owner=member_user,
            organization=org_with_master_key,
            name="Member Survey",
            slug="member-survey",
        )

        kek = os.urandom(32)
        password = "test_password_123"
        recovery_words = generate_bip39_phrase(12)

        # Set up all encryption methods
        survey.set_dual_encryption(kek, password, recovery_words)
        survey.set_org_encryption(kek, org_with_master_key)

        # Log in as organization owner
        client.force_login(org_with_master_key.owner)

        # Perform recovery
        response = client.post(
            f"/surveys/{survey.slug}/organization-recovery/",
            {"confirm": "recover"},
            follow=True,
        )

        # Should be able to access dashboard
        assert response.status_code == 200
        assert "Member Survey" in response.content.decode()

        # Verify session has unlock credentials
        from checktick_app.surveys.views import get_survey_key_from_session

        recovered_kek = get_survey_key_from_session(response.wsgi_request, survey.slug)
        assert recovered_kek == kek
