"""Tests for the Builder layout label (step 6).

Step 6 adds a dismissible label above the Builder rail showing the
current layout and a 'Need a different layout?' link to the Organise
page. The label uses the layout icon components.
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


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    s = Survey.objects.create(owner=owner, organization=org, name="S", slug="s")
    g = QuestionGroup.objects.create(name="Section 1", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT
    )
    return s


@pytest.mark.django_db
def test_builder_shows_linear_layout_label(client, owner, survey):
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Layout: Default (linear)" in html
    assert "Need a different layout?" in html


@pytest.mark.django_db
def test_builder_shows_section_menu_layout_label(client, owner, survey):
    survey.layout = Survey.Layout.SECTION_MENU
    survey.save(update_fields=["layout"])
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Layout: Section menu" in html
    assert "Need a different layout?" in html


@pytest.mark.django_db
def test_builder_layout_label_links_to_organise(client, owner, survey):
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    html = res.content.decode()
    assert f"/surveys/{survey.slug}/groups/" in html


@pytest.mark.django_db
def test_builder_layout_label_hidden_when_no_questions(client, owner, org):
    """The label only shows when the survey has questions (has_questions)."""
    s = Survey.objects.create(owner=owner, organization=org, name="Empty", slug="empty")
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_builder", kwargs={"slug": s.slug}))
    # No groups → redirects to groups page
    assert res.status_code == 302
