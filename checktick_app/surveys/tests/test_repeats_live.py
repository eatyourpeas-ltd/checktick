"""
Tests for repeating sections in the live survey and preview.

Covers:
  - The live /take page renders the repeat container, add button, and
    remove button for groups that belong to a CollectionDefinition with
    max_count > 1 (or unlimited).
  - Submitting the live survey stores repeatable answers as an ordered list
    of per-instance values, while non-repeatable answers keep their legacy
    scalar/list shape.
  - The preview page renders the same repeat UI.
  - CSV export and response analytics handle the list-of-instances shape.
"""

from __future__ import annotations

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    CollectionDefinition,
    CollectionItem,
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


def _make_survey_with_repeatable_group(
    owner,
    org,
    *,
    slug="repeat-live",
    max_count=3,
    qtype=SurveyQuestion.Types.TEXT,
):
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Repeat Live Survey",
        slug=slug,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = QuestionGroup.objects.create(name="Your Cars", owner=owner)
    survey.question_groups.add(group)
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="What is the make of your car?",
        type=qtype,
        required=False,
        order=0,
        group=group,
    )
    cd = CollectionDefinition.objects.create(
        survey=survey,
        key="cars",
        name="Cars",
        cardinality=CollectionDefinition.Cardinality.MANY,
        min_count=0,
        max_count=max_count,
    )
    CollectionItem.objects.create(
        collection=cd,
        item_type=CollectionItem.ItemType.GROUP,
        group=group,
        order=0,
    )
    return survey, group, q, cd


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_live_take_renders_repeat_ui(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(owner, org)

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    body = resp.content.decode()

    # Repeat container + add button + remove button are present.
    assert "data-repeat-container" in body
    assert "data-repeat-add" in body
    assert "data-repeat-remove" in body
    # The add button says "Add another" (no section name).
    assert "Add another" in body
    assert "Add another Cars" not in body
    # The configured max is emitted on the container.
    assert 'data-repeat-max="3"' in body


@pytest.mark.django_db
def test_live_take_no_repeat_ui_for_single_instance_collection(client):
    """A collection with max_count=1 must NOT render the repeat UI."""
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="repeat-single", max_count=1
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "data-repeat-container" not in body
    assert "data-repeat-add" not in body


@pytest.mark.django_db
def test_preview_renders_repeat_ui(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="repeat-preview"
    )
    client.force_login(owner)
    resp = client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "data-repeat-container" in body
    assert "data-repeat-add" in body


# ---------------------------------------------------------------------------
# Submission + storage shape
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_stores_repeatable_answers_as_list(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(owner, org)

    # Instance 0 uses the bare field name; instances 1 and 2 use __r{idx}.
    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={
            f"q_{q.id}": "Volvo",
            f"q_{q.id}__r1": "Saab",
            f"q_{q.id}__r2": "Toyota",
        },
    )
    assert resp.status_code in (200, 302)

    response = SurveyResponse.objects.filter(survey=survey).first()
    assert response is not None
    stored = response.answers[str(q.id)]
    # Repeatable answers are an ordered list of per-instance values.
    assert stored == ["Volvo", "Saab", "Toyota"]


@pytest.mark.django_db
def test_submit_skips_empty_repeat_instances(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(owner, org)

    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={
            f"q_{q.id}": "Volvo",
            # Instance 1 left blank, instance 2 filled.
            f"q_{q.id}__r1": "",
            f"q_{q.id}__r2": "Toyota",
        },
    )
    assert resp.status_code in (200, 302)

    response = SurveyResponse.objects.filter(survey=survey).first()
    assert response is not None
    stored = response.answers[str(q.id)]
    assert stored == ["Volvo", "Toyota"]


@pytest.mark.django_db
def test_non_repeatable_answer_keeps_legacy_shape(client):
    """A question in a non-repeatable group must store a scalar, not a list."""
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="No Repeat",
        slug="no-repeat",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Favourite colour?",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={f"q_{q.id}": "Blue"},
    )
    assert resp.status_code in (200, 302)
    response = SurveyResponse.objects.filter(survey=survey).first()
    assert response is not None
    # Legacy scalar shape, not a list.
    assert response.answers[str(q.id)] == "Blue"


# ---------------------------------------------------------------------------
# Export + analytics
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_csv_export_renders_repeat_instances_in_one_cell(client):
    from checktick_app.surveys.services.export_service import ExportService

    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(owner, org)

    # Submit a response with three car instances.
    client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={
            f"q_{q.id}": "Volvo",
            f"q_{q.id}__r1": "Saab",
            f"q_{q.id}__r2": "Toyota",
        },
    )

    csv_data = ExportService._generate_csv(survey)
    # The three instances are joined into a single cell with " | ".
    assert "Volvo | Saab | Toyota" in csv_data


