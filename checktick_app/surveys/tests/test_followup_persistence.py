"""Tests for follow-up text questions.

Covers:
  - Builder creation of questions with a question-level follow-up toggle
    (single text box offered after all options, intended for dataset-backed
    dropdowns).
  - Builder payload serialization excludes the marker from the options list
    and exposes it as ``question_followup``.
  - Rendering: the marker is never rendered as an option; the question-level
    follow-up input is rendered with ``data-followup-any``.
  - Persistence: follow-up text (per-option, yes/no, and question-level) is
    stored alongside the question's answer on submission and drafts keep the
    legacy answer shape intact.
  - CSV export includes a follow-up column when configured.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)
from checktick_app.surveys.views import _serialize_question_for_builder

pytestmark = pytest.mark.django_db


TEST_PASSWORD = "testpass123"

QF_MARKER = {
    "type": "question_followup",
    "enabled": True,
    "label": "Please specify",
}


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


def _make_survey(owner, *, slug="followup-survey"):
    org = Organization.objects.create(name="Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="Follow-up Survey",
        slug=slug,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )


def _owner(username="fuowner"):
    return User.objects.create_user(username=username, password=TEST_PASSWORD)


def _respondent(username="furespondent"):
    return User.objects.create_user(username=username, password=TEST_PASSWORD)


# ---------------------------------------------------------------------------
# Builder creation
# ---------------------------------------------------------------------------


class TestQuestionFollowupCreation:
    def test_create_dropdown_with_question_followup(self, client):
        """The question-level toggle stores a marker entry in options."""
        owner = _owner()
        survey = _make_survey(owner)
        client.force_login(owner)

        resp = client.post(
            reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
            data={
                "text": "Select your specialty",
                "type": "dropdown",
                "options": "Cardiology\nRadiology\nNeurology",
                "question_followup": "on",
                "question_followup_label": "Other specialty not listed",
            },
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200

        q = SurveyQuestion.objects.get(survey=survey)
        assert q.options[-1] == {
            "type": "question_followup",
            "enabled": True,
            "label": "Other specialty not listed",
        }
        # Real options are untouched and come first.
        assert q.options[0]["label"] == "Cardiology"
        assert len(q.options) == 4

    def test_create_mc_single_question_followup_default_label(self, client):
        owner = _owner("fuowner2")
        survey = _make_survey(owner, slug="followup-survey-2")
        client.force_login(owner)

        resp = client.post(
            reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
            data={
                "text": "How did you hear about us?",
                "type": "mc_single",
                "options": "Friend\nSocial Media",
                "question_followup": "on",
            },
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        q = SurveyQuestion.objects.get(survey=survey)
        assert q.options[-1]["label"] == "Please specify"

    def test_marker_not_stored_without_toggle(self, client):
        owner = _owner("fuowner3")
        survey = _make_survey(owner, slug="followup-survey-3")
        client.force_login(owner)

        client.post(
            reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
            data={
                "text": "Pick one",
                "type": "mc_single",
                "options": "A\nB",
            },
            HTTP_HX_REQUEST="true",
        )
        q = SurveyQuestion.objects.get(survey=survey)
        assert all(
            not (isinstance(o, dict) and o.get("type") == "question_followup")
            for o in q.options
        )


# ---------------------------------------------------------------------------
# Builder payload serialization
# ---------------------------------------------------------------------------


class TestQuestionFollowupSerialization:
    def test_payload_exposes_question_followup_and_excludes_marker(self):
        owner = _owner("fuowner4")
        survey = _make_survey(owner, slug="followup-survey-4")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            order=0,
            options=[
                {"label": "Cardiology", "value": "Cardiology"},
                {"label": "Radiology", "value": "Radiology"},
                dict(QF_MARKER),
            ],
        )
        payload = _serialize_question_for_builder(q)
        assert payload["options"] == ["Cardiology", "Radiology"]
        assert payload["question_followup"] == {"label": "Please specify"}

    def test_payload_omits_question_followup_when_absent(self):
        owner = _owner("fuowner5")
        survey = _make_survey(owner, slug="followup-survey-5")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Pick one",
            type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
            order=0,
            options=[{"label": "A", "value": "A"}],
        )
        payload = _serialize_question_for_builder(q)
        assert "question_followup" not in payload


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestQuestionFollowupRendering:
    def test_take_renders_followup_any_but_not_marker_option(self, client):
        owner = _owner("fuowner6")
        survey = _make_survey(owner, slug="followup-survey-6")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            order=0,
            options=[
                {"label": "Cardiology", "value": "Cardiology"},
                dict(QF_MARKER),
            ],
        )
        resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert f'data-followup-any="q_{q.id}"' in body
        assert f'name="q_{q.id}_followup_any"' in body
        # The marker must not render as a selectable option.
        assert 'value="question_followup"' not in body

    def test_dropdown_without_followup_has_no_any_field(self, client):
        owner = _owner("fuowner7")
        survey = _make_survey(owner, slug="followup-survey-7")
        SurveyQuestion.objects.create(
            survey=survey,
            text="Plain dropdown",
            type=SurveyQuestion.Types.DROPDOWN,
            order=0,
            options=[{"label": "A", "value": "A"}],
        )
        resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
        assert resp.status_code == 200
        assert "data-followup-any" not in resp.content.decode()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestFollowupPersistence:
    def test_submit_stores_followup_text(self, client):
        owner = _owner("fuowner8")
        survey = _make_survey(owner, slug="followup-survey-8")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            order=0,
            options=[
                {"label": "Cardiology", "value": "Cardiology"},
                {
                    "label": "Other",
                    "value": "Other",
                    "followup_text": {"enabled": True, "label": "Which one?"},
                },
                dict(QF_MARKER),
            ],
        )
        respondent = _respondent()
        client.force_login(respondent)
        resp = client.post(
            reverse("surveys:take", kwargs={"slug": survey.slug}),
            data={
                f"q_{q.id}": "Other",
                f"q_{q.id}_followup_1": "Allergy specialist",
                f"q_{q.id}_followup_any": "Also paediatric cardio",
            },
        )
        assert resp.status_code in (200, 302)

        response = SurveyResponse.objects.get(survey=survey)
        # Legacy answer shape is untouched.
        assert response.answers[str(q.id)] == "Other"
        assert response.answers[f"{q.id}_followup"] == {
            "1": "Allergy specialist",
            "any": "Also paediatric cardio",
        }

    def test_submit_without_followup_text_stores_nothing(self, client):
        owner = _owner("fuowner9")
        survey = _make_survey(owner, slug="followup-survey-9")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            order=0,
            options=[{"label": "Cardiology", "value": "Cardiology"}, dict(QF_MARKER)],
        )
        resp = client.post(
            reverse("surveys:take", kwargs={"slug": survey.slug}),
            data={f"q_{q.id}": "Cardiology", f"q_{q.id}_followup_any": ""},
        )
        assert resp.status_code in (200, 302)
        response = SurveyResponse.objects.get(survey=survey)
        assert f"{q.id}_followup" not in response.answers

    def test_yesno_followup_text_is_stored(self, client):
        owner = _owner("fuowner10")
        survey = _make_survey(owner, slug="followup-survey-10")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Do you have allergies?",
            type=SurveyQuestion.Types.YESNO,
            order=0,
            options=[
                {
                    "label": "Yes",
                    "value": "yes",
                    "followup_text": {"enabled": True, "label": "List allergies"},
                },
                {"label": "No", "value": "no"},
            ],
        )
        resp = client.post(
            reverse("surveys:take", kwargs={"slug": survey.slug}),
            data={f"q_{q.id}": "yes", f"q_{q.id}_followup_yes": "Penicillin"},
        )
        assert resp.status_code in (200, 302)
        response = SurveyResponse.objects.get(survey=survey)
        assert response.answers[str(q.id)] == "yes"
        assert response.answers[f"{q.id}_followup"] == {"yes": "Penicillin"}


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestFollowupCsvExport:
    def test_csv_export_includes_followup_column(self, client):
        from checktick_app.surveys.services.export_service import ExportService

        owner = _owner("fuowner11")
        survey = _make_survey(owner, slug="followup-survey-11")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Select specialty",
            type=SurveyQuestion.Types.DROPDOWN,
            order=0,
            options=[
                {"label": "Cardiology", "value": "Cardiology"},
                {
                    "label": "Other",
                    "value": "Other",
                    "followup_text": {"enabled": True, "label": "Which one?"},
                },
                dict(QF_MARKER),
            ],
        )
        SurveyResponse.objects.create(
            survey=survey,
            answers={
                str(q.id): "Other",
                f"{q.id}_followup": {"1": "Allergy specialist"},
            },
        )
        csv_data = ExportService._generate_csv(survey)
        lines = csv_data.strip().splitlines()
        assert f"{q.text} (follow-up)" in lines[0]
        assert "Which one?: Allergy specialist" in lines[1]

    def test_csv_export_without_followup_config_has_no_extra_column(self):
        from checktick_app.surveys.services.export_service import ExportService

        owner = _owner("fuowner12")
        survey = _make_survey(owner, slug="followup-survey-12")
        q = SurveyQuestion.objects.create(
            survey=survey,
            text="Plain",
            type=SurveyQuestion.Types.TEXT,
            order=0,
            options=[{"type": "text", "format": "free"}],
        )
        SurveyResponse.objects.create(survey=survey, answers={str(q.id): "hi"})
        csv_data = ExportService._generate_csv(survey)
        assert "(follow-up)" not in csv_data
