"""Tests for the DELPHI outline grammar + import/export round-trip.

Covers parse_bulk_markdown_with_collections (DELPHI block + ~ round: suffix
+ round window config), the bulk upload application, and
_export_survey_to_markdown round-trip.
"""

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)
from checktick_app.surveys.views import _export_survey_to_markdown

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="delphi_outline@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


# --- parser ---


def test_parse_delphi_block_basic():
    md = """\
DELPHI
  anchor: enrolment
  min_rounds: 2
  max_rounds: 3
  show_progress: true
  allow_revision: true
  round Round 1: 0 .. 14
  round Round 2: 14 .. 28

# Demographics {demographics}    ~ round:Round 1, round:Round 2
## Age {age}
(text)

# Round 1 questions {r1}    ~ round:Round 1
## R1Q {r1q}
(text)

# Round 2 questions {r2}    ~ round:Round 2
## R2Q {r2q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"] is not None
    assert parsed["delphi"]["anchor"] == "enrolment"
    assert parsed["delphi"]["min_rounds"] == 2
    assert parsed["delphi"]["max_rounds"] == 3
    assert parsed["delphi"]["show_progress"] is True
    assert parsed["delphi"]["allow_revision"] is True
    # Round order is first-appearance order (from the config lines).
    assert parsed["delphi"]["round_order"] == ["Round 1", "Round 2"]
    windows = parsed["delphi"]["round_windows"]
    assert windows["Round 1"] == {"start_offset_days": 0, "end_offset_days": 14}
    assert windows["Round 2"] == {"start_offset_days": 14, "end_offset_days": 28}
    groups = {g["name"]: g for g in parsed["groups"]}
    assert groups["Demographics"]["delphi_rounds"] == ["Round 1", "Round 2"]
    assert groups["Round 1 questions"]["delphi_rounds"] == ["Round 1"]
    assert groups["Round 2 questions"]["delphi_rounds"] == ["Round 2"]


def test_parse_delphi_block_default_anchor():
    md = """\
DELPHI

# A {a}    ~ round:R1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"]["anchor"] == "enrolment"


def test_parse_delphi_block_survey_open_anchor():
    md = """\
DELPHI
  anchor: survey_open

# A {a}    ~ round:R1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"]["anchor"] == "survey_open"


def test_parse_delphi_block_invalid_anchor_falls_back():
    md = """\
DELPHI
  anchor: unknown

# A {a}    ~ round:R1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"]["anchor"] == "enrolment"


def test_parse_delphi_round_window_single_value():
    md = """\
DELPHI
  round Later: 100

# A {a}    ~ round:Later
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"]["round_windows"]["Later"] == {
        "start_offset_days": 100,
        "end_offset_days": None,
    }


def test_parse_group_without_round_suffix_is_no_rounds():
    md = """\
DELPHI
  round Round 1: 0 .. 14

# Demographics {demographics}
## Age {age}
(text)

# Round 1 {r1}    ~ round:Round 1
## R1Q {r1q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    groups = {g["name"]: g for g in parsed["groups"]}
    # Demographics (no ~ round:) is in no rounds (unreachable).
    assert groups["Demographics"]["delphi_rounds"] == []


def test_parse_no_delphi_block():
    md = """\
# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"] is None


def test_parse_delphi_round_order_from_suffix_only():
    """A round referenced only via ~ round: (no config line) is still ordered."""
    md = """\
DELPHI

# A {a}    ~ round:Round 2, round:Round 1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    # Rounds appear in first-appearance order from the suffix.
    assert parsed["delphi"]["round_order"] == ["Round 2", "Round 1"]
    # No window config → empty windows dict.
    assert parsed["delphi"]["round_windows"] == {}


def test_parse_delphi_block_config_values():
    md = """\
DELPHI
  min_rounds: 3
  max_rounds: 5
  show_progress: false
  allow_revision: false

# A {a}    ~ round:R1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["delphi"]["min_rounds"] == 3
    assert parsed["delphi"]["max_rounds"] == 5
    assert parsed["delphi"]["show_progress"] is False
    assert parsed["delphi"]["allow_revision"] is False


# --- bulk upload application ---


@pytest.fixture
def delphi_survey_for_upload(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Upload",
        slug="upload-delphi",
    )
    return s


@pytest.mark.django_db
def test_bulk_upload_applies_delphi_config(client, delphi_survey_for_upload, owner):
    from django.urls import reverse

    md = """\
DELPHI
  anchor: survey_open
  min_rounds: 2
  max_rounds: 4
  round Round 1: 0 .. 14
  round Round 2: 14 .. 28

# Demographics {demographics}    ~ round:Round 1, round:Round 2
## Age {age}
(text)

# Round 1 {r1}    ~ round:Round 1
## R1Q {r1q}
(text)

