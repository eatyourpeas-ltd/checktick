"""Tests for tier enforcement in API endpoints."""

from django.contrib.auth import get_user_model
import pytest
from rest_framework.test import APIClient

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import Organization, OrganizationMembership, Survey

User = get_user_model()

TEST_PASSWORD = "x"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def free_user(db):
    """User with FREE tier (default)."""
    user = User.objects.create_user(username="free_user", password=TEST_PASSWORD)
    profile = UserProfile.objects.get(user=user)
    assert profile.account_tier == UserProfile.AccountTier.FREE
    return user


@pytest.fixture
def pro_user(db):
    """User with PRO tier."""
    user = User.objects.create_user(username="pro_user", password=TEST_PASSWORD)
    profile = UserProfile.objects.get(user=user)
    profile.account_tier = UserProfile.AccountTier.PRO
    profile.save()
    return user


@pytest.fixture
def org_user(db):
    """User with ORGANIZATION tier."""
    user = User.objects.create_user(username="org_user", password=TEST_PASSWORD)
    profile = UserProfile.objects.get(user=user)
    profile.account_tier = UserProfile.AccountTier.ORGANIZATION
    profile.save()
    org = Organization.objects.create(name="Test Org", owner=user)
    OrganizationMembership.objects.create(
        organization=org, user=user, role=OrganizationMembership.Role.ADMIN
    )
    return user


@pytest.mark.django_db
class TestSurveyCreationAPI:
    """Test survey creation limits via API."""

    def test_free_user_can_create_first_survey(self, api_client, free_user):
        """FREE tier users can create up to 3 surveys."""
        api_client.force_authenticate(user=free_user)
        response = api_client.post(
            "/api/surveys/",
            {"name": "Test Survey", "slug": "test-survey", "description": "Test"},
        )
        assert response.status_code == 201

    def test_free_user_blocked_after_limit(self, api_client, free_user):
        """FREE tier users cannot create more than 3 surveys."""
        api_client.force_authenticate(user=free_user)

        # Create 3 surveys (limit for FREE tier)
        for i in range(3):
            response = api_client.post(
                "/api/surveys/",
                {
                    "name": f"Survey {i}",
                    "slug": f"survey-{i}",
                    "description": "Test",
                },
            )
            assert response.status_code == 201

        # 4th survey should be blocked
        response = api_client.post(
            "/api/surveys/",
            {"name": "Survey 4", "slug": "survey-4", "description": "Test"},
        )
        assert response.status_code == 403
        assert "limit of 3 surveys" in response.data["detail"].lower()

    def test_pro_user_no_survey_limit(self, api_client, pro_user):
        """PRO tier users have no survey creation limit."""
        api_client.force_authenticate(user=pro_user)

        # Create 5 surveys (more than FREE limit)
        for i in range(5):
            response = api_client.post(
                "/api/surveys/",
                {
                    "name": f"Survey {i}",
                    "slug": f"survey-{i}",
                    "description": "Test",
                },
            )
            assert response.status_code == 201


@pytest.mark.django_db
class TestCollaborationAPI:
    """Test collaboration limits via API."""

    def test_free_user_cannot_add_collaborators(self, api_client, free_user):
        """FREE tier users cannot add collaborators."""
        api_client.force_authenticate(user=free_user)

        # Create an organization and survey
        org = Organization.objects.create(name="Free Org", owner=free_user)
        survey = Survey.objects.create(
            owner=free_user, organization=org, name="Test", slug="test"
        )

        # Try to add a collaborator
        other_user = User.objects.create_user(username="other", password=TEST_PASSWORD)
        response = api_client.post(
            "/api/survey-memberships/",
            {"survey": survey.id, "user": other_user.id, "role": "viewer"},
        )
        assert response.status_code == 403
        # FREE users trying to add viewers get message about Organization tier requirement
        assert "organization tier" in response.data["detail"].lower()

    def test_pro_user_can_add_editors(self, api_client, pro_user):
        """PRO tier users can add editors."""
        api_client.force_authenticate(user=pro_user)

        org = Organization.objects.create(name="Pro Org", owner=pro_user)
        survey = Survey.objects.create(
            owner=pro_user, organization=org, name="Test", slug="test"
        )

        other_user = User.objects.create_user(username="editor", password=TEST_PASSWORD)
        response = api_client.post(
            "/api/survey-memberships/",
            {"survey": survey.id, "user": other_user.id, "role": "editor"},
        )
        assert response.status_code == 201

    def test_pro_user_cannot_add_viewers(self, api_client, pro_user):
        """PRO tier users cannot add viewers (need ORGANIZATION tier)."""
        api_client.force_authenticate(user=pro_user)

        org = Organization.objects.create(name="Pro Org", owner=pro_user)
        survey = Survey.objects.create(
            owner=pro_user, organization=org, name="Test", slug="test"
        )

        other_user = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        response = api_client.post(
            "/api/survey-memberships/",
            {"survey": survey.id, "user": other_user.id, "role": "viewer"},
        )
        assert response.status_code == 403
        assert "organization tier" in response.data["detail"].lower()

    def test_org_user_can_add_viewers(self, api_client, org_user):
        """ORGANIZATION tier users can add viewers."""
        api_client.force_authenticate(user=org_user)

        org = Organization.objects.filter(owner=org_user).first()
        survey = Survey.objects.create(
            owner=org_user, organization=org, name="Test", slug="test"
        )

        other_user = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
        response = api_client.post(
            "/api/survey-memberships/",
            {"survey": survey.id, "user": other_user.id, "role": "viewer"},
        )
        assert response.status_code == 201

    def test_pro_user_limited_to_10_collaborators(self, api_client, pro_user):
        """PRO tier users limited to 10 collaborators per survey."""
        api_client.force_authenticate(user=pro_user)

        org = Organization.objects.create(name="Pro Org", owner=pro_user)
        survey = Survey.objects.create(
            owner=pro_user, organization=org, name="Test", slug="test"
        )

        # Add 10 editors (PRO limit)
        for i in range(10):
            user = User.objects.create_user(
                username=f"editor{i}", password=TEST_PASSWORD
            )
            response = api_client.post(
                "/api/survey-memberships/",
                {"survey": survey.id, "user": user.id, "role": "editor"},
            )
            assert response.status_code == 201

        # 11th should be blocked
        user = User.objects.create_user(username="editor11", password=TEST_PASSWORD)
        response = api_client.post(
            "/api/survey-memberships/",
            {"survey": survey.id, "user": user.id, "role": "editor"},
        )
        assert response.status_code == 403
        assert "10 collaborators" in response.data["detail"].lower()

    def test_org_user_no_collaborator_limit(self, api_client, org_user):
        """ORGANIZATION tier users have no collaborator limit."""
        api_client.force_authenticate(user=org_user)

        org = Organization.objects.filter(owner=org_user).first()
        survey = Survey.objects.create(
            owner=org_user, organization=org, name="Test", slug="test"
        )

        # Add 15 collaborators (more than PRO limit)
        for i in range(15):
            user = User.objects.create_user(
                username=f"collab{i}", password=TEST_PASSWORD
            )
            response = api_client.post(
                "/api/survey-memberships/",
                {"survey": survey.id, "user": user.id, "role": "viewer"},
            )
            assert response.status_code == 201
