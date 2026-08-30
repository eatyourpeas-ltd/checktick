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
    _build_condition_payload,
    _parse_builder_question_form,
    _prepare_question_rendering,
    _serialize_question_for_builder,
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


# --- _parse_builder_question_form ---


def test_parse_form_reads_hidden_by_default_checkbox():
    from django.http import QueryDict

    data = QueryDict("text=Q&type=text&hidden_by_default=on")
    form = _parse_builder_question_form(data)
    assert form["hidden_by_default"] is True


def test_parse_form_hidden_by_default_defaults_false():
    from django.http import QueryDict

    data = QueryDict("text=Q&type=text")
    form = _parse_builder_question_form(data)
    assert form["hidden_by_default"] is False


# --- _serialize_question_for_builder ---


@pytest.mark.django_db
def test_serialize_includes_hidden_by_default_on_question(survey: Survey, owner: User):
    q = _make_question(survey, "Q", 0, hidden_by_default=True)
    payload = _serialize_question_for_builder(q)
    assert payload["hidden_by_default"] is True


@pytest.mark.django_db
def test_serialize_includes_hidden_by_default_on_target_entries(
    survey: Survey, owner: User
):
    g = _make_group(survey, "Group", owner)
    q1 = _make_question(survey, "Q1", 0, g, hidden_by_default=False)
    q2 = _make_question(survey, "Q2", 1, g, hidden_by_default=True)

    prepared = _prepare_question_rendering(survey, [q1, q2])
    q1_payload = next(q for q in prepared if q.id == q1.id).builder_payload
    targets = {t["id"]: t for t in q1_payload["condition_options"]["target_questions"]}
    # q2 is a target of q1; it should carry hidden_by_default=True
    assert targets[q2.id]["hidden_by_default"] is True


# --- _build_condition_payload (action validation via clean) ---


@pytest.mark.django_db
def test_build_payload_rejects_show_on_shown_by_default(survey: Survey, owner: User):
    g = _make_group(survey, "Group", owner)
    source = _make_question(survey, "Source", 0, g)
    target = _make_question(survey, "Target", 1, g, hidden_by_default=False)

    from django.http import QueryDict

    data = QueryDict(f"operator=eq&value=Yes&action=show&target_question={target.id}")
    payload = _build_condition_payload(survey, source, data)
    condition = SurveyQuestionCondition(question=source, **payload)
    with pytest.raises(Exception) as exc:
        condition.full_clean()
    assert "hidden by default" in str(exc.value)


@pytest.mark.django_db
def test_build_payload_accepts_show_on_hidden_by_default(survey: Survey, owner: User):
    g = _make_group(survey, "Group", owner)
    source = _make_question(survey, "Source", 0, g)
    target = _make_question(survey, "Target", 1, g, hidden_by_default=True)

    from django.http import QueryDict

    data = QueryDict(f"operator=eq&value=Yes&action=show&target_question={target.id}")
    payload = _build_condition_payload(survey, source, data)
    condition = SurveyQuestionCondition(question=source, **payload)
    condition.full_clean()  # should not raise


@pytest.mark.django_db
def test_build_payload_rejects_hide_on_hidden_by_default(survey: Survey, owner: User):
    g = _make_group(survey, "Group", owner)
    source = _make_question(survey, "Source", 0, g)
    target = _make_question(survey, "Target", 1, g, hidden_by_default=True)

    from django.http import QueryDict

    data = QueryDict(f"operator=eq&value=Yes&action=hide&target_question={target.id}")
    payload = _build_condition_payload(survey, source, data)
    condition = SurveyQuestionCondition(question=source, **payload)
    with pytest.raises(Exception) as exc:
        condition.full_clean()
    assert "shown by default" in str(exc.value)


@pytest.mark.django_db
def test_build_payload_accepts_hide_on_shown_by_default(survey: Survey, owner: User):
    g = _make_group(survey, "Group", owner)
    source = _make_question(survey, "Source", 0, g)
    target = _make_question(survey, "Target", 1, g, hidden_by_default=False)

    from django.http import QueryDict

    data = QueryDict(f"operator=eq&value=Yes&action=hide&target_question={target.id}")
    payload = _build_condition_payload(survey, source, data)
    condition = SurveyQuestionCondition(question=source, **payload)
    condition.full_clean()  # should not raise


