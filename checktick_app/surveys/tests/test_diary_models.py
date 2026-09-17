"""Tests for the Diary / EMA layout models: Survey.Layout.DIARY choice,
DiaryMenu, DiaryEntry, and the SurveyProgress.diary_enrolled_at field.

These verify the data model and migration (0069_diary_layout). The pure
helpers (``diary.py``) are tested in ``test_diary_helpers.py``; the
runtime hook and organise UI are tested separately.

Mirrors ``test_delphi_models.py`` in structure.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DiaryEntry,
    DiaryMenu,
    Organization,
    Survey,
    SurveyProgress,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="diary_models@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="diary-models-s",
        layout=Survey.Layout.DIARY,
    )


# --- layout choice ---


@pytest.mark.django_db
def test_layout_diary_choice_exists():
    choices = {value for value, _label in Survey.Layout.choices}
    assert "diary" in choices
    assert Survey.Layout.DIARY == "diary"


@pytest.mark.django_db
def test_layout_diary_display_label():
    assert Survey.Layout.DIARY.label == "Diary / EMA"


@pytest.mark.django_db
def test_layout_default_is_linear(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="D", slug="d-lin")
    assert s.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_layout_can_be_set_to_diary(owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="DL", slug="dl", layout=Survey.Layout.DIARY
    )
    s.refresh_from_db()
    assert s.layout == "diary"


# --- DiaryMenu model ---


@pytest.mark.django_db
def test_diary_menu_defaults(survey):
    menu = DiaryMenu.objects.create(survey=survey)
    assert menu.schedule_type == DiaryMenu.ScheduleType.FIXED_INTERVAL
    assert menu.interval_hours is None
    assert menu.burst_on_days is None
    assert menu.burst_off_days is None
    assert menu.anchor == DiaryMenu.Anchor.ENROLMENT
    assert menu.compliance_threshold_pct == 80
    assert menu.grace_minutes == 30
    assert menu.show_progress is True


@pytest.mark.django_db
def test_diary_menu_one_to_one(survey):
    DiaryMenu.objects.create(survey=survey)
    with pytest.raises(Exception):
        DiaryMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_diary_menu_cascade_delete_with_survey(survey):
    menu = DiaryMenu.objects.create(survey=survey)
    menu_id = menu.id
    survey.delete()
    assert not DiaryMenu.objects.filter(id=menu_id).exists()


@pytest.mark.django_db
def test_diary_menu_str(survey):
    menu = DiaryMenu.objects.create(survey=survey)
    assert "DiaryMenu for S" in str(menu)


@pytest.mark.django_db
def test_diary_menu_schedule_type_choices():
    values = {v for v, _ in DiaryMenu.ScheduleType.choices}
    assert values == {"fixed_interval", "event_triggered", "burst"}


@pytest.mark.django_db
def test_diary_menu_anchor_choices():
    values = {v for v, _ in DiaryMenu.Anchor.choices}
    assert values == {"enrolment", "survey_open"}


@pytest.mark.django_db
def test_linear_survey_has_no_diary_menu(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="L", slug="l-nomenu")
    assert not hasattr(s, "diary_menu") or s.diary_menu is None
    assert not DiaryMenu.objects.filter(survey=s).exists()


# --- DiaryEntry model ---


@pytest.fixture
def menu(survey):
    return DiaryMenu.objects.create(
        survey=survey,
        schedule_type=DiaryMenu.ScheduleType.FIXED_INTERVAL,
        interval_hours=6,
    )


@pytest.fixture
def progress(survey, owner):
    now = timezone.now()
    return SurveyProgress.objects.create(
        survey=survey,
        user=owner,
        expires_at=now + timedelta(days=30),
        diary_enrolled_at=now,
    )


@pytest.mark.django_db
def test_diary_entry_defaults(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    assert entry.order == 0
    assert entry.submitted_at is None
    assert entry.is_missed is False


@pytest.mark.django_db
def test_diary_entry_str_pending(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    assert "pending" in str(entry)
    assert "#0" in str(entry)


@pytest.mark.django_db
def test_diary_entry_str_submitted(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=1,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
        submitted_at=now + timedelta(minutes=10),
    )
    assert "submitted" in str(entry)


@pytest.mark.django_db
def test_diary_entry_str_missed(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=2,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
        is_missed=True,
    )
    assert "missed" in str(entry)


@pytest.mark.django_db
def test_diary_entry_cascade_delete_with_menu(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    entry_id = entry.id
    menu.delete()
    assert not DiaryEntry.objects.filter(id=entry_id).exists()


@pytest.mark.django_db
def test_diary_entry_cascade_delete_with_progress(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    entry_id = entry.id
    progress.delete()
    assert not DiaryEntry.objects.filter(id=entry_id).exists()


@pytest.mark.django_db
def test_diary_entry_unique_together_menu_progress_order(menu, progress):
    now = timezone.now()
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    with pytest.raises(Exception):
        DiaryEntry.objects.create(
            menu=menu,
            progress=progress,
            order=0,
            expected_start=now,
            expected_end=now + timedelta(hours=6),
        )


@pytest.mark.django_db
def test_diary_entry_ordering(menu, progress):
    now = timezone.now()
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=2,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=1,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    entries = list(DiaryEntry.objects.filter(menu=menu))
    assert [e.order for e in entries] == [0, 1, 2]


@pytest.mark.django_db
def test_diary_entry_can_be_marked_missed(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now - timedelta(hours=12),
        expected_end=now - timedelta(hours=6),
        is_missed=True,
    )
    entry.refresh_from_db()
    assert entry.is_missed is True
    assert entry.submitted_at is None


@pytest.mark.django_db
def test_diary_entry_can_be_submitted(menu, progress):
    now = timezone.now()
    entry = DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
        submitted_at=now + timedelta(minutes=5),
    )
    entry.refresh_from_db()
    assert entry.submitted_at is not None
    assert entry.is_missed is False


# --- SurveyProgress.diary_enrolled_at ---


@pytest.mark.django_db
def test_diary_enrolled_at_defaults_to_null(owner, org):
    now = timezone.now()
    s = Survey.objects.create(owner=owner, organization=org, name="P", slug="p-dy")
    progress = SurveyProgress.objects.create(survey=s, user=owner, expires_at=now)
    assert progress.diary_enrolled_at is None


@pytest.mark.django_db
def test_diary_enrolled_at_can_be_set(owner, org):
    now = timezone.now()
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="P2",
        slug="p2-dy",
        layout=Survey.Layout.DIARY,
    )
    enrolled = now - timedelta(hours=3)
    progress = SurveyProgress.objects.create(
        survey=s, user=owner, expires_at=now, diary_enrolled_at=enrolled
    )
    progress.refresh_from_db()
    assert progress.diary_enrolled_at == enrolled


@pytest.mark.django_db
def test_diary_entries_reverse_relation(menu, progress):
    """SurveyProgress.diary_entries reverse relation works."""
    now = timezone.now()
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=0,
        expected_start=now,
        expected_end=now + timedelta(hours=6),
    )
    DiaryEntry.objects.create(
        menu=menu,
        progress=progress,
        order=1,
        expected_start=now + timedelta(hours=6),
        expected_end=now + timedelta(hours=12),
    )
    assert progress.diary_entries.count() == 2
    assert progress.diary_entries.first().order == 0


# --- admin registration ---


@pytest.mark.django_db
def test_admin_registration():
    """The models are registered in admin (smoke test via admin.site)."""
    from django.contrib import admin

    assert DiaryMenu in admin.site._registry
    assert DiaryEntry in admin.site._registry
