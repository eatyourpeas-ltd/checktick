"""Tests for the Survey.layout field (docs/survey-layouts.md step 2).

Step 2 only adds the field with a default of ``linear`` and no behaviour
change. These tests pin that contract: the default, the choices, and the
fact that a ``section_menu`` survey still renders exactly like a linear
one until later steps wire up the picker.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import Survey, SurveyQuestion

TEST_PASSWORD = "x"


@pytest.fixture
def survey_owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def published_survey(survey_owner):
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Layout Survey",
        slug="layout-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
    )
    SurveyQuestion.objects.create(
        survey=survey, text="Q1", type=SurveyQuestion.Types.TEXT, required=True, order=0
    )
    return survey


@pytest.mark.django_db
def test_survey_layout_defaults_to_linear(survey_owner):
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Default Layout",
        slug="default-layout",
    )
    assert survey.layout == Survey.Layout.LINEAR
    assert survey.layout == "linear"


@pytest.mark.django_db
def test_survey_layout_choices_exist():
    choices = dict(Survey.Layout.choices)
    assert choices["linear"] == "Linear"
    assert choices["section_menu"] == "Section menu"


@pytest.mark.django_db
def test_survey_layout_can_be_set_to_section_menu(survey_owner):
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Menu Survey",
        slug="menu-survey",
        layout=Survey.Layout.SECTION_MENU,
    )
    survey.refresh_from_db()
    assert survey.layout == "section_menu"


@pytest.mark.django_db
def test_section_menu_survey_renders_picker(client, published_survey, survey_owner):
    """Step 5: a section_menu survey with no selection renders the picker
    instead of the question list."""
    from checktick_app.surveys.models import QuestionGroup

    published_survey.layout = Survey.Layout.SECTION_MENU
    published_survey.save(update_fields=["layout"])
    # The picker needs at least one section to show pickable rows.
    g = QuestionGroup.objects.create(name="Section 1", owner=survey_owner)
    published_survey.question_groups.add(g)

    survey_owner.__class__.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )
    client.login(username="participant@example.com", password=TEST_PASSWORD)
    url = reverse("surveys:take", kwargs={"slug": published_survey.slug})
    response = client.get(url)
    assert response.status_code == 200
    # The picker renders, not the question list.
    assert b"section-picker-form" in response.content


@pytest.mark.django_db
def test_migration_field_present_on_existing_rows(survey_owner):
    """A survey created without specifying layout gets the default via the
    migration (default='linear'). This guards against the migration being
    skipped or the default being dropped later."""
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Migration Check",
        slug="migration-check",
    )
    raw = Survey.objects.values("layout").get(pk=survey.pk)
    assert raw["layout"] == "linear"
