"""Tests for the Delphi preview simulate-round panel + Survey Map round
badges.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    Organization,
    QuestionGroup,
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
        username="delphi_preview@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def delphi_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Delphi Preview",
        slug="delphi-preview",
        layout=Survey.Layout.DELPHI,
    )
    g_r1 = QuestionGroup.objects.create(name="Round1", owner=owner)
    g_r2 = QuestionGroup.objects.create(name="Round2", owner=owner)
    g_shared = QuestionGroup.objects.create(name="Shared", owner=owner)
    s.question_groups.add(g_r1, g_r2, g_shared)
    SurveyQuestion.objects.create(
        survey=s, group=g_r1, text="R1Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_r2, text="R2Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_shared, text="SQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(g_r1, g_shared)
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="Round 2", start_offset_days=7, end_offset_days=14
    )
    r2.groups.add(g_r2, g_shared)
    s._g_r1, s._g_r2, s._g_shared = g_r1, g_r2, g_shared
    s._r1, s._r2 = r1, r2
    return s


# --- preview simulate round ---


@pytest.mark.django_db
def test_preview_shows_simulate_round_panel(client, delphi_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": delphi_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate round" in html
    assert "Round 1" in html
    assert "Round 2" in html


@pytest.mark.django_db
def test_preview_simulate_round_filters_questions(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    # Simulate Round 2.
    res = client.get(url, {"simulate_round": str(delphi_survey._r2.id)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "R2Q" in html
    assert "SQ" in html
    assert "R1Q" not in html


@pytest.mark.django_db
def test_preview_simulate_round_1(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    res = client.get(url, {"simulate_round": str(delphi_survey._r1.id)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "R1Q" in html
    assert "SQ" in html
    assert "R2Q" not in html


@pytest.mark.django_db
def test_preview_without_simulate_round_shows_all(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    # Without simulation, all questions appear.
    assert "R1Q" in html
    assert "R2Q" in html
    assert "SQ" in html


@pytest.mark.django_db
def test_preview_simulate_invalid_round_shows_all(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    res = client.get(url, {"simulate_round": "99999"})
    assert res.status_code == 200
    html = res.content.decode()
    assert "R1Q" in html
    assert "R2Q" in html
    assert "SQ" in html


@pytest.mark.django_db
def test_preview_simulate_round_with_reset(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": delphi_survey.slug})
    # Simulate round 1.
    res = client.get(url, {"simulate_round": str(delphi_survey._r1.id)})
    html = res.content.decode()
    assert "R1Q" in html
    assert "R2Q" not in html
    # Reset link present.
    assert "Reset" in html


# --- survey map round badges ---


@pytest.mark.django_db
def test_survey_map_shows_round_badges(client, delphi_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": delphi_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Delphi — round composition" in html
    assert "Round 1" in html
    assert "Round 2" in html
    # Window text.
    assert "days 0" in html
    assert "days 7" in html
    # Section names.
    assert "Round1" in html
    assert "Round2" in html
    assert "Shared" in html


@pytest.mark.django_db
def test_survey_map_no_round_badges_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-map-delphi"
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert "Delphi — round composition" not in res.content.decode()


@pytest.mark.django_db
def test_survey_map_delphi_no_rounds_warning(client, owner, org):
    """A Delphi survey with no rounds shows a warning on the Survey Map."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Empty Delphi",
        slug="empty-delphi-map",
        layout=Survey.Layout.DELPHI,
    )
    DelphiMenu.objects.create(survey=s)
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    html = res.content.decode()
    assert "Delphi — round composition" in html
    assert "no rounds configured" in html


@pytest.mark.django_db
def test_survey_map_delphi_round_with_no_groups_warning(client, owner, org):
    """A Delphi round with no groups shows a warning on the Survey Map."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Empty Round Delphi",
        slug="empty-round-delphi",
        layout=Survey.Layout.DELPHI,
    )
    menu = DelphiMenu.objects.create(survey=s)
    DelphiRound.objects.create(
        menu=menu, order=0, name="Empty", start_offset_days=0, end_offset_days=7
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    html = res.content.decode()
    assert "Delphi — round composition" in html
    assert "no sections" in html


@pytest.mark.django_db
def test_survey_map_delphi_open_ended_round(client, owner, org):
    """A round with no end_offset_days shows the open-ended window text."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Open Delphi",
        slug="open-delphi-map",
        layout=Survey.Layout.DELPHI,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    menu = DelphiMenu.objects.create(survey=s)
    rnd = DelphiRound.objects.create(
        menu=menu, order=0, name="Open", start_offset_days=0, end_offset_days=None
    )
    rnd.groups.add(g)
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    html = res.content.decode()
    assert "days 0+" in html
