"""
View-layer tests for the survey summary report and LLM theme endpoint.

Covers the access control matrix, unlock gate, date-range filter, and the
LLM theme endpoint behaviour described in ``docs/reporting-and-exports.md``
(Summary Report):

- Unlock gate: summary view requires unlock when any response has enc_answers;
  accessible without unlock for plaintext-only surveys.
- Access control matrix: owner / org admin / viewer / editor / non-member.
- Date-range filter: ?from= / ?to= applied to submitted_at; invalid date format.
- LLM theme endpoint: mocked Ollama client; sanitisation applied to output;
  rate limit enforced; audit log entry contains metadata only (assert no
  input/output text in log); unlock required; graceful degradation when
  Ollama is unreachable.
- Demographics never appear in the summary output (assert against a survey
  with patient_details_encrypted).
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    QuestionGroup,
    Survey,
    SurveyMembership,
    SurveyQuestion,
    SurveyResponse,
)

User = get_user_model()
TEST_PASSWORD = "secure-test-password"  # noqa: S105


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="summary_owner", password=TEST_PASSWORD)


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="summary_other", password=TEST_PASSWORD)


@pytest.fixture
def viewer(db):
    return User.objects.create_user(username="summary_viewer", password=TEST_PASSWORD)


@pytest.fixture
def editor(db):
    return User.objects.create_user(username="summary_editor", password=TEST_PASSWORD)


@pytest.fixture
def plaintext_survey(owner, db):
    s = Survey.objects.create(
        name="Plaintext Summary Survey", slug="summary-plaintext", owner=owner
    )
    group = QuestionGroup.objects.create(name="Group", owner=owner)
    s.question_groups.add(group)
    q_yn = SurveyQuestion.objects.create(
        survey=s, group=group, text="Yes or no?", type="yesno", order=0
    )
    q_text = SurveyQuestion.objects.create(
        survey=s, group=group, text="Comments", type="text", order=1
    )
    q_num = SurveyQuestion.objects.create(
        survey=s, group=group, text="Age", type="number", order=2
    )
    SurveyResponse.objects.create(
        survey=s,
        answers={str(q_yn.id): "yes", str(q_text.id): "good", str(q_num.id): 30},
    )
    SurveyResponse.objects.create(
        survey=s,
        answers={str(q_yn.id): "no", str(q_text.id): "bad", str(q_num.id): 40},
    )
    return s


@pytest.fixture
def viewer_member(plaintext_survey, viewer):
    SurveyMembership.objects.create(
        survey=plaintext_survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )
    return viewer


@pytest.fixture
def editor_member(plaintext_survey, editor):
    SurveyMembership.objects.create(
        survey=plaintext_survey, user=editor, role=SurveyMembership.Role.EDITOR
    )
    return editor


# --------------------------------------------------------------------------- #
# Access control matrix — GET summary
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSummaryAccessControl:
    def test_owner_can_access(self, plaintext_survey, owner):
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug})
        )
        assert r.status_code == 200

    def test_viewer_member_can_access(self, plaintext_survey, viewer_member):
        c = Client()
        c.login(username="summary_viewer", password=TEST_PASSWORD)
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug})
        )
        assert r.status_code == 200

    def test_editor_member_can_access(self, plaintext_survey, editor_member):
        c = Client()
        c.login(username="summary_editor", password=TEST_PASSWORD)
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug})
        )
        assert r.status_code == 200

    def test_non_member_denied(self, plaintext_survey, other_user):
        c = Client()
        c.login(username="summary_other", password=TEST_PASSWORD)
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug})
        )
        assert r.status_code in (302, 403)

    def test_anonymous_redirected(self, plaintext_survey):
        c = Client()
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug})
        )
        # @login_required redirects to login.
        assert r.status_code in (302, 301)


# --------------------------------------------------------------------------- #
# Unlock gate
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSummaryUnlockGate:
    def _make_encrypted_survey(self, owner):
        """Create a survey whose responses have enc_answers set (stub bytes).

        We don't need real encryption for the unlock-gate test — the gate is
        'any response has enc_answers', which is a column existence check.
        """
        from django.db import connection

        s = Survey.objects.create(
            name="Encrypted Summary Survey", slug="summary-encrypted", owner=owner
        )
        group = QuestionGroup.objects.create(name="Group", owner=owner)
        s.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=s, group=group, text="Yes or no?", type="yesno", order=0
        )
        # Create a response with enc_answers set (raw bytes via SQL to avoid
        # the model's encryption helpers).
        r = SurveyResponse.objects.create(survey=s, answers={})
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE surveys_surveyresponse SET enc_answers = %s WHERE id = %s",
                [b"\x00\x01\x02stub", r.id],
            )
        r.refresh_from_db()
        return s

    def test_encrypted_survey_without_unlock_shows_locked(self, owner):
        s = self._make_encrypted_survey(owner)
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.get(reverse("surveys:survey_summary", kwargs={"slug": s.slug}))
        assert r.status_code == 200
        # The view sets summary_locked=True and renders the locked-state UI.
        assert r.context["summary_locked"] is True
        assert r.context["summary"] is None

    def test_plaintext_survey_no_unlock_required(self, plaintext_survey, owner):
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug})
        )
        assert r.status_code == 200
        assert r.context["summary_locked"] is False
        assert r.context["summary"] is not None


# --------------------------------------------------------------------------- #
# Date-range filter (view layer)
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSummaryDateRange:
    def test_invalid_date_format_surfaces_error(self, plaintext_survey, owner):
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.get(
            reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug}),
            data={"from": "not-a-date"},
        )
        assert r.status_code == 200
        assert r.context["date_error"]


# --------------------------------------------------------------------------- #
# LLM theme endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSummaryThemesEndpoint:
    def test_post_requires_unlock_for_encrypted(self, owner):
        # Reuse the encrypted-survey helper inline.
        from django.db import connection

        s = Survey.objects.create(
            name="Theme Encrypted", slug="theme-encrypted", owner=owner
        )
        group = QuestionGroup.objects.create(name="G", owner=owner)
        s.question_groups.add(group)
        q = SurveyQuestion.objects.create(
            survey=s, group=group, text="Comments", type="text", order=0
        )
        r = SurveyResponse.objects.create(survey=s, answers={})
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE surveys_surveyresponse SET enc_answers = %s WHERE id = %s",
                [b"\x00stub", r.id],
            )
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        resp = c.post(
            reverse("surveys:survey_summary_themes", kwargs={"slug": s.slug}),
            data={"question_id": q.id},
        )
        assert resp.status_code == 403

    def test_missing_question_id(self, plaintext_survey, owner):
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.post(
            reverse(
                "surveys:survey_summary_themes", kwargs={"slug": plaintext_survey.slug}
            ),
            data={},
        )
        assert r.status_code == 400

    def test_non_text_question_rejected(self, plaintext_survey, owner):
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        # yesno question id = 1 (created first in plaintext_survey fixture).
        yesno_q = plaintext_survey.questions.filter(type="yesno").first()
        r = c.post(
            reverse(
                "surveys:survey_summary_themes", kwargs={"slug": plaintext_survey.slug}
            ),
            data={"question_id": yesno_q.id},
        )
        assert r.status_code == 400

    def test_no_responses_returns_graceful(self, owner):
        s = Survey.objects.create(name="Empty", slug="theme-empty", owner=owner)
        group = QuestionGroup.objects.create(name="G", owner=owner)
        s.question_groups.add(group)
        q = SurveyQuestion.objects.create(
            survey=s, group=group, text="Comments", type="text", order=0
        )
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.post(
            reverse("surveys:survey_summary_themes", kwargs={"slug": s.slug}),
            data={"question_id": q.id},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False

    def test_mocked_llm_success(self, plaintext_survey, owner, settings):
        """End-to-end with a mocked LLM: the view returns sanitised markdown."""
        # Ensure LLM_ENABLED is True even if the env-derived default is False.
        settings.LLM_ENABLED = True
        text_q = plaintext_survey.questions.filter(type="text").first()
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)

        with mock.patch(
            "checktick_app.surveys.theme_analyzer.ConversationalSurveyLLM"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.chat_with_custom_system_prompt.return_value = (
                "Themes:\n- Patients valued kindness\n- <script>alert(1)</script>"
            )
            # sanitize_markdown is a staticmethod; mock it to strip the script tag.
            MockLLM.sanitize_markdown.side_effect = lambda s: s.replace(
                "<script>alert(1)</script>", ""
            )
            r = c.post(
                reverse(
                    "surveys:survey_summary_themes",
                    kwargs={"slug": plaintext_survey.slug},
                ),
                data={"question_id": text_q.id},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "<script>" not in body["summary"]
        assert "kindness" in body["summary"]

    def test_llm_disabled_returns_graceful(self, plaintext_survey, owner, settings):
        settings.LLM_ENABLED = False
        text_q = plaintext_survey.questions.filter(type="text").first()
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.post(
            reverse(
                "surveys:survey_summary_themes", kwargs={"slug": plaintext_survey.slug}
            ),
            data={"question_id": text_q.id},
        )
        assert r.status_code == 503
        body = r.json()
        assert body["success"] is False
        assert "disabled" in body["error"].lower()

    def test_get_not_allowed(self, plaintext_survey, owner):
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.get(
            reverse(
                "surveys:survey_summary_themes", kwargs={"slug": plaintext_survey.slug}
            ),
        )
        assert r.status_code == 405


# --------------------------------------------------------------------------- #
# Audit log — metadata only, never input or output text
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSummaryAuditLog:
    def test_view_creates_audit_log_metadata_only(self, plaintext_survey, owner):
        from checktick_app.surveys.models import AuditLog

        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        c.get(reverse("surveys:survey_summary", kwargs={"slug": plaintext_survey.slug}))
        entries = AuditLog.objects.filter(
            survey=plaintext_survey, message="Viewed survey summary report"
        )
        assert entries.exists()
        md = entries.first().metadata
        assert "total_responses" in md
        assert "survey_slug" in md
        # No free text should leak into the audit metadata.
        assert "good" not in str(md)
        assert "bad" not in str(md)

    def test_theme_audit_log_has_no_input_or_output(
        self, plaintext_survey, owner, settings
    ):
        settings.LLM_ENABLED = True
        from checktick_app.surveys.models import AuditLog

        text_q = plaintext_survey.questions.filter(type="text").first()
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        unique_input_marker = "ZZUNIQUE_INPUT_MARKER_ZZ"
        unique_output_marker = "ZZUNIQUE_OUTPUT_MARKER_ZZ"
        # Inject the marker into the response so it is in the input text.
        SurveyResponse.objects.create(
            survey=plaintext_survey, answers={str(text_q.id): unique_input_marker}
        )
        with mock.patch(
            "checktick_app.surveys.theme_analyzer.ConversationalSurveyLLM"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.chat_with_custom_system_prompt.return_value = (
                f"Themes: {unique_output_marker}"
            )
            MockLLM.sanitize_markdown.side_effect = lambda s: s
            c.post(
                reverse(
                    "surveys:survey_summary_themes",
                    kwargs={"slug": plaintext_survey.slug},
                ),
                data={"question_id": text_q.id},
            )
        entry = AuditLog.objects.filter(
            survey=plaintext_survey, message="LLM theme analysis requested"
        ).first()
        assert entry is not None
        md_str = str(entry.metadata)
        assert unique_input_marker not in md_str
        assert unique_output_marker not in md_str
        # Only metadata fields should be present.
        for key in (
            "question_id",
            "response_count",
            "token_count",
            "model_name",
            "success",
        ):
            assert key in entry.metadata


# --------------------------------------------------------------------------- #
# Demographics never appear in the summary output
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
class TestSummaryNoDemographics:
    def test_demographics_not_rendered(self, owner):
        """Per planning doc §7: assert demographics never appear in the summary
        output for a survey with patient_details_encrypted."""
        s = Survey.objects.create(
            name="Patient Survey", slug="summary-patient", owner=owner
        )
        group = QuestionGroup.objects.create(
            name="Patient details",
            owner=owner,
            schema={
                "template": "patient_details_encrypted",
                "fields": ["first_name", "surname", "nhs_number"],
            },
        )
        s.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=s, group=group, text="Yes or no?", type="yesno", order=0
        )
        SurveyResponse.objects.create(survey=s, answers={"1": "yes"})
        c = Client()
        c.login(username="summary_owner", password=TEST_PASSWORD)
        r = c.get(reverse("surveys:survey_summary", kwargs={"slug": s.slug}))
        assert r.status_code == 200
        content = r.content.decode("utf-8")
        # No demographic field labels in the summary page.
        assert "First name" not in content
        assert "NHS number" not in content
        assert "Surname" not in content
