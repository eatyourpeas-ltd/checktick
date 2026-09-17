"""Tests for the Diary / EMA Organise page UI.

Covers the layout picker Diary card, the Diary configuration card
(schedule type / anchor / interval / burst / compliance threshold /
grace period / show progress), save handler, and warnings for
misconfiguration.

Mirrors ``test_delphi_organise_ui.py`` in structure.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    DiaryMenu,
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
    user = django_user_model.objects.create_user(
        username="diary_organise@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def diary_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary",
        slug="diary-organise",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.LIKERT, order=0
    )
    s._g = g
    return s


# --- layout picker ---


@pytest.mark.django_db
def test_diary_card_shown_on_organise_page(client, diary_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary (EMA)" in html
    assert "Current" in html


@pytest.mark.django_db
def test_diary_card_shown_for_non_diary_survey(client, owner, org):
    """The Diary card appears on the organise page even for linear surveys."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-organise",
        layout=Survey.Layout.LINEAR,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary (EMA)" in html
    assert "Use this layout" in html


# --- configuration card ---


@pytest.mark.django_db
def test_config_card_shown_for_diary_survey(client, diary_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary / EMA configuration" in html
    assert "Schedule type" in html
    assert "Save configuration" in html


@pytest.mark.django_db
def test_config_card_not_shown_for_linear_survey(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-no-diary-config",
        layout=Survey.Layout.LINEAR,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary / EMA configuration" not in html


# --- save configuration ---


@pytest.mark.django_db
def test_save_diary_menu_fixed_interval(client, diary_survey, owner):
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": diary_survey.slug}),
        {
            "action": "save_diary_menu",
            "schedule_type": "fixed_interval",
            "anchor": "enrolment",
            "interval_hours": "6",
            "compliance_threshold_pct": "80",
            "grace_minutes": "30",
            "show_progress": "1",
        },
    )
    assert res.status_code == 302
    menu = DiaryMenu.objects.get(survey=diary_survey)
    assert menu.schedule_type == "fixed_interval"
    assert menu.anchor == "enrolment"
    assert menu.interval_hours == 6
    assert menu.compliance_threshold_pct == 80
    assert menu.grace_minutes == 30
    assert menu.show_progress is True


@pytest.mark.django_db
def test_save_diary_menu_burst(client, diary_survey, owner):
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": diary_survey.slug}),
        {
            "action": "save_diary_menu",
            "schedule_type": "burst",
            "anchor": "enrolment",
            "burst_on_days": "7",
            "burst_off_days": "7",
            "compliance_threshold_pct": "70",
            "grace_minutes": "15",
            "show_progress": "1",
        },
    )
    assert res.status_code == 302
    menu = DiaryMenu.objects.get(survey=diary_survey)
    assert menu.schedule_type == "burst"
    assert menu.burst_on_days == 7
    assert menu.burst_off_days == 7
    assert menu.compliance_threshold_pct == 70
    assert menu.grace_minutes == 15


@pytest.mark.django_db
def test_save_diary_menu_event_triggered(client, diary_survey, owner):
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": diary_survey.slug}),
        {
            "action": "save_diary_menu",
            "schedule_type": "event_triggered",
            "anchor": "enrolment",
            "show_progress": "1",
        },
    )
    assert res.status_code == 302
    menu = DiaryMenu.objects.get(survey=diary_survey)
    assert menu.schedule_type == "event_triggered"
    assert menu.interval_hours is None


@pytest.mark.django_db
def test_save_diary_menu_creates_menu_if_missing(client, diary_survey, owner):
    """Saving config creates the DiaryMenu if it doesn't exist yet."""
    assert not DiaryMenu.objects.filter(survey=diary_survey).exists()
    client.force_login(owner)
    client.post(
        reverse("surveys:groups", kwargs={"slug": diary_survey.slug}),
        {
            "action": "save_diary_menu",
            "schedule_type": "fixed_interval",
            "anchor": "enrolment",
            "interval_hours": "12",
            "show_progress": "1",
        },
    )
    assert DiaryMenu.objects.filter(survey=diary_survey).exists()


# --- set_layout ---


@pytest.mark.django_db
def test_set_layout_to_diary(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="To Diary",
        slug="to-diary",
        layout=Survey.Layout.LINEAR,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": s.slug}),
        {"action": "set_layout", "layout": "diary"},
    )
    assert res.status_code == 302
    s.refresh_from_db()
    assert s.layout == "diary"


# --- warnings ---


@pytest.mark.django_db
def test_warning_fixed_interval_no_interval(client, diary_survey, owner):
    """Fixed interval with no interval_hours shows a warning."""
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=None,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Fixed interval schedule has no interval set" in html


@pytest.mark.django_db
def test_warning_burst_no_on_days(client, diary_survey, owner):
    """Burst with no on_days shows a warning."""
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.BURST,
        burst_on_days=None,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Burst schedule has no on-days set" in html


@pytest.mark.django_db
def test_warning_survey_open_no_start_date(client, diary_survey, owner):
    """survey_open anchor with no start_at shows a warning."""
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.SURVEY_OPEN,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "no start date" in html


@pytest.mark.django_db
def test_no_warnings_for_valid_config(client, diary_survey, owner):
    """A valid config shows no warnings."""
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        compliance_threshold_pct=80,
        grace_minutes=30,
        show_progress=True,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "alert-warning" not in html


# --- free tier gating ---


@pytest.mark.django_db
def test_free_tier_sees_upgrade_link(client, django_user_model, org):
    """Free tier users see 'Upgrade to use' instead of 'Use this layout'."""
    free_user = django_user_model.objects.create_user(
        username="free_diary@example.com", password=TEST_PASSWORD
    )
    free_user.profile.account_tier = "free"
    free_user.profile.save()
    s = Survey.objects.create(
        owner=free_user,
        organization=None,
        name="Linear",
        slug="free-diary-view",
        layout=Survey.Layout.LINEAR,
    )
    client.force_login(free_user)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Upgrade to use" in html
