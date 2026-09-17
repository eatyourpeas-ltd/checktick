"""Tests for the Diary compliance dashboard + CSV export.

Covers:
- The compliance dashboard section on the survey dashboard (per-participant
  expected/submitted/missed/compliance %).
- The CSV export endpoint (one row per DiaryEntry).
- Threshold highlighting (below-threshold rows flagged).

Mirrors the Delphi feedback tests in structure.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DiaryEntry,
    DiaryMenu,
    Organization,
    QuestionGroup,
    Survey,
    SurveyProgress,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="diary_compliance@example.com", password=TEST_PASSWORD
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
        name="Diary Compliance",
        slug="diary-compliance",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.TEXT, order=0
    )
    return s


def _make_menu_and_participant(survey, participant_user, *, interval_hours=6):
    """Create a DiaryMenu + a SurveyProgress with diary_enrolled_at set."""
    menu = DiaryMenu.objects.create(
        survey=survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=interval_hours,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        compliance_threshold_pct=80,
        grace_minutes=30,
        show_progress=True,
    )
    now = timezone.now()
    progress = SurveyProgress.objects.create(
        survey=survey,
        user=participant_user,
        diary_enrolled_at=now - timedelta(hours=24),
        expires_at=now + timedelta(days=30),
    )
    return menu, progress, now


# --- dashboard shows compliance section ---


@pytest.mark.django_db
def test_dashboard_shows_compliance_section(
    client, diary_survey, owner, django_user_model
):
    participant = django_user_model.objects.create_user(
        username="diary_p1@example.com", password=TEST_PASSWORD
    )
    menu, progress, now = _make_menu_and_participant(diary_survey, participant)
    # Create a submitted entry.
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=progress.diary_enrolled_at,
        expected_end=progress.diary_enrolled_at + timedelta(hours=6),
        submitted_at=now - timedelta(hours=20),
    )

    client.force_login(owner)
    res = client.get(reverse("surveys:dashboard", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary Compliance" in html
    assert "diary_p1@example.com" in html
    assert "Export CSV" in html


@pytest.mark.django_db
def test_dashboard_no_compliance_for_linear_survey(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-no-compliance",
        layout=Survey.Layout.LINEAR,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:dashboard", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary Compliance" not in html


@pytest.mark.django_db
def test_dashboard_shows_threshold(client, diary_survey, owner, django_user_model):
    participant = django_user_model.objects.create_user(
        username="diary_p2@example.com", password=TEST_PASSWORD
    )
    menu, progress, now = _make_menu_and_participant(diary_survey, participant)
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=progress.diary_enrolled_at,
        expected_end=progress.diary_enrolled_at + timedelta(hours=6),
        submitted_at=now - timedelta(hours=20),
    )

    client.force_login(owner)
    res = client.get(reverse("surveys:dashboard", kwargs={"slug": diary_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Compliance threshold: 80%" in html


# --- CSV export ---


@pytest.mark.django_db
def test_csv_export_returns_csv(client, diary_survey, owner, django_user_model):
    participant = django_user_model.objects.create_user(
        username="diary_csv@example.com", password=TEST_PASSWORD
    )
    menu, progress, now = _make_menu_and_participant(diary_survey, participant)
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=progress.diary_enrolled_at,
        expected_end=progress.diary_enrolled_at + timedelta(hours=6),
        submitted_at=now - timedelta(hours=20),
    )
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=1,
        expected_start=progress.diary_enrolled_at + timedelta(hours=6),
        expected_end=progress.diary_enrolled_at + timedelta(hours=12),
        submitted_at=None,
        is_missed=True,
    )

    client.force_login(owner)
    res = client.get(
        reverse(
            "surveys:diary_export_compliance_csv", kwargs={"slug": diary_survey.slug}
        )
    )
    assert res.status_code == 200
    assert res["Content-Type"] == "text/csv"
    assert "attachment" in res["Content-Disposition"]
    content = res.content.decode()
    assert "participant" in content
    assert "window_order" in content
    assert "expected_start" in content
    assert "submitted_at" in content
    assert "is_missed" in content
    assert "diary_csv@example.com" in content
    assert "yes" in content  # is_missed for the second entry


@pytest.mark.django_db
def test_csv_export_empty_survey(client, diary_survey, owner):
    """CSV export works even with no entries."""
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
    )
    client.force_login(owner)
    res = client.get(
        reverse(
            "surveys:diary_export_compliance_csv", kwargs={"slug": diary_survey.slug}
        )
    )
    assert res.status_code == 200
    assert res["Content-Type"] == "text/csv"
    content = res.content.decode()
    assert "participant" in content  # Header row only.


@pytest.mark.django_db
def test_csv_export_rejects_non_diary_survey(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear",
        slug="linear-csv-export",
        layout=Survey.Layout.LINEAR,
    )
    client.force_login(owner)
    res = client.get(
        reverse("surveys:diary_export_compliance_csv", kwargs={"slug": s.slug})
    )
    assert res.status_code == 400


@pytest.mark.django_db
def test_csv_export_requires_edit_permission(client, diary_survey, django_user_model):
    """A user without edit permission cannot export."""
    viewer = django_user_model.objects.create_user(
        username="diary_viewer@example.com", password=TEST_PASSWORD
    )
    client.force_login(viewer)
    res = client.get(
        reverse(
            "surveys:diary_export_compliance_csv", kwargs={"slug": diary_survey.slug}
        )
    )
    # require_can_edit redirects or returns 403.
    assert res.status_code in (302, 403)
