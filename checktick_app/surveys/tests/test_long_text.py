"""Tests for the long_text question type (textarea).

See docs/survey-layouts-technical.md §Long text (prerequisite PR).

long_text is a textarea version of text — same answer storage (string),
but rendered as a multi-line <textarea> in the builder and the take view.
"""

from __future__ import annotations

import textwrap

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import Survey, SurveyQuestion

TEST_PASSWORD = "x"


# --- Parsing ---


def test_parse_long_text_type():
    md = textwrap.dedent("""
        # Section {sec}
        ## Any other comments
        (long_text)
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "long_text"
    assert q["final_options"] == []


def test_parse_long_text_aliases():
    md = textwrap.dedent("""
        # Section {sec}
        ## A
        (textarea)

        ## B
        (paragraph)

        ## C
        (long text)
        """).strip()

    groups = parse_bulk_markdown(md)
    types = [q["final_type"] for q in groups[0]["questions"]]
    assert types == ["long_text", "long_text", "long_text"]


# --- Full bulk upload import ---


@pytest.mark.django_db
def test_bulk_import_creates_long_text_question(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="BulkLong", slug="bulk-long")

    md = textwrap.dedent("""
        # Section {sec}
        ## Any other comments
        (long_text)
        """).strip()

    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": md},
        follow=False,
    )
    assert response.status_code == 302

    q = SurveyQuestion.objects.get(survey=survey, text="Any other comments")
    assert q.type == SurveyQuestion.Types.LONG_TEXT
    assert q.options == []


# --- Builder creation ---


@pytest.mark.django_db
def test_create_long_text_question(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="LongText", slug="long-text")

    client.force_login(user)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})

    response = client.post(
        url,
        {
            "text": "Please describe what happened",
            "type": "long_text",
            "required": "on",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    question = SurveyQuestion.objects.get(survey=survey)
    assert question.type == SurveyQuestion.Types.LONG_TEXT
    assert question.text == "Please describe what happened"
    assert question.required is True
    assert question.options == []
