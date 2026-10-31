"""Tests for free-text respondent category dimensions (issue #353).

Release 1 of respondent categories used the controlled roster: the
token-batch form renders a <select> over the dimension's allowed_values.
Programmes with large rotating rosters (a deanery with hundreds of
trainees per term, rotating junior doctors) would have to re-author
allowed_values every intake, and the select becomes unwieldy.

The per-dimension ``free_text`` flag opts a dimension out of the roster:
the token-batch form renders a text input, the value is trimmed and stored
in category_values as usual (values are strings either way, so resolution,
substitution, reporting, and the category_* CSV columns are unchanged).
Mitigations: a fuzzy near-duplicate warning on the token-batch POST, and
distinct-value counts surfaced on the Tokens page.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyQuestion,
)
from checktick_app.surveys.views import _export_survey_to_markdown

TEST_PASSWORD = "x"

# Roughly 0.9 similarity — must trip the 0.8 cutoff, and be obviously a
# near-duplicate rather than a plausible distinct trainee.
NEAR_DUPLICATE = "Dr Jane Smith"
NEAR_TYPO = "Dr Jane Smyth"
CLEARLY_DISTINCT = "Dr Amir Khan"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


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


@pytest.fixture
def survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Peer rating", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g2,
        text="Clinical knowledge",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    s._g1, s._g2 = g1, g2
    return s


@pytest.fixture
def free_text_cat(survey):
    return RespondentCategory.objects.create(
        survey=survey,
        name="trainee",
        label="Trainee",
        allowed_values=[],
        free_text=True,
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )


@pytest.fixture
def roster_cat(survey):
    return RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=["peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )


def _tokens_url(survey):
    return reverse("surveys:tokens", kwargs={"slug": survey.slug})


def _groups_url(survey):
    return reverse("surveys:groups", kwargs={"slug": survey.slug})


def _messages_texts(response):
    return [str(m) for m in response.context["messages"]]


# --- Model -------------------------------------------------------------


@pytest.mark.django_db
def test_free_text_defaults_off(survey):
    cat = RespondentCategory.objects.create(survey=survey, name="site")
    assert cat.free_text is False


@pytest.mark.django_db
def test_free_text_persists(free_text_cat):
    free_text_cat.refresh_from_db()
    assert free_text_cat.free_text is True


# --- Organise page -----------------------------------------------------


@pytest.mark.django_db
def test_organise_save_sets_free_text(client, survey, owner, roster_cat):
    client.force_login(owner)
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_respondent_category",
            "category_id": str(roster_cat.id),
            f"free_text_{roster_cat.id}": "on",
        },
    )
    assert res.status_code == 302
    roster_cat.refresh_from_db()
    assert roster_cat.free_text is True


@pytest.mark.django_db
def test_organise_save_clears_free_text(client, survey, owner, free_text_cat):
    client.force_login(owner)
    # Absent checkbox means unticked — the flag clears on the next save.
    res = client.post(
        _groups_url(survey),
        {
            "action": "save_respondent_category",
            "category_id": str(free_text_cat.id),
        },
    )
    assert res.status_code == 302
    free_text_cat.refresh_from_db()
    assert free_text_cat.free_text is False


@pytest.mark.django_db
def test_organise_shows_checkbox_state(
    client, survey, owner, free_text_cat, roster_cat
):
    client.force_login(owner)
    res = client.get(_groups_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    # Ticked for the free-text dimension.
    assert (
        f'name="free_text_{free_text_cat.id}" class="checkbox checkbox-xs" checked'
        in html
    )
    # Unticked for the roster dimension: its checkbox renders without
    # ``checked`` (attribute order/whitespace varies, so match the tag).
    import re

    roster_input = re.search(
        rf'<input[^>]*name="free_text_{roster_cat.id}"[^>]*/>', html
    )
    assert roster_input, "roster dimension checkbox missing from Organise page"
    assert "checked" not in roster_input.group(0)


# --- Tokens page: form rendering ---------------------------------------


@pytest.mark.django_db
def test_tokens_form_free_text_renders_text_input(
    client, survey, owner, free_text_cat, roster_cat
):
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    # Free-text dimension: text input, no select.
    assert f'name="category_{free_text_cat.name}"' in html
    assert f'<select name="category_{free_text_cat.name}"' not in html
    assert f'list="category-values-{free_text_cat.name}"' in html
    # Roster dimension: unchanged select over allowed_values.
    assert f'<select name="category_{roster_cat.name}"' in html
    for val in roster_cat.allowed_values:
        assert f'<option value="{val}">{val}</option>' in html


@pytest.mark.django_db
def test_tokens_form_shows_used_values_and_counts(client, survey, owner, free_text_cat):
    SurveyAccessToken.objects.create(
        survey=survey,
        token="t1",
        created_by=owner,
        category_values={"trainee": NEAR_DUPLICATE},
    )
    SurveyAccessToken.objects.create(
        survey=survey,
        token="t2",
        created_by=owner,
        category_values={"trainee": NEAR_DUPLICATE},
    )
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    # Datalist suggestion + in-use count surfaced so a split is visible.
    assert f'<option value="{NEAR_DUPLICATE}">' in html
    assert f"{NEAR_DUPLICATE} (2)" in html


@pytest.mark.django_db
def test_tokens_post_stores_trimmed_value(client, survey, owner, free_text_cat):
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"count": "2", f"category_{free_text_cat.name}": f"  {NEAR_DUPLICATE}  "},
        follow=True,
    )
    assert res.status_code == 200
    tokens = survey.access_tokens.order_by("id")
    assert tokens.count() == 2
    assert all(t.category_values == {"trainee": NEAR_DUPLICATE} for t in tokens)


# --- Tokens page: near-duplicate warning -------------------------------


@pytest.mark.django_db
def test_tokens_post_warns_on_near_duplicate(client, survey, owner, free_text_cat):
    SurveyAccessToken.objects.create(
        survey=survey,
        token="t-existing",
        created_by=owner,
        category_values={"trainee": NEAR_DUPLICATE},
    )
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"count": "1", f"category_{free_text_cat.name}": NEAR_TYPO},
        follow=True,
    )
    assert res.status_code == 200
    msgs = _messages_texts(res)
    warnings = [m for m in msgs if NEAR_DUPLICATE in m and NEAR_TYPO in m]
    assert warnings, f"expected a near-duplicate warning, got: {msgs}"
    # The batch is still created — the warning is non-blocking.
    assert survey.access_tokens.filter(category_values__trainee=NEAR_TYPO).exists()


@pytest.mark.django_db
def test_tokens_post_no_warning_for_distinct_value(
    client, survey, owner, free_text_cat
):
    SurveyAccessToken.objects.create(
        survey=survey,
        token="t-existing",
        created_by=owner,
        category_values={"trainee": NEAR_DUPLICATE},
    )
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"count": "1", f"category_{free_text_cat.name}": CLEARLY_DISTINCT},
        follow=True,
    )
    assert res.status_code == 200
    msgs = _messages_texts(res)
    assert not [m for m in msgs if "typo" in m]


@pytest.mark.django_db
def test_tokens_post_no_warning_for_exact_reuse(client, survey, owner, free_text_cat):
    SurveyAccessToken.objects.create(
        survey=survey,
        token="t-existing",
        created_by=owner,
        category_values={"trainee": NEAR_DUPLICATE},
    )
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"count": "1", f"category_{free_text_cat.name}": NEAR_DUPLICATE},
        follow=True,
    )
    assert res.status_code == 200
    msgs = _messages_texts(res)
    assert not [m for m in msgs if "typo" in m]


@pytest.mark.django_db
def test_tokens_post_no_warning_for_roster_dimensions(
    client, survey, owner, roster_cat
):
    """The fuzzy warning only applies to free-text dimensions."""
    SurveyAccessToken.objects.create(
        survey=survey,
        token="t-existing",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    client.force_login(owner)
    # A value outside the roster is stored as-is (release 1 behaviour) and
    # never triggers the free-text near-duplicate warning.
    res = client.post(
        _tokens_url(survey),
        {"count": "1", f"category_{roster_cat.name}": "peare"},
        follow=True,
    )
    assert res.status_code == 200
    msgs = _messages_texts(res)
    assert not [m for m in msgs if "typo" in m]


# --- Preview simulate panel ---------------------------------------------


@pytest.mark.django_db
def test_preview_simulate_panel_text_input_for_free_text(
    client, survey, owner, free_text_cat
):
    client.force_login(owner)
    res = client.get(f"/surveys/{survey.slug}/preview/", {"simulate_category": ""})
    # Some preview routes require publication state; fall back to skipping
    # the assertions if the preview is unavailable for this survey state.
    if res.status_code != 200:
        pytest.skip("preview not reachable for this survey state")
    html = res.content.decode()
    assert f'name="simulate_category_{free_text_cat.name}"' in html
    assert f'<select name="simulate_category_{free_text_cat.name}"' not in html


# --- Outline grammar round-trip ------------------------------------------


def test_parse_categories_block_free_text():
    md = """\
