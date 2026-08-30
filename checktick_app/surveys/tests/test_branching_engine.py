from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import pytest

from checktick_app.surveys.branching import (
    get_visible_questions,
    resolved_question_order,
    should_show_question,
)
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
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


def _make_question(
    survey: Survey,
    text: str,
    order: int,
    group: QuestionGroup | None = None,
    hidden_by_default: bool = False,
) -> SurveyQuestion:
    return SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=text,
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        required=False,
        order=order,
        hidden_by_default=hidden_by_default,
    )


def _make_group(survey: Survey, name: str, owner: User | None = None) -> QuestionGroup:
    group = QuestionGroup.objects.create(name=name, owner=owner or survey.owner)
    survey.question_groups.add(group)
    return group


# --- resolved_question_order ---


@pytest.mark.django_db
def test_resolved_question_order_follows_group_then_question_order(survey: Survey):
    g1 = _make_group(survey, "Alpha")
    g2 = _make_group(survey, "Beta")
    q1 = _make_question(survey, "Q1", 0, g1)
    q2 = _make_question(survey, "Q2", 1, g1)
    q3 = _make_question(survey, "Q3", 0, g2)

    order = resolved_question_order(survey)
    # Groups sorted by name: Alpha, Beta
    assert order == [q1.id, q2.id, q3.id]


@pytest.mark.django_db
def test_resolved_question_order_respects_explicit_group_order(survey: Survey):
    g1 = _make_group(survey, "Alpha")
    g2 = _make_group(survey, "Beta")
    q1 = _make_question(survey, "Q1", 0, g1)
    q3 = _make_question(survey, "Q3", 0, g2)

    # Override: Beta before Alpha
    survey.style = {"group_order": [g2.id, g1.id]}
    survey.save()

    order = resolved_question_order(survey)
    assert order == [q3.id, q1.id]


# --- should_show_question (toggle-based) ---


@pytest.mark.django_db
def test_should_show_question_shown_by_default_no_conditions(survey: Survey):
    q = _make_question(survey, "Q", 0, hidden_by_default=False)
    assert should_show_question(q, [q], {}) is True


@pytest.mark.django_db
def test_should_show_question_hidden_by_default_no_conditions(survey: Survey):
    q = _make_question(survey, "Q", 0, hidden_by_default=True)
    assert should_show_question(q, [q], {}) is False


@pytest.mark.django_db
def test_should_show_question_shown_by_default_hide_condition_matches(survey: Survey):
    source = _make_question(survey, "Source", 0, hidden_by_default=False)
    target = _make_question(survey, "Target", 1, hidden_by_default=False)

    SurveyQuestionCondition.objects.create(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.HIDE,
    )

    # HIDE condition matches → hidden
    assert (
        should_show_question(target, [source, target], {str(source.id): "Yes"}) is False
    )
    # HIDE condition doesn't match → shown
    assert (
        should_show_question(target, [source, target], {str(source.id): "No"}) is True
    )


@pytest.mark.django_db
def test_should_show_question_hidden_by_default_show_condition_matches(survey: Survey):
    source = _make_question(survey, "Source", 0, hidden_by_default=False)
    target = _make_question(survey, "Target", 1, hidden_by_default=True)

    SurveyQuestionCondition.objects.create(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.SHOW,
    )

    # SHOW condition matches → shown
    assert (
        should_show_question(target, [source, target], {str(source.id): "Yes"}) is True
    )
    # SHOW condition doesn't match → hidden
    assert (
        should_show_question(target, [source, target], {str(source.id): "No"}) is False
    )


# --- get_visible_questions (HIDE actually hides) ---


@pytest.mark.django_db
def test_get_visible_questions_hides_target_via_hide_condition(survey: Survey):
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1)

    SurveyQuestionCondition.objects.create(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.HIDE,
    )

    questions = list(survey.questions.all().order_by("order", "id"))
    # Pre-fetch conditions (as the runtime does)
    for q in questions:
        list(q.conditions.all())

    visible, ended = get_visible_questions(questions, {str(source.id): "Yes"})
    assert [q.id for q in visible] == [source.id]
    assert ended is False


@pytest.mark.django_db
def test_get_visible_questions_shows_target_when_hide_not_triggered(survey: Survey):
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1)

    SurveyQuestionCondition.objects.create(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.HIDE,
    )

    questions = list(survey.questions.all().order_by("order", "id"))
    for q in questions:
        list(q.conditions.all())

    visible, ended = get_visible_questions(questions, {str(source.id): "No"})
    assert [q.id for q in visible] == [source.id, target.id]


# --- clean() validation ---


@pytest.mark.django_db
def test_clean_rejects_show_on_shown_by_default_target(survey: Survey):
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1, hidden_by_default=False)

    cond = SurveyQuestionCondition(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.SHOW,
    )
    with pytest.raises(ValidationError) as exc:
        cond.clean()
    assert "hidden by default" in str(exc.value)


@pytest.mark.django_db
def test_clean_rejects_hide_on_hidden_by_default_target(survey: Survey):
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1, hidden_by_default=True)

    cond = SurveyQuestionCondition(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.HIDE,
    )
    with pytest.raises(ValidationError) as exc:
        cond.clean()
    assert "shown by default" in str(exc.value)


@pytest.mark.django_db
def test_clean_accepts_show_on_hidden_by_default_target(survey: Survey):
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1, hidden_by_default=True)

    cond = SurveyQuestionCondition(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.SHOW,
    )
    cond.clean()  # should not raise


@pytest.mark.django_db
def test_clean_accepts_hide_on_shown_by_default_target(survey: Survey):
    source = _make_question(survey, "Source", 0)
    target = _make_question(survey, "Target", 1, hidden_by_default=False)

    cond = SurveyQuestionCondition(
        question=source,
        target_question=target,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.HIDE,
    )
    cond.clean()  # should not raise


@pytest.mark.django_db
def test_clean_rejects_backward_jump_to(survey: Survey):
    g = _make_group(survey, "Group")
    q1 = _make_question(survey, "Q1", 0, g)
    q2 = _make_question(survey, "Q2", 1, g)

    # Jump from Q2 back to Q1 — backward
    cond = SurveyQuestionCondition(
        question=q2,
        target_question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )
    with pytest.raises(ValidationError) as exc:
        cond.clean()
    assert "after the triggering question" in str(exc.value)


@pytest.mark.django_db
def test_clean_accepts_forward_jump_to(survey: Survey):
    g = _make_group(survey, "Group")
    q1 = _make_question(survey, "Q1", 0, g)
    q2 = _make_question(survey, "Q2", 1, g)

    # Jump from Q1 forward to Q2 — valid
    cond = SurveyQuestionCondition(
        question=q1,
        target_question=q2,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )
    cond.clean()  # should not raise


@pytest.mark.django_db
def test_clean_accepts_end_survey_without_target(survey: Survey):
    source = _make_question(survey, "Source", 0)

    cond = SurveyQuestionCondition(
        question=source,
        target_question=None,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.END_SURVEY,
    )
    cond.clean()  # should not raise
