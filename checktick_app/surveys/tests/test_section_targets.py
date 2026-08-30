from __future__ import annotations

from django.contrib.auth.models import User
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
    _build_branching_config,
    _build_condition_payload,
    _export_survey_to_markdown,
    _prepare_question_rendering,
    _resolve_section_target_question,
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


def _make_group(survey: Survey, name: str, owner: User) -> QuestionGroup:
    group = QuestionGroup.objects.create(name=name, owner=owner)
    survey.question_groups.add(group)
    return group


# --- _resolve_section_target_question ---


@pytest.mark.django_db
def test_resolve_section_target_returns_first_question(survey: Survey, owner: User):
    g = _make_group(survey, "Section", owner)
    q1 = _make_question(survey, "Q1", 0, g)
    _make_question(survey, "Q2", 1, g)

    resolved = _resolve_section_target_question(survey, g)
    assert resolved is not None
    assert resolved.id == q1.id


@pytest.mark.django_db
def test_resolve_section_target_returns_none_for_empty_section(
    survey: Survey, owner: User
):
    g = _make_group(survey, "Empty", owner)
    resolved = _resolve_section_target_question(survey, g)
    assert resolved is None


# --- _build_branching_config resolves target_group ---


@pytest.mark.django_db
def test_build_branching_config_resolves_section_target(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    q2 = _make_question(survey, "Q2", 0, g2)

    SurveyQuestionCondition.objects.create(
        question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g2,
        order=0,
    )

    questions = list(survey.questions.all().order_by("order", "id"))
    config = _build_branching_config(questions)
    cond_data = config["conditions"][str(q1.id)][0]
    # The section target should be resolved to q2's ID.
    assert cond_data["target_question"] == str(q2.id)
    assert cond_data["action"] == "jump_to"


# --- _build_condition_payload accepts target_group ---


@pytest.mark.django_db
def test_build_payload_accepts_section_target(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    _make_question(survey, "Q2", 0, g2)

    from django.http import QueryDict

    data = QueryDict(
        f"operator=eq&value=Yes&action=jump_to&target_type=section&target_group={g2.id}"
    )
    payload = _build_condition_payload(survey, q1, data)
    assert payload["target_group"] == g2
    assert payload["target_question"] is None
    assert payload["action"] == "jump_to"


@pytest.mark.django_db
def test_build_payload_rejects_show_on_section(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    _make_question(survey, "Q2", 0, g2)

    from django.http import QueryDict

    data = QueryDict(
        f"operator=eq&value=Yes&action=show&target_type=section&target_group={g2.id}"
    )
    payload = _build_condition_payload(survey, q1, data)
    condition = SurveyQuestionCondition(question=q1, **payload)
    with pytest.raises(Exception) as exc:
        condition.full_clean()
    assert "questions, not sections" in str(exc.value)


@pytest.mark.django_db
def test_build_payload_rejects_section_from_wrong_survey(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    q1 = _make_question(survey, "Q1", 0, g1)

    # A group not in this survey.
    other_group = QuestionGroup.objects.create(name="Other", owner=owner)

    from django.http import QueryDict

    data = QueryDict(
        f"operator=eq&value=Yes&action=jump_to&target_type=section&target_group={other_group.id}"
    )
    with pytest.raises(Exception):
        _build_condition_payload(survey, q1, data)


# --- clean() validation for target_group ---


@pytest.mark.django_db
def test_clean_rejects_jump_to_own_section(survey: Survey, owner: User):
    g = _make_group(survey, "Section", owner)
    _make_question(survey, "Q1", 0, g)
    q2 = _make_question(survey, "Q2", 1, g)

    cond = SurveyQuestionCondition(
        question=q2,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g,
    )
    with pytest.raises(Exception) as exc:
        cond.full_clean()
    assert "belongs to" in str(exc.value)


@pytest.mark.django_db
def test_clean_rejects_jump_to_empty_section(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Empty", owner)
    q1 = _make_question(survey, "Q1", 0, g1)

    cond = SurveyQuestionCondition(
        question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g2,
    )
    with pytest.raises(Exception) as exc:
        cond.full_clean()
    assert "empty section" in str(exc.value)


@pytest.mark.django_db
def test_clean_accepts_valid_section_target(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    _make_question(survey, "Q2", 0, g2)

    cond = SurveyQuestionCondition(
        question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g2,
    )
    cond.full_clean()  # should not raise


# --- _serialize_question_for_builder includes target_sections ---


@pytest.mark.django_db
def test_serialize_includes_target_sections_excluding_source(
    survey: Survey, owner: User
):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)

    prepared = _prepare_question_rendering(survey, [q1])
    payload = prepared[0].builder_payload
    sections = payload["condition_options"]["target_sections"]
    section_ids = {s["id"] for s in sections}
    assert g2.id in section_ids
    assert g1.id not in section_ids  # source section excluded


# --- branching_data_api resolves section targets ---


@pytest.mark.django_db
def test_branching_data_api_resolves_section_target(survey: Survey, owner: User):
    from checktick_app.surveys.views import branching_data_api

    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    q2 = _make_question(survey, "Q2", 0, g2)

    SurveyQuestionCondition.objects.create(
        question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g2,
        order=0,
    )

    request = RequestFactory().get("/api/branching-data/")
    request.user = owner
    response = branching_data_api(request, survey.slug)
    import json

    data = json.loads(response.content)
    cond = data["conditions"][str(q1.id)][0]
    # The section target should be resolved to q2's ID.
    assert cond["target_question"] == str(q2.id)
    assert cond["target_group"] == str(g2.id)
    assert cond["target_group_name"] == "Target"


# --- Export round-trip ---


@pytest.mark.django_db
def test_export_emits_action_keywords(survey: Survey, owner: User):
    g = _make_group(survey, "Section", owner)
    source = _make_question(survey, "Source", 0, g)
    target_hidden = _make_question(
        survey, "Hidden target", 1, g, hidden_by_default=True
    )
    target_shown = _make_question(survey, "Shown target", 2, g)

    SurveyQuestionCondition.objects.create(
        question=source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.SHOW,
        target_question=target_hidden,
        order=0,
    )
    SurveyQuestionCondition.objects.create(
        question=source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="No",
        action=SurveyQuestionCondition.Action.HIDE,
        target_question=target_shown,
        order=1,
    )
    SurveyQuestionCondition.objects.create(
        question=source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="N/A",
        action=SurveyQuestionCondition.Action.END_SURVEY,
        order=2,
    )

    md = _export_survey_to_markdown(survey)
    assert "? show when" in md
    assert "? hide when" in md
    assert "? end when" in md


@pytest.mark.django_db
def test_export_emits_hidden_flag(survey: Survey, owner: User):
    g = _make_group(survey, "Section", owner)
    _make_question(survey, "Hidden Q", 0, g, hidden_by_default=True)
    _make_question(survey, "Shown Q", 1, g, hidden_by_default=False)

    md = _export_survey_to_markdown(survey)
    assert "HIDDEN" in md


@pytest.mark.django_db
def test_export_emits_section_target(survey: Survey, owner: User):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    _make_question(survey, "Q2", 0, g2)

    SurveyQuestionCondition.objects.create(
        question=q1,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g2,
        order=0,
    )

    md = _export_survey_to_markdown(survey)
    assert "-> #target" in md


@pytest.mark.django_db
def test_export_round_trip_preserves_actions(survey: Survey, owner: User):
    """Export a survey with all action types and re-import; actions survive."""
    from checktick_app.surveys.markdown_import import parse_bulk_markdown

    g = _make_group(survey, "Section", owner)
    source = _make_question(survey, "Source", 0, g)
    target_hidden = _make_question(
        survey, "Hidden target", 1, g, hidden_by_default=True
    )
    target_shown = _make_question(survey, "Shown target", 2, g)

    SurveyQuestionCondition.objects.create(
        question=source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="Yes",
        action=SurveyQuestionCondition.Action.SHOW,
        target_question=target_hidden,
        order=0,
    )
    SurveyQuestionCondition.objects.create(
        question=source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="No",
        action=SurveyQuestionCondition.Action.HIDE,
        target_question=target_shown,
        order=1,
    )

    md = _export_survey_to_markdown(survey)
    groups = parse_bulk_markdown(md)
    branches = groups[0]["questions"][0]["branches"]
    actions = {b["action"] for b in branches}
    assert SurveyQuestionCondition.Action.SHOW in actions
    assert SurveyQuestionCondition.Action.HIDE in actions


# --- Template rendering ---


@pytest.mark.django_db
def test_condition_panel_renders_section_picker(owner: User, survey: Survey):
    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    _make_question(survey, "Q2", 0, g2)

    request = RequestFactory().get("/builder/")
    request.user = owner

    from checktick_app.surveys.views import _render_template_question_row

    response = _render_template_question_row(request, survey, q1, group=g1)
    content = response.content.decode()
    assert "data-target-type-select" in content
    assert 'data-target-select="section"' in content
    assert "Target" in content  # section name in the picker


# --- Condition create view with section target ---


@pytest.mark.django_db
def test_condition_create_with_section_target(owner: User, survey: Survey):
    from django.test import Client

    g1 = _make_group(survey, "Source", owner)
    g2 = _make_group(survey, "Target", owner)
    q1 = _make_question(survey, "Q1", 0, g1)
    _make_question(survey, "Q2", 0, g2)

    client = Client()
    client.force_login(owner)

    response = client.post(
        f"/surveys/{survey.slug}/builder/questions/{q1.id}/conditions/create",
        data={
            "operator": "eq",
            "value": "Yes",
            "action": "jump_to",
            "target_type": "section",
            "target_group": str(g2.id),
        },
    )
    assert response.status_code == 200

    cond = SurveyQuestionCondition.objects.get(question=q1)
    assert cond.target_group_id == g2.id
    assert cond.target_question_id is None
    assert cond.action == SurveyQuestionCondition.Action.JUMP_TO
