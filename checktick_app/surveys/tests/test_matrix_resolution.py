"""Tests for the matrix.py pure helpers (step 2).

Covers section_state, missing_required_question_ids, landing_card_states,
all_sections_complete, add/remove_completed_group.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.matrix import (
    add_completed_group,
    all_sections_complete,
    is_section_complete,
    landing_card_states,
    missing_required_question_ids,
    remove_completed_group,
    section_answered_question_ids,
    section_required_questions,
    section_state,
)
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyProgress,
    SurveyQuestion,
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
        name="M",
        slug="m",
        layout=Survey.Layout.MATRIX,
    )
    return s


@pytest.fixture
def groups(owner, survey):
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="History", owner=owner)
    g3 = QuestionGroup.objects.create(name="Review", owner=owner)
    survey.question_groups.add(g1, g2, g3)
    return (g1, g2, g3)


@pytest.fixture
def questions(survey, groups):
    g1, g2, g3 = groups
    qs = []
    # Demographics: 2 required, 1 optional
    qs.append(
        SurveyQuestion.objects.create(
            survey=survey,
            group=g1,
            text="Name",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )
    )
    qs.append(
        SurveyQuestion.objects.create(
            survey=survey,
            group=g1,
            text="Age",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=1,
        )
    )
    qs.append(
        SurveyQuestion.objects.create(
            survey=survey,
            group=g1,
            text="Nickname",
            type=SurveyQuestion.Types.TEXT,
            required=False,
            order=2,
        )
    )
    # History: 1 required, 1 hidden-by-default (not required until shown)
    qs.append(
        SurveyQuestion.objects.create(
            survey=survey,
            group=g2,
            text="Condition",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )
    )
    qs.append(
        SurveyQuestion.objects.create(
            survey=survey,
            group=g2,
            text="Hidden follow-up",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            hidden_by_default=True,
            order=1,
        )
    )
    # Review: 1 required
    qs.append(
        SurveyQuestion.objects.create(
            survey=survey,
            group=g3,
            text="Score",
            type=SurveyQuestion.Types.TEXT,
            required=True,
            order=0,
        )
    )
    return qs


@pytest.fixture
def progress(survey, owner):
    return SurveyProgress.objects.create(
        survey=survey,
        user=owner,
        expires_at=timezone.now() + timedelta(days=30),
    )


# --- section_required_questions ---


@pytest.mark.django_db
def test_section_required_questions_excludes_optional_and_hidden(
    survey, groups, questions
):
    g1, g2, _g3 = groups
    demo_required = list(section_required_questions(survey.id, g1.id))
    assert {q.text for q in demo_required} == {"Name", "Age"}
    # Hidden-by-default questions are excluded even if required=True.
    hist_required = list(section_required_questions(survey.id, g2.id))
    assert {q.text for q in hist_required} == {"Condition"}


# --- section_answered_question_ids ---


@pytest.mark.django_db
def test_section_answered_question_ids(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    name_q = questions[0]
    progress.partial_answers = {str(name_q.id): "Alice"}
    progress.save()
    answered = section_answered_question_ids(progress.partial_answers, survey.id, g1.id)
    assert name_q.id in answered
    # Age (required, no answer) is not in the set.
    age_q = questions[1]
    assert age_q.id not in answered


@pytest.mark.django_db
def test_section_answered_question_ids_empty_values_excluded(
    progress, survey, groups, questions
):
    g1, _g2, _g3 = groups
    name_q = questions[0]
    age_q = questions[1]
    # Empty string and empty list should not count as answered.
    progress.partial_answers = {str(name_q.id): "", str(age_q.id): []}
    progress.save()
    answered = section_answered_question_ids(progress.partial_answers, survey.id, g1.id)
    assert answered == set()


# --- section_state ---


@pytest.mark.django_db
def test_section_state_not_started(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    assert section_state(progress, survey.id, g1.id) == "not_started"


@pytest.mark.django_db
def test_section_state_in_progress(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    name_q = questions[0]
    progress.partial_answers = {str(name_q.id): "Alice"}
    progress.save()
    assert section_state(progress, survey.id, g1.id) == "in_progress"


@pytest.mark.django_db
def test_section_state_complete(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    add_completed_group(progress, g1.id)
    progress.save()
    assert section_state(progress, survey.id, g1.id) == "complete"


# --- is_section_complete ---


@pytest.mark.django_db
def test_is_section_complete_true_after_add(progress, groups):
    g1, _g2, _g3 = groups
    add_completed_group(progress, g1.id)
    assert is_section_complete(progress, g1.id) is True


@pytest.mark.django_db
def test_is_section_complete_false_default(progress, groups):
    g1, _g2, _g3 = groups
    assert is_section_complete(progress, g1.id) is False


# --- missing_required_question_ids ---


@pytest.mark.django_db
def test_missing_required_all_unanswered(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    name_q, age_q, _nick_q = questions[0], questions[1], questions[2]
    missing = missing_required_question_ids(progress.partial_answers, survey.id, g1.id)
    assert set(missing) == {name_q.id, age_q.id}


@pytest.mark.django_db
def test_missing_required_partial_answer(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    name_q, age_q = questions[0], questions[1]
    progress.partial_answers = {str(name_q.id): "Alice"}
    progress.save()
    missing = missing_required_question_ids(progress.partial_answers, survey.id, g1.id)
    assert missing == [age_q.id]


@pytest.mark.django_db
def test_missing_required_none_when_all_answered(progress, survey, groups, questions):
    g1, _g2, _g3 = groups
    name_q, age_q = questions[0], questions[1]
    progress.partial_answers = {
        str(name_q.id): "Alice",
        str(age_q.id): "30",
    }
    progress.save()
    missing = missing_required_question_ids(progress.partial_answers, survey.id, g1.id)
    assert missing == []


# --- landing_card_states ---


@pytest.mark.django_db
def test_landing_card_states_order_and_fields(progress, survey, groups, questions):
    g1, g2, g3 = groups
    name_q = questions[0]
    progress.partial_answers = {str(name_q.id): "Alice"}
    progress.save()
    cards = landing_card_states(progress, survey.id, [g1.id, g2.id, g3.id])
    assert len(cards) == 3
    assert cards[0]["group_id"] == g1.id
    assert cards[0]["state"] == "in_progress"
    assert cards[0]["answered_count"] == 1
    assert cards[0]["total_questions"] == 3  # Name, Age, Nickname
    assert cards[0]["missing_required_count"] == 1  # Age
    assert cards[1]["state"] == "not_started"
    assert cards[1]["total_questions"] == 2  # Condition + Hidden follow-up
    assert cards[2]["state"] == "not_started"
    assert cards[2]["total_questions"] == 1


# --- all_sections_complete ---


@pytest.mark.django_db
def test_all_sections_complete_false_initially(progress, survey, groups):
    g1, g2, g3 = groups
    assert all_sections_complete(progress, survey.id, [g1.id, g2.id, g3.id]) is False


@pytest.mark.django_db
def test_all_sections_complete_true_when_all_marked(progress, survey, groups):
    g1, g2, g3 = groups
    for g in (g1, g2, g3):
        add_completed_group(progress, g.id)
    progress.save()
    assert all_sections_complete(progress, survey.id, [g1.id, g2.id, g3.id]) is True


@pytest.mark.django_db
def test_all_sections_complete_partial(progress, survey, groups):
    g1, g2, g3 = groups
    add_completed_group(progress, g1.id)
    progress.save()
    assert all_sections_complete(progress, survey.id, [g1.id, g2.id, g3.id]) is False


# --- add/remove_completed_group ---


@pytest.mark.django_db
def test_add_completed_group_idempotent(progress, groups):
    g1, _g2, _g3 = groups
    add_completed_group(progress, g1.id)
    add_completed_group(progress, g1.id)
    assert progress.completed_group_ids == [g1.id]


@pytest.mark.django_db
def test_remove_completed_group(progress, groups):
    g1, g2, _g3 = groups
    add_completed_group(progress, g1.id)
    add_completed_group(progress, g2.id)
    remove_completed_group(progress, g1.id)
    assert progress.completed_group_ids == [g2.id]


@pytest.mark.django_db
def test_remove_completed_group_not_present(progress, groups):
    g1, _g2, _g3 = groups
    remove_completed_group(progress, g1.id)  # no-op
    assert progress.completed_group_ids == []


@pytest.mark.django_db
def test_add_then_remove_then_re_add(progress, groups):
    g1, _g2, _g3 = groups
    add_completed_group(progress, g1.id)
    remove_completed_group(progress, g1.id)
    assert progress.completed_group_ids == []
    add_completed_group(progress, g1.id)
    assert progress.completed_group_ids == [g1.id]
