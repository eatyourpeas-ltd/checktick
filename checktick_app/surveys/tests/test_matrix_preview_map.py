"""Tests for the matrix preview + Survey Map badges (step 6).

Covers the ?simulate_section= preview panel and the matrix configuration
badges on the Survey Map.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    MatrixMenu,
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
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def matrix_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Matrix Preview",
        slug="matrix-preview",
        layout=Survey.Layout.MATRIX,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="History", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Name", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Condition", type=SurveyQuestion.Types.TEXT, order=0
    )
    s._g1 = g1
    s._g2 = g2
    return s


# --- preview ---


@pytest.mark.django_db
def test_preview_shows_simulate_section_panel(client, matrix_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": matrix_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate section" in html
    assert "Demographics" in html
    assert "History" in html


@pytest.mark.django_db
def test_preview_simulate_section_filters(client, matrix_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": matrix_survey.slug})
    url += f"?simulate_section={matrix_survey._g1.id}"
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    assert "Name" in html  # question from Demographics
    assert "Condition" not in html  # question from History should not appear


@pytest.mark.django_db
def test_preview_simulate_section_invalid_id(client, matrix_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:preview", kwargs={"slug": matrix_survey.slug})
    url += "?simulate_section=99999"
    res = client.get(url)
    assert res.status_code == 200
    # Invalid section ID → no filter, all questions shown.
    html = res.content.decode()
    assert "Name" in html
    assert "Condition" in html


@pytest.mark.django_db
def test_preview_creates_default_menu(client, matrix_survey, owner):
    client.force_login(owner)
    client.get(reverse("surveys:preview", kwargs={"slug": matrix_survey.slug}))
    assert MatrixMenu.objects.filter(survey=matrix_survey).exists()


# --- survey map ---


@pytest.mark.django_db
def test_survey_map_shows_matrix_badges(client, matrix_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": matrix_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Matrix — free navigation" in html
    assert "Prompt:" in html
    assert "Order:" in html
    assert "Revisit allowed" in html


@pytest.mark.django_db
def test_survey_map_matrix_badges_show_disabled_revisit(client, matrix_survey, owner):
    MatrixMenu.objects.create(
        survey=matrix_survey,
        prompt_text="Custom prompt",
        order_mode=MatrixMenu.OrderMode.PARTICIPANT,
        allow_revisit=False,
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": matrix_survey.slug}))
    html = res.content.decode()
    assert "Custom prompt" in html
    assert "In visit order" in html
    assert "Revisit disabled" in html


@pytest.mark.django_db
def test_survey_map_no_matrix_badges_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-map"
    )
    QuestionGroup.objects.create(name="G", owner=owner)
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    html = res.content.decode()
    assert "Matrix — free navigation" not in html
