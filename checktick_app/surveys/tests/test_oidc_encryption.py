"""
Tests for OIDC encryption integration.

These tests verify that OIDC authentication integrates properly with
the survey encryption system, enabling automatic survey unlocking
for SSO users.
"""

import os

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from checktick_app.core.models import UserOIDC
from checktick_app.surveys.models import QuestionGroup, Survey

User = get_user_model()
TEST_PASSWORD = "x"


class TestOIDCEncryption(TestCase):
    """Test OIDC encryption functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=TEST_PASSWORD
        )

        # Create UserOIDC record
        self.oidc_record = UserOIDC.get_or_create_for_user(
            user=self.user,
            provider="google",
            subject="google-12345",
            email_verified=True,
        )[0]

        # Create survey
        self.survey = Survey.objects.create(
            name="Test OIDC Survey", owner=self.user, status=Survey.Status.DRAFT
        )

    def test_set_oidc_encryption(self):
        """Test setting up OIDC encryption on a survey."""
        kek = os.urandom(32)

        # Set up OIDC encryption
        self.survey.set_oidc_encryption(kek, self.user)

        # Verify encryption was set up
        assert self.survey.has_oidc_encryption()
        assert self.survey.encrypted_kek_oidc is not None
        assert len(self.survey.encrypted_kek_oidc) > 0

    def test_unlock_with_oidc(self):
        """Test unlocking survey with OIDC."""
        kek = os.urandom(32)

        # Set up OIDC encryption
        self.survey.set_oidc_encryption(kek, self.user)

        # Unlock with OIDC
        unlocked_kek = self.survey.unlock_with_oidc(self.user)

        # Verify unlocking worked
        assert unlocked_kek is not None
        assert unlocked_kek == kek

    def test_unlock_with_wrong_oidc_user(self):
        """Test that unlocking fails with wrong OIDC identity."""
        kek = os.urandom(32)

        # Set up OIDC encryption with first user
        self.survey.set_oidc_encryption(kek, self.user)

        # Create second user with different OIDC identity
        user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass2"
        )
        UserOIDC.get_or_create_for_user(
            user=user2, provider="azure", subject="azure-67890", email_verified=True
        )

        # Try to unlock with second user
        unlocked_kek = self.survey.unlock_with_oidc(user2)

        # Should fail
        assert unlocked_kek is None

    def test_can_user_unlock_automatically(self):
        """Test automatic unlock capability check."""
        kek = os.urandom(32)

        # Initially no OIDC encryption
        assert not self.survey.can_user_unlock_automatically(self.user)

        # Set up OIDC encryption
        self.survey.set_oidc_encryption(kek, self.user)

        # Now should be able to auto-unlock
        assert self.survey.can_user_unlock_automatically(self.user)

        # Create user without OIDC
        user_no_oidc = User.objects.create_user(
            username="nooidc", email="nooidc@example.com", password=TEST_PASSWORD
        )

        # Should not be able to auto-unlock
        assert not self.survey.can_user_unlock_automatically(user_no_oidc)

    def test_combined_dual_and_oidc_encryption(self):
        """Test that dual encryption and OIDC encryption can coexist."""
        kek = os.urandom(32)
        password = "test_password"
        recovery_words = [
            "abandon",
            "ability",
            "able",
            "about",
            "above",
            "absent",
            "absorb",
            "abstract",
            "absurd",
            "abuse",
            "access",
            "accident",
        ]

        # Set up dual encryption
        self.survey.set_dual_encryption(kek, password, recovery_words)

        # Add OIDC encryption
        self.survey.set_oidc_encryption(kek, self.user)

        # Verify both encryption methods work
        assert self.survey.has_dual_encryption()
        assert self.survey.has_oidc_encryption()

        # Test password unlock
        password_kek = self.survey.unlock_with_password(password)
        assert password_kek == kek

        # Test recovery unlock
        recovery_phrase = " ".join(recovery_words)
        recovery_kek = self.survey.unlock_with_recovery(recovery_phrase)
        assert recovery_kek == kek

        # Test OIDC unlock
        oidc_kek = self.survey.unlock_with_oidc(self.user)
        assert oidc_kek == kek

    def test_oidc_auto_unlock_on_patient_data_survey(self):
        """OIDC users can auto-unlock patient data surveys without a passphrase.

        SSO providers enforce MFA/conditional access at the IdP level, which is
        considered sufficient. A separate passphrase is not required and is not
        enforced by the application.
        """
        # Create a survey with a patient data question group
        patient_group = QuestionGroup.objects.create(
            name="Patient Details",
            owner=self.user,
            schema={
                "template": "patient_details_encrypted",
                "fields": ["first_name", "last_name", "nhs_number", "date_of_birth"],
            },
        )
        patient_survey = Survey.objects.create(
            name="Patient OIDC Survey",
            slug="patient-oidc-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )
        patient_survey.question_groups.add(patient_group)

        # Confirm it detects patient data
        assert patient_survey.collects_patient_data() is True

        kek = os.urandom(32)
        patient_survey.set_oidc_encryption(kek, self.user)

        # OIDC auto-unlock should work regardless of patient data content
        assert patient_survey.can_user_unlock_automatically(self.user) is True
        unlocked_kek = patient_survey.unlock_with_oidc(self.user)
        assert unlocked_kek == kek


class TestOIDCEncryptionViews(TestCase):
    """Test OIDC encryption in views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=TEST_PASSWORD
        )

        # Create UserOIDC record
        self.oidc_record = UserOIDC.get_or_create_for_user(
            user=self.user,
            provider="google",
            subject="google-12345",
            email_verified=True,
        )[0]

    def test_survey_create_with_oidc_encryption(self):
        """Test creating survey with OIDC encryption via form."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("surveys:create"),
            {
                "name": "Test OIDC Survey",
                "encryption_option": "option2",
                "password": "test_password",
                "recovery_phrase": "abandon ability able about above absent absorb abstract absurd abuse access accident",
            },
        )

        # Should redirect on success
        assert response.status_code == 302

        # Check survey was created with OIDC encryption
        survey = Survey.objects.get(name="Test OIDC Survey")
        assert survey.has_dual_encryption()
        assert survey.has_oidc_encryption()

    def test_survey_unlock_with_oidc_automatic(self):
        """Test automatic OIDC unlock in unlock view."""
        # Create survey with OIDC encryption
        survey = Survey.objects.create(
            name="Test OIDC Survey",
            slug="test-oidc-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        kek = os.urandom(32)
        password = "test_password"
        recovery_words = [
            "abandon",
            "ability",
            "able",
            "about",
            "above",
            "absent",
            "absorb",
            "abstract",
            "absurd",
            "abuse",
            "access",
            "accident",
        ]

        survey.set_dual_encryption(kek, password, recovery_words)
        survey.set_oidc_encryption(kek, self.user)

        # Login and access unlock page
        self.client.force_login(self.user)
        response = self.client.get(reverse("surveys:unlock", args=[survey.slug]))

        # Should automatically redirect to dashboard (automatic unlock)
        assert response.status_code == 302
        assert response.url == reverse("surveys:dashboard", args=[survey.slug])

    def test_survey_unlock_template_shows_oidc_status(self):
        """Test that unlock template shows OIDC status correctly."""
        # Create survey with only dual encryption (no OIDC)
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        kek = os.urandom(32)
        password = "test_password"
        recovery_words = [
            "abandon",
            "ability",
            "able",
            "about",
            "above",
            "absent",
            "absorb",
            "abstract",
            "absurd",
            "abuse",
            "access",
            "accident",
        ]

        survey.set_dual_encryption(kek, password, recovery_words)

        # Login and access unlock page
        self.client.force_login(self.user)

        # Clear any existing survey KEK from session to ensure no cached unlocks
        session = self.client.session
        for key in list(session.keys()):
            if key.startswith("survey_kek_"):
                del session[key]
        session.save()

        response = self.client.get(reverse("surveys:unlock", args=[survey.slug]))

        # Should show unlock form (no automatic unlock)
        assert response.status_code == 200
        assert "Unlock this survey using your password" in response.content.decode()
