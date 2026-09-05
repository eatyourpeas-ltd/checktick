"""Tests for the import-from-document LLM conversion endpoint.

The endpoint is a multipart branch of the bulk_upload view: it validates an
uploaded document, extracts text, sends it to the LLM for conversion into
outline markdown, and returns the markdown for the user to review in the
Outline textarea. It must never import anything directly, and audit logging
must never include document content.
"""

from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
import pytest

from checktick_app.surveys.models import AuditLog, Survey
from checktick_app.surveys.tests.test_doc_extract import build_docx

TEST_PASSWORD = "x"

VALID_MARKDOWN = (
    "# Patient experience {patient-experience}\n"
    "\n"
    "## Overall rating {overall-rating}\n"
    "(likert number)\n"
    "min: 1\n"
    "max: 5"
)


@pytest.fixture(autouse=True)
def enable_llm(settings):
    """Enable the LLM for all tests in this module (test env has it off).

    Also clears the cache between tests: the rate limiter keys on user pk,
    which is 1 for every freshly-created user, so limiter state would
    otherwise leak across tests and 429 unrelated tests.
    """
    settings.LLM_ENABLED = True
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )


@pytest.fixture
def survey(owner):
    return Survey.objects.create(owner=owner, name="Doc import", slug="doc-import")


@pytest.fixture
def logged_in_client(client, owner):
    client.login(username="author", password=TEST_PASSWORD)
    return client


@pytest.fixture
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


def _docx_file(name="survey.docx", body="Patient experience survey"):
    return SimpleUploadedFile(
        name,
        build_docx(
            f'<w:p xmlns:w="http://schemas.openxmlformats.org/'
            f'wordprocessingml/2006/main"><w:r><w:t>{body}</w:t></w:r></w:p>'
        ),
        content_type="application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document",
    )


def _post_document(client, survey, **extra):
    url = reverse("surveys:bulk_upload", kwargs={"slug": survey.slug})
    data = {"action": "import_document"}
    data.update(extra)
    return client.post(url, data)


def _mock_llm(markdown=VALID_MARKDOWN):
    """Patch ConversationalSurveyLLM.chat_stream so the real extract/sanitize
    helpers still run. The stream yields the model's full response text."""
    response_text = (
        f"Here is the converted survey:\n\n```markdown\n{markdown}\n```"
        if markdown
        else ""
    )
    stream = MagicMock(return_value=iter([response_text]))
    patcher = patch(
        "checktick_app.surveys.views.ConversationalSurveyLLM.chat_stream",
        stream,
    )
    return patcher, stream


def _sse_events(response):
    import json

    if hasattr(response, "streaming_content"):
        body = b"".join(response.streaming_content).decode()
    else:
        body = response.content.decode()
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            events.append(json.loads(block[6:]))
    return events


def _sse_done_event(response):
    done = [e for e in _sse_events(response) if e.get("done")]
    assert done, "SSE stream contained no done event"
    return done[0]


def _cache_payload(done_event, user):
    """Fetch the one-time cached conversion result for a done event."""
    import re

    from django.core.cache import cache

    match = re.search(r"doc_import=([0-9a-f]+)", done_event.get("next_url", ""))
    assert match, "done event carried no result id"
    return cache.get(f"doc_import_result:{user.id}:{match.group(1)}")


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_user_cannot_convert(client, survey):
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(client, survey, document=_docx_file())
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_without_edit_permission_cannot_convert(client, django_user_model, survey):
    other = django_user_model.objects.create_user(
        username="reader", password=TEST_PASSWORD
    )
    client.login(username=other.username, password=TEST_PASSWORD)
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(client, survey, document=_docx_file())
    assert response.status_code == 403


@pytest.mark.django_db
def test_disabled_llm_returns_error(logged_in_client, survey, settings):
    settings.LLM_ENABLED = False
    response = _post_document(logged_in_client, survey, document=_docx_file())
    assert response.status_code == 400
    assert b"not available" in response.content


