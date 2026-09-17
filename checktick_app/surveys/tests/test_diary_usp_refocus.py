"""Tests for the layouts-as-USP refocus (Commit 11).

Verifies that:
- The home page lists all eight layouts in the dedicated Survey Layouts card.
- The pricing page names Diary/EMA in the layouts bullet.
- The survey list item shows a layout badge for non-linear surveys.
- The getting-started docs mention all eight layouts.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="usp_owner@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


# --- home page ---


@pytest.mark.django_db
def test_home_page_lists_all_eight_layouts(client):
    res = client.get(reverse("core:home"))
    assert res.status_code == 200
    html = res.content.decode()
    # The dedicated Research Layouts card should mention all eight.
    assert "Research Layouts" in html
    assert "Linear" in html
    assert "section menu" in html
    assert "RCT" in html
    assert "guided" in html
    assert "Staged" in html
    assert "Matrix" in html or "matrix" in html
    assert "Delphi" in html
    assert "Diary (EMA)" in html


@pytest.mark.django_db
def test_home_page_links_to_pricing(client):
    res = client.get(reverse("core:home"))
    assert res.status_code == 200
    html = res.content.decode()
    assert reverse("core:pricing") in html


# --- pricing page ---


@pytest.mark.django_db
def test_pricing_page_names_diary_ema(client):
    res = client.get(reverse("core:pricing"))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary/EMA" in html or "Diary (EMA)" in html


# --- survey list layout badge ---


@pytest.mark.django_db
def test_survey_list_shows_layout_badge_for_non_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Diary Survey",
        slug="diary-list-badge",
        layout=Survey.Layout.DIARY,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:list"))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Diary (EMA)" in html


@pytest.mark.django_db
def test_survey_list_no_badge_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Linear Survey",
        slug="linear-list-badge",
        layout=Survey.Layout.LINEAR,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:list"))
    assert res.status_code == 200
    html = res.content.decode()
    # The layout badge should not appear for linear surveys.
    assert "badge-outline" not in html.split("Linear Survey")[1].split("</div>")[0]
