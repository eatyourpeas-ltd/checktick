"""Tests for the SECTION_MENU outline grammar (step 7).

Tests the parse → export → parse round-trip for the SECTION_MENU block
and the ``~ pickable`` suffix on group headings.

The grammar places the ``~ pickable`` suffix on the actual content group
headings, not on separate lines in the SECTION_MENU block. This avoids
duplicate group headings and keeps the parser single-pass.

See docs/survey-layouts.md §Outline syntax.
"""

from __future__ import annotations

import textwrap

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections


def test_section_menu_block_parsed():
    """A SECTION_MENU block at the top is parsed into the section_menu dict."""
    md = textwrap.dedent("""
        SECTION_MENU
          prompt: "Which areas would you like to cover?"
          min: 1
          max: 4
          order: authored

        # Demographics {demographics}
        ## Name {name}
        (text)

        # Medical history {medical-history}    ~ pickable
        ## Condition {cond}
        (text)

        # Medications {medications}    ~ pickable, 5 min
        ## Drug {drug}
        (text)

        # Lifestyle {lifestyle}    ~ pickable
        ## Exercise {ex}
        (text)
        """).strip()

    parsed = parse_bulk_markdown_with_collections(md)
    sm = parsed["section_menu"]
    assert sm is not None
    assert sm["prompt_text"] == "Which areas would you like to cover?"
    assert sm["min_selected"] == 1
    assert sm["max_selected"] == 4
    assert sm["order_mode"] == "authored"

    groups = parsed["groups"]
    assert len(groups) == 4

    by_name = {g["name"]: g for g in groups}
    assert by_name["Demographics"]["section_menu_pickable"] is False
    assert by_name["Medical history"]["section_menu_pickable"] is True
    assert by_name["Medications"]["section_menu_pickable"] is True
    assert by_name["Medications"]["section_menu_estimated_minutes"] == 5
    assert by_name["Lifestyle"]["section_menu_pickable"] is True
    assert by_name["Lifestyle"]["section_menu_estimated_minutes"] is None


def test_section_menu_defaults():
    """A SECTION_MENU block with no config lines uses defaults."""
    md = textwrap.dedent("""
        SECTION_MENU

        # Section A {a}    ~ pickable
        ## Q {q}
        (text)

        # Section B {b}
        ## Q2 {q2}
        (text)
        """).strip()

    parsed = parse_bulk_markdown_with_collections(md)
    sm = parsed["section_menu"]
    assert sm is not None
    assert sm["prompt_text"] == "Which sections would you like to complete?"
    assert sm["min_selected"] == 1
    assert sm["max_selected"] is None
    assert sm["order_mode"] == "authored"

    groups = parsed["groups"]
    by_name = {g["name"]: g for g in groups}
    assert by_name["Section A"]["section_menu_pickable"] is True
    assert by_name["Section B"]["section_menu_pickable"] is False


def test_no_section_menu_block():
    """Markdown without a SECTION_MENU block has section_menu=None."""
    md = textwrap.dedent("""
        # Section A {a}
        ## Q {q}
        (text)
        """).strip()

    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["section_menu"] is None


def test_section_menu_select_all_and_estimated_time():
    """The select_all and estimated_time config lines are parsed."""
    md = textwrap.dedent("""
        SECTION_MENU
          prompt: "Pick sections"
          min: 2
          max: 3
          order: participant
          select_all: true
          estimated_time: true

        # A {a}    ~ pickable
        ## Q {q}
        (text)
        """).strip()

    parsed = parse_bulk_markdown_with_collections(md)
    sm = parsed["section_menu"]
    assert sm["show_select_all"] is True
    assert sm["show_estimated_time"] is True
    assert sm["order_mode"] == "participant"
    assert sm["min_selected"] == 2


def test_section_menu_does_not_break_repeats():
    """A SECTION_MENU block coexists with REPEAT markers."""
    md = textwrap.dedent("""
        SECTION_MENU
          min: 1
          max: 2

        REPEAT-3
        # Medications {medications}    ~ pickable
        ## Drug {drug}
        (text)

        # Demographics {demographics}
        ## Name {name}
        (text)
        """).strip()

    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["section_menu"] is not None
    assert len(parsed["repeats"]) == 1
    assert parsed["repeats"][0]["max_count"] == 3
    groups = parsed["groups"]
    assert len(groups) == 2
    by_name = {g["name"]: g for g in groups}
    assert by_name["Medications"]["section_menu_pickable"] is True
    assert by_name["Demographics"]["section_menu_pickable"] is False


@pytest.mark.django_db
def test_section_menu_round_trip_export_import(django_user_model):
    """Export a section_menu survey to markdown, re-parse, and verify the
    section_menu config survives the round-trip."""
    from checktick_app.surveys.models import (
        Organization,
        QuestionGroup,
        SectionMenu,
        SectionMenuItem,
        Survey,
        SurveyQuestion,
    )
    from checktick_app.surveys.views import _export_survey_to_markdown

    owner = django_user_model.objects.create_user(
        username="rt_owner@example.com", password="x"
    )
    org = Organization.objects.create(name="RoundTrip Org", owner=owner)
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RoundTrip",
        slug="roundtrip",
        layout=Survey.Layout.SECTION_MENU,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Medical", owner=owner)
    g3 = QuestionGroup.objects.create(name="Lifestyle", owner=owner)
    survey.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=survey, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=g2,
        text="Condition",
        type=SurveyQuestion.Types.TEXT,
        order=1,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=g3,
        text="Exercise",
        type=SurveyQuestion.Types.TEXT,
        order=2,
    )
    menu = SectionMenu.objects.create(
        survey=survey,
        prompt_text="Which areas would you like to cover?",
        min_selected=1,
        max_selected=2,
        order_mode="authored",
        show_estimated_time=True,
    )
    SectionMenuItem.objects.create(menu=menu, group=g1, is_pickable=False, order=1)
    SectionMenuItem.objects.create(
        menu=menu, group=g2, is_pickable=True, estimated_minutes=5, order=2
    )
    SectionMenuItem.objects.create(menu=menu, group=g3, is_pickable=True, order=3)

    md = _export_survey_to_markdown(survey)
    assert "SECTION_MENU" in md
    assert "Which areas would you like to cover?" in md
    assert "max: 2" in md
    assert "estimated_time: true" in md
    assert "# Demographics {demographics}" in md
    assert "~ pickable, 5 min" in md
    assert "~ pickable" in md

    parsed = parse_bulk_markdown_with_collections(md)
    sm = parsed["section_menu"]
    assert sm is not None
    assert sm["prompt_text"] == "Which areas would you like to cover?"
    assert sm["min_selected"] == 1
    assert sm["max_selected"] == 2
    assert sm["show_estimated_time"] is True

    groups = parsed["groups"]
    by_name = {g["name"]: g for g in groups}
    assert by_name["Demographics"]["section_menu_pickable"] is False
    assert by_name["Medical"]["section_menu_pickable"] is True
    assert by_name["Medical"]["section_menu_estimated_minutes"] == 5
    assert by_name["Lifestyle"]["section_menu_pickable"] is True

    survey.delete()
    org.delete()
