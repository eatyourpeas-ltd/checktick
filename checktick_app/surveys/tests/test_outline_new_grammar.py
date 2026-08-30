from __future__ import annotations

import textwrap

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import (
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)

TEST_PASSWORD = "x"


# --- HIDDEN flag parsing ---


def test_parse_hidden_flag_marks_question_hidden_by_default():
    md = textwrap.dedent("""
        # Section {sec}
        ## Hidden Q {hidden-q}
        (text)
        HIDDEN

        ## Shown Q {shown-q}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    questions = {q["ref"]: q for q in groups[0]["questions"]}
    assert questions["hidden-q"]["hidden_by_default"] is True
    assert questions["shown-q"]["hidden_by_default"] is False


def test_parse_hidden_flag_case_insensitive():
    md = textwrap.dedent("""
        # Section {sec}
        ## Q {q}
        (text)
        hidden
        """).strip()

    groups = parse_bulk_markdown(md)
    assert groups[0]["questions"][0]["hidden_by_default"] is True


# --- Action keywords ---


def test_parse_show_keyword():
    md = textwrap.dedent("""
        # Section {sec}
        ## Trigger {trigger}
        (yesno)
        ? show when equals "Yes" -> {target}

        ## Target {target}
        (text)
        HIDDEN
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["action"] == SurveyQuestionCondition.Action.SHOW
    assert branch["target_kind"] == "question"
    assert branch["target_ref"] == "target"


def test_parse_hide_keyword():
    md = textwrap.dedent("""
        # Section {sec}
        ## Trigger {trigger}
        (yesno)
        ? hide when equals "No" -> {target}

        ## Target {target}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["action"] == SurveyQuestionCondition.Action.HIDE


def test_parse_end_keyword_no_target():
    md = textwrap.dedent("""
        # Section {sec}
        ## Trigger {trigger}
        (yesno)
        ? end when equals "N/A"
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["action"] == SurveyQuestionCondition.Action.END_SURVEY
    assert branch["target_ref"] is None
    assert branch["target_kind"] is None


def test_parse_default_action_is_jump_to():
    md = textwrap.dedent("""
        # Section {sec}
        ## Trigger {trigger}
        (yesno)
        ? when equals "No" -> {target}

        ## Target {target}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["action"] == SurveyQuestionCondition.Action.JUMP_TO


def test_parse_jump_to_keyword_explicit():
    md = textwrap.dedent("""
        # Section {sec}
        ## Trigger {trigger}
        (yesno)
        ? jump_to when equals "No" -> {target}

        ## Target {target}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["action"] == SurveyQuestionCondition.Action.JUMP_TO


# --- Section targets (#section-name) ---


def test_parse_section_target():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? when equals "No" -> #Closing

        # Closing {closing}
        ## End {end-q}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["target_kind"] == "section"
    assert branch["target_ref"] == "closing"
    assert branch["action"] == SurveyQuestionCondition.Action.JUMP_TO
    # Resolved to the group
    assert branch["target_type"] == "group"


def test_parse_section_target_normalizes_name():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? when equals "No" -> #Follow Up

        # Follow Up {follow-up}
        ## End {end-q}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["target_kind"] == "section"
    assert branch["target_ref"] == "follow-up"


# --- Rejections ---


def test_reject_show_on_section_target():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? show when equals "Yes" -> #Closing

        # Closing {closing}
        ## End {end-q}
        (text)
        """).strip()

    with pytest.raises(Exception) as exc:
        parse_bulk_markdown(md)
    assert "cannot target a section" in str(exc.value)


def test_reject_hide_on_section_target():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? hide when equals "No" -> #Closing

        # Closing {closing}
        ## End {end-q}
        (text)
        """).strip()

    with pytest.raises(Exception) as exc:
        parse_bulk_markdown(md)
    assert "cannot target a section" in str(exc.value)


def test_reject_end_with_target():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? end when equals "N/A" -> {target}

        ## Target {target}
        (text)
        """).strip()

    with pytest.raises(Exception) as exc:
        parse_bulk_markdown(md)
    assert "must not have a target" in str(exc.value)


def test_reject_unknown_section_target():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? when equals "No" -> #Nonexistent

        ## Target {target}
        (text)
        """).strip()

    with pytest.raises(Exception) as exc:
        parse_bulk_markdown(md)
    # An unknown section target is reported as an unknown id.
    assert "unknown id" in str(exc.value).lower() or "not a section" in str(exc.value)


def test_reject_question_target_that_resolves_to_group():
    md = textwrap.dedent("""
        # Intro {intro}
        ## Q {q1}
        (yesno)
        ? when equals "No" -> {closing}

        # Closing {closing}
        ## End {end-q}
        (text)
        """).strip()

    with pytest.raises(Exception) as exc:
        parse_bulk_markdown(md)
    assert "not a question" in str(exc.value)


# --- Existing outlines parse unchanged ---


def test_existing_outline_without_keywords_parses_unchanged():
    """Outlines using the old ? when ... -> {target} syntax still work."""
    md = textwrap.dedent("""
        # Intro {intro}
        ## Accept {intro-accept}
        (text)
        ? when equals "No" -> {intro-decline}

        ## Decline {intro-decline}
        (text)
        """).strip()

    groups = parse_bulk_markdown(md)
    branch = groups[0]["questions"][0]["branches"][0]
    assert branch["action"] == SurveyQuestionCondition.Action.JUMP_TO
    assert branch["target_kind"] == "question"
    assert branch["target_ref"] == "intro-decline"


# --- Full import round-trip ---


@pytest.mark.django_db
def test_bulk_import_creates_conditions_with_correct_actions(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="Bulk", slug="bulk-actions")

    md = textwrap.dedent("""
        # Intro {intro}
        ## Trigger {trigger}
        (yesno)
        ? show when equals "Yes" -> {shown}
        ? hide when equals "No" -> {hidden-target}
        ? end when equals "N/A"
        ? when equals "Maybe" -> #Closing

        ## Shown {shown}
        (text)
        HIDDEN

        ## Hidden target {hidden-target}
        (text)

        # Closing {closing}
        ## End {end-q}
        (text)
        """).strip()

    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": md},
        follow=False,
    )
    assert response.status_code == 302

    conditions = SurveyQuestionCondition.objects.filter(question__survey=survey)
    actions = {c.action for c in conditions}
    assert SurveyQuestionCondition.Action.SHOW in actions
    assert SurveyQuestionCondition.Action.HIDE in actions
    assert SurveyQuestionCondition.Action.END_SURVEY in actions
    assert SurveyQuestionCondition.Action.JUMP_TO in actions

    # The HIDDEN flag should have been applied to the 'shown' question.
    shown = SurveyQuestion.objects.get(text="Shown")
    assert shown.hidden_by_default is True

    # The section jump should have resolved to the first question in Closing.
    jump_cond = conditions.filter(action=SurveyQuestionCondition.Action.JUMP_TO).first()
    assert jump_cond is not None
    assert jump_cond.target_question is not None
    assert jump_cond.target_question.text == "End"


@pytest.mark.django_db
def test_bulk_import_hidden_flag_persists(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="BulkHidden", slug="bulk-hidden")

    md = textwrap.dedent("""
        # Section {sec}
        ## Hidden Q {hidden-q}
        (text)
        HIDDEN

        ## Shown Q {shown-q}
        (text)
        """).strip()

    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": md},
        follow=False,
    )
    assert response.status_code == 302

    hidden_q = SurveyQuestion.objects.get(text="Hidden Q")
    shown_q = SurveyQuestion.objects.get(text="Shown Q")
    assert hidden_q.hidden_by_default is True
    assert shown_q.hidden_by_default is False
