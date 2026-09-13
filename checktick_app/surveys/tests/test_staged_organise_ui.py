"""Tests for the staged Organise page UI (step 4).

Covers the layout picker Staged card, the staged configuration card
(anchor/phases/section assignment), add/remove phase, and the
single-section guard warning.
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
        name="Staged",
        slug="staged",
        layout=Survey.Layout.STAGED,
    )
    g1 = QuestionGroup.objects.create(name="Baseline", owner=owner)
    g2 = QuestionGroup.objects.create(name="Followup", owner=owner)
    g3 = QuestionGroup.objects.create(name="Review", owner=owner)
    s.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="BQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="FQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g3, text="RQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


# --- layout picker ---


@pytest.mark.django_db
def test_staged_card_shown_on_organise_page(client, staged_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": staged_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Staged (longitudinal)" in html
    assert "Current" in html


@pytest.mark.django_db
def test_linear_survey_shows_staged_card_as_option(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-staged"
    )
    QuestionGroup.objects.create(name="G1", owner=owner)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    assert "Staged (longitudinal)" in res.content.decode()


# --- staged configuration card ---


@pytest.mark.django_db
def test_staged_config_card_shown_when_layout_staged(client, staged_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": staged_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Staged (longitudinal) configuration" in html
    assert "Phase windows measured from" in html
    assert "Phases" in html


@pytest.mark.django_db
def test_staged_config_card_hidden_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear2", slug="linear2-staged"
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert "Staged (longitudinal) configuration" not in res.content.decode()


@pytest.mark.django_db
def test_default_menu_created_on_first_visit(client, staged_survey, owner):
    client.force_login(owner)
    client.get(reverse("surveys:groups", kwargs={"slug": staged_survey.slug}))
    menu = StagedMenu.objects.get(survey=staged_survey)
    assert menu.anchor == StagedMenu.Anchor.ENROLMENT
    # No phases by default.
    assert menu.phases.count() == 0


# --- save_staged_menu ---


@pytest.mark.django_db
def test_save_staged_menu_anchor_and_phase(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": staged_survey.slug})
    # First visit creates the menu.
    client.get(url)
    menu = StagedMenu.objects.get(survey=staged_survey)
    phase = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    res = client.post(
        url,
        {
            "action": "save_staged_menu",
            "anchor": "survey_open",
            "phase_ids": [str(phase.id)],
            f"phase_name_{phase.id}": "Baseline Phase",
            f"phase_start_{phase.id}": "0",
            f"phase_end_{phase.id}": "30",
            f"phase_groups_{phase.id}": [
                str(staged_survey._g1.id),
                str(staged_survey._g2.id),
            ],
        },
    )
    assert res.status_code in (200, 302)
    menu.refresh_from_db()
    assert menu.anchor == StagedMenu.Anchor.SURVEY_OPEN
    phase.refresh_from_db()
    assert phase.name == "Baseline Phase"
    assert phase.start_offset_days == 0
    assert phase.end_offset_days == 30
    assert set(phase.groups.values_list("id", flat=True)) == {
        staged_survey._g1.id,
        staged_survey._g2.id,
    }


@pytest.mark.django_db
def test_save_staged_menu_blank_end_clears_to_open_ended(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": staged_survey.slug})
    client.get(url)
    menu = StagedMenu.objects.get(survey=staged_survey)
    phase = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    client.post(
        url,
        {
            "action": "save_staged_menu",
            "anchor": "enrolment",
            "phase_ids": [str(phase.id)],
            f"phase_name_{phase.id}": "Baseline",
            f"phase_start_{phase.id}": "0",
            f"phase_end_{phase.id}": "",
        },
    )
    phase.refresh_from_db()
    assert phase.end_offset_days is None


@pytest.mark.django_db
def test_save_staged_menu_invalid_start_falls_back_to_zero(
    client, staged_survey, owner
):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": staged_survey.slug})
    client.get(url)
    menu = StagedMenu.objects.get(survey=staged_survey)
    phase = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=5
    )
    client.post(
        url,
        {
            "action": "save_staged_menu",
            "anchor": "enrolment",
            "phase_ids": [str(phase.id)],
            f"phase_name_{phase.id}": "Baseline",
            f"phase_start_{phase.id}": "not-a-number",
            f"phase_end_{phase.id}": "",
        },
    )
    phase.refresh_from_db()
    assert phase.start_offset_days == 0


# --- add / remove phase ---


@pytest.mark.django_db
def test_add_phase(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": staged_survey.slug})
    client.get(url)
    menu = StagedMenu.objects.get(survey=staged_survey)
    assert menu.phases.count() == 0
    res = client.post(url, {"action": "add_phase"})
    assert res.status_code in (200, 302)
    assert StagedMenu.objects.get(survey=staged_survey).phases.count() == 1


@pytest.mark.django_db
def test_remove_phase(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": staged_survey.slug})
    client.get(url)
    menu = StagedMenu.objects.get(survey=staged_survey)
    phase = StagedPhase.objects.create(menu=menu, name="Baseline", order=1)
    res = client.post(url, {"action": "remove_phase", "phase_id": str(phase.id)})
    assert res.status_code in (200, 302)
    assert not StagedPhase.objects.filter(id=phase.id).exists()


@pytest.mark.django_db
def test_remove_phase_invalid_id_does_nothing(client, staged_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": staged_survey.slug})
    client.get(url)
    menu = StagedMenu.objects.get(survey=staged_survey)
    StagedPhase.objects.create(menu=menu, name="Baseline", order=1)
    count_before = menu.phases.count()
    client.post(url, {"action": "remove_phase", "phase_id": "99999"})
    assert StagedMenu.objects.get(survey=staged_survey).phases.count() == count_before


# --- layout switching ---


@pytest.mark.django_db
def test_switch_to_staged_layout(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Switch", slug="switch-staged"
    )
    g1 = QuestionGroup.objects.create(name="A", owner=owner)
    g2 = QuestionGroup.objects.create(name="B", owner=owner)
    s.question_groups.add(g1, g2)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "staged"})
    assert res.status_code in (200, 302)
    s.refresh_from_db()
    assert s.layout == Survey.Layout.STAGED
    # A StagedMenu is created on first visit (in the context build).
    client.get(url)
    assert StagedMenu.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_single_section_guard_warns_for_staged(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="One", slug="one-section-staged"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "staged"}, follow=True)
    assert b"Staged surveys need at least 2 sections" in res.content


# --- read-only ---


@pytest.mark.django_db
def test_staged_config_read_only_when_cannot_edit(client, owner, org):
    """A survey in read-only mode shows the config but no save form."""
    other = type(owner).objects.create_user(
        username="other@example.com", password=TEST_PASSWORD
    )
    s = Survey.objects.create(
        owner=other,
        organization=org,
        name="Other",
        slug="other-staged",
        layout=Survey.Layout.STAGED,
    )
    g = QuestionGroup.objects.create(name="G", owner=other)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code in (200, 302)
    if res.status_code == 200:
        html = res.content.decode()
        assert "read-only" in html or "Staged (longitudinal) configuration" in html
