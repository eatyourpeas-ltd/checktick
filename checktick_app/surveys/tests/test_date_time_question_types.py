"""Tests for date/time question types (text question formats).

Date and time follow the same pattern as the existing "number" format:
stored as ``type="text"`` with ``options=[{"type": "text", "format": ...}]``.
"""

from __future__ import annotations

import textwrap

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import Survey, SurveyQuestion
from checktick_app.surveys.views import _export_survey_to_markdown

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(username="owner", password="x")


@pytest.fixture
def survey(owner):
    return Survey.objects.create(
        owner=owner,
        name="Dates",
        slug="dates",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )


def _add_question(survey: Survey, text: str, fmt: str, **kwargs) -> SurveyQuestion:
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.first()
    if group is None:
        group = QuestionGroup.objects.create(name="Section", owner=survey.owner)
        survey.question_groups.add(group)
    options = kwargs.pop("options", None) or [{"type": "text", "format": fmt}]
    return SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=text,
        type=SurveyQuestion.Types.TEXT,
        options=options,
        order=0,
        **kwargs,
    )


# --- Markdown outline import ---


@pytest.mark.parametrize(
    "type_name,expected_format",
    [
        ("text date", "date"),
        ("date", "date"),
        ("text time", "time"),
        ("time", "time"),
        ("text datetime", "datetime"),
        ("datetime", "datetime"),
        ("date/time", "datetime"),
    ],
)
def test_parse_markdown_date_time_types(type_name: str, expected_format: str):
    md = textwrap.dedent(f"""
        # Section {{sec}}

        ## When {{when}}
        ({type_name})
        """).strip()
    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "text"
    assert q["final_options"] == [{"type": "text", "format": expected_format}]


# --- Builder question creation ---


def _create_question(client, survey: Survey, text_format: str):
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    return client.post(
        url,
        {"text": "Date of birth?", "type": "text", "text_format": text_format},
        HTTP_HX_REQUEST="true",
    )


def test_builder_creates_date_question(client, owner, survey):
    client.force_login(owner)
    response = _create_question(client, survey, "date")
    assert response.status_code == 200
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [{"type": "text", "format": "date"}]


def test_builder_creates_time_question(client, owner, survey):
    client.force_login(owner)
    response = _create_question(client, survey, "time")
    assert response.status_code == 200
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [{"type": "text", "format": "time"}]


def test_builder_creates_datetime_question(client, owner, survey):
    client.force_login(owner)
    response = _create_question(client, survey, "datetime")
    assert response.status_code == 200
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [{"type": "text", "format": "datetime"}]


def test_builder_rejects_unknown_format(client, owner, survey):
    client.force_login(owner)
    response = _create_question(client, survey, "banana")
    assert response.status_code == 200
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [{"type": "text", "format": "free"}]


# --- Markdown export round trip ---


def test_export_emits_text_date_type(survey):
    _add_question(survey, "Date of birth?", "date")
    md = _export_survey_to_markdown(survey)
    assert "(text date)" in md


def test_export_emits_text_time_type(survey):
    _add_question(survey, "Clinic arrival time?", "time")
    md = _export_survey_to_markdown(survey)
    assert "(text time)" in md


def test_export_emits_text_datetime_type(survey):
    _add_question(survey, "Appointment date and time?", "datetime")
    md = _export_survey_to_markdown(survey)
    assert "(text datetime)" in md


# --- Participant rendering ---


