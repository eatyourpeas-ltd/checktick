"""Tests for the Delphi round-scheduling functions.

Tests ``current_round``, ``next_round``, and ``assign_round_for_progress``
in ``delphi.py``. These mirror the Staged layout's phase-resolution tests
(``test_staged_resolution.py``) but for Delphi rounds.

The round-scheduling logic determines which round a participant should be
on at a given time, based on the menu anchor (enrolment vs survey_open),
the round window offsets, and manual open/close overrides.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.delphi import (
    assign_round_for_progress,
    current_round,
    next_round,
)
from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    Organization,
    Survey,
    SurveyProgress,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="delphi_sched@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="Sched Test",
        slug="delphi-sched",
        layout=Survey.Layout.DELPHI,
    )


@pytest.fixture
def menu(survey):
    return DelphiMenu.objects.create(survey=survey, anchor=DelphiMenu.Anchor.ENROLMENT)


@pytest.fixture
def now():
    return timezone.now()


# --- current_round ---


@pytest.mark.django_db
def test_current_round_no_rounds(menu, now):
    """A menu with no rounds returns None."""
    result = current_round(menu, enrolment=now, survey_start=None, now=now)
    assert result is None


@pytest.mark.django_db
def test_current_round_open_by_window(menu, now):
    """A round whose window is open is returned."""
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    result = current_round(menu, enrolment=now, survey_start=None, now=now)
    assert result == r1


@pytest.mark.django_db
def test_current_round_not_yet_open(menu, now):
    """A round that hasn't reached its start offset is not returned."""
    DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=7, end_offset_days=14
    )
    result = current_round(menu, enrolment=now, survey_start=None, now=now)
    assert result is None


@pytest.mark.django_db
def test_current_round_closed_by_window(menu, now):
    """A round whose window has passed is not returned."""
    enrolment = now - timedelta(days=20)
    DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    result = current_round(menu, enrolment=enrolment, survey_start=None, now=now)
    assert result is None


@pytest.mark.django_db
def test_current_round_open_ended(menu, now):
    """A round with no end_offset_days never closes."""
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=None
    )
    far_future = now + timedelta(days=365)
    result = current_round(menu, enrolment=now, survey_start=None, now=far_future)
    assert result == r1


@pytest.mark.django_db
def test_current_round_second_round_open(menu, now):
    """When the first round's window has passed and the second is open."""
    enrolment = now - timedelta(days=10)
    DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="R2", start_offset_days=7, end_offset_days=14
    )
    result = current_round(menu, enrolment=enrolment, survey_start=None, now=now)
    assert result == r2


@pytest.mark.django_db
def test_current_round_manual_open_override(menu, now):
    """Manual opened_at overrides the window offset."""
    r1 = DelphiRound.objects.create(
        menu=menu,
        order=0,
        name="R1",
        start_offset_days=30,  # Not yet open by window
        end_offset_days=37,
        opened_at=now,  # But manually opened
    )
    result = current_round(menu, enrolment=now, survey_start=None, now=now)
    assert result == r1


@pytest.mark.django_db
def test_current_round_manual_closed_override(menu, now):
    """Manual closed_at closes the round regardless of window."""
    enrolment = now - timedelta(days=3)
    DelphiRound.objects.create(
        menu=menu,
        order=0,
        name="R1",
        start_offset_days=0,
        end_offset_days=7,  # Window still open
        closed_at=now,  # But manually closed
    )
    result = current_round(menu, enrolment=enrolment, survey_start=None, now=now)
    assert result is None


@pytest.mark.django_db
def test_current_round_survey_open_anchor(survey, owner, org):
    """The survey_open anchor uses Survey.start_at instead of enrolment."""
    from django.utils import timezone

    start = timezone.now() - timedelta(days=3)
    survey.start_at = start
    survey.save()
    menu = DelphiMenu.objects.create(
        survey=survey, anchor=DelphiMenu.Anchor.SURVEY_OPEN
    )
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    now = timezone.now()
    result = current_round(menu, enrolment=None, survey_start=start, now=now)
    assert result == r1


