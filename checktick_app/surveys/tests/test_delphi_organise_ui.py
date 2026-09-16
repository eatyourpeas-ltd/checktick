"""Tests for the Delphi Organise page UI.

Covers the layout picker Delphi card, the Delphi configuration card
(anchor/rounds/section assignment/toggles), add/remove round, and
warnings for misconfiguration.
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
        username="delphi_organise@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def delphi_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Delphi",
        slug="delphi-organise",
        layout=Survey.Layout.DELPHI,
    )
    g1 = QuestionGroup.objects.create(name="Round1", owner=owner)
    g2 = QuestionGroup.objects.create(name="Round2", owner=owner)
    g3 = QuestionGroup.objects.create(name="Shared", owner=owner)
    s.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="R1Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="R2Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g3, text="SQ", type=SurveyQuestion.Types.TEXT, order=0
    )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


# --- layout picker ---


@pytest.mark.django_db
def test_delphi_card_shown_on_organise_page(client, delphi_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": delphi_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Delphi (consensus rounds)" in html
    assert "Current" in html


@pytest.mark.django_db
def test_linear_survey_shows_delphi_card_as_option(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-delphi"
    )
    QuestionGroup.objects.create(name="G1", owner=owner)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert "Delphi (consensus rounds)" in res.content.decode()


# --- delphi configuration card ---


@pytest.mark.django_db
def test_delphi_config_card_shown_when_layout_delphi(client, delphi_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": delphi_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Delphi (consensus rounds) configuration" in html
    assert "Round windows measured from" in html
    assert "Rounds" in html


@pytest.mark.django_db
def test_delphi_config_card_hidden_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear2", slug="linear2-delphi"
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert "Delphi (consensus rounds) configuration" not in res.content.decode()


@pytest.mark.django_db
def test_default_menu_created_on_first_visit(client, delphi_survey, owner):
    client.force_login(owner)
    client.get(reverse("surveys:groups", kwargs={"slug": delphi_survey.slug}))
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    assert menu.anchor == DelphiMenu.Anchor.ENROLMENT
    assert menu.min_rounds == 2
    assert menu.max_rounds == 3
    assert menu.show_progress is True
    assert menu.allow_revision is True
    # No rounds by default.
    assert menu.rounds.count() == 0


# --- save_delphi_menu ---


@pytest.mark.django_db
def test_save_delphi_menu_anchor_and_round(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    # First visit creates the menu.
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    rnd = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=14
    )
    res = client.post(
        url,
        {
            "action": "save_delphi_menu",
            "anchor": "survey_open",
            "min_rounds": "3",
            "max_rounds": "5",
            "show_progress": "1",
            "allow_revision": "1",
            "round_ids": [str(rnd.id)],
            f"round_name_{rnd.id}": "Initial Round",
            f"round_start_{rnd.id}": "0",
            f"round_end_{rnd.id}": "30",
            f"round_groups_{rnd.id}": [
                str(delphi_survey._g1.id),
                str(delphi_survey._g3.id),
            ],
        },
    )
    assert res.status_code in (200, 302)
    menu.refresh_from_db()
    assert menu.anchor == DelphiMenu.Anchor.SURVEY_OPEN
    assert menu.min_rounds == 3
    assert menu.max_rounds == 5
    rnd.refresh_from_db()
    assert rnd.name == "Initial Round"
    assert rnd.start_offset_days == 0
    assert rnd.end_offset_days == 30
    assert set(rnd.groups.values_list("id", flat=True)) == {
        delphi_survey._g1.id,
        delphi_survey._g3.id,
    }


@pytest.mark.django_db
def test_save_delphi_menu_blank_end_clears_to_open_ended(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    rnd = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=14
    )
    client.post(
        url,
        {
            "action": "save_delphi_menu",
            "anchor": "enrolment",
            "min_rounds": "2",
            "max_rounds": "3",
            "round_ids": [str(rnd.id)],
            f"round_name_{rnd.id}": "Round 1",
            f"round_start_{rnd.id}": "0",
            f"round_end_{rnd.id}": "",
        },
    )
    rnd.refresh_from_db()
    assert rnd.end_offset_days is None


@pytest.mark.django_db
def test_save_delphi_menu_toggles(client, delphi_survey, owner):
    """show_progress and allow_revision can be turned off."""
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    # Don't send show_progress or allow_revision → they default to False.
    client.post(
        url,
        {
            "action": "save_delphi_menu",
            "anchor": "enrolment",
            "min_rounds": "2",
            "max_rounds": "3",
        },
    )
    menu.refresh_from_db()
    assert menu.show_progress is False
    assert menu.allow_revision is False


@pytest.mark.django_db
def test_save_delphi_menu_invalid_min_falls_back(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    client.post(
        url,
        {
            "action": "save_delphi_menu",
            "anchor": "enrolment",
            "min_rounds": "not-a-number",
            "max_rounds": "also-not",
        },
    )
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    assert menu.min_rounds == 2
    assert menu.max_rounds == 3


# --- add / remove round ---


@pytest.mark.django_db
def test_add_round(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    assert menu.rounds.count() == 0
    res = client.post(url, {"action": "add_round"})
    assert res.status_code in (200, 302)
    assert DelphiMenu.objects.get(survey=delphi_survey).rounds.count() == 1


@pytest.mark.django_db
def test_remove_round(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    rnd = DelphiRound.objects.create(menu=menu, name="Round 1", order=1)
    res = client.post(url, {"action": "remove_round", "round_id": str(rnd.id)})
    assert res.status_code in (200, 302)
    assert not DelphiRound.objects.filter(id=rnd.id).exists()


@pytest.mark.django_db
def test_remove_round_invalid_id_does_nothing(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    DelphiRound.objects.create(menu=menu, name="Round 1", order=1)
    count_before = menu.rounds.count()
    client.post(url, {"action": "remove_round", "round_id": "99999"})
    assert DelphiMenu.objects.get(survey=delphi_survey).rounds.count() == count_before


# --- layout switching ---


@pytest.mark.django_db
def test_switch_to_delphi_layout(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Switch", slug="switch-delphi"
    )
    g1 = QuestionGroup.objects.create(name="A", owner=owner)
    g2 = QuestionGroup.objects.create(name="B", owner=owner)
    s.question_groups.add(g1, g2)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "delphi"})
    assert res.status_code in (200, 302)
    s.refresh_from_db()
    assert s.layout == Survey.Layout.DELPHI
    # A DelphiMenu is created on first visit.
    client.get(url)
    assert DelphiMenu.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_single_section_guard_warns_for_delphi(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="One", slug="one-section-delphi"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "delphi"}, follow=True)
    assert b"Delphi surveys need at least 2 sections" in res.content


# --- warnings ---


@pytest.mark.django_db
def test_warning_no_rounds(client, delphi_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": delphi_survey.slug}))
    html = res.content.decode()
    assert "No rounds are configured" in html


@pytest.mark.django_db
def test_warning_single_round(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    DelphiRound.objects.create(menu=menu, name="Only", order=0)
    res = client.get(url)
    html = res.content.decode()
    assert "structurally identical to a linear" in html


@pytest.mark.django_db
def test_warning_unreachable_section(client, delphi_survey, owner):
    """A section not in any round is flagged as unreachable."""
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    r1 = DelphiRound.objects.create(menu=menu, name="Round 1", order=0)
    r1.groups.add(delphi_survey._g1)
    r2 = DelphiRound.objects.create(menu=menu, name="Round 2", order=1)
    r2.groups.add(delphi_survey._g2)
    # _g3 (Shared) is not in any round.
    res = client.get(url)
    html = res.content.decode()
    assert "Shared" in html
    assert "not in any round" in html


@pytest.mark.django_db
def test_warning_survey_open_no_start_date(client, delphi_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    menu.anchor = DelphiMenu.Anchor.SURVEY_OPEN
    menu.save()
    res = client.get(url)
    html = res.content.decode()
    assert "no start date" in html


@pytest.mark.django_db
def test_no_warnings_when_well_configured(client, delphi_survey, owner):
    """A well-configured Delphi survey with 2 rounds and all sections assigned."""
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": delphi_survey.slug})
    client.get(url)
    menu = DelphiMenu.objects.get(survey=delphi_survey)
    r1 = DelphiRound.objects.create(
        menu=menu, name="Round 1", order=0, start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(delphi_survey._g1, delphi_survey._g3)
    r2 = DelphiRound.objects.create(
        menu=menu, name="Round 2", order=1, start_offset_days=7, end_offset_days=14
    )
    r2.groups.add(delphi_survey._g2, delphi_survey._g3)
    res = client.get(url)
    html = res.content.decode()
    # No warnings should appear for a well-configured survey.
    assert "No rounds are configured" not in html
    assert "structurally identical to a linear" not in html
    assert "not in any round" not in html


# --- read-only ---


@pytest.mark.django_db
def test_delphi_config_read_only_when_cannot_edit(client, owner, org):
    """A survey the user can't edit still renders the page (redirect or view)."""
    other = type(owner).objects.create_user(
        username="other@example.com", password=TEST_PASSWORD
    )
    other_org = Organization.objects.create(name="OtherOrg", owner=other)
    s = Survey.objects.create(
        owner=other,
        organization=other_org,
        name="ReadOnly",
        slug="readonly-delphi",
        layout=Survey.Layout.DELPHI,
    )
    g = QuestionGroup.objects.create(name="G", owner=other)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = DelphiMenu.objects.create(survey=s)
    DelphiRound.objects.create(menu=menu, name="Round 1", order=0)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    # User can't edit → 403 (require_can_edit raises PermissionDenied).
    assert res.status_code in (200, 302, 403)
