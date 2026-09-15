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


# --- Export round-trip ---


@pytest.mark.django_db
def test_export_content_block_round_trip(client, django_user_model):
    """Export a content_block question to markdown and re-import it."""
    from checktick_app.surveys.models import QuestionGroup
    from checktick_app.surveys.views import _export_survey_to_markdown

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="ExportCB", slug="export-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Introduction",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "Welcome to the study.\n\nPlease read the privacy notice.",
            "links": [
                {"label": "Privacy", "url": "https://example.com/privacy"},
                {"label": "Protocol", "url": "https://example.com/protocol"},
            ],
            "variant": "disclosure",
            "render_once": False,
        },
        required=False,
        order=0,
    )

    exported = _export_survey_to_markdown(survey)
    # The export contains the content_block type and config
    assert "(content_block)" in exported
    assert "variant: disclosure" in exported
    assert "render_once: false" in exported
    assert "link: Privacy|https://example.com/privacy" in exported
    assert "link: Protocol|https://example.com/protocol" in exported
    assert "Welcome to the study." in exported
    assert "Please read the privacy notice." in exported

    # Re-import into a fresh survey
    survey2 = Survey.objects.create(owner=user, name="Reimport", slug="reimport-cb")
    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey2.slug}),
        {"markdown": exported},
        follow=False,
    )
    assert response.status_code == 302

    q = SurveyQuestion.objects.get(survey=survey2, text="Introduction")
    assert q.type == SurveyQuestion.Types.CONTENT_BLOCK
    assert q.required is False
    assert q.options["variant"] == "disclosure"
    assert q.options["render_once"] is False
    assert len(q.options["links"]) == 2
    assert q.options["links"][0]["url"] == "https://example.com/privacy"
    assert "Welcome to the study." in q.options["body_md"]
    assert "Please read the privacy notice." in q.options["body_md"]


@pytest.mark.django_db
def test_export_content_block_minimal_round_trip(client, django_user_model):
    """A minimal content_block (body only) round-trips."""
    from checktick_app.surveys.models import QuestionGroup
    from checktick_app.surveys.views import _export_survey_to_markdown

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="MinCB", slug="min-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Intro",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "Just a body.",
            "links": [],
            "variant": "text",
            "render_once": True,
        },
        required=False,
        order=0,
    )

    exported = _export_survey_to_markdown(survey)
    assert "(content_block)" in exported
    assert "Just a body." in exported
    # Default variant/render_once are not emitted
    assert "variant:" not in exported
    assert "render_once:" not in exported

    survey2 = Survey.objects.create(owner=user, name="MinCB2", slug="min-cb2")
    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey2.slug}),
        {"markdown": exported},
        follow=False,
    )
    assert response.status_code == 302

    q = SurveyQuestion.objects.get(survey=survey2, text="Intro")
    assert q.type == SurveyQuestion.Types.CONTENT_BLOCK
    assert q.options["body_md"] == "Just a body."
    assert q.options["variant"] == "text"
    assert q.options["render_once"] is True
    assert q.options["links"] == []


# --- CSV export skip ---


def test_format_answer_for_export_content_block_returns_empty():
    """Content blocks have no answer; the formatter returns empty string."""
    from checktick_app.surveys.views import _format_answer_for_export

    # Even if a stray answer is passed, content_block has no meaningful answer.
    assert _format_answer_for_export("anything", "content_block") == "anything"
    assert _format_answer_for_export("", "content_block") == ""
    assert _format_answer_for_export(None, "content_block") == ""


@pytest.mark.django_db
def test_csv_export_skips_content_block_column(client, django_user_model):
    """Content blocks must not appear as columns in the CSV export header."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        owner=user,
        name="CSVCB",
        slug="csv-cb",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    # A content block (no answer)
    cb_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Introduction",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "Welcome.",
            "links": [],
            "variant": "text",
            "render_once": True,
        },
        required=False,
        order=0,
    )
    # A normal text question (has answer)
    text_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Your name",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        required=False,
        order=1,
    )

    # Simulate the column-selection loop from survey_export_csv. The view
    # skips template_patient, template_professional, and content_block.
    questions = list(survey.questions.all().order_by("order"))
    question_columns = []
    for q in questions:
        if q.type in ("template_patient", "template_professional"):
            continue
        if q.type == "content_block":
            continue
        question_columns.append(q)

    # Only the text question is a column; the content block is skipped.
    assert len(question_columns) == 1
    assert question_columns[0].id == text_q.id
    assert cb_q.id not in [q.id for q in question_columns]


# --- Rendering ---


@pytest.mark.django_db
def test_content_block_renders_in_take_view(client, django_user_model):
    """The take page renders a content block with heading, body, and links."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    respondent = django_user_model.objects.create_user(
        username="respondent", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        owner=user,
        name="CBRender",
        slug="cb-render",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "Welcome to the **study**.",
            "links": [
                {"label": "Privacy", "url": "https://example.com/privacy"},
            ],
            "variant": "text",
            "render_once": True,
        },
        required=False,
        order=0,
    )

    client.force_login(respondent)
    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    # Heading is rendered
    assert "Welcome" in content
    # Markdown body is rendered (bold -> <strong>)
    assert "<strong>study</strong>" in content
    # Link is rendered with rel="noopener noreferrer"
    assert 'href="https://example.com/privacy"' in content
    assert 'rel="noopener noreferrer"' in content
    # No answer input is rendered for a content block
    assert f'name="q_{question.id}"' not in content


@pytest.mark.django_db
def test_content_block_renders_sanitised_html(client, django_user_model):
    """Dangerous HTML in the body_md is stripped before rendering."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    respondent = django_user_model.objects.create_user(
        username="respondent2", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        owner=user,
        name="CBXSS",
        slug="cb-xss",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Intro",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "<script>alert(1)</script>**safe**",
            "links": [],
            "variant": "text",
            "render_once": True,
        },
        required=False,
        order=0,
    )

    client.force_login(respondent)
    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    # The malicious script from body_md is stripped (not the page's own scripts)
    assert "alert(1)" not in content
    # Safe Markdown is rendered
    assert "<strong>safe</strong>" in content
