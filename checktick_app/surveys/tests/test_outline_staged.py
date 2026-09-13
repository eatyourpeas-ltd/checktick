"""Tests for the STAGED outline grammar + import/export round-trip (step 7).

Covers parse_bulk_markdown_with_collections (STAGED block + ~ phase: suffix
+ phase window config), the bulk upload application, and
_export_survey_to_markdown round-trip.
"""

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    StagedMenu,
    StagedPhase,
    Survey,
    SurveyQuestion,
)
from checktick_app.surveys.views import _export_survey_to_markdown

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


# --- parser ---


def test_parse_staged_block_basic():
    md = """\
STAGED
  anchor: enrolment
  phase Baseline: 0 .. 14
  phase Follow-up: 14 .. 28
  phase Review: 180

# Demographics {demographics}    ~ phase:Baseline, phase:Follow-up
## Age {age}
(text)

# Baseline {baseline}    ~ phase:Baseline
## BQ {bq}
(text)

# Follow-up {followup}    ~ phase:Follow-up
## FQ {fq}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["staged"] is not None
    assert parsed["staged"]["anchor"] == "enrolment"
    # Phase order is first-appearance order (from the config lines).
    assert parsed["staged"]["phase_order"] == ["Baseline", "Follow-up", "Review"]
    windows = parsed["staged"]["phase_windows"]
    assert windows["Baseline"] == {"start_offset_days": 0, "end_offset_days": 14}
    assert windows["Follow-up"] == {"start_offset_days": 14, "end_offset_days": 28}
    # Review has no end (open-ended).
    assert windows["Review"] == {"start_offset_days": 180, "end_offset_days": None}
    groups = {g["name"]: g for g in parsed["groups"]}
    assert groups["Demographics"]["staged_phases"] == ["Baseline", "Follow-up"]
    assert groups["Baseline"]["staged_phases"] == ["Baseline"]
    assert groups["Follow-up"]["staged_phases"] == ["Follow-up"]


def test_parse_staged_block_default_anchor():
    md = """\
STAGED

# A {a}    ~ phase:p1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["staged"]["anchor"] == "enrolment"


def test_parse_staged_block_survey_open_anchor():
    md = """\
STAGED
  anchor: survey_open

# A {a}    ~ phase:p1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["staged"]["anchor"] == "survey_open"


def test_parse_staged_block_invalid_anchor_falls_back():
    md = """\
STAGED
  anchor: unknown

# A {a}    ~ phase:p1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["staged"]["anchor"] == "enrolment"


def test_parse_staged_phase_window_single_value():
    md = """\
STAGED
  phase Later: 100

# A {a}    ~ phase:Later
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["staged"]["phase_windows"]["Later"] == {
        "start_offset_days": 100,
        "end_offset_days": None,
    }


def test_parse_group_without_phase_suffix_is_no_phases():
    md = """\
STAGED
  phase Baseline: 0 .. 14

# Demographics {demographics}
## Age {age}
(text)

# Baseline {baseline}    ~ phase:Baseline
## BQ {bq}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    groups = {g["name"]: g for g in parsed["groups"]}
    # Demographics (no ~ phase:) is in no phases (unreachable).
    assert groups["Demographics"]["staged_phases"] == []


def test_parse_no_staged_block():
    md = """\
# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["staged"] is None


def test_parse_staged_phase_order_from_suffix_only():
    """A phase referenced only via ~ phase: (no config line) is still ordered."""
    md = """\
STAGED

# A {a}    ~ phase:Follow-up, phase:Baseline
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    # Phases appear in first-appearance order from the suffix.
    assert parsed["staged"]["phase_order"] == ["Follow-up", "Baseline"]
    # No window config → empty windows dict.
    assert parsed["staged"]["phase_windows"] == {}


# --- bulk upload application ---


@pytest.fixture
def staged_survey_for_upload(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Upload",
        slug="upload-staged",
    )
    return s


