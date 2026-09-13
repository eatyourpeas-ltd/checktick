"""Tests for the matrix runtime hook (step 3): landing page rendering,
per-section view, complete_section action, save_draft un-marking, and
final submit_survey validation + SurveyResponse creation.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    MatrixMenu,
    Organization,
    QuestionGroup,
    Survey,
    SurveyProgress,
    SurveyQuestion,
    SurveyResponse,
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
def participant(django_user_model):
    return django_user_model.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def matrix_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Matrix Survey",
        slug="matrix-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.MATRIX,
        respondent_audience=Survey.RespondentAudience.STAFF,
        audience_confirmed=True,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="History", owner=owner)
    s.question_groups.add(g1, g2)
    # Demographics: 1 required, 1 optional
    SurveyQuestion.objects.create(
        survey=s,
        group=g1,
        text="Name",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g1,
        text="Nickname",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=1,
    )
    # History: 1 required
    SurveyQuestion.objects.create(
        survey=s,
        group=g2,
        text="Condition",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=0,
    )
    s._g1 = g1
    s._g2 = g2
    s._name_q = SurveyQuestion.objects.get(survey=s, text="Name")
    s._condition_q = SurveyQuestion.objects.get(survey=s, text="Condition")
    return s


# --- landing page ---


@pytest.mark.django_db
def test_get_renders_landing_page(client, matrix_survey, participant):
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Demographics" in html
    assert "History" in html
    assert "Not started" in html
    # Submit button should be disabled (no sections complete).
    assert "disabled" in html or "Complete all sections" in html


@pytest.mark.django_db
def test_landing_page_creates_default_menu(client, matrix_survey, participant):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    assert MatrixMenu.objects.filter(survey=matrix_survey).exists()


@pytest.mark.django_db
def test_landing_page_shows_completion_states(client, matrix_survey, participant):
    client.force_login(participant)
    # First visit creates progress.
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    # Mark one section complete.
    progress.completed_group_ids = [matrix_survey._g1.id]
    progress.save()
    res = client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    html = res.content.decode()
    assert "Complete" in html
    assert "In progress" in html or "Not started" in html


# --- per-section view ---


@pytest.mark.django_db
def test_get_with_section_renders_per_section(client, matrix_survey, participant):
    client.force_login(participant)
    url = f"/surveys/{matrix_survey.slug}/take/?section={matrix_survey._g1.id}"
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    assert "Name" in html  # question from Demographics
    assert "Condition" not in html  # question from History should not appear
    assert "Save and complete section" in html
    assert "Back to overview" in html


@pytest.mark.django_db
def test_get_with_invalid_section_falls_back_to_landing(
    client, matrix_survey, participant
):
    client.force_login(participant)
    url = f"/surveys/{matrix_survey.slug}/take/?section=99999"
    res = client.get(url)
    assert res.status_code == 200
    html = res.content.decode()
    # Landing page content, not per-section.
    assert "Not started" in html or "Complete" in html


# --- complete_section ---


@pytest.mark.django_db
def test_complete_section_with_valid_answers(client, matrix_survey, participant):
    client.force_login(participant)
    # First visit creates progress.
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    url = f"/surveys/{matrix_survey.slug}/take/?section={matrix_survey._g1.id}"
    res = client.post(
        url,
        {
            "action": "complete_section",
            "section_id": str(matrix_survey._g1.id),
            f"q_{matrix_survey._name_q.id}": "Alice",
        },
    )
    assert res.status_code in (200, 302)
    progress.refresh_from_db()
    assert matrix_survey._g1.id in progress.completed_group_ids
    assert str(matrix_survey._name_q.id) in progress.partial_answers


@pytest.mark.django_db
def test_complete_section_with_missing_required(client, matrix_survey, participant):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    url = f"/surveys/{matrix_survey.slug}/take/?section={matrix_survey._g1.id}"
    # Don't fill in the required "Name" question.
    res = client.post(
        url,
        {
            "action": "complete_section",
            "section_id": str(matrix_survey._g1.id),
        },
    )
    assert res.status_code in (200, 302)
    progress.refresh_from_db()
    assert matrix_survey._g1.id not in progress.completed_group_ids


@pytest.mark.django_db
def test_complete_section_redirects_to_landing(client, matrix_survey, participant):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    url = f"/surveys/{matrix_survey.slug}/take/?section={matrix_survey._g1.id}"
    res = client.post(
        url,
        {
            "action": "complete_section",
            "section_id": str(matrix_survey._g1.id),
            f"q_{matrix_survey._name_q.id}": "Alice",
        },
    )
    # Should redirect to the landing page (no ?section=).
    assert res.status_code == 302
    assert f"/surveys/{matrix_survey.slug}/take/" in res["Location"]
    # Should not have ?section= in the redirect.
    assert "section=" not in res["Location"]


# --- save_draft un-marks completed section ---


@pytest.mark.django_db
def test_save_draft_unmarks_completed_section(client, matrix_survey, participant):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    # Mark section as complete.
    progress.completed_group_ids = [matrix_survey._g1.id]
    progress.partial_answers = {str(matrix_survey._name_q.id): "Alice"}
    progress.save()
    # Save a draft for that section (editing).
    url = f"/surveys/{matrix_survey.slug}/take/?section={matrix_survey._g1.id}"
    res = client.post(
        url,
        {
            "action": "save_draft",
            "section_id": str(matrix_survey._g1.id),
            f"q_{matrix_survey._name_q.id}": "Alice Updated",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert res.status_code == 200
    progress.refresh_from_db()
    # Section should be un-marked.
    assert matrix_survey._g1.id not in progress.completed_group_ids
    # Answer should be updated.
    assert progress.partial_answers[str(matrix_survey._name_q.id)] == "Alice Updated"


# --- submit_survey ---


@pytest.mark.django_db
def test_submit_survey_blocked_when_sections_incomplete(
    client, matrix_survey, participant
):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    # Only complete one section.
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    progress.completed_group_ids = [matrix_survey._g1.id]
    progress.partial_answers = {str(matrix_survey._name_q.id): "Alice"}
    progress.save()
    res = client.post(
        reverse("surveys:take", kwargs={"slug": matrix_survey.slug}),
        {"action": "submit_survey"},
    )
    assert res.status_code in (200, 302)
    # No SurveyResponse should be created.
    assert not SurveyResponse.objects.filter(survey=matrix_survey).exists()


@pytest.mark.django_db
def test_submit_survey_creates_response_when_all_complete(
    client, matrix_survey, participant
):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    # Complete both sections with valid answers.
    progress.completed_group_ids = [matrix_survey._g1.id, matrix_survey._g2.id]
    progress.partial_answers = {
        str(matrix_survey._name_q.id): "Alice",
        str(matrix_survey._condition_q.id): "Hypertension",
    }
    progress.save()
    res = client.post(
        reverse("surveys:take", kwargs={"slug": matrix_survey.slug}),
        {"action": "submit_survey"},
    )
    assert res.status_code == 302
    # SurveyResponse should be created.
    assert SurveyResponse.objects.filter(survey=matrix_survey).exists()
    # Progress should be marked completed.
    progress.refresh_from_db()
    assert progress.status == SurveyProgress.Status.COMPLETED


@pytest.mark.django_db
def test_submit_survey_hard_gate_revalidates(client, matrix_survey, participant):
    """Even if completed_group_ids says all complete, final submit re-validates."""
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    # Lie: mark both sections complete but don't actually have the answers.
    progress.completed_group_ids = [matrix_survey._g1.id, matrix_survey._g2.id]
    progress.partial_answers = {}  # no answers!
    progress.save()
    res = client.post(
        reverse("surveys:take", kwargs={"slug": matrix_survey.slug}),
        {"action": "submit_survey"},
    )
    assert res.status_code in (200, 302)
    # No SurveyResponse should be created (hard gate caught the lie).
    assert not SurveyResponse.objects.filter(survey=matrix_survey).exists()


@pytest.mark.django_db
def test_submit_survey_redirects_to_thank_you(client, matrix_survey, participant):
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": matrix_survey.slug}))
    progress = SurveyProgress.objects.get(survey=matrix_survey, user=participant)
    progress.completed_group_ids = [matrix_survey._g1.id, matrix_survey._g2.id]
    progress.partial_answers = {
        str(matrix_survey._name_q.id): "Alice",
        str(matrix_survey._condition_q.id): "Hypertension",
    }
    progress.save()
    res = client.post(
        reverse("surveys:take", kwargs={"slug": matrix_survey.slug}),
        {"action": "submit_survey"},
    )
    assert res.status_code == 302
    assert "thank" in res["Location"].lower()
