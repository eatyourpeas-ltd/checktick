"""Tests for the CATEGORIES outline grammar + import/export round-trip
(commit 6).

Covers parse_bulk_markdown_with_collections (CATEGORIES block + ~ cat:
suffix), the bulk upload application, and _export_survey_to_markdown
round-trip.
"""

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyQuestion,
)
from checktick_app.surveys.views import _export_survey_to_markdown

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


# --- parser ---


def test_parse_categories_block_basic():
    md = """\
CATEGORIES
  rater_role:
    values: self, peer, supervisor, patient
    source: token

# Demographics {demographics}
## Age {age}
(text)

# Peer rating {peer-rating}    ~ cat:rater_role:peer
## Clinical knowledge {clinical-knowledge}
(text)

# Self reflection {self-reflection}    ~ cat:rater_role:self
## What went well {went-well}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["categories"] is not None
    dims = parsed["categories"]["dimensions"]
    assert len(dims) == 1
    assert dims[0]["name"] == "rater_role"
    assert dims[0]["allowed_values"] == ["self", "peer", "supervisor", "patient"]
    assert dims[0]["resolution_source"] == "token"
    # Group rules from ~ cat: suffixes.
    rules = parsed["categories_group_rules"]
    assert "Peer rating" in rules
    assert ("rater_role", "peer") in rules["Peer rating"]
    assert "Self reflection" in rules
    assert ("rater_role", "self") in rules["Self reflection"]
    # Demographics has no ~ cat: suffix → not in rules.
    assert "Demographics" not in rules


def test_parse_categories_block_multiple_dimensions():
    md = """\
CATEGORIES
  rater_role:
    values: self, peer, supervisor
    source: token
  subject:
    values: self
    source: self_select
    question: {subject-id}

# Peer rating {peer-rating}    ~ cat:rater_role:peer
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    dims = parsed["categories"]["dimensions"]
    assert len(dims) == 2
    assert dims[0]["name"] == "rater_role"
    assert dims[1]["name"] == "subject"
    assert dims[1]["resolution_source"] == "self_select"
    assert dims[1]["source_question"] == "subject-id"


def test_parse_categories_block_no_block_returns_none():
    md = """\
# Demographics {demographics}
## Age {age}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["categories"] is None
    assert parsed["categories_group_rules"] == {}


def test_parse_categories_block_empty_values():
    md = """\
CATEGORIES
  rater_role:
    source: token

# Demographics {demographics}
## Age {age}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    dims = parsed["categories"]["dimensions"]
    assert len(dims) == 1
    assert dims[0]["allowed_values"] == []


def test_parse_categories_multiple_values_per_section():
    """A section visible to multiple values of a dimension."""
    md = """\
CATEGORIES
  rater_role:
    values: self, peer, supervisor
    source: token

# Shared {shared}    ~ cat:rater_role:peer, cat:rater_role:supervisor
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    rules = parsed["categories_group_rules"]
    assert "Shared" in rules
    assert ("rater_role", "peer") in rules["Shared"]
    assert ("rater_role", "supervisor") in rules["Shared"]


def test_parse_categories_coexists_with_randomised():
    """CATEGORIES + RANDOMISED on the same survey: ~ cat: and ~ arm:
    coexist on the same heading."""
    md = """\
RANDOMISED
  strategy: balanced
  seed: 7

CATEGORIES
  rater_role:
    values: self, peer
    source: token

# Demographics {demographics}    ~ arm:intervention, arm:control
## Age {age}
(text)

# Peer {peer}    ~ arm:intervention, cat:rater_role:peer
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["randomised"] is not None
    assert parsed["categories"] is not None
    # Both suffixes are extracted.
    assert "Peer" in parsed["categories_group_rules"]
    assert ("rater_role", "peer") in parsed["categories_group_rules"]["Peer"]
    groups = {g["name"]: g for g in parsed["groups"]}
    assert groups["Peer"]["randomised_arms"] == ["intervention"]


# --- bulk upload application ---