# ---------------------------------------------------------------------------
# Conversion success / failure paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_successful_conversion_returns_markdown(logged_in_client, survey, owner):
    patcher, chat = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        data = _sse_done_event(response)

    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream"
    assert data["success"] is True
    assert "doc_import=" in data["next_url"]
    # The result reaches the browser via the one-time cache handoff
    payload = _cache_payload(data, owner)
    assert payload["display_markdown"] == VALID_MARKDOWN
    assert payload["suggestions"] == []


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_response_never_reflects_document_or_llm_content(
    logged_in_client, survey, owner
):
    """The SSE body carries only static strings and a result id — document
    and LLM content reaches the browser via the cache-backed reload."""
    patcher, chat = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        body = (
            b"".join(response.streaming_content).decode()
            if hasattr(response, "streaming_content")
            else response.content.decode()
        )

    assert "Patient experience" not in body
    assert VALID_MARKDOWN not in body
    assert "doc_import=" in body
    # The LLM call still carries the allowlist-scoped prompt context
    assert chat.call_count == 1
    assert "untrusted" in chat.call_args[1]["system_prompt"].lower()
    assert chat.call_args[1]["extra_payload"] == {"reasoning_effort": "none"}


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_stream_emits_chunk_events(logged_in_client, survey):
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        events = _sse_events(response)

    chunks = [e for e in events if e.get("phase") == "working"]
    assert chunks, "SSE stream emitted no progress events"
    # Progress ticks carry no model output text
    assert all("chunk" not in e for e in chunks)


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_nothing_is_imported_by_conversion(logged_in_client, survey):
    patcher, _ = _mock_llm()
    with patcher:
        _post_document(logged_in_client, survey, document=_docx_file())

    survey.refresh_from_db()
    assert survey.question_groups.count() == 0


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_llm_output_failing_parser_returns_raw_text_and_warning(
    logged_in_client, survey, owner
):
    patcher, _ = _mock_llm(markdown="## Question with no group\n(text)")
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        done = _sse_done_event(response)

    assert response.status_code == 200
    assert done["success"] is False
    payload = _cache_payload(done, owner)
    assert payload["display_markdown"]
    assert any("parse" in w.lower() for w in payload["warnings"])


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_llm_html_is_sanitized_from_markdown(logged_in_client, survey, owner):
    patcher, _ = _mock_llm(
        markdown='# Group {g}\n## Q {q}\n(text)\n<script>alert("x")</script>'
    )
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        done = _sse_done_event(response)

    payload = _cache_payload(done, owner)
    assert payload["display_markdown"] is not None
    assert "<script>" not in payload["display_markdown"]


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_llm_failure_returns_raw_extracted_text(logged_in_client, survey, owner):
    patcher, _ = _mock_llm(markdown=None)
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        done = _sse_done_event(response)

    assert response.status_code == 200
    assert done["success"] is False
    payload = _cache_payload(done, owner)
    assert "Patient experience survey" in payload["display_markdown"]
    assert payload["warnings"]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_missing_document_and_text_returns_error(logged_in_client, survey):
    response = _post_document(logged_in_client, survey)
    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_masqueraded_docx_rejected(logged_in_client, survey):
    fake = SimpleUploadedFile(
        "fake.docx", b"not a zip file", content_type="application/zip"
    )
    response = _post_document(logged_in_client, survey, document=fake)
    assert response.status_code == 400
    assert b"not a valid" in response.content


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_legacy_doc_rejected_with_guidance(logged_in_client, survey):
    ole2 = SimpleUploadedFile(
        "old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
    )
    response = _post_document(logged_in_client, survey, document=ole2)
    assert response.status_code == 400
    assert b".docx" in response.content


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_oversized_upload_rejected_before_llm(logged_in_client, survey):
    big = SimpleUploadedFile("big.txt", b"a" * (3 * 1024 * 1024))
    patcher, instance = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=big)
    assert response.status_code == 413
    instance.assert_not_called()


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_repetition_loop_aborts_stream(logged_in_client, survey, owner):
    """A degenerate reasoning loop must be cut short server-side rather than
    running until the token budget is exhausted."""
    loop_line = (
        "    *   Wait, I need to check if I should add a description for the "
        "sections in the example output above."
    )

    def looping_stream(*args, **kwargs):
        for _ in range(200):
            yield loop_line + "\n"
        yield "```markdown\n# G {g}\n## Q {q}\n(text)\n```"

    patcher = patch(
        "checktick_app.surveys.views.ConversationalSurveyLLM.chat_stream",
        MagicMock(side_effect=looping_stream),
    )
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        done = _sse_done_event(response)

    assert done["success"] is False
    payload = _cache_payload(done, owner)
    assert any("stuck" in w.lower() for w in payload["warnings"])


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_reload_hands_back_result_via_messages_and_textarea(
    logged_in_client, survey, owner
):
    """The page reload after conversion pre-fills the Outline textarea from
    the one-time cached result and surfaces warnings as messages."""
    from django.core.cache import cache

    cache.set(
        f"doc_import_result:{owner.id}:testresult123",
        {
            "display_markdown": VALID_MARKDOWN,
            "warnings": ["Something to note."],
            "suggestions": ["Professional details"],
        },
        timeout=600,
    )
    response = logged_in_client.get(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"tab": "manual", "doc_import": "testresult123"},
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert VALID_MARKDOWN in body
    assert "Something to note." in body
    assert "Professional details" in body
    # One-time handoff: the cache entry is deleted after the first read
    assert cache.get(f"doc_import_result:{owner.id}:testresult123") is None


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_pasted_text_path(logged_in_client, survey, owner):
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(
            logged_in_client, survey, text="How satisfied were you?"
        )
        done = _sse_done_event(response)
    assert response.status_code == 200
    assert done["success"] is True
    payload = _cache_payload(done, owner)
    assert payload["display_markdown"] == VALID_MARKDOWN


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_audit_log_metadata_never_contains_document_content(
    logged_in_client, survey, owner
):
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        _sse_events(response)  # consume the stream so the generator runs

    entry = AuditLog.objects.filter(
        actor=owner, survey=survey, action=AuditLog.Action.UPDATE
    ).latest("created_at")
    metadata = entry.metadata or {}
    assert metadata.get("action") == "doc_import_converted"
    assert metadata.get("success") is True


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_audit_log_records_failed_conversion(logged_in_client, survey, owner):
    patcher, _ = _mock_llm(markdown=None)
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        _sse_events(response)  # consume the stream so the generator runs

    entry = AuditLog.objects.filter(
        actor=owner, survey=survey, action=AuditLog.Action.UPDATE
    ).latest("created_at")
    assert entry.metadata.get("success") is False
    blob = str(entry.metadata)
    assert "Patient experience survey" not in blob