@pytest.mark.django_db
def test_current_round_survey_open_anchor_no_start(survey):
    """survey_open anchor with no Survey.start_at returns None."""
    menu = DelphiMenu.objects.create(
        survey=survey, anchor=DelphiMenu.Anchor.SURVEY_OPEN
    )
    DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    now = timezone.now()
    result = current_round(menu, enrolment=None, survey_start=None, now=now)
    assert result is None


# --- next_round ---


@pytest.mark.django_db
def test_next_round_returns_next(menu, now):
    r1 = DelphiRound.objects.create(menu=menu, order=0, name="R1")
    r2 = DelphiRound.objects.create(menu=menu, order=1, name="R2")

    # Simulate a progress row with delphi_round set to r1
    class FakeProgress:
        delphi_round = r1

    result = next_round(menu, FakeProgress())
    assert result == r2


@pytest.mark.django_db
def test_next_round_none_on_last(menu, now):
    r1 = DelphiRound.objects.create(menu=menu, order=0, name="R1")

    class FakeProgress:
        delphi_round = r1

    result = next_round(menu, FakeProgress())
    assert result is None


@pytest.mark.django_db
def test_next_round_none_when_no_current(menu):
    class FakeProgress:
        delphi_round = None

    result = next_round(menu, FakeProgress())
    assert result is None


# --- assign_round_for_progress ---


@pytest.fixture
def progress(survey, owner):
    from django.utils import timezone

    return SurveyProgress.objects.create(
        survey=survey,
        user=owner,
        expires_at=timezone.now() + timedelta(hours=1),
    )


@pytest.mark.django_db
def test_assign_round_first_access(menu, progress, now):
    """On first access (no round assigned), assigns the current open round."""
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    result = assign_round_for_progress(progress, menu, now=now)
    assert result == r1
    progress.refresh_from_db()
    assert progress.delphi_round_id == r1.id


@pytest.mark.django_db
def test_assign_round_idempotent(menu, progress, now):
    """If already assigned and still open, returns the same round."""
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    assign_round_for_progress(progress, menu, now=now)
    result = assign_round_for_progress(progress, menu, now=now)
    assert result == r1
    progress.refresh_from_db()
    assert progress.delphi_round_id == r1.id


@pytest.mark.django_db
def test_assign_round_advances_when_closed(menu, progress, now):
    """When the assigned round has closed, advances to the next open round."""
    enrolment = now - timedelta(days=10)
    progress.created_at = enrolment
    progress.save()

    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="R2", start_offset_days=7, end_offset_days=14
    )

    # Assign r1 first
    assign_round_for_progress(progress, menu, now=enrolment)
    assert progress.delphi_round_id == r1.id

    # Now at day 10, r1 has closed and r2 is open
    result = assign_round_for_progress(progress, menu, now=now)
    assert result == r2
    progress.refresh_from_db()
    assert progress.delphi_round_id == r2.id


@pytest.mark.django_db
def test_assign_round_no_round_open(menu, progress, now):
    """When no round is open, returns None and doesn't set the FK."""
    DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=7, end_offset_days=14
    )
    result = assign_round_for_progress(progress, menu, now=now)
    assert result is None
    progress.refresh_from_db()
    assert progress.delphi_round is None


@pytest.mark.django_db
def test_assign_round_no_next_when_last_closed(menu, progress, now):
    """When the last round has closed and there's no next, returns None."""
    enrolment = now - timedelta(days=20)
    progress.created_at = enrolment
    progress.save()

    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    assign_round_for_progress(progress, menu, now=enrolment)
    assert progress.delphi_round_id == r1.id

    # r1 has closed, no r2 exists
    result = assign_round_for_progress(progress, menu, now=now)
    assert result is None
