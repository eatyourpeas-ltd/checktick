"""Tests for the staged Organise page warnings (step 5).

Covers: no phases, single phase, survey_open anchor with no start date,
unreachable sections, overlapping phase windows for the same group, and
branching targeting a phased section.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    StagedMenu,
    StagedPhase,
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
def staged_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Staged",
        slug="staged-warnings",
        layout=Survey.Layout.STAGED,
    )
    g1 = QuestionGroup.objects.create(name="Baseline", owner=owner)
    g2 = QuestionGroup.objects.create(name="Followup", owner=owner)
    g3 = QuestionGroup.objects.create(name="Review", owner=owner)
    s.question_groups.add(g1, g2, g3)
    for g, t in [(g1, "BQ"), (g2, "FQ"), (g3, "RQ")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


def _organise(client, survey, user):
    client.force_login(user)
    return client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))


@pytest.mark.django_db
def test_warning_no_phases(client, staged_survey, owner):
    StagedMenu.objects.create(survey=staged_survey)
    res = _organise(client, staged_survey, owner)
    assert b"No phases are configured" in res.content


@pytest.mark.django_db
def test_warning_single_phase(client, staged_survey, owner):
    menu = StagedMenu.objects.create(survey=staged_survey)
    phase = StagedPhase.objects.create(menu=menu, name="Baseline", order=1)
    phase.groups.add(staged_survey._g1)
    res = _organise(client, staged_survey, owner)
    assert b"single phase" in res.content.lower() or b"Only one phase" in res.content


@pytest.mark.django_db
def test_warning_survey_open_anchor_no_start_date(client, staged_survey, owner):
    menu = StagedMenu.objects.create(
        survey=staged_survey, anchor=StagedMenu.Anchor.SURVEY_OPEN
    )
    p1 = StagedPhase.objects.create(menu=menu, name="A", order=1)
    p2 = StagedPhase.objects.create(menu=menu, name="B", order=2)
    p1.groups.add(staged_survey._g1)
    p2.groups.add(staged_survey._g2)
    res = _organise(client, staged_survey, owner)
    assert b"no start date" in res.content.lower() or b"survey open date" in res.content


@pytest.mark.django_db
def test_warning_unreachable_section(client, staged_survey, owner):
    menu = StagedMenu.objects.create(survey=staged_survey)
    p1 = StagedPhase.objects.create(menu=menu, name="A", order=1)
    p2 = StagedPhase.objects.create(menu=menu, name="B", order=2)
    p1.groups.add(staged_survey._g1)
    p2.groups.add(staged_survey._g2)
    # g3 (Review) is in no phase.
    res = _organise(client, staged_survey, owner)
    assert b"Review" in res.content
    assert b"not in any phase" in res.content


@pytest.mark.django_db
def test_warning_overlapping_phase_windows(client, staged_survey, owner):
    menu = StagedMenu.objects.create(survey=staged_survey)
    # g1 in two phases with overlapping windows [0,14) and [7,28).
    p1 = StagedPhase.objects.create(
        menu=menu, name="A", order=1, start_offset_days=0, end_offset_days=14
    )
    p2 = StagedPhase.objects.create(
        menu=menu, name="B", order=2, start_offset_days=7, end_offset_days=28
    )
    p1.groups.add(staged_survey._g1)
    p2.groups.add(staged_survey._g1, staged_survey._g2)
    res = _organise(client, staged_survey, owner)
    assert b"overlap" in res.content.lower()


@pytest.mark.django_db
def test_no_overlap_warning_for_adjacent_windows(client, staged_survey, owner):
    """Adjacent (non-overlapping) windows [0,14) and [14,28) should not warn."""
    menu = StagedMenu.objects.create(survey=staged_survey)
    p1 = StagedPhase.objects.create(
        menu=menu, name="A", order=1, start_offset_days=0, end_offset_days=14
    )
    p2 = StagedPhase.objects.create(
        menu=menu, name="B", order=2, start_offset_days=14, end_offset_days=28
    )
    p1.groups.add(staged_survey._g1)
    p2.groups.add(staged_survey._g1, staged_survey._g2)
    res = _organise(client, staged_survey, owner)
    assert b"overlap" not in res.content.lower()


@pytest.mark.django_db
def test_warning_branching_targets_phased_section(client, staged_survey, owner):
    menu = StagedMenu.objects.create(survey=staged_survey)
    p1 = StagedPhase.objects.create(menu=menu, name="A", order=1)
    p2 = StagedPhase.objects.create(menu=menu, name="B", order=2)
    p1.groups.add(staged_survey._g1)
    p2.groups.add(staged_survey._g2)
    # A jump from the Baseline question into the Followup group.
    SurveyQuestionCondition.objects.create(
        question=staged_survey.questions.get(group=staged_survey._g1),
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=staged_survey._g2,
    )
    res = _organise(client, staged_survey, owner)
    assert b"phased section" in res.content.lower() or b"phase is closed" in res.content


@pytest.mark.django_db
def test_no_warnings_for_well_configured_staged(client, staged_survey, owner):
    """Two non-overlapping phases covering all sections produce no warnings."""
    menu = StagedMenu.objects.create(survey=staged_survey)
    p1 = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    p2 = StagedPhase.objects.create(
        menu=menu, name="Followup", order=2, start_offset_days=14, end_offset_days=28
    )
    p1.groups.add(staged_survey._g1)
    p2.groups.add(staged_survey._g2, staged_survey._g3)
    res = _organise(client, staged_survey, owner)
    # No warning alerts should appear.
    assert b"alert-warning" not in res.content
