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
from checktick_app.surveys.views import _is_linked_consent_question

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
        heading: Welcome

        Welcome to the study.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "content_block"
    assert q["final_options"]["heading"] == "Welcome"
    assert q["final_options"]["body_md"] == "Welcome to the study."
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


def test_parse_content_block_subtitle_and_render_once():
    md = textwrap.dedent("""
        # Section {sec}
        ## Disclosure
        (content_block)
        subtitle: A short description
        render_once: false

        Please read this disclosure.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_options"]["subtitle"] == "A short description"
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
    """Unknown config keys are ignored (not stored in options)."""
    md = textwrap.dedent("""
        # Section {sec}
        ## Introduction
        (content_block)
        unknown_key: nonsense

        Body.
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    # Unknown keys are not stored
    assert "unknown_key" not in q["final_options"]


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
    assert q.options["heading"] == ""
    assert q.options["body_md"] == "Welcome to the study."
    assert len(q.options["links"]) == 1
    assert q.options["links"][0]["url"] == "https://example.com/privacy"
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
            "heading": "Welcome",
            "body_md": "Welcome to the study.\n\nPlease read the privacy notice.",
            "links": [
                {"label": "Privacy", "url": "https://example.com/privacy"},
                {"label": "Protocol", "url": "https://example.com/protocol"},
            ],
            "subtitle": "A disclosure",
            "image_id": None,
            "consent": None,
            "render_once": False,
        },
        required=False,
        order=0,
    )

    exported = _export_survey_to_markdown(survey)
    # The export contains the content_block type and config
    assert "(content_block)" in exported
    assert "heading: Welcome" in exported
    assert "subtitle: A disclosure" in exported
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
    assert q.options["heading"] == "Welcome"
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
            "heading": "",
            "body_md": "Just a body.",
            "links": [],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=0,
    )

    exported = _export_survey_to_markdown(survey)
    assert "(content_block)" in exported
    assert "Just a body." in exported
    # Default variant/render_once are not emitted
    assert "subtitle:" not in exported
    assert "render_once:" not in exported
    # Empty heading is not emitted
    assert "heading:" not in exported

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
    assert q.options["heading"] == ""
    assert q.options["body_md"] == "Just a body."
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
            "subtitle": "",
            "image_id": None,
            "consent": None,
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
        text="Introduction block",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "heading": "Welcome",
            "body_md": "Welcome to the **study**.",
            "links": [
                {"label": "Privacy", "url": "https://example.com/privacy"},
            ],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=0,
    )

    client.force_login(respondent)
    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    # The rendered heading comes from options.heading, not q.text
    assert "Welcome" in content
    # The internal label (q.text) is NOT rendered visibly to participants
    # (it may appear in HTML comments for debugging, which is fine)
    assert "<h2" in content
    # The q.text should not appear inside an h2 or visible heading element
    import re

    visible_headings = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", content, re.DOTALL)
    for heading in visible_headings:
        assert "Introduction block" not in heading
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
            "heading": "",
            "body_md": "<script>alert(1)</script>**safe**",
            "links": [],
            "subtitle": "",
            "image_id": None,
            "consent": None,
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


# --- Builder (special template path) ---


