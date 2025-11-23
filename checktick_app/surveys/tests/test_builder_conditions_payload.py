from __future__ import annotations

from django.contrib.auth.models import User
from django.db import OperationalError
from django.db.models.query import QuerySet
from django.test import RequestFactory
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)
from checktick_app.surveys.views import (
    _prepare_question_rendering,
    _render_template_question_row,
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


def _create_question(
    survey: Survey,
    group: QuestionGroup | None,
    text: str,
    order: int,
    qtype: str = SurveyQuestion.Types.TEXT,
) -> SurveyQuestion:
    return SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=text,
        type=qtype,
        options=[{"type": "text", "format": "free"}],
        required=False,
        order=order,
    )


@pytest.mark.django_db
def test_prepare_question_rendering_includes_condition_metadata(
    owner: User, survey: Survey
):
    group = QuestionGroup.objects.create(name="Default", owner=owner)
    survey.question_groups.add(group)

    trigger = _create_question(survey, group, "Trigger", order=0)
    target = _create_question(survey, group, "Follow up", order=1)

    SurveyQuestionCondition.objects.create(
        question=trigger,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        target_question=target,
        action=SurveyQuestionCondition.Action.JUMP_TO,
        order=0,
        description="When answer is yes",
    )

    prepared = _prepare_question_rendering(survey, [trigger, target])
    trigger_prepared = next(q for q in prepared if q.id == trigger.id)
    payload = trigger_prepared.builder_payload

    assert payload["conditions"], "Expected serialized conditions in payload"
    condition_payload = payload["conditions"][0]
    assert condition_payload["target"]["id"] == target.id
    assert condition_payload["target"]["type"] == "question"
    assert condition_payload["requires_value"] is True
    assert "Skip ahead to question" in condition_payload["summary"]

    options = payload["condition_options"]
    assert options["has_question_targets"] is True
    question_ids = {entry["id"] for entry in options["target_questions"]}
    assert target.id in question_ids


@pytest.mark.django_db
def test_condition_options_default_to_group_when_no_other_questions(
    owner: User, survey: Survey
):
    group_primary = QuestionGroup.objects.create(name="Primary", owner=owner)
    group_secondary = QuestionGroup.objects.create(name="Secondary", owner=owner)
    survey.question_groups.add(group_primary, group_secondary)

    solo = _create_question(survey, group_primary, "Only question", order=0)

    prepared = _prepare_question_rendering(survey, [solo])
    payload = prepared[0].builder_payload
    options = payload["condition_options"]

    assert options["has_question_targets"] is False
    assert options["can_create"] is False


@pytest.mark.django_db
def test_render_question_row_includes_condition_panel(owner: User, survey: Survey):
    group = QuestionGroup.objects.create(name="Panel", owner=owner)
    survey.question_groups.add(group)
    question = _create_question(survey, group, "Question with UI", order=0)

    request = RequestFactory().get("/builder/")
    request.user = owner

    response = _render_template_question_row(request, survey, question)
    assert b"data-condition-panel" in response.content


@pytest.mark.django_db
def test_prepare_question_rendering_skips_condition_prefetch_when_unavailable(
    monkeypatch: pytest.MonkeyPatch, owner: User, survey: Survey
):
    group = QuestionGroup.objects.create(name="Fallback", owner=owner)
    survey.question_groups.add(group)
    question = _create_question(survey, group, "Standalone", order=0)

    original_prefetch = QuerySet.prefetch_related

    def raising_prefetch(self, *lookups):
        if any("conditions__" in str(lookup) for lookup in lookups):
            raise OperationalError("no such table: surveys_surveyquestioncondition")
        return original_prefetch(self, *lookups)

    monkeypatch.setattr(QuerySet, "prefetch_related", raising_prefetch)

    prepared = _prepare_question_rendering(
        survey, SurveyQuestion.objects.filter(group=group)
    )

    assert prepared, "Questions should still be returned when condition prefetch fails"
    assert prepared[0].builder_payload["conditions"] == []
    assert prepared[0].builder_payload["id"] == question.id
