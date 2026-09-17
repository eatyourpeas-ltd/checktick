"""Tests for the Diary / EMA preview simulate-window panel + Survey Map.

The diary preview shows the schedule config and a note that a diary
entry uses all sections (no filtering needed). The preview renders
all questions so the author can test the instrument.

Mirrors ``test_delphi_preview_map.py`` in structure.
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
        username="diary_preview@example.com", password=TEST_PASSWORD
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
        name="Diary Preview",
        slug="diary-preview",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.TEXT, order=0
    )
    s._g = g
    return s


# --- preview shows simulate panel ---


@pytest.mark.django_db
def test_preview_shows_diary_panel(client, diary_survey, owner):
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary / EMA preview" in html
    assert "Fixed interval" in html
    assert "6h" in html


@pytest.mark.django_db
def test_preview_shows_burst_schedule(client, diary_survey, owner):
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.BURST,
        burst_on_days=7,
        burst_off_days=7,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Burst" in html
    assert "7 on / 7 off" in html


@pytest.mark.django_db
def test_preview_shows_event_triggered(client, diary_survey, owner):
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.EVENT_TRIGGERED,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Event-triggered" in html


# --- preview renders all questions (diary uses full group set) ---


@pytest.mark.django_db
def test_preview_renders_all_questions(client, diary_survey, owner):
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Pain level" in html


# --- preview creates DiaryMenu if missing ---


@pytest.mark.django_db
def test_preview_creates_menu_if_missing(client, diary_survey, owner):
    assert not DiaryMenu.objects.filter(survey=diary_survey).exists()
    client.force_login(owner)
    client.get(reverse("surveys:preview", kwargs={"slug": diary_survey.slug}))
    assert DiaryMenu.objects.filter(survey=diary_survey).exists()


# --- non-diary survey: no diary panel ---


@pytest.mark.django_db
def test_no_diary_panel_for_linear_survey(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-no-diary-panel",
        layout=Survey.Layout.LINEAR,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary / EMA preview" not in html
