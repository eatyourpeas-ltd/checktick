from django.contrib.auth import get_user_model
import pytest

from checktick_app.core.models import UserAPIKey
from checktick_app.surveys.models import Survey, SurveyMembership

User = get_user_model()


def auth_hdr(user) -> dict:
    _, raw_key = UserAPIKey.generate(user=user, name="test")
    return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}


@pytest.mark.django_db
def test_api_survey_list_includes_membership_surveys(client):
    """Test that API survey list includes surveys user has membership to."""
    creator = User.objects.create_user(username="creator_list")
    editor = User.objects.create_user(username="editor_list")
    viewer = User.objects.create_user(username="viewer_list")
    outsider = User.objects.create_user(username="outsider_list")

    survey = Survey.objects.create(
        owner=creator, name="Test Survey", slug="test-survey"
    )
    SurveyMembership.objects.create(
        survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
    )
    SurveyMembership.objects.create(
        survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )

    # creator can see survey
    resp = client.get("/api/surveys/", **auth_hdr(creator))
    assert resp.status_code == 200
    assert any(s["slug"] == "test-survey" for s in resp.json())

    # editor can see survey via membership
    resp = client.get("/api/surveys/", **auth_hdr(editor))
    assert resp.status_code == 200
    assert any(s["slug"] == "test-survey" for s in resp.json())

    # viewer can see survey via membership
    resp = client.get("/api/surveys/", **auth_hdr(viewer))
    assert resp.status_code == 200
    assert any(s["slug"] == "test-survey" for s in resp.json())

    # outsider cannot see survey
    resp = client.get("/api/surveys/", **auth_hdr(outsider))
    assert resp.status_code == 200
    assert not any(s["slug"] == "test-survey" for s in resp.json())


@pytest.mark.django_db
def test_api_editor_permissions(client):
    """Test that EDITOR role can retrieve surveys via API."""
    creator = User.objects.create_user(username="creator_editor")
    editor = User.objects.create_user(username="editor_editor")

    survey = Survey.objects.create(
        owner=creator, name="Test Survey", slug="test-survey-ed"
    )
    SurveyMembership.objects.create(
        survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
    )

    # Test editor can retrieve survey
    resp = client.get(f"/api/surveys/{survey.id}/", **auth_hdr(editor))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_api_viewer_permissions(client):
    """Test that VIEWER role can retrieve surveys via API."""
    creator = User.objects.create_user(username="creator_viewer")
    viewer = User.objects.create_user(username="viewer_viewer")

    survey = Survey.objects.create(
        owner=creator, name="Test Survey", slug="test-survey-view"
    )
    SurveyMembership.objects.create(
        survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )

    # Test viewer can retrieve survey
    resp = client.get(f"/api/surveys/{survey.id}/", **auth_hdr(viewer))
    assert resp.status_code == 200
