"""Tests for StagedMenu / StagedPhase models + the Survey.Layout.STAGED
choice (step 1 of the staged layout).

The phase-resolution helper (step 2) and runtime hook (step 3) build on top
of these.
"""

import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    StagedMenu,
    StagedPhase,
    Survey,
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
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
        layout=Survey.Layout.STAGED,
    )
    return s


@pytest.mark.django_db
def test_layout_staged_choice_exists():
    choices = {value for value, _label in Survey.Layout.choices}
    assert "staged" in choices
    assert Survey.Layout.STAGED == "staged"


@pytest.mark.django_db
def test_layout_default_is_linear(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="D", slug="d")
    assert s.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_staged_menu_defaults(survey):
    menu = StagedMenu.objects.create(survey=survey)
    assert menu.anchor == StagedMenu.Anchor.ENROLMENT


@pytest.mark.django_db
def test_staged_menu_one_to_one(survey):
    StagedMenu.objects.create(survey=survey)
    with pytest.raises(Exception):
        StagedMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_staged_menu_cascade_delete_with_survey(survey):
    menu = StagedMenu.objects.create(survey=survey)
    menu_id = menu.id
    survey.delete()
    assert not StagedMenu.objects.filter(id=menu_id).exists()


@pytest.mark.django_db
def test_staged_phase_defaults(survey):
    menu = StagedMenu.objects.create(survey=survey)
    phase = StagedPhase.objects.create(menu=menu, name="Baseline")
    assert phase.order == 0
    assert phase.start_offset_days == 0
    assert phase.end_offset_days is None


@pytest.mark.django_db
def test_staged_phase_unique_per_menu(survey):
    menu = StagedMenu.objects.create(survey=survey)
    StagedPhase.objects.create(menu=menu, name="Baseline")
    with pytest.raises(Exception):
        StagedPhase.objects.create(menu=menu, name="Baseline")


@pytest.mark.django_db
def test_staged_phase_cascade_delete_with_menu(survey):
    menu = StagedMenu.objects.create(survey=survey)
    phase = StagedPhase.objects.create(menu=menu, name="Baseline")
    phase_id = phase.id
    menu.delete()
    assert not StagedPhase.objects.filter(id=phase_id).exists()


@pytest.mark.django_db
def test_staged_phase_groups_m2m(survey, owner):
    menu = StagedMenu.objects.create(survey=survey)
    phase = StagedPhase.objects.create(menu=menu, name="Baseline")
    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    phase.groups.add(g1, g2)
    assert set(phase.groups.all()) == {g1, g2}
    # A group can be in multiple phases (e.g. demographics in every phase).
    phase2 = StagedPhase.objects.create(menu=menu, name="Follow-up")
    phase2.groups.add(g1)
    assert g1 in phase.groups.all()
    assert g1 in phase2.groups.all()


@pytest.mark.django_db
def test_staged_phase_ordering(survey):
    menu = StagedMenu.objects.create(survey=survey)
    StagedPhase.objects.create(menu=menu, name="B", order=2)
    StagedPhase.objects.create(menu=menu, name="A", order=1)
    StagedPhase.objects.create(menu=menu, name="C", order=3)
    ordered = list(menu.phases.all())
    assert [p.name for p in ordered] == ["A", "B", "C"]


@pytest.mark.django_db
def test_staged_menu_str(survey):
    menu = StagedMenu.objects.create(survey=survey)
    assert "StagedMenu for S" in str(menu)


@pytest.mark.django_db
def test_staged_phase_str(survey):
    menu = StagedMenu.objects.create(survey=survey)
    phase = StagedPhase.objects.create(
        menu=menu, name="Follow-up", start_offset_days=14, end_offset_days=28
    )
    s = str(phase)
    assert "Follow-up" in s
    assert "14" in s
    assert "28" in s


@pytest.mark.django_db
def test_staged_phase_str_open_ended(survey):
    menu = StagedMenu.objects.create(survey=survey)
    phase = StagedPhase.objects.create(menu=menu, name="Baseline")
    # Open-ended phase shows the infinity glyph for the end bound.
    assert "\u221e" in str(phase)


@pytest.mark.django_db
def test_linear_survey_has_no_staged_menu(owner, org):
    """A non-staged survey has no StagedMenu row by convention."""
    s = Survey.objects.create(owner=owner, organization=org, name="L", slug="l")
    assert not hasattr(s, "staged_menu") or s.staged_menu is None
    assert not StagedMenu.objects.filter(survey=s).exists()
