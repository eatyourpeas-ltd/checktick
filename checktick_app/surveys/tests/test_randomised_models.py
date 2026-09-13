"""Tests for RandomisedMenu / RandomisedArm models + the Survey.Layout.RCT
choice + the new SurveyProgress fields (step 2 of the RCT layout).

The allocator (step 3) and runtime hook (step 4) build on top of these.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RandomisedArm,
    RandomisedMenu,
    Survey,
    SurveyProgress,
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
        layout=Survey.Layout.RCT,
    )
    return s


@pytest.mark.django_db
def test_layout_rct_choice_exists():
    choices = {value for value, _label in Survey.Layout.choices}
    assert "rct" in choices
    assert Survey.Layout.RCT == "rct"


@pytest.mark.django_db
def test_layout_default_is_linear(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="D",
        slug="d",
    )
    assert s.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_randomised_menu_defaults(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    assert menu.allocation_strategy == RandomisedMenu.AllocationStrategy.BALANCED
    assert menu.seed is None


@pytest.mark.django_db
def test_randomised_menu_one_to_one(survey):
    RandomisedMenu.objects.create(survey=survey)
    with pytest.raises(Exception):
        RandomisedMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_randomised_menu_cascade_delete_with_survey(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    menu_id = menu.id
    survey.delete()
    assert not RandomisedMenu.objects.filter(id=menu_id).exists()


@pytest.mark.django_db
def test_randomised_arm_defaults(survey, owner):
    menu = RandomisedMenu.objects.create(survey=survey)
    arm = RandomisedArm.objects.create(menu=menu, name="Intervention")
    assert arm.allocation_ratio == 1
    assert arm.order == 0


@pytest.mark.django_db
def test_randomised_arm_unique_per_menu(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    RandomisedArm.objects.create(menu=menu, name="Control")
    with pytest.raises(Exception):
        RandomisedArm.objects.create(menu=menu, name="Control")


@pytest.mark.django_db
def test_randomised_arm_cascade_delete_with_menu(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    arm = RandomisedArm.objects.create(menu=menu, name="Intervention")
    arm_id = arm.id
    menu.delete()
    assert not RandomisedArm.objects.filter(id=arm_id).exists()


@pytest.mark.django_db
def test_randomised_arm_groups_m2m(survey, owner):
    menu = RandomisedMenu.objects.create(survey=survey)
    arm = RandomisedArm.objects.create(menu=menu, name="Intervention")
    g1 = QuestionGroup.objects.create(name="G1", owner=owner)
    g2 = QuestionGroup.objects.create(name="G2", owner=owner)
    arm.groups.add(g1, g2)
    assert set(arm.groups.all()) == {g1, g2}
    # A group can be in multiple arms.
    arm2 = RandomisedArm.objects.create(menu=menu, name="Control")
    arm2.groups.add(g1)
    assert g1 in arm.groups.all()
    assert g1 in arm2.groups.all()


@pytest.mark.django_db
def test_randomised_arm_ordering(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    RandomisedArm.objects.create(menu=menu, name="B", order=2)
    RandomisedArm.objects.create(menu=menu, name="A", order=1)
    RandomisedArm.objects.create(menu=menu, name="C", order=3)
    ordered = list(menu.arms.all())
    assert [a.name for a in ordered] == ["A", "B", "C"]


@pytest.mark.django_db
def test_randomised_menu_str(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    assert "RandomisedMenu for S" in str(menu)


@pytest.mark.django_db
def test_randomised_arm_str(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    arm = RandomisedArm.objects.create(
        menu=menu, name="Intervention", allocation_ratio=2
    )
    assert "Intervention" in str(arm)
    assert "ratio 2" in str(arm)


@pytest.mark.django_db
def test_survey_progress_randomisation_fields_default(survey, owner):
    """randomisation_seed and assigned_arm are null by default for any layout."""
    progress = SurveyProgress.objects.create(
        survey=survey,
        expires_at=timezone.now() + timedelta(days=30),
    )
    assert progress.randomisation_seed is None
    assert progress.assigned_arm is None


@pytest.mark.django_db
def test_survey_progress_assigned_arm_set_null_on_arm_delete(survey, owner):
    """If an arm is deleted after enrolment, the progress keeps its
    selected_group_ids (preserved on resume) but the FK is nulled."""
    menu = RandomisedMenu.objects.create(survey=survey)
    arm = RandomisedArm.objects.create(menu=menu, name="Intervention")
    progress = SurveyProgress.objects.create(
        survey=survey,
        assigned_arm=arm,
        randomisation_seed=12345,
        selected_group_ids=[1, 2],
        expires_at=timezone.now() + timedelta(days=30),
    )
    arm.delete()
    progress.refresh_from_db()
    assert progress.assigned_arm is None
    # The seed is preserved — the participant keeps their allocation
    # audit trail even if the arm definition is removed.
    assert progress.randomisation_seed == 12345
    assert progress.selected_group_ids == [1, 2]
