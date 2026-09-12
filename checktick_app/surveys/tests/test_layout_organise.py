"""Tests for the layout picker on the Organise page (step 3).

Step 3 adds a read-only summary card plus a POST handler to switch the
survey's layout. The SectionMenu configuration card (per-section
mandatory/pickable, min/max, etc.) lands in step 4.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="S", slug="s")
    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Q1", type=SurveyQuestion.Types.TEXT
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Q2", type=SurveyQuestion.Types.TEXT
    )
    return s


@pytest.mark.django_db
def test_organise_page_shows_layout_picker(client, owner, survey):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Survey layout" in html
    assert "Default (linear)" in html
    assert "Section menu" in html
    # Linear is current by default
    assert "Current" in html


@pytest.mark.django_db
def test_organise_page_marks_section_menu_as_current(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # Both cards render but only the section_menu card shows the "Use this
    # layout" button (the linear one does, since it's not current).
    assert "Section menu" in html


@pytest.mark.django_db
def test_switch_layout_to_section_menu(client, owner, survey):
    client.force_login(owner)
    assert survey.layout == Survey.Layout.LINEAR
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "section_menu"},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.SECTION_MENU


@pytest.mark.django_db
def test_switch_layout_back_to_linear(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "linear"},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_switch_layout_rejects_unknown_value(client, owner, survey):
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "nonsense"},
    )
    assert res.status_code == 302
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_switch_layout_requires_edit_permission(client, owner, survey):
    """A viewer (can_view but not can_edit) cannot switch layout."""
    viewer = owner.__class__.objects.create_user(
        username="viewer@example.com", password=TEST_PASSWORD
    )
    # Add viewer as a member with view-only role
    from checktick_app.surveys.models import SurveyMembership

    SurveyMembership.objects.create(survey=survey, user=viewer, role="viewer")
    client.force_login(viewer)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": survey.slug}),
        {"action": "set_layout", "layout": "section_menu"},
    )
    # require_can_edit raises PermissionDenied -> 403
    assert res.status_code == 403
    survey.refresh_from_db()
    assert survey.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_single_section_survey_shows_warning_hint(client, owner, org):
    """A survey with < 2 sections shows the 'needs at least 2 sections' hint."""
    s = Survey.objects.create(
        owner=owner, organization=org, name="Single", slug="single"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Needs at least 2 sections" in html


@pytest.mark.django_db
def test_switch_to_section_menu_with_one_section_warns(client, owner, org):
    """Switching to section_menu with < 2 sections still succeeds but warns."""
    s = Survey.objects.create(
        owner=owner, organization=org, name="Single", slug="single-w"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": s.slug}),
        {"action": "set_layout", "layout": "section_menu"},
        follow=True,
    )
    assert res.status_code == 200
    s.refresh_from_db()
    assert s.layout == Survey.Layout.SECTION_MENU
    messages = list(res.context["messages"])
    assert any("at least 2 sections" in str(m) for m in messages)
