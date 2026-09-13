"""Tests for the RANDOMISED outline grammar + import/export round-trip (step 6).

Covers parse_bulk_markdown_with_collections (RANDOMISED block + ~ arm: suffix),
the bulk upload application, and _export_survey_to_markdown round-trip.
"""

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RandomisedArm,
    RandomisedMenu,
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


def test_parse_randomised_block_basic():
    md = """\
RANDOMISED
  strategy: balanced
  seed: 42

# Demographics {demographics}    ~ arm:intervention, arm:control
## Age {age}
(text)

# Intervention {intervention}    ~ arm:intervention
## Dose {dose}
(text)

# Control {control}    ~ arm:control
## Placebo {placebo}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["randomised"] is not None
    assert parsed["randomised"]["allocation_strategy"] == "balanced"
    assert parsed["randomised"]["seed"] == 42
    # Arm order is first-appearance order.
    assert parsed["randomised"]["arm_order"] == ["intervention", "control"]
    groups = {g["name"]: g for g in parsed["groups"]}
    assert groups["Demographics"]["randomised_arms"] == ["intervention", "control"]
    assert groups["Intervention"]["randomised_arms"] == ["intervention"]
    assert groups["Control"]["randomised_arms"] == ["control"]


def test_parse_randomised_block_no_seed():
    md = """\
RANDOMISED
  strategy: simple

# A {a}    ~ arm:arm1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["randomised"]["allocation_strategy"] == "simple"
    assert parsed["randomised"]["seed"] is None


def test_parse_randomised_block_invalid_seed_ignored():
    md = """\
RANDOMISED
  strategy: balanced
  seed: not-a-number

# A {a}    ~ arm:arm1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["randomised"]["seed"] is None


def test_parse_randomised_block_invalid_strategy_falls_back():
    md = """\
RANDOMISED
  strategy: unknown

# A {a}    ~ arm:arm1
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["randomised"]["allocation_strategy"] == "balanced"


def test_parse_group_without_arm_suffix_is_all_arms():
    md = """\
RANDOMISED
  strategy: balanced

# Demographics {demographics}
## Age {age}
(text)

# Intervention {intervention}    ~ arm:intervention
## Dose {dose}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    groups = {g["name"]: g for g in parsed["groups"]}
    # Demographics has no ~ arm: → empty list → all arms.
    assert groups["Demographics"]["randomised_arms"] == []


def test_parse_no_randomised_block():
    md = """\
# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["randomised"] is None


def test_parse_arm_order_preserves_first_appearance():
    md = """\
RANDOMISED
  strategy: balanced

# Z {z}    ~ arm:control, arm:intervention
## Q {q}
(text)

# A {a}    ~ arm:control
## Q2 {q2}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    # control appears first (in Z), then intervention.
    assert parsed["randomised"]["arm_order"] == ["control", "intervention"]


# --- bulk upload application ---


@pytest.fixture
def rct_survey_for_upload(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Upload",
        slug="upload",
    )
    return s


@pytest.mark.django_db
def test_bulk_upload_page_documents_randomised_syntax(
    client, rct_survey_for_upload, owner
):
    """The bulk upload advanced-features card points to the RCT outline reference."""
    from django.urls import reverse

    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": rct_survey_for_upload.slug})
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    # The advanced-features card lists RCT as an option and links to the
    # outline reference (the inline examples moved to the docs).
    assert "Randomised (RCT)" in html
    assert "/docs/import.md#randomised-rct-layout" in html
    assert "/docs/survey-layouts.md" in html


@pytest.mark.django_db
def test_bulk_upload_applies_randomised_config(client, rct_survey_for_upload, owner):
    from django.urls import reverse

    md = """\
RANDOMISED
  strategy: balanced
  seed: 7

# Demographics {demographics}    ~ arm:intervention, arm:control
## Age {age}
(text)

# Intervention {intervention}    ~ arm:intervention
## Dose {dose}
(text)

