from __future__ import annotations

import json
import re

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion

TEST_PASSWORD = "x"


@pytest.mark.django_db
def test_group_question_edit_updates_text_format(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey = Survey.objects.create(owner=owner, name="Demo", slug="demo")
    group = QuestionGroup.objects.create(name="Group", owner=owner)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Age",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )

    client.force_login(owner)
    url = reverse(
        "surveys:builder_group_question_edit",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": question.id},
    )
    resp = client.post(
        url,
        {
            "text": "Age",
            "type": "text",
            "text_format": "number",
        },
        HTTP_HX_REQUEST="true",
    )

    assert resp.status_code == 200
    assert b"Question updated." in resp.content
    html = resp.content.decode()
    assert html.count("question-row-") == 1
    assert html.count("alert alert-success") == 1
    question.refresh_from_db()
    assert question.options == [{"type": "text", "format": "number"}]


@pytest.mark.django_db
def test_question_edit_splits_multiple_choice_options(client):
    owner = User.objects.create_user(username="editor", password=TEST_PASSWORD)
    survey = Survey.objects.create(owner=owner, name="Choices", slug="choices")
    question = SurveyQuestion.objects.create(
        survey=survey,
        text="Favourite colour",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=["Existing"],
        order=1,
    )

    client.force_login(owner)
    url = reverse(
        "surveys:builder_question_edit",
        kwargs={"slug": survey.slug, "qid": question.id},
    )
    resp = client.post(
        url,
        {
            "text": "Favourite colour",
            "type": "mc_single",
            "options": "Red\nBlue\n",
            "required": "on",
        },
        HTTP_HX_REQUEST="true",
    )

    assert resp.status_code == 200
    assert b"Question updated." in resp.content
    html = resp.content.decode()
    assert html.count("question-row-") == 1
    assert html.count("alert alert-success") == 1
    question.refresh_from_db()
    assert question.required is True
    assert question.options == [
        {"label": "Red", "value": "Red"},
        {"label": "Blue", "value": "Blue"},
    ]


@pytest.mark.django_db
def test_question_copy_duplicates_after_original(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey = Survey.objects.create(owner=owner, name="Copy", slug="copy")
    first = SurveyQuestion.objects.create(
        survey=survey,
        text="Favourite colour",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=["Red", "Blue"],
        order=1,
    )
    second = SurveyQuestion.objects.create(
        survey=survey,
        text="Next question",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=2,
    )

    client.force_login(owner)
    url = reverse(
        "surveys:builder_question_copy",
        kwargs={"slug": survey.slug, "qid": first.id},
    )
    resp = client.post(url, HTTP_HX_REQUEST="true")

    assert resp.status_code == 200
    first.refresh_from_db()
    second.refresh_from_db()
    all_questions = list(
        SurveyQuestion.objects.filter(survey=survey).order_by("order", "id")
    )
    assert len(all_questions) == 3
    copied = next(q for q in all_questions if q.id not in {first.id, second.id})
    assert copied.text == first.text
    assert copied.options == first.options
    assert copied.order == first.order + 1
    assert second.order == copied.order + 1

    html = resp.content.decode()
    script_id = f"question-data-{copied.id}"
    match = re.search(rf'<div id="{script_id}"[^>]*>(.*?)</div>', html, re.DOTALL)
    assert match, f"Payload div for {script_id} missing in response"
    payload_text = match.group(1).strip()
    assert payload_text and payload_text != "null"
    payload = json.loads(payload_text)
    assert payload["id"] == copied.id
    assert payload["text"] == copied.text
    assert html.count("Question copied.") == 1
    assert html.count("alert alert-success") == 1


@pytest.mark.django_db
def test_group_question_copy_preserves_group(client):
    owner = User.objects.create_user(username="group-owner", password=TEST_PASSWORD)
    survey = Survey.objects.create(owner=owner, name="Grouped", slug="grouped")
    group = QuestionGroup.objects.create(name="Vitals", owner=owner)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Age",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "number"}],
        order=1,
    )

    client.force_login(owner)
    url = reverse(
        "surveys:builder_group_question_copy",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": question.id},
    )
    resp = client.post(url, HTTP_HX_REQUEST="true")

    assert resp.status_code == 200
    question.refresh_from_db()
    questions = list(
        SurveyQuestion.objects.filter(survey=survey).order_by("order", "id")
    )
    assert len(questions) == 2
    copied = next(q for q in questions if q.id != question.id)
    assert copied.group_id == group.id
    assert copied.order == question.order + 1

    html = resp.content.decode()
    script_id = f"question-data-{copied.id}"
    match = re.search(rf'<div id="{script_id}"[^>]*>(.*?)</div>', html, re.DOTALL)
    assert match, f"Payload div for {script_id} missing in response"
    payload_text = match.group(1).strip()
    assert payload_text and payload_text != "null"
    payload = json.loads(payload_text)
    assert payload["id"] == copied.id
    assert payload["text"] == copied.text
    assert html.count("Question copied.") == 1
    assert html.count("alert alert-success") == 1


@pytest.mark.django_db
def test_question_copy_requires_edit_permission(client):
    owner = User.objects.create_user(username="owner2", password=TEST_PASSWORD)
    viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
    survey = Survey.objects.create(owner=owner, name="Locked", slug="locked")
    question = SurveyQuestion.objects.create(
        survey=survey,
        text="Locked question",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )

    client.force_login(viewer)
    url = reverse(
        "surveys:builder_question_copy",
        kwargs={"slug": survey.slug, "qid": question.id},
    )
    resp = client.post(url, HTTP_HX_REQUEST="true")

    assert resp.status_code == 403
    assert SurveyQuestion.objects.filter(survey=survey).count() == 1


@pytest.mark.django_db
def test_group_builder_includes_payload_metadata(client):
    owner = User.objects.create_user(username="payload", password=TEST_PASSWORD)
    survey = Survey.objects.create(owner=owner, name="Payload", slug="payload")
    group = QuestionGroup.objects.create(name="Vitals", owner=owner)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Age",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "number"}],
        order=1,
    )

    client.force_login(owner)
    url = reverse(
        "surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id}
    )
    resp = client.get(url)

    assert resp.status_code == 200
    questions = resp.context["questions"]
    assert questions
    first_question = list(questions)[0]
    payload = getattr(first_question, "builder_payload", None)
    assert payload is not None
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload.get("text_format") == "number"
