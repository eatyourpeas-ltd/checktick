from __future__ import annotations

import textwrap

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion
from checktick_app.surveys.views import _parse_builder_question_form

TEST_PASSWORD = "x"


# --- Builder form parsing ---


def test_parse_builder_form_yesno_custom_labels():
    data = {
        "text": "Would you like to take part?",
        "type": "yesno",
        "yesno_yes_label": "Yes, please",
        "yesno_no_label": "No, thank you",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["options"] == [
        {"label": "Yes, please", "value": "yes"},
        {"label": "No, thank you", "value": "no"},
    ]


def test_parse_builder_form_yesno_default_labels():
    data = {"text": "OK?", "type": "yesno"}
    form_data = _parse_builder_question_form(data)
    assert form_data["options"] == [
        {"label": "Yes", "value": "yes"},
        {"label": "No", "value": "no"},
    ]


def test_parse_builder_form_yesno_blank_labels_fall_back():
    data = {
        "text": "OK?",
        "type": "yesno",
        "yesno_yes_label": "   ",
        "yesno_no_label": "",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["options"] == [
        {"label": "Yes", "value": "yes"},
        {"label": "No", "value": "no"},
    ]


# --- Markdown import/export round trip ---


def test_parse_yesno_custom_labels_from_option_lines():
    md = textwrap.dedent("""
        # Section {sec}
        ## Take part?
        (yesno)
        - Agree
        - Disagree
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "yesno"
    assert q["final_options"] == [
        {"label": "Agree", "value": "yes"},
        {"label": "Disagree", "value": "no"},
    ]


def test_parse_yesno_labels_with_followups():
    md = textwrap.dedent("""
        # Section {sec}
        ## Take part?
        (yesno)
        - Agree
          + Tell us more
        - Disagree
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    yes_opt, no_opt = q["final_options"]
    assert yes_opt["label"] == "Agree"
    assert yes_opt["followup_text"] == {"enabled": True, "label": "Tell us more"}
    assert no_opt["label"] == "Disagree"


# --- Summary analytics ---


@pytest.mark.django_db
def test_summary_distribution_uses_custom_labels(django_user_model):
    from checktick_app.surveys.models import SurveyResponse
    from checktick_app.surveys.services.response_analytics import (
        compute_response_analytics,
    )

    user = django_user_model.objects.create_user(
        username="yesnolabels", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(name="YN Labels", slug="yn-labels", owner=user)
    group = QuestionGroup.objects.create(name="G", owner=user)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Take part?",
        type="yesno",
        order=0,
        options=[
            {"label": "Agree", "value": "yes"},
            {"label": "Disagree", "value": "no"},
        ],
    )
    SurveyResponse.objects.create(survey=survey, answers={str(question.id): "yes"})
    SurveyResponse.objects.create(survey=survey, answers={str(question.id): "no"})

    analytics = compute_response_analytics(survey)
    dist = analytics.distributions[0]
    labels = {o["label"] for o in dist.options}
    assert labels == {"Agree", "Disagree"}


# --- Participant-facing rendering ---


@pytest.mark.django_db
def test_take_page_renders_custom_yesno_labels(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="yntake", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        name="YN Take",
        slug="yn-take",
        owner=user,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = QuestionGroup.objects.create(name="G", owner=user)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Take part?",
        type="yesno",
        order=0,
        options=[
            {"label": "Agree", "value": "yes"},
            {"label": "Disagree", "value": "no"},
        ],
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Agree" in html
    assert "Disagree" in html


@pytest.mark.django_db
def test_take_page_defaults_to_yes_no(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="yndefault", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        name="YN Default",
        slug="yn-default",
        owner=user,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    group = QuestionGroup.objects.create(name="G", owner=user)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey, group=group, text="OK?", type="yesno", order=0
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert ">Yes<" in html
    assert ">No<" in html
