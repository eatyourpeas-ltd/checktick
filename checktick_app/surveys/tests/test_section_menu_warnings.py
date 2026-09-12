"""Tests for section menu warnings (step 8).

Tests the three warnings from docs/survey-layouts.md §Issues to bake in:
1. Branching targets a pickable section (dead branch warning)
2. Empty selection (no mandatory + min_selected=0)
3. Single-section guard (already tested in test_layout_organise.py)
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    SectionMenu,
    SectionMenuItem,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
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
        slug="menu-warnings",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.SECTION_MENU,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Medical", owner=owner)
    g3 = QuestionGroup.objects.create(name="Lifestyle", owner=owner)
    s.question_groups.add(g1, g2, g3)
    q1 = SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    q2 = SurveyQuestion.objects.create(
        survey=s, group=g2, text="Condition", type=SurveyQuestion.Types.TEXT, order=1
    )
    q3 = SurveyQuestion.objects.create(
        survey=s, group=g3, text="Exercise", type=SurveyQuestion.Types.TEXT, order=2
    )
    menu = SectionMenu.objects.create(survey=s, min_selected=1, max_selected=2)
    SectionMenuItem.objects.create(menu=menu, group=g1, is_pickable=False, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g2, is_pickable=True, order=2)
    SectionMenuItem.objects.create(menu=menu, group=g3, is_pickable=True, order=3)
    s._g1, s._g2, s._g3 = g1, g2, g3
    s._q1, s._q2, s._q3 = q1, q2, q3
    return s


@pytest.mark.django_db
def test_branching_warning_shown(client, owner, section_menu_survey):
    """A jump_to condition targeting a pickable section shows a warning."""
    # Add a branching condition from q1 (Demographics) to q3 (Lifestyle, pickable)
    SurveyQuestionCondition.objects.create(
        question=section_menu_survey._q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="50",
        target_question=section_menu_survey._q3,
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )
    client.force_login(owner)
    res = client.get(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable section" in html.lower() or "dead branch" in html.lower()
    assert "Lifestyle" in html


@pytest.mark.django_db
def test_no_warning_when_no_branching(client, owner, section_menu_survey):
    """No branching conditions → no warnings."""
    client.force_login(owner)
    res = client.get(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable section" not in html.lower()


@pytest.mark.django_db
def test_no_warning_for_mandatory_section_target(client, owner, section_menu_survey):
    """A jump_to to a mandatory section (not pickable) shows no warning."""
    SurveyQuestionCondition.objects.create(
        question=section_menu_survey._q2,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        target_question=section_menu_survey._q1,  # Demographics (mandatory)
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )
    client.force_login(owner)
    res = client.get(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable section" not in html.lower()


@pytest.mark.django_db
def test_empty_selection_warning_on_save(client, owner, section_menu_survey):
    """Saving with no mandatory sections and min_selected=0 warns."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "min_selected": "0",
            # No mandatory_group_ids → all pickable
        },
        follow=True,
    )
    assert res.status_code == 200
    messages = list(res.context["messages"])
    assert any("empty survey" in str(m) for m in messages)


@pytest.mark.django_db
def test_single_section_hint_on_organise(client, owner, org):
    """A survey with < 2 sections shows the hint on the Organise page."""
    s = Survey.objects.create(
        owner=owner, organization=org, name="Single", slug="single-warn"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Needs at least 2 sections" in html
