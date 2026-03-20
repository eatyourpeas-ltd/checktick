from django.utils import timezone
import pytest
from rest_framework.test import APIClient

from checktick_app.surveys.models import (
    Survey,
    SurveyMembership,
    SurveyResponse,
)


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
