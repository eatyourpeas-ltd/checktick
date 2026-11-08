"""Grouped single-choice questions (census-style option groups).

A grouped ``mc_single`` question stores visual group headings as marker
entries in the flat options list (``{"type": "option_group", "label": ...}``),
following the same pattern as the question-level follow-up marker. Markers
are presentation only: they never consume a follow-up index, never appear as
answerable options, and every consumer except the grouped ``mc_single``
renderer skips them. The motivating use case is the GSS/census ethnic-group
question — one selection overall, grouped categories, "any other" options
with a free-text follow-up.
"""

from __future__ import annotations

import textwrap

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import Survey, SurveyQuestion
from checktick_app.surveys.services.export_service import _question_followup_labels
from checktick_app.surveys.services.response_analytics import (
    _reorder_by_question_options,
)
from checktick_app.surveys.templatetags.survey_extras import (
    as_list,
    grouped_options,
)
from checktick_app.surveys.views import (
    _export_survey_to_markdown,
    _parse_builder_question_form,
    _serialize_question_for_builder,
)

TEST_PASSWORD = "testpass123"

ETHNICITY_OPTIONS = [
    {"type": "option_group", "label": "White"},
    {"label": "British", "value": "British"},
    {"label": "Irish", "value": "Irish"},
    {
        "label": "Any other White background",
        "value": "Any other White background",
        "followup_text": {"enabled": True, "label": "Please state your background"},
    },
    {"type": "option_group", "label": "Asian or Asian British"},
    {"label": "Indian", "value": "Indian"},
    {"label": "Pakistani", "value": "Pakistani"},
]


def _make_survey(user: User, name: str = "Grouped MC Test") -> Survey:
    return Survey.objects.create(owner=user, name=name, slug=f"grouped-mc-{user.id}")


# --- Template filters ---


def test_as_list_strips_group_markers():
    opts = as_list(ETHNICITY_OPTIONS)
    # Markers are configuration, not renderable options.
    assert all(
        not (isinstance(o, dict) and o.get("type") == "option_group") for o in opts
    )
    assert [o["label"] for o in opts if isinstance(o, dict)] == [
        "British",
        "Irish",
        "Any other White background",
        "Indian",
        "Pakistani",
    ]


def test_grouped_options_chunks_and_renderable_indices():
    chunks = grouped_options(ETHNICITY_OPTIONS)
    assert [c["label"] for c in chunks] == [
        "White",
        "Asian or Asian British",
    ]
    # idx is the position among renderable options — markers never consume
    # one, so the "Any other" follow-up keeps a stable suffix.
    assert [item["idx"] for item in chunks[0]["options"]] == [0, 1, 2]
    assert [item["idx"] for item in chunks[1]["options"]] == [3, 4]
    assert chunks[0]["options"][2]["opt"]["followup_text"]["enabled"] is True


def test_grouped_options_ungrouped_single_chunk():
    opts = [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}]
    chunks = grouped_options(opts)
    assert len(chunks) == 1
    assert chunks[0]["label"] == ""
    assert [i["idx"] for i in chunks[0]["options"]] == [0, 1]


def test_group_render_mode_filter():
    from checktick_app.surveys.templatetags.survey_extras import group_render_mode

    class FakeQuestion:
        options = ETHNICITY_OPTIONS

    assert group_render_mode(FakeQuestion()) == "expanded"

    class FakeCascading:
        options = ETHNICITY_OPTIONS + [
            {"type": "option_group_render", "mode": "cascading"}
        ]

    assert group_render_mode(FakeCascading()) == "cascading"

    class FakeNoGroups:
        options = [
            {"label": "Yes", "value": "Yes"},
            {"type": "option_group_render", "mode": "cascading"},
        ]

    # Without group headings the mode never applies.
    assert group_render_mode(FakeNoGroups()) == "expanded"


# --- Builder form parsing ---


def test_parse_builder_form_grouped_options():
    data = {
        "text": "What is your ethnic group?",
        "type": "mc_single",
        "required": "on",
        "options": (
            "[White]\n"
            "British\n"
            "Irish\n"
            "Any other White background\n"
            "[Asian or Asian British]\n"
            "Indian\n"
            "Pakistani"
        ),
        # Follow-up keyed by renderable index (group headings skipped):
        # British=0, Irish=1, Any other=2, Indian=3, Pakistani=4.
        "option_2_followup": "on",
        "option_2_followup_label": "Please state your background",
    }
    form_data = _parse_builder_question_form(data)
    options = form_data["options"]
    assert options[0] == {"type": "option_group", "label": "White"}
    assert options[1] == {"label": "British", "value": "British"}
    assert options[3] == {
        "label": "Any other White background",
        "value": "Any other White background",
        "followup_text": {
            "enabled": True,
            "label": "Please state your background",
        },
    }
    assert options[4] == {"type": "option_group", "label": "Asian or Asian British"}
    # Exactly one option carries a follow-up, and no group heading does.
    with_followup = [
        o["label"] for o in options if isinstance(o, dict) and o.get("followup_text")
    ]
    assert with_followup == ["Any other White background"]