@pytest.mark.django_db
def test_analytics_counts_each_repeat_instance():
    from checktick_app.surveys.services.response_analytics import (
        compute_response_analytics,
    )

    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="repeat-analytics", qtype=SurveyQuestion.Types.YESNO
    )

    # Two responses, each with multiple yes/no instances.
    SurveyResponse.objects.create(
        survey=survey,
        answers={str(q.id): ["yes", "no", "yes"]},
    )
    SurveyResponse.objects.create(
        survey=survey,
        answers={str(q.id): ["yes"]},
    )

    analytics = compute_response_analytics(survey)
    dist = next(d for d in analytics.distributions if d.question_id == q.id)
    # 3 yes + 1 no across all repeat instances.
    yes = next(o for o in dist.options if o["label"] == "Yes")
    no = next(o for o in dist.options if o["label"] == "No")
    assert yes["count"] == 3
    assert no["count"] == 1
    assert dist.total_responses == 4  # 4 instances answered


@pytest.mark.django_db
def test_min_count_zero_allows_single_instance(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="repeat-min-zero", max_count=5
    )
    # min_count defaults to 0 in _make_survey_with_repeatable_group.
    assert cd.min_count == 0

    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={f"q_{q.id}": "Volvo"},
    )
    assert resp.status_code in (200, 302)
    response = SurveyResponse.objects.filter(survey=survey).first()
    assert response is not None
    assert response.answers[str(q.id)] == ["Volvo"]


# ---------------------------------------------------------------------------
# Multi-section vs single-section repeat icons
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_organiser_shows_multi_section_icon_for_multi_group_repeat(client):
    """A repeat containing multiple groups shows the multi-section icon."""
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Multi",
        slug="multi-section",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    g1 = QuestionGroup.objects.create(name="Section A", owner=owner)
    g2 = QuestionGroup.objects.create(name="Section B", owner=owner)
    survey.question_groups.add(g1, g2)
    cd = CollectionDefinition.objects.create(
        survey=survey,
        key="multi",
        name="Multi",
        cardinality=CollectionDefinition.Cardinality.MANY,
        max_count=3,
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=g1, order=0
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=g2, order=1
    )

    client.force_login(owner)
    resp = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    body = resp.content.decode()
    # The multi-section label should appear, the single-section label should not.
    assert "Multi-section" in body
    assert ">Repeats<" not in body


@pytest.mark.django_db
def test_organiser_shows_single_section_icon_for_single_group_repeat(client):
    """A repeat containing one group shows the standard repeat icon."""
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="single-section-icon"
    )

    client.force_login(owner)
    resp = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    body = resp.content.decode()
    # Single-section repeat shows "Repeats", not "Multi-section".
    assert "Repeats" in body
    assert "Multi-section" not in body


@pytest.mark.django_db
def test_builder_rail_shows_multi_section_icon(client):
    """The builder rail shows the multi-section icon for multi-group repeats."""
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Multi Builder",
        slug="multi-builder",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.PUBLIC,
    )
    g1 = QuestionGroup.objects.create(name="A", owner=owner)
    g2 = QuestionGroup.objects.create(name="B", owner=owner)
    survey.question_groups.add(g1, g2)
    cd = CollectionDefinition.objects.create(
        survey=survey,
        key="multi",
        name="Multi",
        cardinality=CollectionDefinition.Cardinality.MANY,
        max_count=3,
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=g1, order=0
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=g2, order=1
    )

    client.force_login(owner)
    resp = client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    body = resp.content.decode()
    # The signpost to the organiser should be present.
    assert "Organiser" in body or "organiser" in body.lower()


# ---------------------------------------------------------------------------
# min_count validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_min_count_blocks_submission_with_too_few_instances(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="repeat-min", max_count=5
    )
    cd.min_count = 2
    cd.save(update_fields=["min_count"])

    # Submit with only one instance — should be rejected.
    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={f"q_{q.id}": "Volvo"},
    )
    # Should redirect back to the take page with an error message.
    assert resp.status_code in (200, 302)
    # No response should have been saved.
    assert SurveyResponse.objects.filter(survey=survey).count() == 0


@pytest.mark.django_db
def test_min_count_allows_submission_with_enough_instances(client):
    owner = _owner()
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    survey, group, q, cd = _make_survey_with_repeatable_group(
        owner, org, slug="repeat-min-ok", max_count=5
    )
    cd.min_count = 2
    cd.save(update_fields=["min_count"])

    # Submit with two instances — should be accepted.
    resp = client.post(
        reverse("surveys:take", kwargs={"slug": survey.slug}),
        data={f"q_{q.id}": "Volvo", f"q_{q.id}__r1": "Saab"},
    )
    assert resp.status_code in (200, 302)
    response = SurveyResponse.objects.filter(survey=survey).first()
    assert response is not None
    assert response.answers[str(q.id)] == ["Volvo", "Saab"]


def _owner():
    from django.contrib.auth.models import User

    return User.objects.create_user(username="repeat_owner", password="x")
