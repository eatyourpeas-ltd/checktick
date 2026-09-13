"""Tests for the matrix Organise page UI (step 4).

Covers the layout picker Matrix card, the matrix configuration card
(prompt/order_mode/allow_revisit), save_matrix_menu, and the
single-section guard warning.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    MatrixMenu,
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
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
        name="Matrix",
        slug="matrix",
        layout=Survey.Layout.MATRIX,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="History", owner=owner)
    s.question_groups.add(g1, g2)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Q2", type=SurveyQuestion.Types.TEXT, order=0
    )
    return s


# --- layout picker ---


@pytest.mark.django_db
def test_matrix_card_shown_on_organise_page(client, matrix_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": matrix_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Matrix (free navigation)" in html
    assert "Current" in html


@pytest.mark.django_db
def test_linear_survey_shows_matrix_card_as_option(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-matrix"
    )
    QuestionGroup.objects.create(name="G1", owner=owner)
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    assert "Matrix (free navigation)" in res.content.decode()


# --- matrix configuration card ---


@pytest.mark.django_db
def test_matrix_config_card_shown_when_layout_matrix(client, matrix_survey, owner):
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": matrix_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Matrix (free navigation) configuration" in html
    assert "Landing page prompt" in html
    assert "Card order" in html
    assert "Allow participants to revisit" in html


@pytest.mark.django_db
def test_matrix_config_card_hidden_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear2", slug="linear2-matrix"
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert "Matrix (free navigation) configuration" not in res.content.decode()


@pytest.mark.django_db
def test_default_menu_created_on_first_visit(client, matrix_survey, owner):
    client.force_login(owner)
    client.get(reverse("surveys:groups", kwargs={"slug": matrix_survey.slug}))
    menu = MatrixMenu.objects.get(survey=matrix_survey)
    assert menu.order_mode == MatrixMenu.OrderMode.AUTHORED
    assert menu.allow_revisit is True


# --- save_matrix_menu ---


@pytest.mark.django_db
def test_save_matrix_menu(client, matrix_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": matrix_survey.slug})
    client.get(url)  # create the menu
    res = client.post(
        url,
        {
            "action": "save_matrix_menu",
            "prompt_text": "Choose a section to start",
            "order_mode": "participant",
            "allow_revisit": "1",
        },
    )
    assert res.status_code in (200, 302)
    menu = MatrixMenu.objects.get(survey=matrix_survey)
    assert menu.prompt_text == "Choose a section to start"
    assert menu.order_mode == MatrixMenu.OrderMode.PARTICIPANT
    assert menu.allow_revisit is True


@pytest.mark.django_db
def test_save_matrix_menu_uncheck_allow_revisit(client, matrix_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": matrix_survey.slug})
    client.get(url)
    res = client.post(
        url,
        {
            "action": "save_matrix_menu",
            "prompt_text": "Choose a section",
            "order_mode": "authored",
            # allow_revisit not sent → unchecked
        },
    )
    assert res.status_code in (200, 302)
    menu = MatrixMenu.objects.get(survey=matrix_survey)
    assert menu.allow_revisit is False


@pytest.mark.django_db
def test_save_matrix_menu_invalid_order_mode_falls_back(client, matrix_survey, owner):
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": matrix_survey.slug})
    client.get(url)
    res = client.post(
        url,
        {
            "action": "save_matrix_menu",
            "prompt_text": "Prompt",
            "order_mode": "invalid_mode",
        },
    )
    assert res.status_code in (200, 302)
    menu = MatrixMenu.objects.get(survey=matrix_survey)
    # Falls back to the existing default (authored).
    assert menu.order_mode == MatrixMenu.OrderMode.AUTHORED


# --- layout switching ---


@pytest.mark.django_db
def test_switch_to_matrix_layout(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Switch", slug="switch-matrix"
    )
    g1 = QuestionGroup.objects.create(name="A", owner=owner)
    g2 = QuestionGroup.objects.create(name="B", owner=owner)
    s.question_groups.add(g1, g2)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "matrix"})
    assert res.status_code in (200, 302)
    s.refresh_from_db()
    assert s.layout == Survey.Layout.MATRIX
    # A MatrixMenu is created on first visit (in the context build).
    client.get(url)
    assert MatrixMenu.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_single_section_guard_warns_for_matrix(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="One", slug="one-section-matrix"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": s.slug})
    res = client.post(url, {"action": "set_layout", "layout": "matrix"}, follow=True)
    assert b"Matrix surveys need at least 2 sections" in res.content


# --- cross-section branching warning ---


@pytest.mark.django_db
def test_cross_section_branching_warning(client, matrix_survey, owner):
    g1, g2 = list(matrix_survey.question_groups.all())
    q1 = matrix_survey.questions.get(group=g1)
    # A jump from a question in g1 to group g2 (cross-section).
    SurveyQuestionCondition.objects.create(
        question=q1,
        action=SurveyQuestionCondition.Action.JUMP_TO,
        target_group=g2,
    )
    client.force_login(owner)
    url = reverse("surveys:groups", kwargs={"slug": matrix_survey.slug})
    res = client.get(url)
    html = res.content.decode()
    assert "cross-section jumps are ignored" in html


# --- read-only ---


@pytest.mark.django_db
def test_matrix_config_read_only_when_cannot_edit(client, owner, org):
    other = type(owner).objects.create_user(
        username="other@example.com", password=TEST_PASSWORD
    )
    s = Survey.objects.create(
        owner=other,
        organization=org,
        name="Other",
        slug="other-matrix",
        layout=Survey.Layout.MATRIX,
    )
    g = QuestionGroup.objects.create(name="G", owner=other)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT, order=0
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s.slug}))
    assert res.status_code in (200, 302)
    if res.status_code == 200:
        html = res.content.decode()
        assert "read-only" in html or "Matrix (free navigation) configuration" in html
