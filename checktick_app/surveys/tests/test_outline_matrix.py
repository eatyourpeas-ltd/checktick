"""Tests for the MATRIX outline grammar + import/export round-trip (step 5).

Covers parse_bulk_markdown_with_collections (MATRIX block + config lines),
the bulk upload application, and _export_survey_to_markdown round-trip.
"""

import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    MatrixMenu,
    Organization,
    QuestionGroup,
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


def test_parse_matrix_block_basic():
    md = """\
MATRIX
  prompt: "Choose a section to begin"
  order: participant
  allow_revisit: false

# Demographics {demographics}
## Name {name}
(text)

# History {history}
## Condition {condition}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["matrix"] is not None
    assert parsed["matrix"]["prompt_text"] == "Choose a section to begin"
    assert parsed["matrix"]["order_mode"] == "participant"
    assert parsed["matrix"]["allow_revisit"] is False


def test_parse_matrix_block_defaults():
    md = """\
MATRIX

# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["matrix"] is not None
    assert parsed["matrix"]["prompt_text"] == (
        "Click a section to begin. You can complete them in any order."
    )
    assert parsed["matrix"]["order_mode"] == "authored"
    assert parsed["matrix"]["allow_revisit"] is True


def test_parse_matrix_block_single_quotes():
    md = """\
MATRIX
  prompt: 'Single quoted prompt'

# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["matrix"]["prompt_text"] == "Single quoted prompt"


def test_parse_matrix_block_invalid_order_falls_back():
    md = """\
MATRIX
  order: invalid

# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["matrix"]["order_mode"] == "authored"


def test_parse_matrix_block_allow_revisit_yes():
    md = """\
MATRIX
  allow_revisit: yes

# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["matrix"]["allow_revisit"] is True


def test_parse_no_matrix_block():
    md = """\
# A {a}
## Q {q}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["matrix"] is None


# --- bulk upload application ---


@pytest.fixture
def matrix_survey_for_upload(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Upload",
        slug="upload-matrix",
    )
    return s


@pytest.mark.django_db
def test_bulk_upload_applies_matrix_config(client, matrix_survey_for_upload, owner):
    from django.urls import reverse

    md = """\
MATRIX
  prompt: "Pick a section"
  order: participant
  allow_revisit: false

# Demographics {demographics}
## Name {name}
(text)

# History {history}
## Condition {condition}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": matrix_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    matrix_survey_for_upload.refresh_from_db()
    assert matrix_survey_for_upload.layout == Survey.Layout.MATRIX
    menu = MatrixMenu.objects.get(survey=matrix_survey_for_upload)
    assert menu.prompt_text == "Pick a section"
    assert menu.order_mode == MatrixMenu.OrderMode.PARTICIPANT
    assert menu.allow_revisit is False


@pytest.mark.django_db
def test_bulk_upload_matrix_defaults(client, matrix_survey_for_upload, owner):
    from django.urls import reverse

    md = """\
MATRIX

# A {a}
## Q {q}
(text)
"""
    client.force_login(owner)
    url = reverse("surveys:bulk_upload", kwargs={"slug": matrix_survey_for_upload.slug})
    res = client.post(url, {"markdown": md})
    assert res.status_code in (200, 302)
    menu = MatrixMenu.objects.get(survey=matrix_survey_for_upload)
    assert menu.prompt_text == (
        "Click a section to begin. You can complete them in any order."
    )
    assert menu.order_mode == MatrixMenu.OrderMode.AUTHORED
    assert menu.allow_revisit is True


# --- export round-trip ---


@pytest.mark.django_db
def test_export_emits_matrix_block(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Export",
        slug="export-matrix",
        layout=Survey.Layout.MATRIX,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="History", owner=owner)
    s.question_groups.add(g1, g2)
    for g, t in [(g1, "Name"), (g2, "Condition")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    MatrixMenu.objects.create(
        survey=s,
        prompt_text="Pick a section",
        order_mode=MatrixMenu.OrderMode.PARTICIPANT,
        allow_revisit=False,
    )
    exported = _export_survey_to_markdown(s)
    assert "MATRIX" in exported
    assert 'prompt: "Pick a section"' in exported
    assert "order: participant" in exported
    assert "allow_revisit: false" in exported


@pytest.mark.django_db
def test_export_round_trip(owner, org):
    """Export → import preserves the matrix config."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RoundTrip",
        slug="roundtrip-matrix",
        layout=Survey.Layout.MATRIX,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="History", owner=owner)
    s.question_groups.add(g1, g2)
    for g, t in [(g1, "Name"), (g2, "Condition")]:
        SurveyQuestion.objects.create(
            survey=s, group=g, text=t, type=SurveyQuestion.Types.TEXT, order=0
        )
    MatrixMenu.objects.create(
        survey=s,
        prompt_text="Choose a section",
        order_mode=MatrixMenu.OrderMode.PARTICIPANT,
        allow_revisit=False,
    )

    exported = _export_survey_to_markdown(s)
    parsed = parse_bulk_markdown_with_collections(exported)
    assert parsed["matrix"] is not None
    assert parsed["matrix"]["prompt_text"] == "Choose a section"
    assert parsed["matrix"]["order_mode"] == "participant"
    assert parsed["matrix"]["allow_revisit"] is False