def test_parse_builder_form_brackets_literal_for_mc_multi():
    """Only mc_single treats [bracketed] lines as group headings."""
    data = {
        "text": "Tick all that apply",
        "type": "mc_multi",
        "options": "[White]\nIrish",
    }
    form_data = _parse_builder_question_form(data)
    labels = [o["label"] for o in form_data["options"]]
    assert labels == ["[White]", "Irish"]


def test_parse_builder_form_grouped_render_cascading():
    data = {
        "text": "What is your ethnic group?",
        "type": "mc_single",
        "options": "[White]\nBritish\nIrish",
        "grouped_render": "cascading",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["options"][-1] == {
        "type": "option_group_render",
        "mode": "cascading",
    }


def test_parse_builder_form_grouped_render_cascading_radios():
    data = {
        "text": "What is your ethnic group?",
        "type": "mc_single",
        "options": "[White]\nBritish\nIrish",
        "grouped_render": "cascading_radios",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["options"][-1] == {
        "type": "option_group_render",
        "mode": "cascading_radios",
    }


def test_parse_builder_form_grouped_render_default_omits_marker():
    data = {
        "text": "What is your ethnic group?",
        "type": "mc_single",
        "options": "[White]\nBritish\nIrish",
    }
    form_data = _parse_builder_question_form(data)
    assert all(o.get("type") != "option_group_render" for o in form_data["options"])


# --- Builder edit payload round-trip ---


@pytest.mark.django_db
def test_question_payload_round_trips_groups():
    user = User.objects.create_user(username="gmc-payload", password=TEST_PASSWORD)
    survey = _make_survey(user, "Payload")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="What is your ethnic group?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        order=1,
        options=ETHNICITY_OPTIONS,
    )
    payload = _serialize_question_for_builder(q)
    # Group headings round-trip as [bracketed] textarea lines.
    assert payload["options"] == [
        "[White]",
        "British",
        "Irish",
        "Any other White background",
        "[Asian or Asian British]",
        "Indian",
        "Pakistani",
    ]
    # Follow-up config keyed by renderable index.
    assert payload["followup_config"] == {
        "2": {"label": "Please state your background"}
    }
    assert payload["grouped_render"] == "expanded"


@pytest.mark.django_db
def test_question_payload_grouped_render_cascading():
    user = User.objects.create_user(username="gmc-cascade", password=TEST_PASSWORD)
    survey = _make_survey(user, "Cascading")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="What is your ethnic group?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        order=1,
        options=ETHNICITY_OPTIONS
        + [{"type": "option_group_render", "mode": "cascading"}],
    )
    payload = _serialize_question_for_builder(q)
    assert payload["grouped_render"] == "cascading"


# --- Markdown import / export ---


def test_markdown_import_grouped_options():
    md = textwrap.dedent("""
        # Grouped
        ## What is your ethnic group?*
        (mc_single)
        - [White]
        - British
        - Irish
        - Any other White background
          + Please state your background
        - [Asian or Asian British]
        - Indian
        """)
    parsed = parse_bulk_markdown_with_collections(md)
    q = parsed["groups"][0]["questions"][0]
    assert q["final_type"] == "mc_single"
    options = q["final_options"]
    assert options[0] == {"type": "option_group", "label": "White"}
    assert options[3] == {
        "label": "Any other White background",
        "value": "Any other White background",
        "followup_text": {"enabled": True, "label": "Please state your background"},
    }
    assert options[4] == {"type": "option_group", "label": "Asian or Asian British"}


@pytest.mark.django_db
def test_markdown_export_round_trips_groups():
    from checktick_app.surveys.models import QuestionGroup

    user = User.objects.create_user(username="gmc-export", password=TEST_PASSWORD)
    survey = _make_survey(user, "Export")
    group = QuestionGroup.objects.create(name="Demographics", owner=user)
    group.surveys.set([survey])
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="What is your ethnic group?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        order=1,
        options=ETHNICITY_OPTIONS,
    )
    md = _export_survey_to_markdown(survey)
    assert "- [White]" in md
    assert "- [Asian or Asian British]" in md
    # Re-import produces the same marker structure.
    parsed = parse_bulk_markdown_with_collections(md)
    q = parsed["groups"][0]["questions"][0]
    assert q["final_options"] == ETHNICITY_OPTIONS


def test_markdown_import_cascading_render():
    md = textwrap.dedent("""
        # Grouped
        ## What is your ethnic group?*
        (mc_single)
        render: cascading
        - [White]
        - British
        - Irish
        """)
    parsed = parse_bulk_markdown_with_collections(md)
    q = parsed["groups"][0]["questions"][0]
    assert q["final_options"][-1] == {
        "type": "option_group_render",
        "mode": "cascading",
    }


def test_markdown_import_cascading_radios_hyphen_normalised():
    md = textwrap.dedent("""
        # Grouped
        ## What is your ethnic group?*
        (mc_single)
        render: cascading-radios
        - [White]
        - British
        - Irish
        """)
    parsed = parse_bulk_markdown_with_collections(md)
    q = parsed["groups"][0]["questions"][0]
    assert q["final_options"][-1] == {
        "type": "option_group_render",
        "mode": "cascading_radios",
    }


