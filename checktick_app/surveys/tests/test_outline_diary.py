"""Tests for the DIARY outline grammar + import/export round-trip.

Covers parse_bulk_markdown_with_collections (DIARY block), the bulk
upload application, and _export_survey_to_markdown round-trip.

Mirrors ``test_outline_delphi.py`` in structure.
"""

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    DiaryMenu,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)
from checktick_app.surveys.views import _export_survey_to_markdown

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="diary_outline@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


# --- parser ---


def test_parse_diary_block_fixed_interval():
    md = """\
DIARY
  schedule: fixed_interval
  interval_hours: 6
  anchor: enrolment
  compliance_threshold: 80
  grace_minutes: 30
  show_progress: true

# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["diary"] is not None
    assert parsed["diary"]["schedule_type"] == "fixed_interval"
    assert parsed["diary"]["interval_hours"] == 6
    assert parsed["diary"]["anchor"] == "enrolment"
    assert parsed["diary"]["compliance_threshold_pct"] == 80
    assert parsed["diary"]["grace_minutes"] == 30
    assert parsed["diary"]["show_progress"] is True
    assert len(parsed["groups"]) == 1
    assert parsed["groups"][0]["name"] == "Daily check-in"


def test_parse_diary_block_burst():
    md = """\
DIARY
  schedule: burst
  burst_on_days: 7
  burst_off_days: 7
  anchor: survey_open

# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["diary"] is not None
    assert parsed["diary"]["schedule_type"] == "burst"
    assert parsed["diary"]["burst_on_days"] == 7
    assert parsed["diary"]["burst_off_days"] == 7
    assert parsed["diary"]["anchor"] == "survey_open"


def test_parse_diary_block_event_triggered():
    md = """\
DIARY
  schedule: event_triggered
  anchor: enrolment
  show_progress: false

# Symptom report {symptom-report}
## Symptoms {symptoms}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["diary"] is not None
    assert parsed["diary"]["schedule_type"] == "event_triggered"
    assert parsed["diary"]["interval_hours"] is None
    assert parsed["diary"]["show_progress"] is False


def test_parse_diary_block_defaults():
    """A DIARY block with no config lines uses defaults."""
    md = """\
DIARY

# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["diary"] is not None
    assert parsed["diary"]["schedule_type"] == "fixed_interval"
    assert parsed["diary"]["anchor"] == "enrolment"
    assert parsed["diary"]["compliance_threshold_pct"] == 80
    assert parsed["diary"]["grace_minutes"] == 30
    assert parsed["diary"]["show_progress"] is True


def test_parse_no_diary_block():
    """No DIARY block → diary is None."""
    md = """\
# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["diary"] is None


def test_parse_diary_block_ignores_invalid_schedule():
    md = """\
DIARY
  schedule: invalid_type
  interval_hours: 6

# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["diary"] is not None
    # Invalid schedule_type falls back to the default.
    assert parsed["diary"]["schedule_type"] == "fixed_interval"


# --- export round-trip ---


@pytest.mark.django_db
def test_export_diary_block_fixed_interval(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Export",
        slug="diary-export",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.LIKERT, order=0
    )
    DiaryMenu.objects.create(
        survey=s,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        compliance_threshold_pct=80,
        grace_minutes=30,
        show_progress=True,
    )
    md = _export_survey_to_markdown(s)
    assert "DIARY" in md
    assert "schedule: fixed_interval" in md
    assert "interval_hours: 6" in md
    assert "anchor: enrolment" in md
    assert "compliance_threshold: 80" in md
    assert "grace_minutes: 30" in md
    assert "show_progress: true" in md
    assert "Daily check-in" in md


