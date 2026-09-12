"""Tests for Survey Map pickable badges + preview simulate selection (step 9)."""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    SectionMenu,
    SectionMenuItem,
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
def section_menu_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Menu Survey",
        slug="menu-step9",
        layout=Survey.Layout.SECTION_MENU,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Medical", owner=owner)
    g3 = QuestionGroup.objects.create(name="Lifestyle", owner=owner)
    s.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Condition", type=SurveyQuestion.Types.TEXT, order=1
    )
    SurveyQuestion.objects.create(
        survey=s, group=g3, text="Exercise", type=SurveyQuestion.Types.TEXT, order=2
    )
    menu = SectionMenu.objects.create(survey=s, min_selected=1, max_selected=2)
    SectionMenuItem.objects.create(menu=menu, group=g1, is_pickable=False, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g2, is_pickable=True, order=2)
    SectionMenuItem.objects.create(
        menu=menu, group=g3, is_pickable=True, estimated_minutes=3, order=3
    )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


# --- Survey Map pickable badges ---


@pytest.mark.django_db
def test_survey_map_shows_pickable_badges(client, owner, section_menu_survey):
    client.force_login(owner)
    res = client.get(
        reverse("surveys:survey_map", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable" in html.lower()
    assert "mandatory" in html.lower()
    assert "Medical" in html
    assert "Demographics" in html


@pytest.mark.django_db
def test_survey_map_no_badges_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-map"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable status" not in html.lower()


# --- Preview simulate selection ---


@pytest.mark.django_db
def test_preview_shows_simulate_panel(client, owner, section_menu_survey):
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate section selection" in html
    assert "Medical" in html
    assert "Lifestyle" in html


@pytest.mark.django_db
def test_preview_simulate_filters_questions(client, owner, section_menu_survey):
    """When simulate_groups is set, only selected + mandatory questions appear."""
    client.force_login(owner)
    # Simulate selecting only Medical (g2), not Lifestyle (g3)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
        + f"?simulate_groups={section_menu_survey._g2.id}"
    )
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (mandatory) should appear
    assert "Age" in html
    # Medical (selected) should appear
    assert "Condition" in html
    # Lifestyle (not selected) should NOT appear
    assert "Exercise" not in html


@pytest.mark.django_db
def test_preview_simulate_reset_shows_all(client, owner, section_menu_survey):
    """Without simulate_groups, all questions appear in preview."""
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "Condition" in html
    assert "Exercise" in html


@pytest.mark.django_db
def test_preview_simulate_estimated_time(client, owner, section_menu_survey):
    """The simulate panel shows estimated time when enabled."""
    section_menu_survey.section_menu.show_estimated_time = True
    section_menu_survey.section_menu.save(update_fields=["show_estimated_time"])
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "~3 min" in html
