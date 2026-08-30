from __future__ import annotations

from django.contrib.auth.models import User
import pytest

from checktick_app.surveys.models import (
    Organization,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="owner", password="x")


@pytest.fixture
def org(owner: User) -> Organization:
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner: User, org: Organization) -> Survey:
    return Survey.objects.create(
        owner=owner, organization=org, name="Survey", slug="survey"
    )


def _make_question(survey: Survey, text: str, order: int) -> SurveyQuestion:
    return SurveyQuestion.objects.create(
        survey=survey,
        group=None,
        text=text,
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        required=False,
        order=order,
    )


@pytest.mark.django_db
def test_action_enum_uses_hide_not_skip():
    """The stored enum value is 'hide', not 'skip'. The Python symbol is HIDE."""
    assert SurveyQuestionCondition.Action.HIDE.value == "hide"
    # SKIP must no longer exist on the enum.
    assert not hasattr(SurveyQuestionCondition.Action, "SKIP")
    # The choices contain 'hide' and not 'skip'.
    values = {value for value, _label in SurveyQuestionCondition.Action.choices}
    assert "hide" in values
    assert "skip" not in values


@pytest.mark.django_db
def test_hidden_by_default_defaults_false(survey: Survey):
    q = _make_question(survey, "Q1", 0)
    assert q.hidden_by_default is False


@pytest.mark.django_db
def test_skip_value_round_trips_as_hide(survey: Survey):
    """A condition created with the HIDE action stores 'hide' and reads back as HIDE."""
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1)
    cond = SurveyQuestionCondition.objects.create(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.HIDE,
    )
    cond.refresh_from_db()
    assert cond.action == SurveyQuestionCondition.Action.HIDE
    assert cond.action == "hide"


@pytest.mark.django_db
def test_migration_backfill_marks_show_targets_hidden_by_default(survey: Survey):
    """
    Reproduces the migration backfill logic: a question with an incoming SHOW
    condition should be marked hidden_by_default=True.
    """
    source = _make_question(survey, "Source", 0)
    shown = _make_question(survey, "Shown via SHOW", 1)
    plain = _make_question(survey, "Plain", 2)

    # Before: nothing is hidden by default.
    assert source.hidden_by_default is False
    assert shown.hidden_by_default is False
    assert plain.hidden_by_default is False

    SurveyQuestionCondition.objects.create(
        question=source,
        target_question=shown,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.SHOW,
    )

    # Re-run the backfill function against the current state.
    from django.apps import apps as django_apps

    from checktick_app.surveys.migrations._backfill_helpers import (
        backfill_hidden_by_default,
    )

    backfill_hidden_by_default(django_apps, None)

    shown.refresh_from_db()
    plain.refresh_from_db()
    source.refresh_from_db()
    assert shown.hidden_by_default is True
    assert plain.hidden_by_default is False
    assert source.hidden_by_default is False


@pytest.mark.django_db
def test_migration_rename_skip_to_hide(survey: Survey):
    """
    Reproduces the migration rename: a condition with action='skip' (the old
    stored value) becomes 'hide'.
    """
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1)

    # Insert a row with the legacy stored value directly, bypassing the enum.
    SurveyQuestionCondition.objects.create(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action="skip",
    )

    from django.apps import apps as django_apps

    from checktick_app.surveys.migrations._backfill_helpers import (
        rename_skip_to_hide,
    )

    rename_skip_to_hide(django_apps, None)

    cond = SurveyQuestionCondition.objects.get(question=source)
    assert cond.action == "hide"
    assert cond.action == SurveyQuestionCondition.Action.HIDE
