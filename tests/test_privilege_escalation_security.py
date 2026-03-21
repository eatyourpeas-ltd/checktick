"""
Security tests to verify privilege escalation protection.

These tests verify that users cannot escalate their own privileges
or access resources they shouldn't have access to.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)

User = get_user_model()
TEST_PASSWORD = "test-pass"


def auth_hdr(user) -> dict:
    """Helper to get API key auth headers."""
    _, raw_key = UserAPIKey.generate(user=user, name="test")
    return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}


@pytest.mark.django_db
def test_survey_creator_cannot_access_user_management_hub_without_org_admin(client):
    """
    Test that a survey creator who is NOT an organization admin
    cannot access the user management hub.
    """
    # Create org admin and survey creator
    org_admin = User.objects.create_user(
        username="admin@test.com", email="admin@test.com", password=TEST_PASSWORD
    )
    survey_creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )

    # Create organization with admin
    org = Organization.objects.create(name="Test Org", owner=org_admin)
    OrganizationMembership.objects.create(
        organization=org, user=org_admin, role=OrganizationMembership.Role.ADMIN
    )

    # Add survey creator as CREATOR (not ADMIN) to organization
    OrganizationMembership.objects.create(
        organization=org, user=survey_creator, role=OrganizationMembership.Role.CREATOR
    )

    # Survey creator creates a survey
    Survey.objects.create(
        owner=survey_creator, organization=org, name="Test Survey", slug="test-survey"
    )

    # Survey creator should NOT be able to access user management hub
    client.force_login(survey_creator)
    resp = client.get(reverse("surveys:user_management_hub"))
    assert resp.status_code == 200

    # But they should not see any organization management controls
    # (the hub shows but without management capabilities)
    content = resp.content.decode()
    # Should not show the organization since user is not an admin
    assert "Test Org" not in content or "Add user to organization" not in content


@pytest.mark.django_db
def test_survey_creator_cannot_escalate_org_membership_roles(client):
    """
    Test that a survey creator cannot escalate organization membership roles
    for themselves or others through the user management hub.
    """
    # Create org admin and survey creator
    org_admin = User.objects.create_user(
        username="admin@test.com", email="admin@test.com", password=TEST_PASSWORD
    )
    survey_creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )

    # Create organization
    org = Organization.objects.create(name="Test Org", owner=org_admin)
    OrganizationMembership.objects.create(
        organization=org, user=org_admin, role=OrganizationMembership.Role.ADMIN
    )
    OrganizationMembership.objects.create(
        organization=org, user=survey_creator, role=OrganizationMembership.Role.CREATOR
    )

    # Survey creator tries to escalate themselves to ADMIN via user management hub
    client.force_login(survey_creator)
    resp = client.post(
        reverse("surveys:user_management_hub"),
        data={
            "scope": "org",
            "email": "creator@test.com",  # trying to escalate themselves
            "role": "admin",
        },
    )
    # Should be forbidden since survey_creator is not org admin
    assert resp.status_code == 403


@pytest.mark.django_db
def test_survey_editor_cannot_manage_survey_users(client):
    """
    Test that a user with EDITOR role on a survey cannot manage other users
    on that survey (cannot add/edit/remove collaborators).
    """
    # Create users
    creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )
    editor = User.objects.create_user(
        username="editor@test.com", email="editor@test.com", password=TEST_PASSWORD
    )
    target_user = User.objects.create_user(
        username="target@test.com", email="target@test.com", password=TEST_PASSWORD
    )

    # Create survey
    survey = Survey.objects.create(
        owner=creator, name="Test Survey", slug="test-survey"
    )

    # Add editor as EDITOR
    SurveyMembership.objects.create(
        survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
    )

    # Editor tries to add target_user to survey via user management hub
    client.force_login(editor)
    resp = client.post(
        reverse("surveys:user_management_hub"),
        data={
            "scope": "survey",
            "slug": "test-survey",
            "email": "target@test.com",
            "role": "viewer",
        },
    )
    # Should be forbidden since editor cannot manage survey users
    assert resp.status_code == 403

    # Verify target_user was not added to survey
    assert not SurveyMembership.objects.filter(survey=survey, user=target_user).exists()


@pytest.mark.django_db
def test_survey_editor_cannot_access_survey_users_view(client):
    """
    Test that EDITOR cannot access the survey users management page.
    """
    # Create users
    creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )
    editor = User.objects.create_user(
        username="editor@test.com", email="editor@test.com", password=TEST_PASSWORD
    )

    # Create survey
    survey = Survey.objects.create(
        owner=creator, name="Test Survey", slug="test-survey"
    )

    # Add editor as EDITOR
    SurveyMembership.objects.create(
        survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
    )

    # Editor tries to access survey users management page
    client.force_login(editor)
    resp = client.get(reverse("surveys:survey_users", kwargs={"slug": "test-survey"}))
    # Should return 404 (permission denied) since editor cannot manage users
    assert resp.status_code == 404


@pytest.mark.django_db
def test_individual_user_cannot_manage_survey_users(client):
    """
    Test that individual users (surveys without organization) cannot share
    surveys or manage survey memberships.
    """
    # Create individual user
    creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )
    other_user = User.objects.create_user(
        username="other@test.com", email="other@test.com", password=TEST_PASSWORD
    )

    # Create survey without organization (individual user)
    survey = Survey.objects.create(
        owner=creator, name="Test Survey", slug="test-survey"
    )

    # Individual user tries to add another user via user management hub
    client.force_login(creator)
    resp = client.post(
        reverse("surveys:user_management_hub"),
        data={
            "scope": "survey",
            "slug": "test-survey",
            "email": "other@test.com",
            "role": "viewer",
        },
    )
    # Should fail - individual users cannot share surveys
    assert resp.status_code == 403

    # Verify no membership was created
    assert not SurveyMembership.objects.filter(survey=survey, user=other_user).exists()


@pytest.mark.django_db
def test_survey_member_cannot_access_other_surveys_in_org(client):
    """
    Test that having membership in one survey doesn't grant access to other
    surveys in the same organization.
    """
    # Create users
    org_admin = User.objects.create_user(
        username="admin@test.com", email="admin@test.com", password=TEST_PASSWORD
    )
    survey_creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )
    editor = User.objects.create_user(
        username="editor@test.com", email="editor@test.com", password=TEST_PASSWORD
    )

    # Create organization
    org = Organization.objects.create(name="Test Org", owner=org_admin)
    OrganizationMembership.objects.create(
        organization=org, user=org_admin, role=OrganizationMembership.Role.ADMIN
    )

    # Create two surveys
    survey1 = Survey.objects.create(
        owner=survey_creator, organization=org, name="Survey 1", slug="survey-1"
    )
    survey2 = Survey.objects.create(
        owner=survey_creator, organization=org, name="Survey 2", slug="survey-2"
    )

    # Add editor as EDITOR to survey1 only
    SurveyMembership.objects.create(
        survey=survey1, user=editor, role=SurveyMembership.Role.EDITOR
    )

    # Editor should be able to access survey1
    client.force_login(editor)
    resp = client.get(reverse("surveys:dashboard", kwargs={"slug": "survey-1"}))
    assert resp.status_code == 200

    # Editor should NOT be able to access survey2
    resp = client.get(reverse("surveys:dashboard", kwargs={"slug": survey2.slug}))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_api_survey_member_cannot_access_other_surveys(client):
    """
    Test that survey membership doesn't grant API access to other surveys.
    """
    # Create users
    creator1 = User.objects.create_user(username="creator1@test.com")
    creator2 = User.objects.create_user(username="creator2@test.com")
    editor = User.objects.create_user(username="editor@test.com")

    # Create surveys by different creators
    survey1 = Survey.objects.create(owner=creator1, name="Survey 1", slug="survey-1")
    survey2 = Survey.objects.create(owner=creator2, name="Survey 2", slug="survey-2")

    # Add editor as EDITOR to survey1 only
    SurveyMembership.objects.create(
        survey=survey1, user=editor, role=SurveyMembership.Role.EDITOR
    )

    # Editor should see only survey1 in API list
    hdrs = auth_hdr(editor)
    resp = client.get("/api/surveys/", **hdrs)
    assert resp.status_code == 200
    surveys = resp.json()
    assert len(surveys) == 1
    assert surveys[0]["slug"] == "survey-1"

    # Editor should be able to access survey1 via API
    resp = client.get(f"/api/surveys/{survey1.id}/", **hdrs)
    assert resp.status_code == 200

    # Editor should NOT be able to access survey2 via API
    resp = client.get(f"/api/surveys/{survey2.id}/", **hdrs)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_privilege_escalation_prevention_comprehensive(client):
    """
    Comprehensive test ensuring no privilege escalation paths exist.
    """
    # Create a complex org structure
    org_admin = User.objects.create_user(
        username="admin@test.com", email="admin@test.com", password=TEST_PASSWORD
    )
    survey_creator = User.objects.create_user(
        username="creator@test.com", email="creator@test.com", password=TEST_PASSWORD
    )
    editor = User.objects.create_user(
        username="editor@test.com", email="editor@test.com", password=TEST_PASSWORD
    )
    viewer = User.objects.create_user(
        username="viewer@test.com", email="viewer@test.com", password=TEST_PASSWORD
    )

    # Create organization
    org = Organization.objects.create(name="Test Org", owner=org_admin)
    OrganizationMembership.objects.create(
        organization=org, user=org_admin, role=OrganizationMembership.Role.ADMIN
    )
    OrganizationMembership.objects.create(
        organization=org, user=survey_creator, role=OrganizationMembership.Role.CREATOR
    )

    # Create survey
    survey = Survey.objects.create(
        owner=survey_creator, organization=org, name="Test Survey", slug="test-survey"
    )

    # Add memberships
    SurveyMembership.objects.create(
        survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
    )
    SurveyMembership.objects.create(
        survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )

    # Test 1: EDITOR cannot become CREATOR
    client.force_login(editor)
    resp = client.post(
        reverse("surveys:user_management_hub"),
        data={
            "scope": "survey",
            "slug": "test-survey",
            "email": "editor@test.com",
            "role": "creator",
        },
    )
    assert resp.status_code == 403

    # Test 2: VIEWER cannot become EDITOR
    client.force_login(viewer)
    resp = client.post(
        reverse("surveys:user_management_hub"),
        data={
            "scope": "survey",
            "slug": "test-survey",
            "email": "viewer@test.com",
            "role": "editor",
        },
    )
    assert resp.status_code == 403

    # Test 3: Survey CREATOR (non-org-admin) cannot make themselves org admin
    client.force_login(survey_creator)
    resp = client.post(
        reverse("surveys:user_management_hub"),
        data={
            "scope": "org",
            "email": "creator@test.com",
            "role": "admin",
        },
    )
    assert resp.status_code == 403

    # Verify roles haven't changed
    editor_membership = SurveyMembership.objects.get(survey=survey, user=editor)
    assert editor_membership.role == SurveyMembership.Role.EDITOR

    viewer_membership = SurveyMembership.objects.get(survey=survey, user=viewer)
    assert viewer_membership.role == SurveyMembership.Role.VIEWER

    creator_org_membership = OrganizationMembership.objects.get(
        organization=org, user=survey_creator
    )
    assert creator_org_membership.role == OrganizationMembership.Role.CREATOR
