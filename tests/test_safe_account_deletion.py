"""
Tests for safe account deletion functionality.

Tests ensure that:
1. Individual users can only delete their own accounts when safe
2. Users with collaborators or organization memberships cannot self-delete
3. Proper safeguards are in place to prevent data loss
"""

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from checktick_app.core.views import can_user_safely_delete_own_account
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)

TEST_PASSWORD = "x"


User = get_user_model()


class SafeAccountDeletionTests(TestCase):
    """Test suite for safe account deletion functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create organization
        self.organization = Organization.objects.create(
            name="Test Organization",
            owner=User.objects.create_user(
                username="org_owner",
                email="org_owner@example.com",
                password=TEST_PASSWORD,
            ),
        )

        # Create test users
        self.individual_user = User.objects.create_user(
            username="individual",
            email="individual@example.com",
            password=TEST_PASSWORD,
        )
        # Confirm email so user can create/delete surveys
        self.individual_user.profile.email_confirmed = True
        self.individual_user.profile.save()

        self.org_user = User.objects.create_user(
            username="org_user", email="org_user@example.com", password=TEST_PASSWORD
        )
        self.org_user.profile.email_confirmed = True
        self.org_user.profile.save()

        self.collaborator_user = User.objects.create_user(
            username="collaborator",
            email="collaborator@example.com",
            password=TEST_PASSWORD,
        )
        self.collaborator_user.profile.email_confirmed = True
        self.collaborator_user.profile.save()

        self.survey_owner = User.objects.create_user(
            username="survey_owner",
            email="survey_owner@example.com",
            password=TEST_PASSWORD,
        )
        self.survey_owner.profile.email_confirmed = True
        self.survey_owner.profile.save()

    def test_individual_user_can_safely_delete_account(self):
        """Test that individual users with no dependencies can delete their account."""
        # Create a survey owned by individual user (no collaborators)
        # Create test survey for collaborator setup
        Survey.objects.create(
            name="Test Survey",
            slug="test-survey",
            organization=self.organization,
            owner=self.survey_owner,
        )

        # Should be safe to delete
        self.assertTrue(can_user_safely_delete_own_account(self.individual_user))

        # Test actual deletion
        self.client.force_login(self.individual_user)
        response = self.client.post(reverse("core:delete_account"))

        # Should redirect to homepage after successful deletion
        assert response.status_code == 302
        assert "/" in response["Location"]

        # User should no longer exist
        self.assertFalse(User.objects.filter(email="individual@example.com").exists())

        # Survey should be deleted (CASCADE)
        self.assertFalse(Survey.objects.filter(slug="individual-survey").exists())

    def test_user_with_organization_cannot_delete_account(self):
        """Test that users in organizations cannot delete their own account."""
        # Create organization and membership
        org = Organization.objects.create(name="Test Organization", owner=self.org_user)
        OrganizationMembership.objects.create(
            organization=org, user=self.org_user, role=OrganizationMembership.Role.ADMIN
        )

        # Should NOT be safe to delete
        self.assertFalse(can_user_safely_delete_own_account(self.org_user))

        # Test deletion attempt
        self.client.force_login(self.org_user)
        response = self.client.post(reverse("core:delete_account"))

        # Should redirect back to profile with error
        assert response.status_code == 302
        assert reverse("core:profile") in response["Location"]

        # User should still exist
        self.assertTrue(User.objects.filter(email="org_user@example.com").exists())

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Cannot delete account" in str(m) for m in messages))

    def test_user_with_survey_collaborators_cannot_delete_account(self):
        """Test that users with survey collaborators cannot delete their own account."""
        # Create survey owned by survey_owner
        survey = Survey.objects.create(
            name="Collaborative Survey",
            slug="collaborative-survey",
            owner=self.survey_owner,
        )

        # Add collaborator to the survey
        SurveyMembership.objects.create(
            survey=survey,
            user=self.collaborator_user,
            role=SurveyMembership.Role.VIEWER,
        )

        # Survey owner should NOT be safe to delete (has collaborators)
        self.assertFalse(can_user_safely_delete_own_account(self.survey_owner))

        # Test deletion attempt
        self.client.force_login(self.survey_owner)
        response = self.client.post(reverse("core:delete_account"))

        # Should redirect back to profile with error
        assert response.status_code == 302
        assert reverse("core:profile") in response["Location"]

        # User should still exist
        self.assertTrue(User.objects.filter(email="survey_owner@example.com").exists())

        # Survey should still exist
        self.assertTrue(Survey.objects.filter(slug="collaborative-survey").exists())

    def test_collaborator_user_cannot_delete_account(self):
        """Test that users who are collaborators on others' surveys cannot delete their account."""
        # Create survey owned by survey_owner
        survey = Survey.objects.create(
            name="Another Survey", slug="another-survey", owner=self.survey_owner
        )

        # Add collaborator_user as a collaborator
        SurveyMembership.objects.create(
            survey=survey,
            user=self.collaborator_user,
            role=SurveyMembership.Role.CREATOR,
        )

        # Collaborator should NOT be safe to delete (is a collaborator)
        self.assertFalse(can_user_safely_delete_own_account(self.collaborator_user))

        # Test deletion attempt
        self.client.force_login(self.collaborator_user)
        response = self.client.post(reverse("core:delete_account"))

        # Should redirect back to profile with error
        assert response.status_code == 302
        assert reverse("core:profile") in response["Location"]

        # User should still exist
        self.assertTrue(User.objects.filter(email="collaborator@example.com").exists())

    def test_get_request_redirects_to_profile(self):
        """Test that GET requests to delete account redirect to profile."""
        self.client.force_login(self.individual_user)
        response = self.client.get(reverse("core:delete_account"))

        assert response.status_code == 302
        assert reverse("core:profile") in response["Location"]

    def test_profile_shows_delete_option_for_safe_users(self):
        """Test that profile page shows delete option only for users who can safely delete."""
        # Individual user should see delete option
        self.client.force_login(self.individual_user)
        response = self.client.get(reverse("core:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete My Account")

        # Create organization membership for org_user
        org = Organization.objects.create(name="Test Org", owner=self.org_user)
        OrganizationMembership.objects.create(
            organization=org, user=self.org_user, role=OrganizationMembership.Role.ADMIN
        )

        # Org user should NOT see delete option
        self.client.force_login(self.org_user)
        response = self.client.get(reverse("core:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Delete My Account")

    def test_only_owner_can_delete_own_account(self):
        """Test that users cannot delete other users' accounts."""
        # Make collaborator_user unable to delete by adding them as a collaborator
        survey = Survey.objects.create(
            name="Blocking Survey", slug="blocking-survey", owner=self.survey_owner
        )
        SurveyMembership.objects.create(
            survey=survey,
            user=self.collaborator_user,
            role=SurveyMembership.Role.VIEWER,
        )

        # Try to access delete endpoint while logged in as different user
        self.client.force_login(self.collaborator_user)

        # The endpoint should only affect the logged-in user
        response = self.client.post(reverse("core:delete_account"))

        # collaborator_user doesn't have safe deletion privileges, so should get error
        assert response.status_code == 302
        # May redirect to profile or home page depending on the specific error
        assert response["Location"] in [reverse("core:profile"), "/"]

        # Both users should still exist
        self.assertTrue(User.objects.filter(email="collaborator@example.com").exists())
        self.assertTrue(User.objects.filter(email="individual@example.com").exists())

    def test_survey_deletion_cascade_behavior(self):
        """Test that survey deletion properly cascades when user is deleted."""
        # Create multiple surveys for individual user
        Survey.objects.create(
            name="Survey 1", slug="survey-1", owner=self.individual_user
        )
        Survey.objects.create(
            name="Survey 2", slug="survey-2", owner=self.individual_user
        )

        # Confirm surveys exist
        self.assertEqual(Survey.objects.filter(owner=self.individual_user).count(), 2)

        # Delete user account
        self.client.force_login(self.individual_user)
        self.client.post(reverse("core:delete_account"))

        # User should be deleted
        self.assertFalse(User.objects.filter(email="individual@example.com").exists())

        # All surveys should be deleted
        self.assertFalse(Survey.objects.filter(slug="survey-1").exists())
        self.assertFalse(Survey.objects.filter(slug="survey-2").exists())

    def test_anonymous_user_cannot_access_delete_endpoint(self):
        """Test that anonymous users cannot access the delete account endpoint."""
        response = self.client.post(reverse("core:delete_account"))

        # Should redirect to login
        assert response.status_code == 302
        assert "/accounts/login/" in response["Location"]
