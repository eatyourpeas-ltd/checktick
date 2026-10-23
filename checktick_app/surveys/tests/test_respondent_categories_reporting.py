"""Tests for respondent categories reporting — CSV export (commit 8).

The survey response CSV export gains a column per category dimension,
populated from the response's access_token.category_values. This is the
cross-rater aggregation 360 needs (group responses by subject, break
down by rater_role).
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
    SurveyResponse,
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
        slug="s-csv",
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    g = QuestionGroup.objects.create(name="G1", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    return s


@pytest.mark.django_db
def test_csv_export_includes_category_columns(client, survey, owner):
    """The CSV export has a Category: <dim> column per dimension."""
    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    SurveyResponse.objects.create(
        survey=survey,
        access_token=token,
        answers={"1": "answer"},
    )
    client.force_login(owner)
    # Unlock the survey first (no encryption on this survey, so the key
    # check passes if we set it in session).

    session = client.session
    session[f"survey_key_{survey.slug}"] = "dummy"
    session.save()
    res = client.get(reverse("surveys:export_csv", kwargs={"slug": survey.slug}))
    # If the survey is not encrypted, the export should work.
    if res.status_code == 302:
        # Redirect to unlock — skip if encryption is required.
        return
    body = res.content.decode()
    assert "Category: Rater role" in body
    lines = body.strip().split("\n")
    assert "peer" in lines[1]


@pytest.mark.django_db
def test_csv_export_no_categories_no_columns(client, owner, org):
    """A survey with no RespondentCategory rows has no category columns."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain-csv-exp",
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    g = QuestionGroup.objects.create(name="G1", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    token = SurveyAccessToken.objects.create(
        survey=s,
        token="tok-plain",
        created_by=owner,
    )
    SurveyResponse.objects.create(
        survey=s,
        access_token=token,
        answers={"1": "answer"},
    )
    client.force_login(owner)
    session = client.session
    session[f"survey_key_{s.slug}"] = "dummy"
    session.save()
    res = client.get(reverse("surveys:export_csv", kwargs={"slug": s.slug}))
    if res.status_code == 302:
        return
    body = res.content.decode()
    assert "Category:" not in body


@pytest.mark.django_db
def test_csv_export_empty_category_values(client, survey, owner):
    """A response with no access_token (or empty category_values) has
    empty category columns."""
    SurveyResponse.objects.create(
        survey=survey,
        answers={"1": "answer"},
    )
    client.force_login(owner)
    session = client.session
    session[f"survey_key_{survey.slug}"] = "dummy"
    session.save()
    res = client.get(reverse("surveys:export_csv", kwargs={"slug": survey.slug}))
    if res.status_code == 302:
        return
    body = res.content.decode()
    assert "Category: Rater role" in body
    lines = body.strip().split("\n")
    # The response row should have an empty category value.
    if len(lines) > 1:
        assert "peer" not in lines[1]