@pytest.mark.django_db
def test_bulk_upload_creates_categories(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
    )
    client.force_login(owner)
    md = """\
CATEGORIES
  rater_role:
    values: self, peer, supervisor
    source: token

# Demographics {demographics}
## Age {age}
(text)

# Peer rating {peer-rating}    ~ cat:rater_role:peer
## Q {q}
(text)
"""
    res = client.post(f"/surveys/{s.slug}/bulk-upload/", {"markdown": md})
    assert res.status_code == 302
    cats = list(RespondentCategory.objects.filter(survey=s))
    assert len(cats) == 1
    assert cats[0].name == "rater_role"
    assert cats[0].allowed_values == ["self", "peer", "supervisor"]
    # Check groups created by the bulk upload.
    groups = list(s.question_groups.all())
    group_names = {g.name for g in groups}
    assert "Demographics" in group_names
    assert "Peer rating" in group_names
    # Peer rating group has required_categories.
    peer = next(g for g in groups if g.name == "Peer rating")
    assert peer.required_categories == {"rater_role": ["peer"]}
    # Demographics has no rules.
    demo = next(g for g in groups if g.name == "Demographics")
    assert demo.required_categories == {}


@pytest.mark.django_db
def test_bulk_upload_replaces_existing_categories(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s2",
    )
    RespondentCategory.objects.create(
        survey=s,
        name="old_dim",
        allowed_values=["a", "b"],
    )
    client.force_login(owner)
    md = """\
CATEGORIES
  rater_role:
    values: self, peer
    source: token

# Demographics {demographics}
## Age {age}
(text)
"""
    res = client.post(f"/surveys/{s.slug}/bulk-upload/", {"markdown": md})
    assert res.status_code == 302
    cats = RespondentCategory.objects.filter(survey=s)
    assert cats.count() == 1
    assert cats.first().name == "rater_role"


# --- export round-trip ---


@pytest.mark.django_db
def test_export_categories_block(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s3",
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_peer = QuestionGroup.objects.create(name="Peer rating", owner=owner)
    s.question_groups.add(g_demo, g_peer)
    SurveyQuestion.objects.create(
        survey=s, group=g_demo, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_peer, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
        order=1,
    )
    g_peer.required_categories = {"rater_role": ["peer"]}
    g_peer.save(update_fields=["required_categories"])

    md = _export_survey_to_markdown(s)
    assert "CATEGORIES" in md
    assert "rater_role:" in md
    assert "self, peer, supervisor" in md
    assert "source: token" in md
    # ~ cat: suffix on Peer rating.
    assert "cat:rater_role:peer" in md
    # Demographics has no ~ cat: suffix.
    demo_line = next(line for line in md.splitlines() if "Demographics" in line)
    assert "cat:" not in demo_line


@pytest.mark.django_db
def test_export_import_round_trip(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s4",
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_peer = QuestionGroup.objects.create(name="Peer rating", owner=owner)
    g_self = QuestionGroup.objects.create(name="Self reflection", owner=owner)
    s.question_groups.add(g_demo, g_peer, g_self)
    SurveyQuestion.objects.create(
        survey=s, group=g_demo, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_peer, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_self, text="Q2", type=SurveyQuestion.Types.TEXT, order=0
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
        order=1,
    )
    g_peer.required_categories = {"rater_role": ["peer"]}
    g_peer.save(update_fields=["required_categories"])
    g_self.required_categories = {"rater_role": ["self"]}
    g_self.save(update_fields=["required_categories"])

    md = _export_survey_to_markdown(s)
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["categories"] is not None
    dims = parsed["categories"]["dimensions"]
    assert len(dims) == 1
    assert dims[0]["name"] == "rater_role"
    assert dims[0]["allowed_values"] == ["self", "peer", "supervisor"]
    rules = parsed["categories_group_rules"]
    assert ("rater_role", "peer") in rules.get("Peer rating", [])
    assert ("rater_role", "self") in rules.get("Self reflection", [])
    assert "Demographics" not in rules