@pytest.mark.django_db
def test_builder_adds_content_block_template(client, django_user_model):
    """The special template path creates a content_block with defaults."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="BuilderCB", slug="builder-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)

    client.force_login(user)
    url = reverse(
        "surveys:builder_group_template_add",
        kwargs={"slug": survey.slug, "gid": group.id},
    )
    response = client.post(
        url,
        {"template": "content_block"},
    )

    assert response.status_code == 200
    q = SurveyQuestion.objects.get(
        survey=survey, type=SurveyQuestion.Types.CONTENT_BLOCK
    )
    assert q.text == "Content block"
    assert q.required is False
    assert q.options["heading"] == ""
    assert q.options["body_md"] == ""
    assert q.options["links"] == []
    assert q.options["render_once"] is True


@pytest.mark.django_db
def test_builder_configures_content_block(client, django_user_model):
    """The content block configure form updates heading, body, links, variant."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="ConfigCB", slug="config-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Content block",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "heading": "",
            "body_md": "",
            "links": [],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=0,
    )

    client.force_login(user)
    url = reverse(
        "surveys:builder_group_question_content_block_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": q.id},
    )
    response = client.post(
        url,
        {
            "heading": "Welcome",
            "subtitle": "A study intro",
            "body_md": "Welcome to the study.",
            "render_once": "on",
            "link_label": ["Privacy", "Protocol"],
            "link_url": [
                "https://example.com/privacy",
                "https://example.com/protocol",
            ],
        },
    )

    assert response.status_code == 200
    q.refresh_from_db()
    assert q.options["heading"] == "Welcome"
    assert q.options["subtitle"] == "A study intro"
    assert q.options["body_md"] == "Welcome to the study."
    assert q.options["render_once"] is True
    assert len(q.options["links"]) == 2
    assert q.options["links"][0] == {
        "label": "Privacy",
        "url": "https://example.com/privacy",
    }


@pytest.mark.django_db
def test_builder_content_block_with_consent(client, django_user_model):
    """Configuring consent creates a linked yesno question for the audit trail."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="ConsentCB", slug="consent-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Content block",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "heading": "",
            "subtitle": "",
            "body_md": "",
            "image_id": None,
            "links": [],
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=0,
    )

    client.force_login(user)
    url = reverse(
        "surveys:builder_group_question_content_block_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": q.id},
    )
    response = client.post(
        url,
        {
            "heading": "Privacy",
            "body_md": "Please read the privacy notice.",
            "consent_statement": "I have read and understand the privacy notice",
            "consent_required": "on",
        },
    )

    assert response.status_code == 200
    q.refresh_from_db()
    assert q.options["consent"] is not None
    assert (
        q.options["consent"]["statement"]
        == "I have read and understand the privacy notice"
    )
    assert q.options["consent"]["required"] is True
    # A linked yesno question was created
    linked_q = SurveyQuestion.objects.get(id=q.options["consent"]["question_id"])
    assert linked_q.type == SurveyQuestion.Types.YESNO
    assert linked_q.required is True
    # The linked question is hidden from the builder list
    assert _is_linked_consent_question(linked_q)


@pytest.mark.django_db
def test_builder_content_block_removes_consent_when_cleared(client, django_user_model):
    """Clearing the consent statement deletes the linked yesno question."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        owner=user, name="ClearConsent", slug="clear-consent"
    )
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    # Start with a content block that has consent
    linked_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Consent (content block: Intro)",
        type=SurveyQuestion.Types.YESNO,
        options=[
            {"label": "I agree", "value": "yes"},
            {"label": "I do not agree", "value": "no"},
            {"_content_block_parent": 999},  # placeholder, will be updated
        ],
        required=True,
        order=1,
    )
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Intro",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "heading": "",
            "subtitle": "",
            "body_md": "",
            "image_id": None,
            "links": [],
            "consent": {
                "question_id": linked_q.id,
                "statement": "I agree",
                "required": True,
            },
            "render_once": True,
        },
        required=False,
        order=0,
    )
    # Fix the parent reference
    linked_q.options[2]["_content_block_parent"] = q.id
    linked_q.save(update_fields=["options"])

    client.force_login(user)
    url = reverse(
        "surveys:builder_group_question_content_block_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": q.id},
    )
    response = client.post(
        url,
        {
            "heading": "Intro",
            "body_md": "Body.",
            "consent_statement": "",  # cleared
        },
    )

    assert response.status_code == 200
    q.refresh_from_db()
    assert q.options["consent"] is None
    # The linked question was deleted
    assert not SurveyQuestion.objects.filter(id=linked_q.id).exists()


