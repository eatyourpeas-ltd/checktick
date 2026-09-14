"""Tests for the content_block question type — model and validation.

See docs/survey-layouts-technical.md §Content blocks.
"""

from __future__ import annotations

import textwrap

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import Survey, SurveyQuestion

TEST_PASSWORD = "x"


# --- Model and validation ---


@pytest.mark.django_db
def test_content_block_type_exists():
    """The CONTENT_BLOCK choice is present on SurveyQuestion.Types."""
    assert "content_block" in dict(SurveyQuestion.Types.choices).keys()
    assert SurveyQuestion.Types.CONTENT_BLOCK == "content_block"


@pytest.mark.django_db
def test_content_block_clean_rejects_required_true():
    """A content_block with required=True must fail validation."""
    User = get_user_model()
    user = User.objects.create_user(username="author", password="x")
    survey = Survey.objects.create(owner=user, name="CB", slug="cb")
    q = SurveyQuestion(
        survey=survey,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"body_md": "Hello"},
        required=True,
    )
    with pytest.raises(ValidationError) as exc:
        q.clean()
    assert "required" in exc.value.message_dict


@pytest.mark.django_db
def test_content_block_clean_accepts_required_false():
    """A content_block with required=False passes validation."""
    User = get_user_model()
    user = User.objects.create_user(username="author2", password="x")
    survey = Survey.objects.create(owner=user, name="CB2", slug="cb2")
    q = SurveyQuestion(
        survey=survey,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"body_md": "Hello"},
        required=False,
    )
    q.clean()  # should not raise


@pytest.mark.django_db
def test_content_block_default_required_is_false():
    """A newly created content_block question defaults to required=False."""
    User = get_user_model()
    user = User.objects.create_user(username="author3", password="x")
    survey = Survey.objects.create(owner=user, name="CB3", slug="cb3")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Intro",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"body_md": "Welcome"},
    )
    assert q.required is False


# --- Parsing ---


def test_parse_content_block_type():
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)

        Welcome to the study.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "content_block"
    assert q["final_options"]["body_md"] == "Welcome to the study."
    assert q["final_options"]["variant"] == "text"
    assert q["final_options"]["render_once"] is True
    assert q["final_options"]["links"] == []
    assert q["required"] is False


def test_parse_content_block_aliases():
    md = textwrap.dedent("""
        # Section {sec}
        ## A
        (content block)

        ## B
        (contentblock)
        """).strip()

    groups = parse_bulk_markdown(md)
    types = [q["final_type"] for q in groups[0]["questions"]]
    assert types == ["content_block", "content_block"]


def test_parse_content_block_with_links():
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)
        link: Privacy notice|https://example.com/privacy
        link: Study protocol|https://example.com/protocol

        Welcome to the study.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert len(q["final_options"]["links"]) == 2
    assert q["final_options"]["links"][0] == {
        "label": "Privacy notice",
        "url": "https://example.com/privacy",
    }
    assert q["final_options"]["links"][1] == {
        "label": "Study protocol",
        "url": "https://example.com/protocol",
    }


def test_parse_content_block_variant_and_render_once():
    md = textwrap.dedent("""
        # Section {sec}
        ## Disclosure
        (content_block)
        variant: disclosure
        render_once: false

        Please read this disclosure.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_options"]["variant"] == "disclosure"
    assert q["final_options"]["render_once"] is False


def test_parse_content_block_forces_required_false():
    """Even with the * suffix, a content_block must not be required."""
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction*
        (content_block)

        Welcome.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["required"] is False


def test_parse_content_block_multiline_body():
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)

        Welcome to the study.

        Please read the privacy notice before continuing.

        Thank you.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    body = q["final_options"]["body_md"]
    assert "Welcome to the study." in body
    assert "Please read the privacy notice before continuing." in body
    assert "Thank you." in body
    # Paragraph breaks preserved
    assert "\n\n" in body


def test_parse_content_block_strips_javascript_link():
    """Dangerous URL schemes in links must be stripped at parse time."""
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)
        link: Evil|javascript:alert(1)

        Body.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    # The dangerous link is dropped entirely
    assert q["final_options"]["links"] == []


def test_parse_content_block_invalid_variant_defaults_to_text():
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)
        variant: nonsense_variant

        Body.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_options"]["variant"] == "text"


# --- Full bulk upload import ---


@pytest.mark.django_db
def test_bulk_import_creates_content_block_question(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="BulkCB", slug="bulk-cb")

    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)
        link: Privacy|https://example.com/privacy

        Welcome to the study.
        """).strip()

    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": md},
        follow=False,
    )
    assert response.status_code == 302

    q = SurveyQuestion.objects.get(survey=survey, text="Introduction")
    assert q.type == SurveyQuestion.Types.CONTENT_BLOCK
    assert q.required is False
    assert q.options["body_md"] == "Welcome to the study."
    assert len(q.options["links"]) == 1
    assert q.options["links"][0]["url"] == "https://example.com/privacy"
    assert q.options["variant"] == "text"
    assert q.options["render_once"] is True