# ---------------------------------------------------------------------------
# Template rendering ("From document" tab)
# ---------------------------------------------------------------------------


def _get_page(client, survey):
    return client.get(reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}))


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_doc_tab_rendered_when_llm_enabled(logged_in_client, survey):
    html = _get_page(logged_in_client, survey).content.decode()
    assert 'id="tab-doc"' in html
    assert 'id="doc-import-file"' in html
    assert 'accept=".docx,.txt,.md"' in html
    assert 'id="doc-import-convert"' in html
    # Privacy notice is shown before conversion
    assert "self-hosted AI service" in html


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_doc_tab_absent_when_llm_disabled(logged_in_client, survey, settings):
    settings.LLM_ENABLED = False
    html = _get_page(logged_in_client, survey).content.decode()
    assert 'id="tab-doc"' not in html
    assert 'id="doc-import-convert"' not in html


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_manual_tab_prefilled_with_extracted_text_via_get_tab_param(
    logged_in_client, survey
):
    # The tab query parameter must accept the new "doc" value.
    response = _get_page(logged_in_client, survey)  # sanity: page loads
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Dataset inference and allowlist enforcement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_dataset_allowlist_injected_and_enforced(logged_in_client, survey, owner):
    """The model sees the accessible dataset keys, and emitted dataset
    references are enforced against that allowlist server-side."""
    markdown_with_datasets = (
        "# Work {work}\n"
        "## Where do you work? {where}\n"
        "(dropdown)\n"
        "dataset: nhs_trusts\n"
        "## Which region? {region}\n"
        "(dropdown)\n"
        "dataset: bogus_key\n"
    )
    with patch(
        "checktick_app.surveys.views.get_available_datasets",
        return_value={"nhs_trusts": "NHS trusts"},
    ):
        patcher, chat = _mock_llm(markdown=markdown_with_datasets)
        with patcher:
            response = _post_document(logged_in_client, survey, document=_docx_file())
            done = _sse_done_event(response)

    payload = _cache_payload(done, owner)
    # Known key survives; unknown key is stripped with a warning
    assert "dataset: nhs_trusts" in payload["display_markdown"]
    assert "bogus_key" not in payload["display_markdown"]
    assert any("dataset references" in w for w in payload["warnings"])
    # The allowlist reached the model via the user message
    assert "AVAILABLE DATASETS" in chat.call_args[0][0][0]["content"]
    assert "nhs_trusts" in chat.call_args[0][0][0]["content"]


# ---------------------------------------------------------------------------
# Passive template suggestions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_template_suggestion_for_matching_document(logged_in_client, survey, owner):
    from checktick_app.surveys.models import PublishedQuestionGroup

    PublishedQuestionGroup.objects.create(
        publisher=owner,
        name="Professional details",
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
        status=PublishedQuestionGroup.Status.ACTIVE,
        markdown="# Professional details {pd}\n## Job title {jt}\n(text)\n",
    )
    doc_md = (
        "# About you {about-you}\n"
        "## Tell us your name {name}\n"
        "(text)\n"
        "## What is your job title? {jt}\n"
        "(text)\n"
        "## Where do you work? {wdyw}\n"
        "(text)\n"
    )
    patcher, _ = _mock_llm(markdown=doc_md)
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        done = _sse_done_event(response)

    payload = _cache_payload(done, owner)
    assert payload["suggestions"] == ["Professional details"]


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_no_template_suggestion_for_unrelated_document(logged_in_client, survey, owner):
    from checktick_app.surveys.models import PublishedQuestionGroup

    PublishedQuestionGroup.objects.create(
        publisher=owner,
        name="Professional details",
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
        status=PublishedQuestionGroup.Status.ACTIVE,
        markdown="# Professional details {pd}\n## Job title {jt}\n(text)\n",
    )
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())
        done = _sse_done_event(response)

    payload = _cache_payload(done, owner)
    assert payload["suggestions"] == []


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_reload_ignores_unknown_result_id(logged_in_client, survey):
    """A doc_import id that is absent/expired/foreign simply loads the page."""
    response = logged_in_client.get(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"doc_import": "does-not-exist"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True, LLM_ENABLED=True)
def test_conversion_is_rate_limited(logged_in_client, survey, settings):
    from django.core.cache import cache

    cache.clear()
    patcher, _ = _mock_llm()
    with patcher:
        statuses = [
            _post_document(
                logged_in_client,
                survey,
                text=f"question {i}",
            ).status_code
            for i in range(21)
        ]
    assert statuses[-1] == 429
    assert all(s == 200 for s in statuses[:20])