@pytest.mark.django_db
def test_export_diary_block_burst(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Burst Export",
        slug="diary-burst-export",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Symptom report", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Symptoms", type=SurveyQuestion.Types.TEXT, order=0
    )
    DiaryMenu.objects.create(
        survey=s,
        schedule_type=DiaryMenu.ScheduleType.BURST,
        burst_on_days=7,
        burst_off_days=7,
        anchor=DiaryMenu.Anchor.SURVEY_OPEN,
        show_progress=False,
    )
    md = _export_survey_to_markdown(s)
    assert "DIARY" in md
    assert "schedule: burst" in md
    assert "burst_on_days: 7" in md
    assert "burst_off_days: 7" in md
    assert "anchor: survey_open" in md
    assert "show_progress: false" in md


@pytest.mark.django_db
def test_export_diary_block_event_triggered(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Event Export",
        slug="diary-event-export",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Event report", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s,
        group=g,
        text="What happened?",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    DiaryMenu.objects.create(
        survey=s,
        schedule_type=DiaryMenu.ScheduleType.EVENT_TRIGGERED,
        anchor=DiaryMenu.Anchor.ENROLMENT,
        show_progress=True,
    )
    md = _export_survey_to_markdown(s)
    assert "DIARY" in md
    assert "schedule: event_triggered" in md
    # interval_hours/burst fields should not appear when None.
    assert "interval_hours" not in md
    assert "burst_on_days" not in md


@pytest.mark.django_db
def test_round_trip_fixed_interval(owner, org):
    """Parse → export → parse produces the same config."""
    original_md = """\
DIARY
  schedule: fixed_interval
  interval_hours: 6
  anchor: enrolment
  compliance_threshold: 80
  grace_minutes: 30
  show_progress: true

# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(original_md)
    assert parsed["diary"] is not None

    # Create the survey + menu from the parsed config.
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Round Trip",
        slug="diary-round-trip",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.TEXT, order=0
    )
    DiaryMenu.objects.create(
        survey=s,
        schedule_type=parsed["diary"]["schedule_type"],
        interval_hours=parsed["diary"]["interval_hours"],
        anchor=parsed["diary"]["anchor"],
        compliance_threshold_pct=parsed["diary"]["compliance_threshold_pct"],
        grace_minutes=parsed["diary"]["grace_minutes"],
        show_progress=parsed["diary"]["show_progress"],
    )

    # Export and re-parse.
    exported_md = _export_survey_to_markdown(s)
    reparsed = parse_bulk_markdown_with_collections(exported_md)
    assert reparsed["diary"] is not None
    assert reparsed["diary"]["schedule_type"] == "fixed_interval"
    assert reparsed["diary"]["interval_hours"] == 6
    assert reparsed["diary"]["anchor"] == "enrolment"
    assert reparsed["diary"]["compliance_threshold_pct"] == 80
    assert reparsed["diary"]["grace_minutes"] == 30
    assert reparsed["diary"]["show_progress"] is True


@pytest.mark.django_db
def test_round_trip_burst(owner, org):
    """Parse → export → parse produces the same burst config."""
    original_md = """\
DIARY
  schedule: burst
  burst_on_days: 7
  burst_off_days: 7
  anchor: survey_open
  show_progress: false

# Daily check-in {daily-check-in}
## Pain level {pain}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(original_md)
    assert parsed["diary"] is not None

    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Burst Round Trip",
        slug="diary-burst-rt",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="Daily check-in", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Pain level", type=SurveyQuestion.Types.TEXT, order=0
    )
    DiaryMenu.objects.create(
        survey=s,
        schedule_type=parsed["diary"]["schedule_type"],
        burst_on_days=parsed["diary"]["burst_on_days"],
        burst_off_days=parsed["diary"]["burst_off_days"],
        anchor=parsed["diary"]["anchor"],
        show_progress=parsed["diary"]["show_progress"],
    )

    exported_md = _export_survey_to_markdown(s)
    reparsed = parse_bulk_markdown_with_collections(exported_md)
    assert reparsed["diary"] is not None
    assert reparsed["diary"]["schedule_type"] == "burst"
    assert reparsed["diary"]["burst_on_days"] == 7
    assert reparsed["diary"]["burst_off_days"] == 7
    assert reparsed["diary"]["anchor"] == "survey_open"
    assert reparsed["diary"]["show_progress"] is False
