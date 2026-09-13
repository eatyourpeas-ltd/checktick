"""Tests for the Guided layout rendering (docs/survey-layouts-technical.md
§Guided layout).

Guided is a one-question-at-a-time rendering layer. The runtime pipeline
is reused unchanged — all questions still render in the DOM and a
client-side ``guided.js`` module shows one at a time. These tests pin the
server-side contract: the ``is_guided`` flag, the ``data-guided`` form
attribute, the guided nav bar, the ``data-guided-group`` / ``data-guided-
extra`` markers, and the ``guided.js`` script include. The client-side
navigation logic is covered by the rendering contract (the script is
loaded) and the existing branching/repeat tests.
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
def guided_survey(owner, org):
    """A published guided survey with two sections and two questions."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Guided",
        slug="guided",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.GUIDED,
    )
    g1 = QuestionGroup.objects.create(name="Section 1", owner=owner)
    g2 = QuestionGroup.objects.create(name="Section 2", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Q2", type=SurveyQuestion.Types.TEXT, order=1
    )
    return s


@pytest.fixture
def participant(django_user_model):
    return django_user_model.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )


@pytest.mark.django_db
def test_guided_survey_renders_with_nav(client, guided_survey, participant):
    """A guided survey renders the take view with the guided nav bar and
    the data-guided form attribute."""
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": guided_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    # The form is marked guided so the scoped CSS applies.
    assert "data-guided" in html
    # The guided nav bar is present.
    assert "data-guided-nav" in html
    assert "data-guided-back" in html
    assert "data-guided-next" in html
    # The guided submit button is present (hidden until the last step).
    assert "data-guided-submit" in html
    # The step indicator element is present.
    assert "data-guided-step-indicator" in html


@pytest.mark.django_db
def test_guided_survey_includes_guided_js(client, guided_survey, participant):
    """The guided.js script is included for guided surveys."""
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": guided_survey.slug}))
    html = res.content.decode()
    assert "js/guided.js" in html


@pytest.mark.django_db
def test_guided_survey_marks_group_fieldsets(client, guided_survey, participant):
    """Group fieldsets carry data-guided-group so the guided JS can show
    the section header for the current question's group."""
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": guided_survey.slug}))
    html = res.content.decode()
    assert "data-guided-group" in html


@pytest.mark.django_db
def test_linear_survey_does_not_render_guided_nav(client, guided_survey, participant):
    """A linear survey does not render the guided nav bar or script."""
    guided_survey.layout = Survey.Layout.LINEAR
    guided_survey.save(update_fields=["layout"])
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": guided_survey.slug}))
    html = res.content.decode()
    assert "data-guided-nav" not in html
    assert "js/guided.js" not in html
    # The form is not marked guided.
    assert "data-guided" not in html


@pytest.mark.django_db
def test_guided_preview_renders_nav(client, guided_survey, owner):
    """Preview of a guided survey also renders the guided nav so the
    author can test the one-question-at-a-time flow."""
    client.force_login(owner)
    res = client.get(reverse("surveys:preview", kwargs={"slug": guided_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "data-guided-nav" in html
    assert "js/guided.js" in html


@pytest.mark.django_db
def test_guided_survey_submits_like_linear(client, guided_survey, participant):
    """A guided survey submits and records a response just like a linear
    one — the guided layer is rendering-only and does not change the
    submit path."""
    from checktick_app.surveys.models import SurveyResponse

    client.force_login(participant)
    q1 = guided_survey.questions.first()
    res = client.post(
        reverse("surveys:take", kwargs={"slug": guided_survey.slug}),
        {f"q_{q1.id}": "answer"},
    )
    # Successful submit redirects to the thank-you page.
    assert res.status_code == 302
    assert SurveyResponse.objects.filter(survey=guided_survey).exists()
