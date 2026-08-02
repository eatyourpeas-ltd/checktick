from __future__ import annotations

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DataSet,
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
)

TEST_PASSWORD = "test-pass"


@pytest.mark.django_db
def test_anon_sees_no_surveys_in_list(client):
    # Setup minimal data
    owner = Organization._meta.apps.get_model("auth", "User").objects.create_user(
        username="owner_anon", password=TEST_PASSWORD
    )
    org = Organization.objects.create(name="OrgAnon", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    Survey.objects.create(owner=owner, organization=org, name="S1", slug="s1")

    resp = client.get(reverse("surveys:list"))
    # login_required should redirect anonymous users away from SSR list
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_anon_cannot_access_management_pages(client):
    owner = Organization._meta.apps.get_model("auth", "User").objects.create_user(
        username="owner_manage", password=TEST_PASSWORD
    )
    org = Organization.objects.create(name="OrgManage", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey = Survey.objects.create(owner=owner, organization=org, name="S2", slug="s2")

    # Management endpoints must redirect unauthenticated users to login
    urls = [
        reverse("surveys:dashboard", kwargs={"slug": survey.slug}),
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        reverse("surveys:preview", kwargs={"slug": survey.slug}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_anon_cannot_view_non_live_survey_detail(client):
    owner = Organization._meta.apps.get_model("auth", "User").objects.create_user(
        username="owner_nonlive", password=TEST_PASSWORD
    )
    org = Organization.objects.create(name="OrgNonLive", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    # Make survey not live yet
    future = timezone.now() + timezone.timedelta(days=1)
    survey = Survey.objects.create(
        owner=owner, organization=org, name="S3", slug="s3", start_at=future
    )

    resp = client.get(reverse("surveys:detail", kwargs={"slug": survey.slug}))
    # All surveys require authentication (redirect/unauthorized/forbidden for anon)
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_anon_respondent_gets_ssr_professional_field_options(client):
    """F8 regression: professional-field dropdown options are rendered
    server-side so anonymous respondents never call the datasets API
    (which requires authentication).
    """
    owner = Organization._meta.apps.get_model("auth", "User").objects.create_user(
        username="owner_ssr", password=TEST_PASSWORD
    )
    org = Organization.objects.create(name="OrgSSR", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Public prof survey",
        slug="public-prof-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
        start_at=timezone.now() - timezone.timedelta(days=1),
    )
    prof_group = QuestionGroup.objects.create(
        name="Professional details",
        owner=owner,
        schema={
            "template": "professional_details",
            "fields": ["employing_trust"],
            "ods": {},
        },
    )
    survey.question_groups.add(prof_group)
    DataSet.objects.create(
        key="nhs_trusts",
        name="NHS Trusts",
        category="rcpch",
        source_type="api",
        is_custom=False,
        is_global=True,
        is_active=True,
        options={"RCF": "AIREDALE NHS FOUNDATION TRUST"},
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))

    assert resp.status_code == 200
    html = resp.content.decode()
    # The dropdown and its dataset options are baked into the page
    assert 'name="prof_employing_trust"' in html
    assert "AIREDALE NHS FOUNDATION TRUST" in html
    # No client-side fetch of the datasets API remains
    assert "professional-fields.js" not in html
    assert "/api/datasets/" not in html
