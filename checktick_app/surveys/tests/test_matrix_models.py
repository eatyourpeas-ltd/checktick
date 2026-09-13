"""Tests for MatrixMenu model, Survey.Layout.MATRIX choice, and the
SurveyProgress.completed_group_ids field (step 1 of the matrix layout).

The pure helpers (step 2) and runtime hook (step 3) build on top of these.
"""

import pytest

from checktick_app.surveys.models import (
    MatrixMenu,
    Organization,
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
        layout=Survey.Layout.MATRIX,
    )
    return s


# --- layout choice ---


@pytest.mark.django_db
def test_layout_matrix_choice_exists():
    choices = {value for value, _label in Survey.Layout.choices}
    assert "matrix" in choices
    assert Survey.Layout.MATRIX == "matrix"


@pytest.mark.django_db
def test_layout_default_is_linear(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="D", slug="d")
    assert s.layout == Survey.Layout.LINEAR


@pytest.mark.django_db
def test_layout_matrix_display_label():
    assert Survey.Layout.MATRIX.label == "Matrix (free navigation)"


# --- MatrixMenu model ---


@pytest.mark.django_db
def test_matrix_menu_defaults(survey):
    menu = MatrixMenu.objects.create(survey=survey)
    assert menu.order_mode == MatrixMenu.OrderMode.AUTHORED
    assert menu.allow_revisit is True
    assert "Click a section to begin" in menu.prompt_text


@pytest.mark.django_db
def test_matrix_menu_one_to_one(survey):
    MatrixMenu.objects.create(survey=survey)
    with pytest.raises(Exception):
        MatrixMenu.objects.create(survey=survey)


@pytest.mark.django_db
def test_matrix_menu_cascade_delete_with_survey(survey):
    menu = MatrixMenu.objects.create(survey=survey)
    menu_id = menu.id
    survey.delete()
    assert not MatrixMenu.objects.filter(id=menu_id).exists()


@pytest.mark.django_db
def test_matrix_menu_str(survey):
    menu = MatrixMenu.objects.create(survey=survey)
    assert "MatrixMenu for S" in str(menu)


@pytest.mark.django_db
def test_matrix_menu_order_mode_choices():
    values = {v for v, _ in MatrixMenu.OrderMode.choices}
    assert values == {"authored", "participant"}


@pytest.mark.django_db
def test_linear_survey_has_no_matrix_menu(owner, org):
    """A non-matrix survey has no MatrixMenu row by convention."""
    s = Survey.objects.create(owner=owner, organization=org, name="L", slug="l")
    assert not hasattr(s, "matrix_menu") or s.matrix_menu is None
    assert not MatrixMenu.objects.filter(survey=s).exists()


# --- SurveyProgress.completed_group_ids ---


@pytest.mark.django_db
def test_completed_group_ids_defaults_to_empty_list(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="P", slug="p")
    progress = SurveyProgress.objects.create(
        survey=s,
        user=owner,
        expires_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
    )
    assert progress.completed_group_ids == []
    assert isinstance(progress.completed_group_ids, list)


@pytest.mark.django_db
def test_completed_group_ids_can_hold_ids(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="P2", slug="p2")
    progress = SurveyProgress.objects.create(
        survey=s,
        user=owner,
        completed_group_ids=[1, 2, 3],
        expires_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
    )
    progress.refresh_from_db()
    assert progress.completed_group_ids == [1, 2, 3]


# --- admin registration ---


@pytest.mark.django_db
def test_admin_registration():
    """The model is registered in admin (smoke test via admin.site)."""
    from django.contrib import admin

    assert MatrixMenu in admin.site._registry