# --- Take-page rendering ---


@pytest.mark.django_db
class TestGroupedTakePage:
    def setup_method(self):
        self.user = User.objects.create_user(username="gmctake", password=TEST_PASSWORD)
        self.survey = Survey.objects.create(
            owner=self.user,
            name="Grouped Take",
            slug=f"grouped-take-{self.user.id}",
            status=Survey.Status.PUBLISHED,
            visibility=Survey.Visibility.PUBLIC,
        )
        self.q = SurveyQuestion.objects.create(
            survey=self.survey,
            text="What is your ethnic group?",
            type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
            required=True,
            order=1,
            options=ETHNICITY_OPTIONS,
        )

    def test_take_page_renders_group_headings(self, client):
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        assert res.status_code == 200
        html = res.content.decode()
        # Group headings render as text, not as selectable options.
        assert "White" in html
        assert "Asian or Asian British" in html
        # Exactly one radio per option, named after the question.
        assert html.count(f'name="q_{self.q.id}"') == 5
        # The follow-up input keeps its renderable index (2) as suffix.
        assert f'name="q_{self.q.id}_followup_2"' in html
        # Markers never render as radio values.
        assert 'value="option_group"' not in html

    def test_take_page_ungrouped_unchanged(self, client):
        self.q.options = [
            {"label": "Yes", "value": "Yes"},
            {"label": "No", "value": "No"},
        ]
        self.q.save()
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        html = res.content.decode()
        assert html.count(f'name="q_{self.q.id}"') == 2
        assert "data-option-group" not in html

    def test_take_page_cascading_dropdowns_render(self, client):
        self.q.options = ETHNICITY_OPTIONS + [
            {"type": "option_group_render", "mode": "cascading"}
        ]
        self.q.save()
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        assert res.status_code == 200
        html = res.content.decode()
        # Level 1: a transient category select, named with a _group suffix so
        # it never collides with the stored answer.
        assert f'name="q_{self.q.id}_group"' in html
        assert "data-cascading-dropdown=" in html
        assert "data-group-select=" in html
        # Level 2: one hidden, disabled select per group — disabled selects
        # never submit, so only the revealed panel's value is stored.
        assert html.count("data-group-panel=") == 2
        assert html.count("disabled") >= 2
        # The leaf options carry their renderable index for follow-ups.
        assert "data-followup-target=" in html
        # Group headings are select options, not answer values.
        assert "Asian or Asian British" in html

    def test_take_page_cascading_radios_render(self, client):
        self.q.options = ETHNICITY_OPTIONS + [
            {"type": "option_group_render", "mode": "cascading_radios"}
        ]
        self.q.save()
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        assert res.status_code == 200
        html = res.content.decode()
        # Level 1: transient group radios, named after the question with a
        # _group suffix so they never collide with the stored answer.
        assert f'name="q_{self.q.id}_group"' in html
        assert "data-group-trigger=" in html
        assert "data-cascading=" in html
        # Level 2: hidden panels keyed by group, containing the leaf radios
        # that actually store the answer.
        assert "data-group-panel=" in html
        assert html.count(f'name="q_{self.q.id}"') == 5
        # Group headings are not themselves answer values.
        assert 'value="White"' in html  # level-1 trigger value

    def test_take_page_cascading_childless_group_self_answers(self, client):
        opts = [
            {"type": "option_group", "label": "White"},
            {"label": "Irish", "value": "Irish"},
            {"type": "option_group", "label": "Chinese or other"},
        ]
        self.q.options = opts + [
            {"type": "option_group_render", "mode": "cascading_radios"}
        ]
        self.q.save()
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        html = res.content.decode()
        # The childless group's panel contains a single leaf equal to the
        # group itself, so selecting the group still yields an answer.
        assert 'value="Chinese or other"' in html


# --- Analytics / export consumers ---


@pytest.mark.django_db
def test_analytics_reorder_skips_group_markers():
    user = User.objects.create_user(username="gmc-analytics", password=TEST_PASSWORD)
    survey = _make_survey(user, "Analytics")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="What is your ethnic group?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        order=1,
        options=ETHNICITY_OPTIONS,
    )
    options = [
        {"label": "Pakistani", "count": 3, "percent": 60.0},
        {"label": "British", "count": 2, "percent": 40.0},
    ]
    reordered = _reorder_by_question_options(q, options)
    assert [o["label"] for o in reordered] == ["British", "Pakistani"]


@pytest.mark.django_db
def test_export_followup_labels_skip_group_markers():
    user = User.objects.create_user(username="gmc-exportlabels", password=TEST_PASSWORD)
    survey = _make_survey(user, "ExportLabels")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="What is your ethnic group?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        order=1,
        options=ETHNICITY_OPTIONS,
    )
    labels = _question_followup_labels(q)
    # Suffix 2 = "Any other White background" (renderable index), not the
    # stored-list index (which would be 3 with the group marker counted).
    assert labels == {"2": "Please state your background"}
