"""Tests for the staged preview simulate-phase panel + Survey Map phase
badges (step 6).
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
        name="Staged Preview",
        slug="staged-preview",
        layout=Survey.Layout.STAGED,
    )
    g_base = QuestionGroup.objects.create(name="Baseline", owner=owner)
    g_follow = QuestionGroup.objects.create(name="Followup", owner=owner)
    g_review = QuestionGroup.objects.create(name="Review", owner=owner)
    s.question_groups.add(g_base, g_follow, g_review)
    SurveyQuestion.objects.create(
        survey=s, group=g_base, text="BQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_follow, text="FQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_review, text="RQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = StagedMenu.objects.create(survey=s)
    p1 = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    p1.groups.add(g_base)
    p2 = StagedPhase.objects.create(
        menu=menu, name="Followup", order=2, start_offset_days=14, end_offset_days=28
    )
    p2.groups.add(g_follow)
    p3 = StagedPhase.objects.create(
        menu=menu, name="Review", order=3, start_offset_days=180, end_offset_days=None
    )
    p3.groups.add(g_review)
    s._g_base, s._g_follow, s._g_review = g_base, g_follow, g_review
    s._p1, s._p2, s._p3 = p1, p2, p3
    return s


# --- preview simulate phase ---


@pytest.mark.django_db
def test_preview_shows_simulate_phase_panel(client, staged_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": staged_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate phase" in html
    assert "Baseline" in html
    assert "Followup" in html
    assert "Review" in html


@pytest.mark.django_db
def test_preview_simulate_phase_filters_questions(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": staged_survey.slug})
    # Simulate the Followup phase (a future phase).
    res = client.get(url, {"simulate_phase": str(staged_survey._p2.id)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "FQ" in html
    assert "BQ" not in html
    assert "RQ" not in html


@pytest.mark.django_db
def test_preview_simulate_baseline_phase(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": staged_survey.slug})
    res = client.get(url, {"simulate_phase": str(staged_survey._p1.id)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "BQ" in html
    assert "FQ" not in html


@pytest.mark.django_db
def test_preview_without_simulate_phase_shows_all(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": staged_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    # Without simulation, all questions appear (the union of all phases).
    assert "BQ" in html
    assert "FQ" in html
    assert "RQ" in html


@pytest.mark.django_db
def test_preview_simulate_invalid_phase_shows_all(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": staged_survey.slug})
    res = client.get(url, {"simulate_phase": "99999"})
    assert res.status_code == 200
    html = res.content.decode()
    assert "BQ" in html
    assert "FQ" in html
    assert "RQ" in html


# --- survey map phase badges ---


@pytest.mark.django_db
def test_survey_map_shows_phase_badges(client, staged_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": staged_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Staged — phase composition" in html
    assert "Baseline" in html
    assert "Followup" in html
    assert "Review" in html
    # Window text for the open-ended Review phase.
    assert "180" in html


@pytest.mark.django_db
def test_survey_map_no_phase_badges_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-map-staged"
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert "Staged — phase composition" not in res.content.decode()
