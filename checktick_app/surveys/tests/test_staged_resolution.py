"""Tests for the staged phase-resolution helpers (step 2).

Pure-function tests for checktick_app/surveys/staged.py. The runtime hook
(step 3) and organise UI (step 4) build on top of these.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    StagedMenu,
    StagedPhase,
    Survey,
)
from checktick_app.surveys.staged import (
    anchor_time,
    is_phase_open,
    open_group_ids,
    open_phases,
    phases_for_group,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner, organization=org, name="S", slug="s", layout=Survey.Layout.STAGED
    )


@pytest.fixture
def menu(survey):
    return StagedMenu.objects.create(survey=survey)


@pytest.fixture
def now():
    return timezone.now()


def _phase(menu, name, *, start, end=None, order=0, groups=()):
    p = StagedPhase.objects.create(
        menu=menu, name=name, order=order, start_offset_days=start, end_offset_days=end
    )
    for g in groups:
        p.groups.add(g)
    return p


# --- anchor_time ---


@pytest.mark.django_db
def test_anchor_enrolment_uses_enrolment(menu, now):
    survey_start = now - timedelta(days=10)
    enrolment = now - timedelta(days=2)
    assert (
        anchor_time(menu, enrolment=enrolment, survey_start=survey_start) == enrolment
    )


@pytest.mark.django_db
def test_anchor_enrolment_falls_back_to_survey_start(menu, now):
    survey_start = now - timedelta(days=10)
    assert anchor_time(menu, enrolment=None, survey_start=survey_start) == survey_start


@pytest.mark.django_db
def test_anchor_survey_open_uses_survey_start(menu, now):
    menu.anchor = StagedMenu.Anchor.SURVEY_OPEN
    menu.save(update_fields=["anchor"])
    enrolment = now - timedelta(days=2)
    survey_start = now - timedelta(days=10)
    assert (
        anchor_time(menu, enrolment=enrolment, survey_start=survey_start)
        == survey_start
    )


# --- is_phase_open ---


@pytest.mark.django_db
def test_is_phase_open_at_start_boundary(menu, now):
    anchor = now - timedelta(days=14)
    p = _phase(menu, "Follow-up", start=14, end=28)
    assert is_phase_open(p, anchor, now) is True


@pytest.mark.django_db
def test_is_phase_open_just_before_start(menu, now):
    anchor = now - timedelta(days=13, hours=23)
    p = _phase(menu, "Follow-up", start=14, end=28)
    assert is_phase_open(p, anchor, now) is False


@pytest.mark.django_db
def test_is_phase_open_at_end_boundary_exclusive(menu, now):
    # now == anchor + 28 days → end is exclusive → closed
    anchor = now - timedelta(days=28)
    p = _phase(menu, "Follow-up", start=14, end=28)
    assert is_phase_open(p, anchor, now) is False


@pytest.mark.django_db
def test_is_phase_open_open_ended_never_closes(menu, now):
    anchor = now - timedelta(days=365)
    p = _phase(menu, "Baseline", start=0, end=None)
    assert is_phase_open(p, anchor, now) is True


@pytest.mark.django_db
def test_is_phase_open_baseline_at_anchor(menu, now):
    anchor = now
    p = _phase(menu, "Baseline", start=0, end=14)
    assert is_phase_open(p, anchor, now) is True


# --- open_phases ---


@pytest.mark.django_db
def test_open_phases_returns_ordered_subset(menu, owner, now):
    enrolment = now - timedelta(days=20)
    g = QuestionGroup.objects.create(name="G", owner=owner)
    _phase(menu, "Baseline", start=0, end=14, order=1, groups=(g,))
    followup = _phase(menu, "Follow-up", start=14, end=28, order=2, groups=(g,))
    _phase(menu, "Review", start=180, end=None, order=3, groups=(g,))
    # Day 20: baseline closed, follow-up open, review not yet.
    open_list = open_phases(menu, enrolment=enrolment, survey_start=None, now=now)
    assert open_list == [followup]


@pytest.mark.django_db
def test_open_phases_multiple_open(menu, owner, now):
    enrolment = now - timedelta(days=5)
    g = QuestionGroup.objects.create(name="G", owner=owner)
    a = _phase(menu, "A", start=0, end=10, order=1, groups=(g,))
    b = _phase(menu, "B", start=0, end=None, order=2, groups=(g,))
    open_list = open_phases(menu, enrolment=enrolment, survey_start=None, now=now)
    assert set(open_list) == {a, b}
    # Ordered by order, id.
    assert open_list == [a, b]


@pytest.mark.django_db
def test_open_phases_survey_open_anchor_no_start_returns_empty(menu, now):
    menu.anchor = StagedMenu.Anchor.SURVEY_OPEN
    menu.save(update_fields=["anchor"])
    _phase(menu, "Baseline", start=0, end=None)
    # No survey_start → anchor is None → nothing open.
    assert open_phases(menu, enrolment=now, survey_start=None, now=now) == []


# --- open_group_ids ---


@pytest.mark.django_db
def test_open_group_ids_dedupes_across_phases(menu, owner, now):
    enrolment = now - timedelta(days=5)
    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    # g1 is in both open phases; should appear once.
    _phase(menu, "A", start=0, end=10, order=1, groups=(g1, g2))
    _phase(menu, "B", start=0, end=None, order=2, groups=(g1,))
    ids = open_group_ids(menu, enrolment=enrolment, survey_start=None, now=now)
    assert ids.count(g1.id) == 1
    assert g2.id in ids


@pytest.mark.django_db
def test_open_group_ids_empty_when_no_phases_open(menu, now):
    enrolment = now
    _phase(menu, "Later", start=100, end=None)
    assert open_group_ids(menu, enrolment=enrolment, survey_start=None, now=now) == []


# --- phases_for_group ---


@pytest.mark.django_db
def test_phases_for_group(menu, owner):
    g = QuestionGroup.objects.create(name="G", owner=owner)
    a = _phase(menu, "A", start=0, end=None, order=1, groups=(g,))
    b = _phase(menu, "B", start=14, end=None, order=2, groups=(g,))
    other = QuestionGroup.objects.create(name="Other", owner=owner)
    _phase(menu, "C", start=0, end=None, order=3, groups=(other,))
    result = list(phases_for_group(menu, g.id))
    assert result == [a, b]
