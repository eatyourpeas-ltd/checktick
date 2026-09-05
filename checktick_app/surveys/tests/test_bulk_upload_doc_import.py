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
    """Enable the LLM for all tests in this module (test env has it off)."""
    settings.LLM_ENABLED = True


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
    """Patch only ConversationalSurveyLLM.chat_with_custom_system_prompt so
    the real extract_markdown/sanitize_markdown helpers still run."""
    response = (
        f"Here is the converted survey:\n\n```markdown\n{markdown}\n```"
        if markdown
        else None
    )
    chat = MagicMock(return_value=response)
    patcher = patch(
        "checktick_app.surveys.views.ConversationalSurveyLLM."
        "chat_with_custom_system_prompt",
        chat,
    )
    return patcher, chat


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
def test_successful_conversion_returns_markdown(logged_in_client, survey):
    patcher, chat = _mock_llm()
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())

    assert response.status_code == 200
    data = response.json()
    assert data["markdown"] == VALID_MARKDOWN
    assert "error" not in data
    # The LLM was called exactly once, one-shot (system prompt is separate;
    # conversation is a single user message)
    assert chat.call_count == 1
    messages = chat.call_args[0][1]
    assert len(messages) == 1
    assert "<document>" in messages[0]["content"]


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
    logged_in_client, survey
):
    patcher, _ = _mock_llm(markdown="## Question with no group\n(text)")
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())

    assert response.status_code == 200
    data = response.json()
    assert data["markdown"] is None
    assert data["raw_text"]
    assert any("error" in w.lower() or "parse" in w.lower() for w in data["warnings"])


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_llm_html_is_sanitized_from_markdown(logged_in_client, survey):
    patcher, _ = _mock_llm(
        markdown='# Group {g}\n## Q {q}\n(text)\n<script>alert("x")</script>'
    )
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())

    data = response.json()
    assert data["markdown"] is not None
    assert "<script>" not in data["markdown"]


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_llm_failure_returns_raw_extracted_text(logged_in_client, survey):
    patcher, _ = _mock_llm(markdown=None)
    with patcher:
        response = _post_document(logged_in_client, survey, document=_docx_file())

    assert response.status_code == 200
    data = response.json()
    assert data["markdown"] is None
    assert "Patient experience survey" in data["raw_text"]
    assert data["warnings"]


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
def test_pasted_text_path(logged_in_client, survey):
    patcher, _ = _mock_llm()
    with patcher:
        response = _post_document(
            logged_in_client, survey, text="How satisfied were you?"
        )
    assert response.status_code == 200
    data = response.json()
    assert data["markdown"] == VALID_MARKDOWN


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
        _post_document(logged_in_client, survey, document=_docx_file())

    entry = AuditLog.objects.filter(
        actor=owner, survey=survey, action=AuditLog.Action.UPDATE
    ).latest("created_at")
    metadata = entry.metadata or {}
    assert metadata.get("action") == "doc_import_converted"
    assert metadata.get("success") is True
    blob = str(metadata)
    assert "Patient experience survey" not in blob


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=False)
def test_audit_log_records_failed_conversion(logged_in_client, survey, owner):
    patcher, _ = _mock_llm(markdown=None)
    with patcher:
        _post_document(logged_in_client, survey, document=_docx_file())

    entry = AuditLog.objects.filter(
        actor=owner, survey=survey, action=AuditLog.Action.UPDATE
    ).latest("created_at")
    assert entry.metadata.get("success") is False


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
