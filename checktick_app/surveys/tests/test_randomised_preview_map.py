"""Tests for the RCT preview simulate-arm panel + Survey Map arm badges (steps 8-9)."""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RandomisedArm,
    RandomisedMenu,
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
def rct_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RCT Preview",
        slug="rct-preview",
        layout=Survey.Layout.RCT,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_int = QuestionGroup.objects.create(name="Intervention", owner=owner)
    g_ctrl = QuestionGroup.objects.create(name="Control", owner=owner)
    s.question_groups.add(g_demo, g_int, g_ctrl)
    SurveyQuestion.objects.create(
        survey=s, group=g_demo, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_int, text="Dose", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_ctrl, text="Placebo", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = RandomisedMenu.objects.create(survey=s, seed=42)
    arm_int = RandomisedArm.objects.create(menu=menu, name="Intervention", order=1)
    arm_ctrl = RandomisedArm.objects.create(menu=menu, name="Control", order=2)
    arm_int.groups.add(g_demo, g_int)
    arm_ctrl.groups.add(g_demo, g_ctrl)
    s._g_demo, s._g_int, s._g_ctrl = g_demo, g_int, g_ctrl
    s._arm_int, s._arm_ctrl = arm_int, arm_ctrl
    return s


# --- preview simulate arm ---


@pytest.mark.django_db
def test_preview_shows_simulate_arm_panel(client, rct_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": rct_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate arm" in html
    assert "Intervention" in html
    assert "Control" in html


@pytest.mark.django_db
def test_preview_simulate_arm_filters_questions(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": rct_survey.slug})
    # Simulate the Intervention arm.
    res = client.get(url, {"simulate_arm": str(rct_survey._arm_int.id)})
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (shared) + Dose (Intervention) appear; Placebo does not.
    assert "Age" in html
    assert "Dose" in html
    assert "Placebo" not in html


@pytest.mark.django_db
def test_preview_simulate_control_arm(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": rct_survey.slug})
    res = client.get(url, {"simulate_arm": str(rct_survey._arm_ctrl.id)})
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "Placebo" in html
    assert "Dose" not in html


@pytest.mark.django_db
def test_preview_without_simulate_arm_shows_all(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": rct_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    # Without simulation, all questions appear (the union of all arms).
    assert "Age" in html
    assert "Dose" in html
    assert "Placebo" in html


@pytest.mark.django_db
def test_preview_simulate_invalid_arm_shows_all(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": rct_survey.slug})
    res = client.get(url, {"simulate_arm": "99999"})
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "Dose" in html
    assert "Placebo" in html


# --- survey map arm badges ---


@pytest.mark.django_db
def test_survey_map_shows_arm_badges(client, rct_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": rct_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Randomised trial — arm composition" in html
    assert "Intervention" in html
    assert "Control" in html
    assert "Demographics" in html
    assert "ratio 1" in html


@pytest.mark.django_db
def test_survey_map_no_arm_badges_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-map"
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    html = res.content.decode()
    assert "Randomised trial — arm composition" not in html
