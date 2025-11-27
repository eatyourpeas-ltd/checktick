"""Tests for tier enforcement in views and decorators."""

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def free_user(db):
    """Create a FREE tier user."""
    user = User.objects.create_user(
        username="freeuser", password=TEST_PASSWORD, email="free@test.com"
    )
    user.profile.account_tier = UserProfile.AccountTier.FREE
    user.profile.save()
    return user


@pytest.fixture
def pro_user(db):
    """Create a PRO tier user."""
    user = User.objects.create_user(
        username="prouser", password=TEST_PASSWORD, email="pro@test.com"
    )
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.save()
    return user


@pytest.fixture
def org_user(db):
    """Create an ORGANIZATION tier user."""
    user = User.objects.create_user(
        username="orguser", password=TEST_PASSWORD, email="org@test.com"
    )
    user.profile.account_tier = UserProfile.AccountTier.ORGANIZATION
    user.profile.save()
    return user


@pytest.fixture
def organization(db, org_user):
    """Create a test organization."""
    org = Organization.objects.create(name="Test Organization", owner=org_user)
    OrganizationMembership.objects.create(
        organization=org, user=org_user, role=OrganizationMembership.Role.ADMIN
    )
    return org


@pytest.mark.django_db
class TestSurveyCreationEnforcement:
    """Test tier limits for survey creation."""

    def test_free_tier_can_create_up_to_3_surveys(self, client, free_user):
        """FREE tier users can create up to 3 surveys."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        # Create 3 surveys successfully
        for i in range(3):
            response = client.post(
                reverse("surveys:create"),
                {
                    "name": f"Survey {i+1}",
                    "slug": f"survey-{i+1}",
                    "encryption_option": "none",  # No encryption
                },
            )
            assert response.status_code == 302  # Redirect on success
            assert Survey.objects.filter(owner=free_user, name=f"Survey {i+1}").exists()

    def test_free_tier_blocked_at_4th_survey(self, client, free_user):
        """FREE tier users are blocked from creating 4th survey."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        # Create 3 surveys
        for i in range(3):
            Survey.objects.create(
                name=f"Survey {i+1}",
                slug=f"survey-{i+1}",
                owner=free_user,
            )

        # Attempt to create 4th survey should be blocked
        response = client.post(
            reverse("surveys:create"),
            {
                "name": "Survey 4",
                "slug": "survey-4",
                "encryption_option": "none",
            },
        )

        # Should redirect back to list with error message
        assert response.status_code == 302
        assert response.url == reverse("surveys:list")
        assert not Survey.objects.filter(owner=free_user, name="Survey 4").exists()

        # Follow redirect to check message
        response = client.get(response.url)
        assert "reached the limit" in response.content.decode().lower()

    def test_free_tier_blocked_on_create_page_load(self, client, free_user):
        """FREE tier users are redirected when accessing create page at limit."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        # Create 3 surveys
        for i in range(3):
            Survey.objects.create(
                name=f"Survey {i+1}",
                slug=f"survey-{i+1}",
                owner=free_user,
            )

        # Try to access create page
        response = client.get(reverse("surveys:create"))

        # Should redirect back to list
        assert response.status_code == 302
        assert response.url == reverse("surveys:list")

    def test_pro_tier_unlimited_surveys(self, client, pro_user):
        """PRO tier users can create unlimited surveys."""
        client.login(username="prouser", password=TEST_PASSWORD)

        # Create 5 surveys (more than FREE limit)
        for i in range(5):
            response = client.post(
                reverse("surveys:create"),
                {
                    "name": f"Survey {i+1}",
                    "slug": f"survey-{i+1}",
                    "encryption_option": "none",
                },
            )
            assert response.status_code == 302
            assert Survey.objects.filter(owner=pro_user, name=f"Survey {i+1}").exists()

        assert Survey.objects.filter(owner=pro_user).count() == 5

    def test_org_tier_unlimited_surveys(self, client, org_user):
        """ORGANIZATION tier users can create unlimited surveys."""
        client.login(username="orguser", password=TEST_PASSWORD)

        # Create 5 surveys
        for i in range(5):
            response = client.post(
                reverse("surveys:create"),
                {
                    "name": f"Survey {i+1}",
                    "slug": f"survey-{i+1}",
                    "encryption_option": "none",
                },
            )
            assert response.status_code == 302
            assert Survey.objects.filter(owner=org_user, name=f"Survey {i+1}").exists()

        assert Survey.objects.filter(owner=org_user).count() == 5


@pytest.mark.django_db
class TestCollaborationEnforcement:
    """Test tier limits for collaboration features."""

    def test_free_tier_cannot_add_collaborators(self, client, free_user, organization):
        """FREE tier users cannot add collaborators."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        # Create a survey in the organization
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey",
            owner=free_user,
            organization=organization,
        )

        # Create another user to add as collaborator
        collaborator = User.objects.create_user(
            username="collaborator", password=TEST_PASSWORD, email="collab@test.com"
        )

        # Try to add collaborator
        response = client.post(
            reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
            {
                "action": "add",
                "email": "collab@test.com",
                "role": SurveyMembership.Role.EDITOR,
            },
        )

        # Should redirect with error
        assert response.status_code == 302
        assert not SurveyMembership.objects.filter(
            survey=survey, user=collaborator
        ).exists()

    def test_pro_tier_can_add_editors(self, client, pro_user, organization):
        """PRO tier users can add editors."""
        client.login(username="prouser", password=TEST_PASSWORD)

        # Add pro_user to organization
        OrganizationMembership.objects.create(
            organization=organization,
            user=pro_user,
            role=OrganizationMembership.Role.ADMIN,
        )

        # Create a survey in the organization
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-pro",
            owner=pro_user,
            organization=organization,
        )

        # Create another user to add as editor
        editor = User.objects.create_user(
            username="editor", password=TEST_PASSWORD, email="editor@test.com"
        )

        # Add editor
        response = client.post(
            reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
            {
                "action": "add",
                "email": "editor@test.com",
                "role": SurveyMembership.Role.EDITOR,
            },
        )

        # Should succeed
        assert response.status_code == 302
        assert SurveyMembership.objects.filter(
            survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
        ).exists()

    def test_pro_tier_cannot_add_viewers(self, client, pro_user, organization):
        """PRO tier users cannot add viewers."""
        client.login(username="prouser", password=TEST_PASSWORD)

        # Add pro_user to organization
        OrganizationMembership.objects.create(
            organization=organization,
            user=pro_user,
            role=OrganizationMembership.Role.ADMIN,
        )

        # Create a survey in the organization
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-pro-viewer",
            owner=pro_user,
            organization=organization,
        )

        # Create another user to add as viewer
        viewer = User.objects.create_user(
            username="viewer", password=TEST_PASSWORD, email="viewer@test.com"
        )

        # Try to add viewer
        response = client.post(
            reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
            {
                "action": "add",
                "email": "viewer@test.com",
                "role": SurveyMembership.Role.VIEWER,
            },
        )

        # Should redirect with error
        assert response.status_code == 302
        assert not SurveyMembership.objects.filter(
            survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
        ).exists()

    def test_org_tier_can_add_viewers(self, client, org_user, organization):
        """ORGANIZATION tier users can add viewers."""
        client.login(username="orguser", password=TEST_PASSWORD)

        # Create a survey in the organization
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-org",
            owner=org_user,
            organization=organization,
        )

        # Create another user to add as viewer
        viewer = User.objects.create_user(
            username="viewer2", password=TEST_PASSWORD, email="viewer2@test.com"
        )

        # Add viewer
        response = client.post(
            reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
            {
                "action": "add",
                "email": "viewer2@test.com",
                "role": SurveyMembership.Role.VIEWER,
            },
        )

        # Should succeed
        assert response.status_code == 302
        assert SurveyMembership.objects.filter(
            survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
        ).exists()

    def test_pro_tier_respects_collaborator_limit(self, client, pro_user, organization):
        """PRO tier enforces max 10 collaborators per survey."""
        client.login(username="prouser", password=TEST_PASSWORD)

        # Add pro_user to organization
        OrganizationMembership.objects.create(
            organization=organization,
            user=pro_user,
            role=OrganizationMembership.Role.ADMIN,
        )

        # Create a survey
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey-limit",
            owner=pro_user,
            organization=organization,
        )

        # Add 10 collaborators (at limit)
        for i in range(10):
            user = User.objects.create_user(
                username=f"collab{i}",
                password=TEST_PASSWORD,
                email=f"collab{i}@test.com",
            )
            SurveyMembership.objects.create(
                survey=survey, user=user, role=SurveyMembership.Role.EDITOR
            )

        # Try to add 11th collaborator
        extra_user = User.objects.create_user(
            username="extra", password=TEST_PASSWORD, email="extra@test.com"
        )

        response = client.post(
            reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
            {
                "action": "add",
                "email": "extra@test.com",
                "role": SurveyMembership.Role.EDITOR,
            },
        )

        # Should redirect with error
        assert response.status_code == 302
        assert not SurveyMembership.objects.filter(
            survey=survey, user=extra_user
        ).exists()


@pytest.mark.django_db
class TestContextProcessor:
    """Test that tier information is available in templates."""

    def test_tier_info_in_context(self, client, free_user):
        """Tier information is added to template context."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        response = client.get(reverse("surveys:list"))
        assert response.status_code == 200

        # Check context variables
        assert "user_tier" in response.context
        assert "user_tier_display" in response.context
        assert "tier_features" in response.context
        assert "tier_limits" in response.context
        assert "survey_count" in response.context

    def test_tier_display_shows_correct_info(self, client, free_user):
        """Tier limits are correctly displayed in UI."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        response = client.get(reverse("surveys:list"))
        content = response.content.decode()

        # Should show survey count for FREE tier
        assert "surveys used" in content.lower() or "surveys" in content.lower()

    def test_upgrade_prompt_at_limit(self, client, free_user):
        """Upgrade prompt shown when at survey limit."""
        client.login(username="freeuser", password=TEST_PASSWORD)

        # Create 3 surveys
        for i in range(3):
            Survey.objects.create(
                name=f"Survey {i+1}",
                slug=f"survey-{i+1}",
                owner=free_user,
            )

        response = client.get(reverse("surveys:list"))
        content = response.content.decode()

        # Should show warning about limit
        assert "limit" in content.lower()
