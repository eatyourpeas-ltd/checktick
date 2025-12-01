from django.utils import timezone
import pytest
from rest_framework.test import APIClient

from checktick_app.surveys.models import (
    QuestionGroup,
    Survey,
    SurveyMembership,
    SurveyResponse,
)


@pytest.mark.django_db
def test_publish_settings_get_requires_view_permission(django_user_model):
    owner = django_user_model.objects.create_user(username="owner", password="x")
    viewer = django_user_model.objects.create_user(username="viewer", password="x")
    client = APIClient()
    client.force_authenticate(viewer)
    survey = Survey.objects.create(owner=owner, name="S1", slug="s1")
    # Viewer has survey membership
    SurveyMembership.objects.create(
        user=viewer, survey=survey, role=SurveyMembership.Role.VIEWER
    )
    url = f"/api/surveys/{survey.id}/publish/"
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data["status"] == survey.status


@pytest.mark.django_db
def test_publish_settings_put_requires_edit_permission(django_user_model):
    owner = django_user_model.objects.create_user(username="owner2", password="x")
    viewer = django_user_model.objects.create_user(username="viewer2", password="x")
    client = APIClient()
    survey = Survey.objects.create(owner=owner, name="S1", slug="s1")
    # Grant viewer membership to viewer
    SurveyMembership.objects.create(
        user=viewer, survey=survey, role=SurveyMembership.Role.VIEWER
    )
    client.force_authenticate(viewer)
    url = f"/api/surveys/{survey.id}/publish/"
    resp = client.put(
        url, {"status": "published", "visibility": "authenticated"}, format="json"
    )
    # Viewer cannot edit
    assert resp.status_code in (403, 401)
    # Owner can edit
    client.force_authenticate(owner)
    resp2 = client.put(
        url, {"status": "published", "visibility": "authenticated"}, format="json"
    )
    assert resp2.status_code == 200
    assert resp2.data["status"] == "published"


@pytest.mark.django_db
def test_metrics_counts_and_permissions(django_user_model):
    owner = django_user_model.objects.create_user(username="owner3", password="x")
    creator = django_user_model.objects.create_user(username="creator3", password="x")
    viewer = django_user_model.objects.create_user(username="viewer3", password="x")
    outsider = django_user_model.objects.create_user(username="outsider3", password="x")
    client = APIClient()
    survey = Survey.objects.create(owner=owner, name="S1", slug="s1")
    SurveyMembership.objects.create(
        user=creator, survey=survey, role=SurveyMembership.Role.CREATOR
    )
    SurveyMembership.objects.create(
        user=viewer, survey=survey, role=SurveyMembership.Role.VIEWER
    )
    # Seed some responses
    SurveyResponse.objects.create(survey=survey, answers={}, submitted_by=owner)
    SurveyResponse.objects.create(survey=survey, answers={}, submitted_by=creator)
    # Yesterday
    r = SurveyResponse.objects.create(survey=survey, answers={}, submitted_by=viewer)
    r.submitted_at = timezone.now() - timezone.timedelta(days=1)
    r.save(update_fields=["submitted_at"])

    url = f"/api/surveys/{survey.id}/metrics/responses/"

    # Outsider blocked
    client.force_authenticate(outsider)
    resp = client.get(url)
    assert resp.status_code in (403, 404)

    # Viewer allowed
    client.force_authenticate(viewer)
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data["total"] == 3
    assert resp.data["today"] >= 2
    assert resp.data["last7"] >= 3

    # Creator allowed
    client.force_authenticate(creator)
    resp = client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_patient_data_ack_required_for_public_visibility(django_user_model):
    owner = django_user_model.objects.create_user(username="owner4", password="x")
    client = APIClient()
    client.force_authenticate(owner)
    survey = Survey.objects.create(owner=owner, name="S1", slug="s1")
    # Add a patient details group to enforce the safeguard
    QuestionGroup.objects.create(
        owner=owner,
        name="Patient details",
        schema={"template": "patient_details_encrypted", "fields": ["first_name"]},
    )
    survey.question_groups.add(QuestionGroup.objects.first())
    url = f"/api/surveys/{survey.id}/publish/"
    resp = client.put(
        url, {"status": "published", "visibility": "public"}, format="json"
    )
    assert resp.status_code == 400
    assert "no_patient_data_ack" in resp.data


@pytest.mark.django_db
def test_encryption_required_for_patient_data_surveys(django_user_model):
    """API should block publishing surveys with patient data if no encryption exists."""
    from checktick_app.core.models import UserProfile

    owner = django_user_model.objects.create_user(username="owner5", password="x")
    # Upgrade to PRO so tier check passes - we want to test encryption requirement
    owner.profile.account_tier = UserProfile.AccountTier.PRO
    owner.profile.save()

    client = APIClient()
    client.force_authenticate(owner)
    survey = Survey.objects.create(owner=owner, name="Patient Survey", slug="s-patient")

    # Add a patient details group
    group = QuestionGroup.objects.create(
        owner=owner,
        name="Patient Details",
        schema={
            "template": "patient_details_encrypted",
            "fields": ["first_name", "surname"],
        },
    )
    survey.question_groups.add(group)

    url = f"/api/surveys/{survey.id}/publish/"

    # Attempt to publish without encryption should fail
    resp = client.put(
        url, {"status": "published", "visibility": "authenticated"}, format="json"
    )
    assert resp.status_code == 400
    assert "encryption" in resp.data
    assert "web interface" in resp.data["encryption"].lower()

    # Verify survey was NOT published
    survey.refresh_from_db()
    assert survey.status == Survey.Status.DRAFT


@pytest.mark.django_db
def test_non_patient_data_surveys_can_publish_without_encryption(django_user_model):
    """API should allow publishing surveys without patient data even if no encryption."""
    owner = django_user_model.objects.create_user(username="owner6", password="x")
    client = APIClient()
    client.force_authenticate(owner)
    survey = Survey.objects.create(
        owner=owner, name="Non-Patient Survey", slug="s-non-patient"
    )

    # No patient data groups - just a regular survey

    url = f"/api/surveys/{survey.id}/publish/"

    # Should succeed without encryption
    resp = client.put(
        url, {"status": "published", "visibility": "authenticated"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["status"] == "published"

    # Verify survey was published
    survey.refresh_from_db()
    assert survey.status == Survey.Status.PUBLISHED