# Round 2 {r2}    ~ round:Round 2
## R2Q {r2q}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": delphi_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    delphi_survey_for_upload.refresh_from_db()
    assert delphi_survey_for_upload.layout == Survey.Layout.DELPHI
    menu = DelphiMenu.objects.get(survey=delphi_survey_for_upload)
    assert menu.anchor == DelphiMenu.Anchor.SURVEY_OPEN
    assert menu.min_rounds == 2
    assert menu.max_rounds == 4
    rounds = list(menu.rounds.order_by("order"))
    assert [r.name for r in rounds] == ["Round 1", "Round 2"]
    r1 = next(r for r in rounds if r.name == "Round 1")
    r2 = next(r for r in rounds if r.name == "Round 2")
    assert r1.start_offset_days == 0
    assert r1.end_offset_days == 14
    assert r2.start_offset_days == 14
    assert r2.end_offset_days == 28
    # Check group assignments.
    demo = QuestionGroup.objects.get(name="Demographics")
    r1_grp = QuestionGroup.objects.get(name="Round 1")
    r2_grp = QuestionGroup.objects.get(name="Round 2")
    assert set(r1.groups.values_list("id", flat=True)) == {demo.id, r1_grp.id}
    assert set(r2.groups.values_list("id", flat=True)) == {demo.id, r2_grp.id}


@pytest.mark.django_db
def test_bulk_upload_delphi_round_no_window_defaults(
    client, delphi_survey_for_upload, owner
):
    """A round referenced only via ~ round: (no config line) defaults to
    start=0, end=None (open from the anchor)."""
    from django.urls import reverse

    md = """\
DELPHI

# A {a}    ~ round:Open
## Q {q}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": delphi_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    menu = DelphiMenu.objects.get(survey=delphi_survey_for_upload)
    rnd = menu.rounds.get(name="Open")
    assert rnd.start_offset_days == 0
    assert rnd.end_offset_days is None


# --- export round-trip ---


@pytest.mark.django_db
def test_export_emits_delphi_block(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Export",
        slug="export-delphi",
        layout=Survey.Layout.DELPHI,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_r1 = QuestionGroup.objects.create(name="Round1", owner=owner)
    g_r2 = QuestionGroup.objects.create(name="Round2", owner=owner)
    s.question_groups.add(g_demo, g_r1, g_r2)
    for g, t in [(g_demo, "Age"), (g_r1, "R1Q"), (g_r2, "R2Q")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    menu = DelphiMenu.objects.create(
        survey=s,
        anchor=DelphiMenu.Anchor.SURVEY_OPEN,
        min_rounds=2,
        max_rounds=4,
        show_progress=False,
        allow_revision=False,
    )
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=14
    )
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="Round 2", start_offset_days=14, end_offset_days=28
    )
    r1.groups.add(g_demo, g_r1)
    r2.groups.add(g_demo, g_r2)
    exported = _export_survey_to_markdown(s)
    assert "DELPHI" in exported
    assert "anchor: survey_open" in exported
    assert "min_rounds: 2" in exported
    assert "max_rounds: 4" in exported
    assert "show_progress: false" in exported
    assert "allow_revision: false" in exported
    assert "round Round 1: 0 .. 14" in exported
    assert "round Round 2: 14 .. 28" in exported
    assert "~ round:Round 1" in exported
    assert "~ round:Round 2" in exported


@pytest.mark.django_db
def test_export_round_trip(owner, org):
    """Export → import preserves the delphi config + round assignments + windows."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RoundTrip",
        slug="roundtrip-delphi",
        layout=Survey.Layout.DELPHI,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_r1 = QuestionGroup.objects.create(name="Round1", owner=owner)
    g_r2 = QuestionGroup.objects.create(name="Round2", owner=owner)
    s.question_groups.add(g_demo, g_r1, g_r2)
    for g, t in [(g_demo, "Age"), (g_r1, "R1Q"), (g_r2, "R2Q")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    menu = DelphiMenu.objects.create(survey=s, anchor=DelphiMenu.Anchor.ENROLMENT)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=14
    )
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="Round 2", start_offset_days=14, end_offset_days=None
    )
    r1.groups.add(g_demo, g_r1)
    r2.groups.add(g_r2)

    exported = _export_survey_to_markdown(s)
    parsed = parse_bulk_markdown_with_collections(exported)
    assert parsed["delphi"] is not None
    assert parsed["delphi"]["anchor"] == "enrolment"
    assert set(parsed["delphi"]["round_order"]) == {"Round 1", "Round 2"}
    windows = parsed["delphi"]["round_windows"]
    assert windows["Round 1"] == {"start_offset_days": 0, "end_offset_days": 14}
    assert windows["Round 2"] == {"start_offset_days": 14, "end_offset_days": None}
    groups = {g["name"]: g for g in parsed["groups"]}
    assert set(groups["Demographics"]["delphi_rounds"]) == {"Round 1"}
    assert groups["Round1"]["delphi_rounds"] == ["Round 1"]
    assert groups["Round2"]["delphi_rounds"] == ["Round 2"]


@pytest.mark.django_db
def test_export_delphi_open_ended_round(owner, org):
    """A round with no end_offset_days exports as 'round <name>: <start>'."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="OpenEnded",
        slug="open-ended-delphi",
        layout=Survey.Layout.DELPHI,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = DelphiMenu.objects.create(survey=s)
    rnd = DelphiRound.objects.create(
        menu=menu, order=0, name="Open", start_offset_days=0, end_offset_days=None
    )
    rnd.groups.add(g)
    exported = _export_survey_to_markdown(s)
    assert "round Open: 0" in exported
    # Should NOT contain the .. range syntax.
    assert "round Open: 0 .." not in exported
