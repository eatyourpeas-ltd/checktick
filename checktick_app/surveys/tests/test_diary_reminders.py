"""Tests for the diary reminder email + process_diary_reminders command.

Covers:
- send_diary_reminder_email: sends a branded email with the survey name,
  link, and window end time.
- process_diary_reminders: sends reminders for open windows where the
  participant hasn't submitted; skips submitted entries, event-triggered
  surveys, and participants without email addresses.
"""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
import pytest

from checktick_app.core.email_utils import send_diary_reminder_email
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
        username="diary_reminder_owner@example.com",
        password=TEST_PASSWORD,
        email="diary_reminder_owner@example.com",
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
        name="Diary Reminder Test",
        slug="diary-reminder-test",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.TEXT, order=0
    )
    return s


def _make_participant(django_user_model, survey, *, email="p@example.com"):
    """Create a participant with an enrolled progress row."""
    participant = django_user_model.objects.create_user(
        username=email, password=TEST_PASSWORD, email=email
    )
    now = timezone.now()
    progress = SurveyProgress.objects.create(
        survey=survey,
        user=participant,
        diary_enrolled_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=30),
    )
    return participant, progress


# --- send_diary_reminder_email ---


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_send_diary_reminder_email_sends(mailoutbox, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    ok = send_diary_reminder_email(
        to_email="participant@example.com",
        survey_name="Pain Diary",
        survey_url="https://example.com/surveys/pain-diary/",
        window_end="18:00",
    )
    assert ok is True
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert "Pain Diary" in email.subject
    assert "participant@example.com" in email.to
    # The .md template renders (not the f-string fallback).
    body = email.alternatives[0][0] if email.alternatives else email.body
    assert "New Diary Entry Available" in body
    assert "Window closes at" in body
    assert "18:00" in body
    assert "Complete Your Diary Entry" in body


# --- process_diary_reminders command ---


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_command_sends_reminder_for_open_window(
    client, diary_survey, owner, django_user_model, mailoutbox, settings
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        grace_minutes=30,
    )
    _participant, progress = _make_participant(
        django_user_model, diary_survey, email="reminded@example.com"
    )

    out = StringIO()
    call_command("process_diary_reminders", stdout=out)
    output = out.getvalue()
    assert "Sent 1 diary reminder" in output
    assert len(mailoutbox) == 1
    assert "reminded@example.com" in mailoutbox[0].to


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_command_skips_submitted_entry(
    diary_survey, owner, django_user_model, mailoutbox, settings
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    menu = DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        grace_minutes=30,
    )
    _participant, progress = _make_participant(
        django_user_model, diary_survey, email="submitted@example.com"
    )
    # Create a submitted DiaryEntry for the current window (order 0).
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=progress.diary_enrolled_at,
        expected_end=progress.diary_enrolled_at + timedelta(hours=6),
        submitted_at=timezone.now(),
    )

    out = StringIO()
    call_command("process_diary_reminders", stdout=out)
    output = out.getvalue()
    assert "Sent 0 diary reminder" in output
    assert len(mailoutbox) == 0


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_command_skips_event_triggered(
    diary_survey, owner, django_user_model, mailoutbox, settings
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.EVENT_TRIGGERED,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    _participant, _progress = _make_participant(
        django_user_model, diary_survey, email="event@example.com"
    )

    out = StringIO()
    call_command("process_diary_reminders", stdout=out)
    output = out.getvalue()
    assert "Sent 0 diary reminder" in output
    assert len(mailoutbox) == 0


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_command_skips_participant_without_email(
    diary_survey, owner, django_user_model, mailoutbox, settings
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    _participant, _progress = _make_participant(
        django_user_model, diary_survey, email="no-email@example.com"
    )
    # Clear the email address.
    _participant.email = ""
    _participant.save()

    out = StringIO()
    call_command("process_diary_reminders", stdout=out)
    output = out.getvalue()
    assert "Sent 0 diary reminder" in output
    assert len(mailoutbox) == 0


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_command_dry_run_sends_nothing(
    diary_survey, owner, django_user_model, mailoutbox, settings
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
    )
    _participant, _progress = _make_participant(
        django_user_model, diary_survey, email="dryrun@example.com"
    )

    out = StringIO()
    call_command("process_diary_reminders", "--dry-run", stdout=out)
    output = out.getvalue()
    assert "DRY RUN" in output
    assert len(mailoutbox) == 0


@pytest.mark.django_db
@override_settings(SITE_URL="https://example.com")
def test_command_skips_no_window_open(
    diary_survey, owner, django_user_model, mailoutbox, settings
):
    """When no window is open (e.g. burst off-period), no reminder is sent."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    DiaryMenu.objects.create(
        survey=diary_survey,
        schedule_type=DiaryMenu.ScheduleType.BURST,
        burst_on_days=1,
        burst_off_days=7,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        grace_minutes=30,
    )
    _participant, progress = _make_participant(
        django_user_model, diary_survey, email="offperiod@example.com"
    )
    # Move the enrolment anchor 3 days into the past — past the 1-day
    # on-period, into the off-period.
    progress.diary_enrolled_at = timezone.now() - timedelta(days=3)
    progress.save(update_fields=["diary_enrolled_at"])

    out = StringIO()
    call_command("process_diary_reminders", stdout=out)
    output = out.getvalue()
    assert "Sent 0 diary reminder" in output
    assert len(mailoutbox) == 0
