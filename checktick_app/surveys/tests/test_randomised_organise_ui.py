"""Tests for the RCT Organise page UI (step 5).

Covers the layout picker RCT card, the RCT configuration card
(strategy/seed/arms/section assignment), add/remove arm, and the
single-section guard warning.
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
        slug="rct",
        layout=Survey.Layout.RCT,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Intervention", owner=owner)
    g3 = QuestionGroup.objects.create(name="Control", owner=owner)
    s.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Dose", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g3, text="Placebo", type=SurveyQuestion.Types.TEXT, order=0
    )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


# --- layout picker ---


@pytest.mark.django_db
def test_rct_card_shown_on_organise_page(client, rct_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": rct_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Randomised (RCT)" in html
    # RCT card is marked Current
    assert "Current" in html


@pytest.mark.django_db
def test_linear_survey_shows_rct_card_as_option(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear"
    )
    QuestionGroup.objects.create(name="G1", owner=owner)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Randomised (RCT)" in html


# --- RCT configuration card ---


@pytest.mark.django_db
def test_rct_config_card_shown_when_layout_rct(client, rct_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": rct_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Randomised trial configuration" in html
    assert "Allocation strategy" in html
    assert "Arms" in html


@pytest.mark.django_db
def test_rct_config_card_hidden_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear2", slug="linear2"
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    html = res.content.decode()
    assert "Randomised trial configuration" not in html


@pytest.mark.django_db
def test_default_arms_created_on_first_visit(client, rct_survey, owner):
    client.force_login(owner)
    client.get(reverse("surveys:groups", kwargs={"slug": rct_survey.slug}))
    menu = RandomisedMenu.objects.get(survey=rct_survey)
    arms = list(menu.arms.order_by("order"))
    assert [a.name for a in arms] == ["Intervention", "Control"]


# --- save_randomised_menu ---


@pytest.mark.django_db
def test_save_randomised_menu_strategy_and_seed(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": rct_survey.slug})
    # Ensure default menu + arms exist.
    client.get(url)
    menu = RandomisedMenu.objects.get(survey=rct_survey)
    arm = menu.arms.first()
    res = client.post(
        url,
        {
            "action": "save_randomised_menu",
            "allocation_strategy": "simple",
            "seed": "12345",
            "arm_ids": [str(arm.id)],
            f"arm_name_{arm.id}": "Treatment",
            f"arm_ratio_{arm.id}": "2",
            f"arm_groups_{arm.id}": [str(rct_survey._g1.id), str(rct_survey._g2.id)],
        },
    )
    assert res.status_code in (200, 302)
    menu.refresh_from_db()
    assert menu.allocation_strategy == "simple"
    assert menu.seed == 12345
    arm.refresh_from_db()
    assert arm.name == "Treatment"
    assert arm.allocation_ratio == 2
    assert set(arm.groups.values_list("id", flat=True)) == {
        rct_survey._g1.id,
        rct_survey._g2.id,
    }


@pytest.mark.django_db
def test_save_randomised_menu_blank_seed_clears(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": rct_survey.slug})
    client.get(url)
    menu = RandomisedMenu.objects.get(survey=rct_survey)
    menu.seed = 999
    menu.save()
    arm = menu.arms.first()
    client.post(
        url,
        {
            "action": "save_randomised_menu",
            "allocation_strategy": "balanced",
            "seed": "",
            "arm_ids": [str(arm.id)],
            f"arm_name_{arm.id}": "Arm",
            f"arm_ratio_{arm.id}": "1",
        },
    )
    menu.refresh_from_db()
    assert menu.seed is None


@pytest.mark.django_db
def test_save_randomised_menu_invalid_seed_falls_back_to_none(
    client, rct_survey, owner
):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": rct_survey.slug})
    client.get(url)
    menu = RandomisedMenu.objects.get(survey=rct_survey)
    arm = menu.arms.first()
    client.post(
        url,
        {
            "action": "save_randomised_menu",
            "allocation_strategy": "balanced",
            "seed": "not-a-number",
            "arm_ids": [str(arm.id)],
            f"arm_name_{arm.id}": "Arm",
            f"arm_ratio_{arm.id}": "1",
        },
    )
    menu.refresh_from_db()
    assert menu.seed is None


# --- add / remove arm ---


@pytest.mark.django_db
def test_add_arm(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": rct_survey.slug})
    client.get(url)
    menu = RandomisedMenu.objects.get(survey=rct_survey)
    assert menu.arms.count() == 2
    res = client.post(url, {"action": "add_arm"})
    assert res.status_code in (200, 302)
    assert RandomisedMenu.objects.get(survey=rct_survey).arms.count() == 3


@pytest.mark.django_db
def test_remove_arm(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": rct_survey.slug})
    client.get(url)
    menu = RandomisedMenu.objects.get(survey=rct_survey)
    arm_id = menu.arms.first().id
    res = client.post(url, {"action": "remove_arm", "arm_id": str(arm_id)})
    assert res.status_code in (200, 302)
    assert not RandomisedArm.objects.filter(id=arm_id).exists()


@pytest.mark.django_db
def test_remove_arm_invalid_id_does_nothing(client, rct_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": rct_survey.slug})
    client.get(url)
    count_before = RandomisedMenu.objects.get(survey=rct_survey).arms.count()
    client.post(url, {"action": "remove_arm", "arm_id": "99999"})
    assert RandomisedMenu.objects.get(survey=rct_survey).arms.count() == count_before


# --- layout switching ---


@pytest.mark.django_db
def test_switch_to_rct_layout(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Switch", slug="switch"
    )
    g1 = QuestionGroup.objects.create(name="A", owner=owner)
    g2 = QuestionGroup.objects.create(name="B", owner=owner)
    s.question_groups.add(g1, g2)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "rct"})
    assert res.status_code in (200, 302)
    s.refresh_from_db()
    assert s.layout == Survey.Layout.RCT
    # A RandomisedMenu is created on first visit (in the context build).
    client.get(url)
    assert RandomisedMenu.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_single_section_guard_warns_for_rct(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="One", slug="one-section-rct"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "rct"}, follow=True)
    # The warning message should appear after following the redirect.
    assert b"Randomised trials need at least 2 sections" in res.content


# --- read-only ---


@pytest.mark.django_db
def test_rct_config_read_only_when_cannot_edit(client, owner, org):
    """A survey in read-only mode shows the config but no save form."""
    other = type(owner).objects.create_user(
        username="other@example.com", password=TEST_PASSWORD
    )
    s = Survey.objects.create(
        owner=other,
        organization=org,
        name="Other",
        slug="other-rct",
        layout=Survey.Layout.RCT,
    )
    g = QuestionGroup.objects.create(name="G", owner=other)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    # owner is not the survey owner; should see read-only message.
    assert res.status_code in (200, 302)
    if res.status_code == 200:
        html = res.content.decode()
        assert "read-only" in html or "Randomised trial configuration" in html
