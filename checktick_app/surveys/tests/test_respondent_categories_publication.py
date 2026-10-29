"""Tests for respondent categories publication workflow (commit 7).

Token batch generation accepts category_values per batch — each token
in the batch carries the same category_values (e.g. {"rater_role": "peer"}
for a peer-rater batch). The token CSV export includes a column per
category dimension.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
)

TEST_PASSWORD = "x"


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
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor", "patient"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    return s


def _tokens_url(survey):
    return reverse("surveys:tokens", kwargs={"slug": survey.slug})


# --- Token batch with category_values ---


@pytest.mark.django_db
def test_token_batch_with_category_values(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"count": "5", "category_rater_role": "peer"},
    )
    assert res.status_code == 302
    tokens = list(SurveyAccessToken.objects.filter(survey=survey))
    assert len(tokens) == 5
    for t in tokens:
        assert t.category_values == {"rater_role": "peer"}


@pytest.mark.django_db
def test_token_batch_without_category_values(client, survey, owner):
    """A batch with no category values creates tokens with empty
    category_values — the dimension falls back to its next resolution
    source at take time."""
    client.force_login(owner)
    res = client.post(_tokens_url(survey), {"count": "3"})
    assert res.status_code == 302
    tokens = list(SurveyAccessToken.objects.filter(survey=survey))
    assert len(tokens) == 3
    for t in tokens:
        assert t.category_values == {}


@pytest.mark.django_db
def test_token_batch_ignores_unknown_dimensions(client, survey, owner):
    """Dimensions not defined on the survey are silently dropped."""
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"count": "2", "category_rater_role": "peer", "category_unknown_dim": "x"},
    )
    assert res.status_code == 302
    tokens = list(SurveyAccessToken.objects.filter(survey=survey))
    assert len(tokens) == 2
    for t in tokens:
        assert t.category_values == {"rater_role": "peer"}
        assert "unknown_dim" not in t.category_values


# --- Tokens page shows category field ---


@pytest.mark.django_db
def test_tokens_page_shows_category_field(client, survey, owner):
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Categories for this batch" in html
    assert "rater_role" in html or "Rater role" in html


@pytest.mark.django_db
def test_tokens_page_no_category_field_without_categories(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain",
        visibility=Survey.Visibility.TOKEN,
    )
    client.force_login(owner)
    res = client.get(_tokens_url(s))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Category values for this batch" not in html


# --- Token CSV export ---


@pytest.mark.django_db
def test_token_csv_export_includes_category_columns(client, survey, owner):
    SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-empty",
        created_by=owner,
        category_values={},
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:tokens_export_csv", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    body = res.content.decode()
    assert "category_rater_role" in body
    lines = body.strip().split("\n")
    # Header + 2 tokens.
    assert len(lines) == 3
    assert "peer" in lines[1]
    # tok-empty has empty category value.
    assert lines[2].rstrip().endswith(",")


@pytest.mark.django_db
def test_token_csv_export_no_categories(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain-csv",
        visibility=Survey.Visibility.TOKEN,
    )
    SurveyAccessToken.objects.create(
        survey=s,
        token="tok-plain",
        created_by=owner,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:tokens_export_csv", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    body = res.content.decode()
    assert "category_" not in body
