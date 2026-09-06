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


def test_parse_builder_form_yesno_dont_know_option():
    data = {
        "text": "Take part?",
        "type": "yesno",
        "yesno_include_dontknow": "on",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["options"] == [
        {"label": "Yes", "value": "yes"},
        {"label": "No", "value": "no"},
        {"label": "Don't know", "value": "dont_know"},
    ]


def test_parse_builder_form_yesno_dont_know_custom_label_and_followup():
    data = {
        "text": "Take part?",
        "type": "yesno",
        "yesno_include_dontknow": "on",
        "yesno_dontknow_label": "Not sure",
        "yesno_dont_know_followup": "on",
    }
    form_data = _parse_builder_question_form(data)
    dk = form_data["options"][2]
    assert dk["label"] == "Not sure"
    assert dk["followup_text"] == {"enabled": True, "label": "Please elaborate"}


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


def test_parse_yesno_dont_know_third_option_line():
    md = textwrap.dedent("""
        # Section {sec}
        ## Take part?
        (yesno)
        - Yes, please
        - No, thank you
        - Not sure
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_options"] == [
        {"label": "Yes, please", "value": "yes"},
        {"label": "No, thank you", "value": "no"},
        {"label": "Not sure", "value": "dont_know"},
    ]


def test_parse_yesno_dont_know_with_followup():
    md = textwrap.dedent("""
        # Section {sec}
        ## Take part?
        (yesno)
        - Agree
        - Disagree
        - Not sure
          + What would help you decide?
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    yes_opt, no_opt, dk_opt = q["final_options"]
    assert dk_opt["label"] == "Not sure"
    assert dk_opt["value"] == "dont_know"
    assert dk_opt["followup_text"] == {
        "enabled": True,
        "label": "What would help you decide?",
    }
    assert "followup_text" not in yes_opt
    assert "followup_text" not in no_opt


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
    # Options carry their semantic value for chart colouring
    values = {o["label"]: o.get("value") for o in dist.options}
    assert values["Agree"] == "yes"
    assert values["Disagree"] == "no"


@pytest.mark.django_db
def test_summary_distribution_with_dont_know(django_user_model):
    from checktick_app.surveys.models import SurveyResponse
    from checktick_app.surveys.services.response_analytics import (
        compute_response_analytics,
    )

    user = django_user_model.objects.create_user(
        username="yndk", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(name="YN DK", slug="yn-dk", owner=user)
    group = QuestionGroup.objects.create(name="G", owner=user)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Take part?",
        type="yesno",
        order=0,
        options=[
            {"label": "Yes", "value": "yes"},
            {"label": "No", "value": "no"},
            {"label": "Not sure", "value": "dont_know"},
        ],
    )
    SurveyResponse.objects.create(survey=survey, answers={str(question.id): "yes"})
    SurveyResponse.objects.create(
        survey=survey, answers={str(question.id): "dont_know"}
    )

    analytics = compute_response_analytics(survey)
    dist = analytics.distributions[0]
    values = {o["label"]: o["value"] for o in dist.options}
    assert values == {"Yes": "yes", "Not sure": "dont_know"}
    by_value = {o["value"]: o["count"] for o in dist.options}
    assert by_value == {"yes": 1, "dont_know": 1}


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


@pytest.mark.django_db
def test_take_page_renders_dont_know_option(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="yndktake", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(
        name="YN DK Take",
        slug="yn-dk-take",
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
            {"label": "Yes", "value": "yes"},
            {"label": "No", "value": "no"},
            {"label": "Not sure", "value": "dont_know"},
        ],
    )

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'value="dont_know"' in html
    assert "Not sure" in html
