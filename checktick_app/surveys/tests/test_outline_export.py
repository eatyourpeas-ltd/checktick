"""Tests for the outline (bulk import) notation export side.

`docs/import.md` is the canonical source of the outline notation. These tests
pin the pieces the visual builder can author that must round-trip through it:

- the question-level ``followup:`` kv line (parser + export),
- per-option follow-ups in both stored shapes (``followup_text`` dict and the
  legacy ``has_followup_text`` keys),
- likert *slider* categories stored by the builder as a plain string list,
- dropdown ``dataset:`` links and the professional template's
  ``address_lookup:`` toggle,
- HIDDEN, Yes/No labels + ``Don't know``, and branch actions/targets.
"""

import pytest

from checktick_app.surveys.markdown_import import (
    parse_bulk_markdown,
    parse_bulk_markdown_with_collections,
)
from checktick_app.surveys.models import (
    DataSet,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)
from checktick_app.surveys.views import _export_survey_to_markdown

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="outline_export@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="Export",
        slug="export-roundtrip",
    )


def _add_group(survey, name="Group", ref_hint="group"):
    g = QuestionGroup.objects.create(
        name=name, description=f"{name} desc", owner=survey.owner
    )
    survey.question_groups.add(g)
    return g


# --- parser: question-level followup line ---


def test_parse_followup_kv_line_mc_and_dropdown():
    md = """\
# G {g}
## Single {q1}
(mc_single)
- A
- B
followup: Anything else?

## Multi {q2}
(mc_multi)
- A
followup: Tick one?

## Trust {q3}
(dropdown)
dataset: nhs_trusts
followup: Which trust?
"""
    parsed = parse_bulk_markdown_with_collections(md)
    questions = {q["title"]: q for q in parsed["groups"][0]["questions"]}
    marker = questions["Single"]["final_options"][-1]
    assert marker == {
        "type": "question_followup",
        "enabled": True,
        "label": "Anything else?",
    }
    assert questions["Multi"]["final_options"][-1]["label"] == "Tick one?"
    trust = questions["Trust"]
    assert trust["final_options"][-1]["label"] == "Which trust?"
    # The dataset line still resolves alongside the followup line.
    assert trust["dataset_key"] == "nhs_trusts"


def test_parse_followup_kv_line_not_applied_to_orderable():
    md = """\
# G {g}
## Rank {q}
(orderable)
- A
- B
followup: Ignored
"""
    parsed = parse_bulk_markdown(md)
    opts = parsed[0]["questions"][0]["final_options"]
    assert all(o.get("type") != "question_followup" for o in opts)


def test_parse_followup_kv_line_quoted_label():
    md = """\
# G {g}
## Single {q}
(mc_single)
- A
followup: "Please describe"
"""
    parsed = parse_bulk_markdown(md)
    marker = parsed[0]["questions"][0]["final_options"][-1]
    assert marker["label"] == "Please describe"


# --- export: per-option follow-ups (both stored shapes) ---


def test_export_per_option_followup_dict_shape(survey):
    g = _add_group(survey, name="Employment")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Employment status",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[
            {"label": "Employed", "value": "Employed"},
            {
                "label": "Self-employed",
                "value": "Self-employed",
                "followup_text": {"enabled": True, "label": "What type of business?"},
            },
        ],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "- Self-employed" in md
    assert "  + What type of business?" in md
    # Round-trip: the exported outline re-imports with the follow-up intact.
    parsed = parse_bulk_markdown(md)
    opts = parsed[0]["questions"][0]["final_options"]
    assert opts[1]["followup_text"] == {
        "enabled": True,
        "label": "What type of business?",
    }


def test_export_per_option_followup_legacy_shape(survey):
    """Legacy rows stored follow-ups as has_followup_text/followup_text_label."""
    g = _add_group(survey, name="Legacy")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Legacy question",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[
            {
                "label": "Other",
                "value": "Other",
                "has_followup_text": True,
                "followup_text_label": "Please specify",
            }
        ],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "  + Please specify" in md


# --- export: question-level follow-up marker ---