@pytest.mark.parametrize(
    "fmt,input_type",
    [
        ("date", "date"),
        ("time", "time"),
        ("datetime", "datetime-local"),
    ],
)
def test_take_view_renders_html_input_types(survey, client, fmt, input_type):
    SurveyQuestion.objects.create(
        survey=survey,
        text="When?",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": fmt}],
        order=0,
    )
    url = reverse("surveys:take", kwargs={"slug": survey.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert f'type="{input_type}"' in response.content.decode()


# --- Import -> export round trip ---


def test_round_trip_text_date(survey, owner):
    md_in = textwrap.dedent("""
        # Section {sec}

        ## Date of birth?* {dob}
        (text date)
        """).strip()
    groups = parse_bulk_markdown(md_in)
    q = groups[0]["questions"][0]
    _add_question(
        survey,
        q["title"],
        q["final_options"][0]["format"],
        required=bool(q.get("required")),
    )
    md_out = _export_survey_to_markdown(survey)
    assert "(text date)" in md_out
    assert "*" in md_out


# --- Optional min/max ranges (builder + markdown) ---


def test_builder_persists_date_range(client, owner, survey):
    client.force_login(owner)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    response = client.post(
        url,
        {
            "text": "Appointment date?",
            "type": "text",
            "text_format": "date",
            "text_min": "2026-01-01",
            "text_max": "2026-12-31",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [
        {"type": "text", "format": "date", "min": "2026-01-01", "max": "2026-12-31"}
    ]


def test_builder_drops_invalid_range(client, owner, survey):
    client.force_login(owner)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    client.post(
        url,
        {
            "text": "Appointment date?",
            "type": "text",
            "text_format": "date",
            "text_min": "not-a-date",
            "text_max": "2026-12-31",
        },
        HTTP_HX_REQUEST="true",
    )
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [{"type": "text", "format": "date", "max": "2026-12-31"}]


def test_builder_drops_reversed_range(client, owner, survey):
    client.force_login(owner)
    url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
    client.post(
        url,
        {
            "text": "Appointment date?",
            "type": "text",
            "text_format": "date",
            "text_min": "2026-12-31",
            "text_max": "2026-01-01",
        },
        HTTP_HX_REQUEST="true",
    )
    q = SurveyQuestion.objects.get(survey=survey)
    assert q.options == [{"type": "text", "format": "date"}]


def test_markdown_import_parses_date_range():
    md = textwrap.dedent("""
        # Section {sec}

        ## Clinic date {clinic-date}
        (text date)
        min: 2026-01-01
        max: 2026-12-31
        """).strip()
    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_options"] == [
        {"type": "text", "format": "date", "min": "2026-01-01", "max": "2026-12-31"}
    ]


def test_export_emits_date_range_lines(survey):
    _add_question(
        survey,
        "Clinic date?",
        "date",
        options=[
            {
                "type": "text",
                "format": "date",
                "min": "2026-01-01",
                "max": "2026-12-31",
            }
        ],
    )
    md = _export_survey_to_markdown(survey)
    assert "min: 2026-01-01" in md
    assert "max: 2026-12-31" in md


def test_take_view_renders_range_attributes(survey, client):
    _add_question(
        survey,
        "Clinic date?",
        "date",
        options=[
            {
                "type": "text",
                "format": "date",
                "min": "2026-01-01",
                "max": "2026-12-31",
            }
        ],
    )
    url = reverse("surveys:take", kwargs={"slug": survey.slug})
    html = client.get(url).content.decode()
    assert 'min="2026-01-01"' in html
    assert 'max="2026-12-31"' in html


# --- Server-side answer validation ---


from checktick_app.surveys.views import _validate_text_format_answers  # noqa: E402


def test_validation_rejects_unparseable_date(survey):
    _add_question(survey, "Clinic date?", "date")
    q = SurveyQuestion.objects.get(survey=survey)
    errors = _validate_text_format_answers(survey, {str(q.id): "garbage"})
    assert len(errors) == 1
    assert "valid date" in errors[0]


def test_validation_accepts_valid_date(survey):
    _add_question(survey, "Clinic date?", "date")
    q = SurveyQuestion.objects.get(survey=survey)
    assert _validate_text_format_answers(survey, {str(q.id): "2026-06-15"}) == []


def test_validation_rejects_out_of_range(survey):
    _add_question(
        survey,
        "Clinic date?",
        "date",
        options=[{"type": "text", "format": "date", "min": "2026-01-01"}],
    )
    q = SurveyQuestion.objects.get(survey=survey)
    errors = _validate_text_format_answers(survey, {str(q.id): "2025-12-31"})
    assert len(errors) == 1
    assert "earlier than" in errors[0]


def test_validation_rejects_out_of_range_time(survey):
    _add_question(
        survey,
        "Arrival time?",
        "time",
        options=[
            {
                "type": "text",
                "format": "time",
                "min": "09:00",
                "max": "17:00",
            }
        ],
    )
    q = SurveyQuestion.objects.get(survey=survey)
    errors = _validate_text_format_answers(survey, {str(q.id): "18:30"})
    assert len(errors) == 1
    assert "later than" in errors[0]


def test_validation_skips_blank_answers(survey):
    _add_question(survey, "Clinic date?", "date")
    q = SurveyQuestion.objects.get(survey=survey)
    assert _validate_text_format_answers(survey, {str(q.id): ""}) == []
    assert _validate_text_format_answers(survey, {}) == []


def test_validation_handles_repeatable_instances(survey):
    _add_question(survey, "Clinic date?", "date")
    q = SurveyQuestion.objects.get(survey=survey)
    assert (
        _validate_text_format_answers(survey, {str(q.id): ["2026-06-01", "2026-07-01"]})
        == []
    )
    errors = _validate_text_format_answers(survey, {str(q.id): ["2026-06-01", "nope"]})
    assert len(errors) == 1


# --- Analytics ---


from checktick_app.surveys.models import SurveyResponse  # noqa: E402
from checktick_app.surveys.services.response_analytics import (  # noqa: E402
    compute_survey_summary,
)


def test_summary_routes_date_question_to_datetime_summary(survey):
    q = _add_question(survey, "Clinic date?", "date")
    SurveyResponse.objects.create(survey=survey, answers={str(q.id): "2026-03-01"})
    SurveyResponse.objects.create(survey=survey, answers={str(q.id): "2026-03-10"})
    summary = compute_survey_summary(survey, survey.responses.all())
    assert len(summary.datetime_summaries) == 1
    dt = summary.datetime_summaries[0]
    assert dt.count == 2
    assert dt.earliest == "2026-03-01"
    assert dt.latest == "2026-03-10"
    assert dt.fmt == "date"
    assert summary.question_index[q.id] == ("datetime", 0)


def test_datetime_summary_skips_unparseable_values(survey):
    q = _add_question(survey, "Clinic date?", "date")
    SurveyResponse.objects.create(survey=survey, answers={str(q.id): "2026-03-01"})
    SurveyResponse.objects.create(survey=survey, answers={str(q.id): "garbage"})
    summary = compute_survey_summary(survey, survey.responses.all())
    dt = summary.datetime_summaries[0]
    assert dt.count == 1
    assert dt.latest == "2026-03-01"


def test_time_summary_earliest_latest(survey):
    q = _add_question(survey, "Arrival time?", "time")
    SurveyResponse.objects.create(survey=survey, answers={str(q.id): "09:30"})
    SurveyResponse.objects.create(survey=survey, answers={str(q.id): "08:15"})
    summary = compute_survey_summary(survey, survey.responses.all())
    dt = summary.datetime_summaries[0]
    assert dt.count == 2
    assert dt.earliest == "08:15"
    assert dt.latest == "09:30"
    assert dt.fmt == "time"


def test_free_text_question_still_gets_text_collation(survey):
    _add_question(survey, "Comments?", "free")
    SurveyResponse.objects.create(survey=survey, answers={"x": "hello world"})
    summary = compute_survey_summary(survey, survey.responses.all())
    assert len(summary.datetime_summaries) == 0
