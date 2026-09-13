"""Tests for the RCT Organise page warnings (step 7).

Covers: no arms, single arm, allocation ratio sum zero, unreachable
sections, all arms share the same group set, and branching targeting
an arm-exclusive section.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RandomisedArm,
    RandomisedMenu,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def rct_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RCT",
        slug="rct-warnings",
        layout=Survey.Layout.RCT,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Intervention", owner=owner)
    g3 = QuestionGroup.objects.create(name="Control", owner=owner)
    s.question_groups.add(g1, g2, g3)
    for g, t in [(g1, "Age"), (g2, "Dose"), (g3, "Placebo")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


def _organise(client, survey, user):
    client.force_login(user)
    return client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))


@pytest.mark.django_db
def test_warning_single_arm(client, rct_survey, owner):
    menu = RandomisedMenu.objects.create(survey=rct_survey)
    RandomisedArm.objects.create(menu=menu, name="Only", order=1)
    res = _organise(client, rct_survey, owner)
    assert b"single arm" in res.content.lower() or b"Only one arm" in res.content


@pytest.mark.django_db
def test_warning_allocation_ratio_sum_zero(client, rct_survey, owner):
    menu = RandomisedMenu.objects.create(survey=rct_survey)
    RandomisedArm.objects.create(menu=menu, name="A", order=1, allocation_ratio=0)
    RandomisedArm.objects.create(menu=menu, name="B", order=2, allocation_ratio=0)
    res = _organise(client, rct_survey, owner)
    assert b"allocation ratio 0" in res.content


@pytest.mark.django_db
def test_warning_unreachable_section(client, rct_survey, owner):
    menu = RandomisedMenu.objects.create(survey=rct_survey)
    a1 = RandomisedArm.objects.create(menu=menu, name="Int", order=1)
    a2 = RandomisedArm.objects.create(menu=menu, name="Ctrl", order=2)
    a1.groups.add(rct_survey._g1, rct_survey._g2)
    a2.groups.add(rct_survey._g1)
    # g3 (Control) is not in any arm → unreachable.
    res = _organise(client, rct_survey, owner)
    assert b"not in any arm" in res.content


@pytest.mark.django_db
def test_warning_all_arms_share_same_group_set(client, rct_survey, owner):
    menu = RandomisedMenu.objects.create(survey=rct_survey)
    a1 = RandomisedArm.objects.create(menu=menu, name="A", order=1)
    a2 = RandomisedArm.objects.create(menu=menu, name="B", order=2)
    a1.groups.add(rct_survey._g1, rct_survey._g2)
    a2.groups.add(rct_survey._g1, rct_survey._g2)
    res = _organise(client, rct_survey, owner)
    assert b"structurally identical to a linear survey" in res.content


@pytest.mark.django_db
def test_no_warnings_when_well_configured(client, rct_survey, owner):
    menu = RandomisedMenu.objects.create(survey=rct_survey)
    a1 = RandomisedArm.objects.create(menu=menu, name="Int", order=1)
    a2 = RandomisedArm.objects.create(menu=menu, name="Ctrl", order=2)
    a1.groups.add(rct_survey._g1, rct_survey._g2)
    a2.groups.add(rct_survey._g1, rct_survey._g3)
    res = _organise(client, rct_survey, owner)
    html = res.content.decode()
    # No warnings about arms, unreachable, or identical.
    assert "No arms configured" not in html
    assert "not in any arm" not in html
    assert "structurally identical" not in html


@pytest.mark.django_db
def test_warning_branching_targets_arm_exclusive_section(client, rct_survey, owner):
    menu = RandomisedMenu.objects.create(survey=rct_survey)
    a1 = RandomisedArm.objects.create(menu=menu, name="Int", order=1)
    a2 = RandomisedArm.objects.create(menu=menu, name="Ctrl", order=2)
    a1.groups.add(rct_survey._g1, rct_survey._g2)
    a2.groups.add(rct_survey._g1, rct_survey._g3)
    # g2 (Intervention) is arm-exclusive to a1. A jump from g1 → g2 is a
    # dead branch for participants in a2.
    q1 = rct_survey.questions.get(group=rct_survey._g1)
    q2 = rct_survey.questions.get(group=rct_survey._g2)
    SurveyQuestionCondition.objects.create(
        question=q1,
        action=SurveyQuestionCondition.Action.JUMP_TO,
        operator="equals",
        value="yes",
        target_question=q2,
    )
    res = _organise(client, rct_survey, owner)
    assert b"dead branch" in res.content or b"arm-exclusive" in res.content
