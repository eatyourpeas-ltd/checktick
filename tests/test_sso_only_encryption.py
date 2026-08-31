"""
Tests for SSO-only encryption workflows.

These tests verify the new SSO-only encryption strategy:
- Organization + SSO: Auto-encrypted, no password/recovery needed
- Individual + SSO: Choice between SSO-only or SSO+recovery
- Password users: Traditional password + recovery (unchanged)
"""

import os

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from checktick_app.core.models import UserOIDC
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

User = get_user_model()
TEST_PASSWORD = "x"


def add_patient_data_group(survey):
    """Helper to add a patient data group to a survey (triggers encryption requirement)."""
    group = QuestionGroup.objects.create(
        name="Patient Details",
        owner=survey.owner,
        schema={
            "template": "patient_details_encrypted",
            "fields": ["first_name", "surname", "date_of_birth", "hospital_number"],
        },
    )
    survey.question_groups.add(group)
    return group


class TestOrganizationSSORAutoEncryption(TestCase):
    """Test auto-encryption for organization members using SSO."""

    def setUp(self):
        """Set up test data."""
        # Create organization owner
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password=TEST_PASSWORD
        )

        # Create organization with master key
        self.org = Organization.objects.create(
            name="Test Org",
            owner=self.owner,
        )
        # Set up organization master key (directly, no method needed)
        self.org.encrypted_master_key = os.urandom(32)
        self.org.save()

        # Create SSO user who is org member
        self.sso_user = User.objects.create_user(
            username="ssouser", email="sso@example.com", password=TEST_PASSWORD
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.sso_user,
            role=OrganizationMembership.Role.CREATOR,
        )

        # Add OIDC record for SSO user
        UserOIDC.get_or_create_for_user(
            user=self.sso_user,
            provider="google",
            subject="google-123",
            email_verified=True,
        )

        self.client = Client()

    def test_org_sso_user_auto_encrypts_on_first_publish(self):
        """Organization SSO users should auto-encrypt without setup page."""
        # Login as SSO user
        self.client.login(username="ssouser", password=TEST_PASSWORD)

        # Create draft survey in organization
        survey = Survey.objects.create(
            name="Org SSO Survey",
            slug="org-sso-survey",
            owner=self.sso_user,
            organization=self.org,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        # Add a question (required for publish)
        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # Attempt to publish
        url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        response = self.client.post(
            url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Should NOT redirect to encryption setup (auto-encrypted)
        # Should redirect to dashboard instead
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard/", response.url)

        # Verify survey is published
        survey.refresh_from_db()
        self.assertEqual(survey.status, Survey.Status.PUBLISHED)

        # Verify encryption was set up (both OIDC and org)
        self.assertTrue(survey.has_oidc_encryption())
        self.assertTrue(survey.has_org_encryption())
        self.assertTrue(survey.has_any_encryption())

        # Verify NO password/recovery encryption
        self.assertFalse(survey.has_dual_encryption())
        self.assertIsNone(survey.encrypted_kek_password)
        self.assertIsNone(survey.encrypted_kek_recovery)

    def test_org_sso_user_sees_success_message(self):
        """Should see success message indicating auto-encryption."""
        self.client.login(username="ssouser", password=TEST_PASSWORD)

        survey = Survey.objects.create(
            name="Org SSO Survey",
            slug="org-sso-survey2",
            owner=self.sso_user,
            organization=self.org,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        response = self.client.post(
            url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
            follow=True,
        )

        # Should see success message about auto-encryption
        messages = list(response.context["messages"])
        self.assertTrue(
            any("automatically" in str(m).lower() for m in messages),
            f"Expected auto-encryption message, got: {[str(m) for m in messages]}",
        )


class TestIndividualSSOEncryptionChoice(TestCase):
    """Test encryption choice for individual users using SSO."""

    def setUp(self):
        """Set up test data."""
        # Create individual SSO user (no organization)
        self.user = User.objects.create_user(
            username="ssouser", email="sso@example.com", password=TEST_PASSWORD
        )

        # Add OIDC record
        UserOIDC.get_or_create_for_user(
            user=self.user,
            provider="google",
            subject="google-456",
            email_verified=True,
        )

        self.client = Client()
        self.client.login(username="ssouser", password=TEST_PASSWORD)

    def test_individual_sso_user_redirected_to_encryption_setup(self):
        """Individual SSO users should see encryption setup page with choices."""
        survey = Survey.objects.create(
            name="Individual SSO Survey",
            slug="individual-sso-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # Attempt to publish
        url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        response = self.client.post(
            url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Should redirect to encryption setup page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/encryption/setup"))

    def test_sso_only_choice_creates_oidc_encryption_only(self):
        """Choosing SSO-only should create OIDC encryption without recovery."""
        survey = Survey.objects.create(
            name="SSO Only Survey",
            slug="sso-only-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # First, trigger encryption setup by attempting to publish
        publish_url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        self.client.post(
            publish_url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Now submit encryption setup with SSO-only choice
        setup_url = reverse("surveys:encryption_setup", kwargs={"slug": survey.slug})
        response = self.client.post(
            setup_url,
            {
                "encryption_choice": "sso_only",
            },
        )

        # Should redirect to dashboard (no recovery phrase display)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard/", response.url)

        # Verify encryption setup
        survey.refresh_from_db()
        self.assertTrue(survey.has_oidc_encryption())
        self.assertTrue(survey.has_any_encryption())

        # Verify NO password/recovery encryption
        self.assertFalse(survey.has_dual_encryption())
        self.assertIsNone(survey.encrypted_kek_password)
        self.assertIsNone(survey.encrypted_kek_recovery)

        # Verify survey is published
        self.assertEqual(survey.status, Survey.Status.PUBLISHED)

    def test_sso_recovery_choice_creates_oidc_plus_recovery(self):
        """Choosing SSO+recovery should create OIDC + recovery phrase encryption."""
        survey = Survey.objects.create(
            name="SSO Recovery Survey",
            slug="sso-recovery-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # First, trigger encryption setup
        publish_url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        self.client.post(
            publish_url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Submit encryption setup with SSO+recovery choice
        setup_url = reverse("surveys:encryption_setup", kwargs={"slug": survey.slug})
        response = self.client.post(
            setup_url,
            {
                "encryption_choice": "sso_recovery",
            },
        )

        # Should redirect to encryption display page (shows recovery phrase)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/encryption/display"))

        # Verify encryption setup
        survey.refresh_from_db()
        self.assertTrue(survey.has_oidc_encryption())
        self.assertTrue(survey.has_any_encryption())

        # Verify HAS recovery encryption (but not password)
        self.assertIsNotNone(survey.encrypted_kek_recovery)
        self.assertIsNotNone(survey.recovery_code_hint)
        self.assertIsNone(survey.encrypted_kek_password)  # No password!

        # Verify survey is published
        self.assertEqual(survey.status, Survey.Status.PUBLISHED)

    def test_sso_user_must_choose_encryption_option(self):
        """Individual SSO user must select an encryption option."""
        survey = Survey.objects.create(
            name="Choice Required Survey",
            slug="choice-required-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # Trigger encryption setup
        publish_url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        self.client.post(
            publish_url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Submit without choosing an option
        setup_url = reverse("surveys:encryption_setup", kwargs={"slug": survey.slug})
        response = self.client.post(setup_url, {})

        # Should show error and stay on setup page
        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(
            any("select" in str(m).lower() for m in messages),
            "Expected error about selecting encryption option",
        )

        # Survey should NOT be published
        survey.refresh_from_db()
        self.assertEqual(survey.status, Survey.Status.DRAFT)


class TestPasswordUserEncryptionUnchanged(TestCase):
    """Verify password users still get traditional password + recovery encryption."""

    def setUp(self):
        """Set up test data."""
        # Create password user (no OIDC)
        self.user = User.objects.create_user(
            username="passuser", email="pass@example.com", password=TEST_PASSWORD
        )

        self.client = Client()
        self.client.login(username="passuser", password=TEST_PASSWORD)

    def test_password_user_sees_password_form(self):
        """Password users should see traditional password form."""
        survey = Survey.objects.create(
            name="Password Survey",
            slug="password-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # Trigger encryption setup
        publish_url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        self.client.post(
            publish_url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Get encryption setup page
        setup_url = reverse("surveys:encryption_setup", kwargs={"slug": survey.slug})
        response = self.client.get(setup_url)

        self.assertEqual(response.status_code, 200)
        # Should contain password fields
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="password_confirm"')
        # Should NOT contain SSO choice radio buttons
        self.assertNotContains(response, 'name="encryption_choice"')

    def test_password_user_creates_dual_encryption(self):
        """Password users should create password + recovery encryption."""
        survey = Survey.objects.create(
            name="Password Dual Survey",
            slug="password-dual-survey",
            owner=self.user,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # Trigger encryption setup
        publish_url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        self.client.post(
            publish_url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Submit password
        setup_url = reverse("surveys:encryption_setup", kwargs={"slug": survey.slug})
        response = self.client.post(
            setup_url,
            {
                "password": "MySecurePassword123",
                "password_confirm": "MySecurePassword123",
            },
        )

        # Should redirect to encryption display
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/encryption/display"))

        # Verify dual encryption
        survey.refresh_from_db()
        self.assertTrue(survey.has_dual_encryption())
        self.assertTrue(survey.has_any_encryption())
        self.assertIsNotNone(survey.encrypted_kek_password)
        self.assertIsNotNone(survey.encrypted_kek_recovery)


class TestOrganizationPasswordUserEncryption(TestCase):
    """Test organization members using password auth get all encryption paths."""

    def setUp(self):
        """Set up test data."""
        # Create organization owner
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password=TEST_PASSWORD
        )

        # Create organization with master key
        self.org = Organization.objects.create(
            name="Test Org",
            owner=self.owner,
        )
        self.org.encrypted_master_key = os.urandom(32)
        self.org.save()

        # Create password user (no OIDC) who is org member
        self.password_user = User.objects.create_user(
            username="passuser", email="pass@example.com", password=TEST_PASSWORD
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.password_user,
            role=OrganizationMembership.Role.CREATOR,
        )

        self.client = Client()
        self.client.login(username="passuser", password=TEST_PASSWORD)

    def test_org_password_user_creates_all_encryption_paths(self):
        """Org password users should get password + recovery + org encryption."""
        survey = Survey.objects.create(
            name="Org Password Survey",
            slug="org-password-survey",
            owner=self.password_user,
            organization=self.org,
            status=Survey.Status.DRAFT,
        )

        # Add patient data group to trigger encryption requirement
        add_patient_data_group(survey)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Test question",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )

        # Trigger encryption setup
        publish_url = reverse("surveys:publish_update", kwargs={"slug": survey.slug})
        self.client.post(
            publish_url,
            {
                "status": "published",
                "respondent_audience": "staff",
                "visibility": "authenticated",
            },
        )

        # Submit password
        setup_url = reverse("surveys:encryption_setup", kwargs={"slug": survey.slug})
        self.client.post(
            setup_url,
            {
                "password": "MySecurePassword123",
                "password_confirm": "MySecurePassword123",
            },
        )

        # Verify all encryption paths
        survey.refresh_from_db()
        self.assertTrue(survey.has_dual_encryption())
        self.assertTrue(survey.has_org_encryption())
        self.assertTrue(survey.has_any_encryption())
        self.assertIsNotNone(survey.encrypted_kek_password)
        self.assertIsNotNone(survey.encrypted_kek_recovery)
        self.assertIsNotNone(survey.encrypted_kek_org)


class TestSurveyHasAnyEncryption(TestCase):
    """Test the new has_any_encryption() method."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=TEST_PASSWORD
        )

    def test_has_any_encryption_password_only(self):
        """Should return True when only password encryption exists."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey",
            owner=self.user,
        )

        kek = os.urandom(32)
        password = "TestPassword123"
        from checktick_app.surveys.utils import generate_bip39_phrase

        recovery_words = generate_bip39_phrase(12)

        survey.set_dual_encryption(kek, password, recovery_words)

        self.assertTrue(survey.has_any_encryption())

    def test_has_any_encryption_oidc_only(self):
        """Should return True when only OIDC encryption exists."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-oidc",
            owner=self.user,
        )

        # Add OIDC to user
        UserOIDC.get_or_create_for_user(
            user=self.user,
            provider="google",
            subject="google-789",
            email_verified=True,
        )

        kek = os.urandom(32)
        survey.set_oidc_encryption(kek, self.user)

        self.assertTrue(survey.has_any_encryption())

    def test_has_any_encryption_org_only(self):
        """Should return True when only org encryption exists."""
        org = Organization.objects.create(
            name="Test Org",
            owner=self.user,
        )
        org.encrypted_master_key = os.urandom(32)
        org.save()

        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-org",
            owner=self.user,
            organization=org,
        )

        kek = os.urandom(32)
        survey.set_org_encryption(kek, org)

        self.assertTrue(survey.has_any_encryption())

    def test_has_any_encryption_none(self):
        """Should return False when no encryption exists."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-none",
            owner=self.user,
        )

        self.assertFalse(survey.has_any_encryption())