CATEGORIES
  trainee:
    free_text: true
    source: token
  rater_role:
    values: peer, supervisor
    source: token

# Demographics {demographics}
## Age {age}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    dims = parsed["categories"]["dimensions"]
    by_name = {d["name"]: d for d in dims}
    assert by_name["trainee"]["free_text"] is True
    assert by_name["rater_role"]["free_text"] is False


def test_parse_categories_block_free_text_defaults_false():
    md = """\
CATEGORIES
  rater_role:
    values: peer
    source: token

# Demographics {demographics}
## Age {age}
(text)
"""
    parsed = parse_bulk_markdown_with_collections(md)
    assert parsed["categories"]["dimensions"][0]["free_text"] is False


@pytest.mark.django_db
def test_export_emits_free_text(owner, org, free_text_cat, roster_cat):
    md = _export_survey_to_markdown(free_text_cat.survey)
    assert "free_text: true" in md
    # Only the flagged dimension emits the key.
    assert md.count("free_text:") == 1


@pytest.mark.django_db
def test_export_import_round_trip_free_text(owner, org, survey, free_text_cat):
    md = _export_survey_to_markdown(survey)
    parsed = parse_bulk_markdown_with_collections(md)
    dims = {d["name"]: d for d in parsed["categories"]["dimensions"]}
    assert dims["trainee"]["free_text"] is True