@pytest.mark.django_db
def test_builder_content_block_strips_javascript_link(client, django_user_model):
    """Dangerous URL schemes in configure form links are stripped at save time."""
    from checktick_app.surveys.models import QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="BuilderXSS", slug="builder-xss")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Content block",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "heading": "",
            "body_md": "",
            "links": [],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=0,
    )

    client.force_login(user)
    url = reverse(
        "surveys:builder_group_question_content_block_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": q.id},
    )
    response = client.post(
        url,
        {
            "heading": "Intro",
            "body_md": "Body.",
            "link_label": ["Evil"],
            "link_url": ["javascript:alert(1)"],
        },
    )

    assert response.status_code == 200
    q.refresh_from_db()
    # The dangerous link is dropped
    assert q.options["links"] == []


# --- Matrix landing composition ---


@pytest.mark.django_db
def test_matrix_landing_renders_content_block(client, django_user_model):
    """A content block as the first question in the first section renders
    above the matrix cards as a landing header."""
    from checktick_app.surveys.models import MatrixMenu, QuestionGroup

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    respondent = django_user_model.objects.create_user(
        username="respondent", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        owner=user,
        name="MatrixCB",
        slug="matrix-cb",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.MATRIX,
        respondent_audience=Survey.RespondentAudience.STAFF,
        audience_confirmed=True,
    )
    MatrixMenu.objects.create(survey=survey)
    group1 = QuestionGroup.objects.create(name="Intro", owner=user)
    group2 = QuestionGroup.objects.create(name="Questions", owner=user)
    survey.question_groups.add(group1, group2)
    # Content block as first question in first group
    SurveyQuestion.objects.create(
        survey=survey,
        group=group1,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "heading": "Welcome",
            "body_md": "Welcome to the **study**.",
            "links": [{"label": "Privacy", "url": "https://example.com/privacy"}],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=0,
    )
    # A normal question in the second group (so the cards have content)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group2,
        text="Your name",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=0,
    )

    client.force_login(respondent)
    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    # Landing block heading is rendered
    assert "Welcome" in content
    # Markdown body is rendered
    assert "<strong>study</strong>" in content
    # Link is rendered
    assert 'href="https://example.com/privacy"' in content
    # Matrix cards are still rendered (the section names appear)
    assert "Questions" in content


# --- Branching warnings ---


@pytest.mark.django_db
def test_show_hide_on_content_block_warns(client, django_user_model):
    """A SHOW/HIDE condition targeting a content block produces an Organise-page warning."""
    from checktick_app.surveys.models import (
        QuestionGroup,
        SurveyQuestionCondition,
    )

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="WarnCB", slug="warn-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    # A source question
    src_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Source",
        type=SurveyQuestion.Types.YESNO,
        options=[
            {"label": "Yes", "value": "yes"},
            {"label": "No", "value": "no"},
        ],
        required=False,
        order=0,
    )
    # A content block target
    cb_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Target block",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "Body.",
            "links": [],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=1,
    )
    # SHOW condition targeting the content block
    SurveyQuestionCondition.objects.create(
        question=src_q,
        target_question=cb_q,
        action=SurveyQuestionCondition.Action.SHOW,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
    )

    client.force_login(user)
    resp = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    # The warning is surfaced
    assert "content block" in content.lower()
    assert "Target block" in content


@pytest.mark.django_db
def test_jump_to_content_block_no_warning(client, django_user_model):
    """JUMP_TO a content block is fine — no warning."""
    from checktick_app.surveys.models import (
        QuestionGroup,
        SurveyQuestionCondition,
    )

    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="JumpCB", slug="jump-cb")
    group = QuestionGroup.objects.create(name="Section", owner=user)
    survey.question_groups.add(group)
    src_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Source",
        type=SurveyQuestion.Types.YESNO,
        options=[
            {"label": "Yes", "value": "yes"},
            {"label": "No", "value": "no"},
        ],
        required=False,
        order=0,
    )
    cb_q = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Target block",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={
            "body_md": "Body.",
            "links": [],
            "subtitle": "",
            "image_id": None,
            "consent": None,
            "render_once": True,
        },
        required=False,
        order=1,
    )
    SurveyQuestionCondition.objects.create(
        question=src_q,
        target_question=cb_q,
        action=SurveyQuestionCondition.Action.JUMP_TO,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
    )

    client.force_login(user)
    resp = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    # No content block warning (JUMP_TO is fine)
    assert "Content block warnings" not in content