def test_export_question_level_followup_roundtrip(survey):
    g = _add_group(survey, name="Trust")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Your trust",
        type=SurveyQuestion.Types.DROPDOWN,
        options=[
            {"label": "Trust A", "value": "Trust A"},
            {"label": "Trust B", "value": "Trust B"},
            {"type": "question_followup", "enabled": True, "label": "Anything else?"},
        ],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "followup: Anything else?" in md
    # The marker must not leak as a `- ` option line.
    assert "- question_followup" not in md
    parsed = parse_bulk_markdown(md)
    opts = parsed[0]["questions"][0]["final_options"]
    assert opts[-1] == {
        "type": "question_followup",
        "enabled": True,
        "label": "Anything else?",
    }
    assert [o["label"] for o in opts[:2]] == ["Trust A", "Trust B"]


# --- export: likert slider categories stored as a plain string list ---


def test_export_likert_slider_categories_builder_shape(survey):
    """The builder stores slider-mode category labels as a plain string list.

    Exporting must keep `likert categories` — a bare `(likert)` would
    re-import as a number scale and lose the labels.
    """
    g = _add_group(survey, name="Opinion")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Agreement",
        type=SurveyQuestion.Types.LIKERT,
        options=["Strongly disagree", "Disagree", "Agree", "Strongly agree"],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "(likert categories)" in md
    for label in ("Strongly disagree", "Disagree", "Agree", "Strongly agree"):
        assert f"- {label}" in md
    parsed = parse_bulk_markdown(md)
    q = parsed[0]["questions"][0]
    assert q["final_type"] == "likert"
    assert q["final_options"][0]["labels"] == [
        "Strongly disagree",
        "Disagree",
        "Agree",
        "Strongly agree",
    ]


def test_export_likert_number_builder_shape_roundtrip(survey):
    """Builder likert number uses left/right keys; importer uses left_label/right_label."""
    g = _add_group(survey, name="Rating")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Satisfaction",
        type=SurveyQuestion.Types.LIKERT,
        options=[
            {
                "type": "number-scale",
                "min": 0,
                "max": 10,
                "left": "Not at all",
                "right": "Completely",
                "render": "radio",
            }
        ],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "(likert number)" in md
    assert "min: 0" in md
    assert "max: 10" in md
    assert "left: Not at all" in md
    assert "right: Completely" in md
    assert "render: radio" in md
    parsed = parse_bulk_markdown(md)
    opts = parsed[0]["questions"][0]["final_options"][0]
    assert opts["min"] == 0
    assert opts["max"] == 10
    assert opts["render"] == "radio"


# --- export: dropdown dataset link + professional template toggle ---


def test_export_dropdown_dataset(survey):
    ds = DataSet.objects.create(
        key="main_specialty_test",
        name="Main Specialty (test)",
        is_active=True,
    )
    g = _add_group(survey, name="Specialty")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Your specialty",
        type=SurveyQuestion.Types.DROPDOWN,
        options=[{"label": "Cardiology", "value": "Cardiology"}],
        dataset=ds,
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "dataset: main_specialty_test" in md


def test_export_template_professional_address_lookup(survey):
    g = _add_group(survey, name="Professional")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Your details",
        type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL,
        options={"template": "professional_details", "address_lookup": True},
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "(template_professional)" in md
    assert "address_lookup: true" in md
    parsed = parse_bulk_markdown(md)
    q = parsed[0]["questions"][0]
    assert q["final_type"] == "template_professional"
    assert q["final_options"]["address_lookup"] is True


# --- export: HIDDEN, Yes/No labels + Don't know, branch actions ---


def test_export_hidden_marker(survey):
    g = _add_group(survey, name="Sensitive")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Optional detail",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        hidden_by_default=True,
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "HIDDEN" in md
    parsed = parse_bulk_markdown(md)
    assert parsed[0]["questions"][0]["hidden_by_default"] is True


def test_export_yesno_labels_dontknow_and_followups(survey):
    g = _add_group(survey, name="Consent")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Do you agree?",
        type=SurveyQuestion.Types.YESNO,
        options=[
            {
                "label": "Agree",
                "value": "yes",
                "followup_text": {"enabled": True, "label": "Why?"},
            },
            {"label": "Disagree", "value": "no"},
            {"label": "Not sure", "value": "dont_know"},
        ],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    # Labels export as option lines (line 1 = Yes, line 2 = No,
    # line 3 = Don't know) so the round-trip restores all three.
    assert "- Agree" in md
    assert "  + Why?" in md
    assert "- Disagree" in md
    assert "- Not sure" in md
    parsed = parse_bulk_markdown(md)
    opts = parsed[0]["questions"][0]["final_options"]
    assert opts[0]["label"] == "Agree"
    assert opts[0]["value"] == "yes"
    assert opts[0]["followup_text"]["label"] == "Why?"
    assert opts[1]["label"] == "Disagree"
    assert opts[2]["value"] == "dont_know"
    assert opts[2]["label"] == "Not sure"