@pytest.mark.django_db
def test_build_payload_rejects_backward_jump_to(survey: Survey, owner: User):
    g = _make_group(survey, "Group", owner)
    q1 = _make_question(survey, "Q1", 0, g)
    q2 = _make_question(survey, "Q2", 1, g)

    from django.http import QueryDict

    # Jump from q2 back to q1 — backward
    data = QueryDict(f"operator=eq&value=Yes&action=jump_to&target_question={q1.id}")
    payload = _build_condition_payload(survey, q2, data)
    condition = SurveyQuestionCondition(question=q2, **payload)
    with pytest.raises(Exception) as exc:
        condition.full_clean()
    assert "after the triggering question" in str(exc.value)


@pytest.mark.django_db
def test_build_payload_accepts_forward_jump_to(survey: Survey, owner: User):
    g = _make_group(survey, "Group", owner)
    q1 = _make_question(survey, "Q1", 0, g)
    q2 = _make_question(survey, "Q2", 1, g)

    from django.http import QueryDict

    # Jump from q1 forward to q2 — valid
    data = QueryDict(f"operator=eq&value=Yes&action=jump_to&target_question={q2.id}")
    payload = _build_condition_payload(survey, q1, data)
    condition = SurveyQuestionCondition(question=q1, **payload)
    condition.full_clean()  # should not raise


# --- Template rendering (action picker relabel) ---


@pytest.mark.django_db
def test_condition_panel_renders_hide_not_skip(owner: User, survey: Survey):
    g = _make_group(survey, "Group", owner)
    q1 = _make_question(survey, "Q1", 0, g)
    _make_question(survey, "Q2", 1, g)  # second question so targets exist

    request = RequestFactory().get("/builder/")
    request.user = owner

    from checktick_app.surveys.views import _render_template_question_row

    response = _render_template_question_row(request, survey, q1, group=g)
    content = response.content.decode()
    assert 'data-action="hide"' in content
    assert 'data-action="skip"' not in content


@pytest.mark.django_db
def test_condition_panel_target_options_carry_hidden_by_default(
    owner: User, survey: Survey
):
    g = _make_group(survey, "Group", owner)
    q1 = _make_question(survey, "Q1", 0, g, hidden_by_default=False)
    _make_question(survey, "Q2", 1, g, hidden_by_default=True)

    request = RequestFactory().get("/builder/")
    request.user = owner

    from checktick_app.surveys.views import _render_template_question_row

    response = _render_template_question_row(request, survey, q1, group=g)
    content = response.content.decode()
    # q2's option should carry data-hidden-by-default="1"
    assert 'data-hidden-by-default="1"' in content


# --- Question create/edit views persist hidden_by_default ---


@pytest.mark.django_db
def test_builder_question_create_persists_hidden_by_default(
    owner: User, survey: Survey
):
    from django.test import Client

    g = _make_group(survey, "Group", owner)
    client = Client()
    client.force_login(owner)

    response = client.post(
        f"/surveys/{survey.slug}/builder/groups/{g.id}/questions/create",
        data={
            "text": "Hidden Q",
            "type": "text",
            "hidden_by_default": "on",
            "text_format": "free",
        },
    )
    assert response.status_code == 200
    created = SurveyQuestion.objects.get(text="Hidden Q")
    assert created.hidden_by_default is True


@pytest.mark.django_db
def test_builder_question_edit_updates_hidden_by_default(owner: User, survey: Survey):
    from django.test import Client

    g = _make_group(survey, "Group", owner)
    q = _make_question(survey, "Q", 0, g, hidden_by_default=False)

    client = Client()
    client.force_login(owner)

    response = client.post(
        f"/surveys/{survey.slug}/builder/groups/{g.id}/questions/{q.id}/edit",
        data={
            "text": "Q",
            "type": "text",
            "hidden_by_default": "on",
            "text_format": "free",
        },
    )
    assert response.status_code == 200
    q.refresh_from_db()
    assert q.hidden_by_default is True
