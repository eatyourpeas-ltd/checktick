"""Tests for the Diary / EMA runtime hook.

When survey.layout == diary, the take view:
- Sets diary_enrolled_at on first access (enrolment anchor).
- Marks past-unsent entries as missed (compliance audit trail).
- Ensures a DiaryEntry exists for the current window.
- Renders the diary landing page when no window is open.
- Renders the entry form (?entry=1) when a window is open.
- On submit (action=submit_entry), sets entry.submitted_at and marks
  progress as completed.

Mirrors ``test_delphi_runtime.py`` in structure.
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
    SurveyResponse,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="diary_owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def participant(django_user_model):
    return django_user_model.objects.create_user(
        username="diary_participant@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


def _make_diary_survey(owner, org, *, slug="diary-survey", start_at=None):
    """A published Diary survey with one group and one question."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Survey",
        slug=slug,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.DIARY,
        start_at=start_at,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s,
        group=g,
        text="Pain level",
        type=SurveyQuestion.Types.LIKERT,
        order=0,
    )
    s._g = g
    return s


def _make_fixed_interval_menu(survey, *, interval_hours=6, anchor="enrolment"):
    return DiaryMenu.objects.create(
        survey=survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=interval_hours,
        anchor=anchor,
        grace_minutes=30,
        show_progress=True,
    )


# --- first access: enrolment anchor set ---


@pytest.mark.django_db
def test_first_access_sets_enrolment_anchor(client, owner, org, participant):
    s = _make_diary_survey(owner, org)
    _make_fixed_interval_menu(s, interval_hours=6)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.diary_enrolled_at is not None


# --- window open: landing page renders ---


@pytest.mark.django_db
def test_window_open_renders_landing_page(client, owner, org, participant):
    s = _make_diary_survey(owner, org)
    _make_fixed_interval_menu(s, interval_hours=6)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # Landing page shows the "Start this entry" button.
    assert "Start this entry" in html
    assert "Pain level" not in html  # Questions not rendered on landing page


# --- window open: entry form renders with ?entry=1 ---


@pytest.mark.django_db
def test_window_open_entry_form_renders_questions(client, owner, org, participant):
    s = _make_diary_survey(owner, org)
    _make_fixed_interval_menu(s, interval_hours=6)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}) + "?entry=1")
    assert res.status_code == 200
    html = res.content.decode()
    assert "Pain level" in html


# --- DiaryEntry created on access ---


@pytest.mark.django_db
def test_diary_entry_created_on_access(client, owner, org, participant):
    s = _make_diary_survey(owner, org)
    menu = _make_fixed_interval_menu(s, interval_hours=6)

    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    entries = DiaryEntry.objects.filter(menu=menu, progress=progress)
    assert entries.count() == 1
    entry = entries.first()
    assert entry.order == 0
    assert entry.submitted_at is None
    assert entry.is_missed is False
    assert entry.expected_start is not None
    assert entry.expected_end is not None


# --- no window open: waiting page renders ---


@pytest.mark.django_db
def test_no_window_open_renders_waiting_page(client, owner, org, participant):
    s = _make_diary_survey(owner, org, slug="diary-future")
    # Use a burst schedule with a short on-period that has already passed.
    # anchor = enrolment, on_days=1, off_days=7. After day 1, no window is
    # open until day 8.
    menu = DiaryMenu.objects.create(
        survey=s,
        schedule_type=DiaryMenu.ScheduleType.BURST,
        burst_on_days=1,
        burst_off_days=7,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        grace_minutes=30,
        show_progress=True,
    )

    client.force_login(participant)
    # First access creates the progress row + enrolment anchor.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    # Move the enrolment anchor 3 days into the past — past the 1-day
    # on-period, into the off-period.
    past = timezone.now() - timedelta(days=3)
    progress.diary_enrolled_at = past
    progress.save(update_fields=["diary_enrolled_at"])
    # Also move the DiaryEntry's expected times into the past so it gets
    # marked as missed, and the current_window returns None (off-period).
    DiaryEntry.objects.filter(menu=menu, progress=progress).update(
        expected_start=past,
        expected_end=past + timedelta(hours=24),
    )

    # Second access: no window open (off-period) → waiting page.
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "No diary window open right now" in html
    assert "Pain level" not in html


# --- no DiaryMenu configured: error redirect ---


@pytest.mark.django_db
def test_no_diary_menu_renders_error(client, owner, org, participant):
    s = _make_diary_survey(owner, org, slug="diary-unconfigured")
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    # Redirects to the detail page with an error message.
    assert res.status_code == 302


# --- submit entry: marks entry submitted and progress completed ---


@pytest.mark.django_db
def test_submit_entry_marks_submitted(client, owner, org, participant):
    s = _make_diary_survey(owner, org)
    menu = _make_fixed_interval_menu(s, interval_hours=6)

    client.force_login(participant)
    # First GET to create the progress row + DiaryEntry.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    entry = DiaryEntry.objects.get(menu=menu, progress=progress)
    assert entry.submitted_at is None

    # Submit the entry.
    q = s.questions.first()
    res = client.post(
        reverse("surveys:take", kwargs={"slug": s.slug}) + "?entry=1",
        {
            "action": "submit_entry",
            f"q_{q.id}": "3",  # likert value
        },
    )
    assert res.status_code == 302
    entry.refresh_from_db()
    assert entry.submitted_at is not None
    progress.refresh_from_db()
    assert progress.status == SurveyProgress.Status.COMPLETED
    assert SurveyResponse.objects.filter(survey=s).count() == 1


# --- missed entry: marked when window closes ---


@pytest.mark.django_db
def test_missed_entry_marked_when_window_closes(client, owner, org, participant):
    s = _make_diary_survey(owner, org, slug="diary-missed")
    menu = _make_fixed_interval_menu(s, interval_hours=6, anchor="enrolment")

    client.force_login(participant)
    # First access creates the progress row + enrolment anchor + DiaryEntry.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    entry = DiaryEntry.objects.get(menu=menu, progress=progress)
    assert entry.is_missed is False

    # Move the enrolment anchor far into the past so the window has closed
    # and the grace period has expired.
    past = timezone.now() - timedelta(hours=10)
    progress.diary_enrolled_at = past
    progress.save(update_fields=["diary_enrolled_at"])
    # Also move the entry's expected times into the past.
    entry.expected_start = past
    entry.expected_end = past + timedelta(hours=6)
    entry.save(update_fields=["expected_start", "expected_end"])

    # Second access: the runtime hook marks the entry as missed.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    entry.refresh_from_db()
    assert entry.is_missed is True


# --- resume preserves enrolment anchor ---


@pytest.mark.django_db
def test_resume_preserves_enrolment_anchor(client, owner, org, participant):
    s = _make_diary_survey(owner, org)
    _make_fixed_interval_menu(s, interval_hours=6)

    client.force_login(participant)
    # First access.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    enrolled = progress.diary_enrolled_at
    assert enrolled is not None

    # Second access — enrolment anchor unchanged.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress.refresh_from_db()
    assert progress.diary_enrolled_at == enrolled


# --- event_triggered schedule: always renders waiting page ---


@pytest.mark.django_db
def test_event_triggered_renders_waiting_page(client, owner, org, participant):
    s = _make_diary_survey(owner, org, slug="diary-event")
    DiaryMenu.objects.create(
        survey=s,
        schedule_type=DiaryMenu.ScheduleType.EVENT_TRIGGERED,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        show_progress=True,
    )

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # Event-triggered has no scheduled windows, so the waiting page renders.
    assert "No diary window open right now" in html
