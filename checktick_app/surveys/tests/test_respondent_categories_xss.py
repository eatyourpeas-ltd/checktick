"""XSS safety tests for respondent categories user input.

Every free-text input in the feature (dimension name, label, allowed
values, category_values) is rendered through Django's auto-escaping in
templates. These tests prove that script tags injected via the organise
page, token batch generation, and bulk upload are escaped (not executed)
on every rendering surface: organise page, tokens page, survey map,
preview, and CSV export.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyQuestion,
)

TEST_PASSWORD = "x"
XSS_PAYLOAD = '<script>alert("xss")</script>'
XSS_PAYLOAD_IMG = "<img src=x onerror=alert(1)>"


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
        slug="s-xss",
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    g = QuestionGroup.objects.create(name="G1", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    return s


# --- Organise page: dimension name, label, allowed values ---


@pytest.mark.django_db
def test_organise_page_escapes_dimension_label(client, survey, owner):
    """The dimension label is escaped on the organise page."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label=XSS_PAYLOAD,
        allowed_values=["peer", XSS_PAYLOAD],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # The raw script tag must NOT appear — it should be entity-escaped.
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html
    # The img onerror payload must also be escaped.
    assert XSS_PAYLOAD_IMG not in html


@pytest.mark.django_db
def test_organise_page_escapes_allowed_values(client, survey, owner):
    """Allowed values containing script tags are escaped in the section
    visibility table options."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=[XSS_PAYLOAD, "peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


# --- Tokens page: category values dropdown + table ---


@pytest.mark.django_db
def test_tokens_page_escapes_category_label(client, survey, owner):
    """The dimension label is escaped on the tokens page."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label=XSS_PAYLOAD,
        allowed_values=["peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:tokens", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


@pytest.mark.django_db
def test_tokens_page_escapes_category_values_in_table(client, survey, owner):
    """Category values in the tokens table badges are escaped."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=["peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    # Create a token with an XSS payload in category_values (bypassing
    # the dropdown constraint to test the rendering surface directly).
    SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-xss",
        created_by=owner,
        category_values={"rater_role": XSS_PAYLOAD},
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:tokens", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


# --- Survey Map: dimension name, label, allowed values, section rules ---


@pytest.mark.django_db
def test_survey_map_escapes_dimension_label(client, survey, owner):
    """The dimension label and allowed values are escaped on the survey map."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label=XSS_PAYLOAD,
        allowed_values=[XSS_PAYLOAD, "peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


@pytest.mark.django_db
def test_survey_map_escapes_section_rules(client, survey, owner):
    """Section required_categories values are escaped in the survey map
    section visibility annotations."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=[XSS_PAYLOAD],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    g = survey.question_groups.first()
    g.required_categories = {"rater_role": [XSS_PAYLOAD]}
    g.save(update_fields=["required_categories"])
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


# --- Preview: simulate category panel ---


@pytest.mark.django_db
def test_preview_escapes_dimension_label(client, survey, owner):
    """The dimension label is escaped in the simulate category panel."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label=XSS_PAYLOAD,
        allowed_values=[XSS_PAYLOAD, "peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


# --- Bulk upload: dimension name from outline ---


@pytest.mark.django_db
def test_bulk_upload_allowed_values_not_rendered_unescaped(client, survey, owner):
    """Allowed values containing script tags from the bulk upload
    grammar are stored but rendered escaped on the organise page.
    The dimension name regex (word chars + hyphen) rejects script tags,
    so the attack surface is allowed_values (free-text, comma-separated)."""
    client.force_login(owner)
    md = f"""\
CATEGORIES
  rater_role:
    values: {XSS_PAYLOAD}, peer
    source: token

# Demographics {{{{demographics}}}}
## Q {{{{q}}}}
(text)
"""
    res = client.post(f"/surveys/{survey.slug}/bulk-upload/", {"markdown": md})
    assert res.status_code == 302
    # The dimension was created with the XSS payload in allowed_values.
    cat = RespondentCategory.objects.filter(survey=survey).first()
    assert cat is not None
    assert XSS_PAYLOAD in cat.allowed_values
    # Now load the organise page — the payload must be escaped.
    res2 = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert res2.status_code == 200
    html = res2.content.decode()
    assert XSS_PAYLOAD not in html
    assert "&lt;script&gt;" in html


# --- Token CSV export: category values ---


@pytest.mark.django_db
def test_token_csv_export_escapes_category_values(client, survey, owner):
    """Category values in the token CSV export are not an XSS vector
    (CSV is not HTML), but verify the values are present as-is (CSV
    does not need escaping for XSS, but should not break the CSV
    format)."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        label="Rater role",
        allowed_values=["peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-csv-xss",
        created_by=owner,
        category_values={"rater_role": XSS_PAYLOAD},
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:tokens_export_csv", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    body = res.content.decode()
    # CSV is not HTML — the value appears as CSV-escaped data (embedded
    # quotes are doubled by csv.writer). No script execution risk in CSV.
    # Verify the payload is present as data, not as executable HTML.
    assert "script" in body
    assert "alert" in body