# Control {control}    ~ arm:control
## Placebo {placebo}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": rct_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    rct_survey_for_upload.refresh_from_db()
    assert rct_survey_for_upload.layout == Survey.Layout.RCT
    menu = RandomisedMenu.objects.get(survey=rct_survey_for_upload)
    assert menu.allocation_strategy == "balanced"
    assert menu.seed == 7
    arms = list(menu.arms.order_by("order"))
    assert [a.name for a in arms] == ["intervention", "control"]
    # Check group assignments.
    demo = QuestionGroup.objects.get(name="Demographics")
    interv = QuestionGroup.objects.get(name="Intervention")
    ctrl = QuestionGroup.objects.get(name="Control")
    assert set(arms[0].groups.values_list("id", flat=True)) == {demo.id, interv.id}
    assert set(arms[1].groups.values_list("id", flat=True)) == {demo.id, ctrl.id}


@pytest.mark.django_db
def test_bulk_upload_group_without_arm_suffix_in_all_arms(
    client, rct_survey_for_upload, owner
):
    from django.urls import reverse

    md = """\
RANDOMISED
  strategy: balanced

# Demographics {demographics}
## Age {age}
(text)

# Intervention {intervention}    ~ arm:intervention
## Dose {dose}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": rct_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    menu = RandomisedMenu.objects.get(survey=rct_survey_for_upload)
    arms = list(menu.arms.order_by("order"))
    demo = QuestionGroup.objects.get(name="Demographics")
    # Demographics (no ~ arm:) is in all arms.
    assert demo in arms[0].groups.all()
    # Only one arm (intervention) was defined.
    assert len(arms) == 1


# --- export round-trip ---


@pytest.mark.django_db
def test_export_emits_randomised_block(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Export",
        slug="export",
        layout=Survey.Layout.RCT,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_int = QuestionGroup.objects.create(name="Intervention", owner=owner)
    g_ctrl = QuestionGroup.objects.create(name="Control", owner=owner)
    s.question_groups.add(g_demo, g_int, g_ctrl)
    for g, t in [(g_demo, "Age"), (g_int, "Dose"), (g_ctrl, "Placebo")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    menu = RandomisedMenu.objects.create(
        survey=s, allocation_strategy="balanced", seed=42
    )
    arm_int = RandomisedArm.objects.create(menu=menu, name="intervention", order=1)
    arm_ctrl = RandomisedArm.objects.create(menu=menu, name="control", order=2)
    arm_int.groups.add(g_demo, g_int)
    arm_ctrl.groups.add(g_demo, g_ctrl)
    exported = _export_survey_to_markdown(s)
    assert "RANDOMISED" in exported
    assert "strategy: balanced" in exported
    assert "seed: 42" in exported
    assert "~ arm:intervention" in exported
    assert "~ arm:control" in exported


@pytest.mark.django_db
def test_export_round_trip(owner, org):
    """Export → import preserves the RCT config + arm assignments."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RoundTrip",
        slug="roundtrip",
        layout=Survey.Layout.RCT,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_int = QuestionGroup.objects.create(name="Intervention", owner=owner)
    g_ctrl = QuestionGroup.objects.create(name="Control", owner=owner)
    s.question_groups.add(g_demo, g_int, g_ctrl)
    for g, t in [(g_demo, "Age"), (g_int, "Dose"), (g_ctrl, "Placebo")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    menu = RandomisedMenu.objects.create(
        survey=s, allocation_strategy="simple", seed=99
    )
    arm_int = RandomisedArm.objects.create(menu=menu, name="intervention", order=1)
    arm_ctrl = RandomisedArm.objects.create(menu=menu, name="control", order=2)
    arm_int.groups.add(g_demo, g_int)
    arm_ctrl.groups.add(g_demo, g_ctrl)

    exported = _export_survey_to_markdown(s)
    parsed = parse_bulk_markdown_with_collections(exported)
    assert parsed["randomised"] is not None
    assert parsed["randomised"]["allocation_strategy"] == "simple"
    assert parsed["randomised"]["seed"] == 99
    assert set(parsed["randomised"]["arm_order"]) == {"intervention", "control"}
    groups = {g["name"]: g for g in parsed["groups"]}
    assert set(groups["Demographics"]["randomised_arms"]) == {"intervention", "control"}
    assert groups["Intervention"]["randomised_arms"] == ["intervention"]
    assert groups["Control"]["randomised_arms"] == ["control"]