@pytest.mark.django_db
def test_bulk_upload_applies_staged_config(client, staged_survey_for_upload, owner):
    from django.urls import reverse

    md = """\
STAGED
  anchor: survey_open
  phase Baseline: 0 .. 14
  phase Follow-up: 14 .. 28

# Demographics {demographics}    ~ phase:Baseline, phase:Follow-up
## Age {age}
(text)

# Baseline {baseline}    ~ phase:Baseline
## BQ {bq}
(text)

# Follow-up {followup}    ~ phase:Follow-up
## FQ {fq}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": staged_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    staged_survey_for_upload.refresh_from_db()
    assert staged_survey_for_upload.layout == Survey.Layout.STAGED
    menu = StagedMenu.objects.get(survey=staged_survey_for_upload)
    assert menu.anchor == StagedMenu.Anchor.SURVEY_OPEN
    phases = list(menu.phases.order_by("order"))
    assert [p.name for p in phases] == ["Baseline", "Follow-up"]
    baseline = next(p for p in phases if p.name == "Baseline")
    followup = next(p for p in phases if p.name == "Follow-up")
    assert baseline.start_offset_days == 0
    assert baseline.end_offset_days == 14
    assert followup.start_offset_days == 14
    assert followup.end_offset_days == 28
    # Check group assignments.
    demo = QuestionGroup.objects.get(name="Demographics")
    base_grp = QuestionGroup.objects.get(name="Baseline")
    follow_grp = QuestionGroup.objects.get(name="Follow-up")
    assert set(baseline.groups.values_list("id", flat=True)) == {demo.id, base_grp.id}
    assert set(followup.groups.values_list("id", flat=True)) == {
        demo.id,
        follow_grp.id,
    }


@pytest.mark.django_db
def test_bulk_upload_staged_phase_no_window_defaults(
    client, staged_survey_for_upload, owner
):
    """A phase referenced only via ~ phase: (no config line) defaults to
    start=0, end=None (open from the anchor)."""
    from django.urls import reverse

    md = """\
STAGED

# A {a}    ~ phase:Open
## Q {q}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": staged_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    menu = StagedMenu.objects.get(survey=staged_survey_for_upload)
    phase = menu.phases.get(name="Open")
    assert phase.start_offset_days == 0
    assert phase.end_offset_days is None


# --- export round-trip ---


@pytest.mark.django_db
def test_export_emits_staged_block(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Export",
        slug="export-staged",
        layout=Survey.Layout.STAGED,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_base = QuestionGroup.objects.create(name="Baseline", owner=owner)
    g_follow = QuestionGroup.objects.create(name="Followup", owner=owner)
    s.question_groups.add(g_demo, g_base, g_follow)
    for g, t in [(g_demo, "Age"), (g_base, "BQ"), (g_follow, "FQ")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    menu = StagedMenu.objects.create(survey=s, anchor=StagedMenu.Anchor.SURVEY_OPEN)
    p1 = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    p2 = StagedPhase.objects.create(
        menu=menu, name="Followup", order=2, start_offset_days=14, end_offset_days=28
    )
    p1.groups.add(g_demo, g_base)
    p2.groups.add(g_demo, g_follow)
    exported = _export_survey_to_markdown(s)
    assert "STAGED" in exported
    assert "anchor: survey_open" in exported
    assert "phase Baseline: 0 .. 14" in exported
    assert "phase Followup: 14 .. 28" in exported
    assert "~ phase:Baseline" in exported
    assert "~ phase:Followup" in exported


@pytest.mark.django_db
def test_export_round_trip(owner, org):
    """Export → import preserves the staged config + phase assignments + windows."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RoundTrip",
        slug="roundtrip-staged",
        layout=Survey.Layout.STAGED,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_base = QuestionGroup.objects.create(name="Baseline", owner=owner)
    g_review = QuestionGroup.objects.create(name="Review", owner=owner)
    s.question_groups.add(g_demo, g_base, g_review)
    for g, t in [(g_demo, "Age"), (g_base, "BQ"), (g_review, "RQ")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    menu = StagedMenu.objects.create(survey=s, anchor=StagedMenu.Anchor.ENROLMENT)
    p1 = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    p2 = StagedPhase.objects.create(
        menu=menu, name="Review", order=2, start_offset_days=180, end_offset_days=None
    )
    p1.groups.add(g_demo, g_base)
    p2.groups.add(g_review)

    exported = _export_survey_to_markdown(s)
    parsed = parse_bulk_markdown_with_collections(exported)
    assert parsed["staged"] is not None
    assert parsed["staged"]["anchor"] == "enrolment"
    assert set(parsed["staged"]["phase_order"]) == {"Baseline", "Review"}
    windows = parsed["staged"]["phase_windows"]
    assert windows["Baseline"] == {"start_offset_days": 0, "end_offset_days": 14}
    assert windows["Review"] == {"start_offset_days": 180, "end_offset_days": None}
    groups = {g["name"]: g for g in parsed["groups"]}
    assert set(groups["Demographics"]["staged_phases"]) == {"Baseline"}
    assert groups["Baseline"]["staged_phases"] == ["Baseline"]
    assert groups["Review"]["staged_phases"] == ["Review"]