def test_export_branch_actions_and_targets(survey):
    g = _add_group(survey, name="Flow")
    other = _add_group(survey, name="Exit")
    q_source = SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Gate",
        type=SurveyQuestion.Types.YESNO,
        options=[{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}],
        order=0,
    )
    q_target = SurveyQuestion.objects.create(
        survey=survey,
        group=other,
        text="Detail",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )
    SurveyQuestionCondition.objects.create(
        question=q_source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_question=q_target,
        order=0,
    )
    SurveyQuestionCondition.objects.create(
        question=q_source,
        operator=SurveyQuestionCondition.Operator.GREATER_THAN,
        value="3",
        action=SurveyQuestionCondition.Action.SHOW,
        target_question=q_target,
        order=1,
    )
    SurveyQuestionCondition.objects.create(
        question=q_source,
        operator=SurveyQuestionCondition.Operator.NOT_EXISTS,
        value="",
        action=SurveyQuestionCondition.Action.END_SURVEY,
        order=2,
    )
    md = _export_survey_to_markdown(survey)
    assert "? when eq yes -> {detail}" in md
    assert "? show when gt 3 -> {detail}" in md
    # 'end' carries no target.
    assert "? end when not_exists" in md
    parsed = parse_bulk_markdown(md)
    branches = parsed[0]["questions"][0]["branches"]
    actions = [b["action"] for b in branches]
    assert SurveyQuestionCondition.Action.JUMP_TO in actions
    assert SurveyQuestionCondition.Action.SHOW in actions
    assert SurveyQuestionCondition.Action.END_SURVEY in actions
    # NOT_EXISTS needs no comparison value.
    end_branch = next(
        b for b in branches if b["action"] == SurveyQuestionCondition.Action.END_SURVEY
    )
    assert end_branch["value"] == ""


def test_export_branch_section_target(survey):
    g = _add_group(survey, name="Intro")
    dest = _add_group(survey, name="Medical History")
    q_source = SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="History?",
        type=SurveyQuestion.Types.YESNO,
        options=[{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}],
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=dest,
        text="Condition",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )
    SurveyQuestionCondition.objects.create(
        question=q_source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=dest,
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "# Medical History {medical-history}" in md
    assert "? when eq yes -> #medical-history" in md
    parsed = parse_bulk_markdown_with_collections(md)
    q = parsed["groups"][0]["questions"][0]
    assert q["branches"][0]["target_kind"] == "section"
    assert q["branches"][0]["target_ref"] == "medical-history"


def test_export_empty_options_does_not_crash(survey):
    """Questions with empty/plain-string options must export without errors."""
    g = _add_group(survey, name="Mixed")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Plain options",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=["Alpha", "Beta"],
        order=0,
    )
    md = _export_survey_to_markdown(survey)
    assert "- Alpha" in md
    assert "- Beta" in md


def test_full_round_trip_preserves_structure(survey):
    """A builder-shaped survey exports and re-imports to the same shapes."""
    g = _add_group(survey, name="Round")
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Status",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[
            {"label": "A", "value": "A"},
            {
                "label": "B",
                "value": "B",
                "followup_text": {"enabled": True, "label": "Explain B"},
            },
        ],
        required=True,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=g,
        text="Notes",
        type=SurveyQuestion.Types.LONG_TEXT,
        options=[],
        order=1,
    )
    md = _export_survey_to_markdown(survey)
    parsed = parse_bulk_markdown(md)
    q = parsed[0]["questions"][0]
    assert q["required"] is True
    assert q["final_type"] == "mc_single"
    assert q["final_options"][1]["followup_text"]["label"] == "Explain B"
    notes = parsed[0]["questions"][1]
    assert notes["final_type"] == "long_text"
