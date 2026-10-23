"""Tests for ``_resolve_categories_for_progress`` (commit 2 of respondent
categories).

The resolution logic resolves a category value per participant x dimension,
from four sources in priority order: invite token, self-select question,
system assignment (RCT allocator), profile field. Resolved values are
persisted as ``RespondentAssignment`` rows and preserved on resume — same
lifecycle as ``assigned_arm`` (RCT) and ``delphi_round`` (Delphi).

The runtime hook (commit 3) consumes the resolved map to filter sections.
"""

from datetime import timedelta

from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyProgress,
    SurveyQuestion,
)
from checktick_app.surveys.views import _resolve_categories_for_progress

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
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
    )


@pytest.fixture
def progress(survey):
    return SurveyProgress.objects.create(
        survey=survey,
        expires_at=timezone.now() + timedelta(days=30),
    )


# --- No categories: no-op ---------------------------------------------


@pytest.mark.django_db
def test_resolve_no_categories_returns_empty(survey, progress):
    assert _resolve_categories_for_progress(progress) == {}


@pytest.mark.django_db
def test_resolve_no_categories_creates_no_assignments(survey, progress):
    _resolve_categories_for_progress(progress)
    assert progress.category_assignments.count() == 0


# --- Source 1: invite token --------------------------------------------


@pytest.mark.django_db
def test_resolve_from_token(survey, progress, owner):
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer", "supervisor", "patient"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    progress.access_token = token
    progress.save(update_fields=["access_token"])

    resolved = _resolve_categories_for_progress(progress)

    assert resolved == {"rater_role": "peer"}
    assert progress.category_assignments.count() == 1
    assert progress.category_assignments.get().value == "peer"


@pytest.mark.django_db
def test_resolve_token_missing_dimension_leaves_unset(survey, progress, owner):
    """A token without the dimension's value leaves it unset."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-empty",
        created_by=owner,
        category_values={},  # no rater_role
    )
    progress.access_token = token
    progress.save(update_fields=["access_token"])

    resolved = _resolve_categories_for_progress(progress)

    assert resolved == {}
    assert progress.category_assignments.count() == 0


# --- Source 2: self-select question ------------------------------------


@pytest.mark.django_db
def test_resolve_from_self_select_question(survey, progress):
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=["clinic_a", "clinic_b"],
        resolution_source=RespondentCategory.ResolutionSource.SELF_SELECT,
    )
    question = SurveyQuestion.objects.create(
        survey=survey,
        text="Which clinic?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options=[{"label": "Clinic A", "value": "clinic_a"}],
    )
    cat.source_question = question
    cat.save(update_fields=["source_question"])

    progress.partial_answers = {str(question.id): "clinic_a"}
    progress.save(update_fields=["partial_answers"])

    resolved = _resolve_categories_for_progress(progress)

    assert resolved == {"site": "clinic_a"}
    assert progress.category_assignments.count() == 1


@pytest.mark.django_db
def test_resolve_self_select_unanswered_leaves_unset(survey, progress):
    """If the self-select question hasn't been answered yet, the dimension
    is unresolved (the runtime hook will hide sections requiring it)."""
    cat = RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=["clinic_a", "clinic_b"],
        resolution_source=RespondentCategory.ResolutionSource.SELF_SELECT,
    )
    question = SurveyQuestion.objects.create(
        survey=survey,
        text="Which clinic?",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
    )
    cat.source_question = question
    cat.save(update_fields=["source_question"])

    resolved = _resolve_categories_for_progress(progress)

    assert resolved == {}
    assert progress.category_assignments.count() == 0


# --- Source 3: system assignment (RCT allocator) ----------------------


@pytest.mark.django_db
def test_resolve_from_system_assignment(survey, progress):
    """System-assigned dimensions reuse the RCT allocator over
    allowed_values (ratio 1 each, balanced strategy)."""
    RespondentCategory.objects.create(
        survey=survey,
        name="cohort",
        allowed_values=["a", "b"],
        resolution_source=RespondentCategory.ResolutionSource.SYSTEM,
    )

    resolved = _resolve_categories_for_progress(progress)

    assert "cohort" in resolved
    assert resolved["cohort"] in ("a", "b")
    assert progress.category_assignments.count() == 1
    # The seed is set on first access (same as RCT).
    assert progress.randomisation_seed is not None


@pytest.mark.django_db
def test_resolve_system_assignment_deterministic_from_seed(survey, progress):
    """With a fixed randomisation_seed, the system assignment is
    deterministic (same as RCT balanced allocation from a fixed seed)."""
    RespondentCategory.objects.create(
        survey=survey,
        name="cohort",
        allowed_values=["a", "b"],
        resolution_source=RespondentCategory.ResolutionSource.SYSTEM,
    )
    progress.randomisation_seed = 12345
    progress.save(update_fields=["randomisation_seed"])

    first = _resolve_categories_for_progress(progress)
    # Reset the assignment but keep the seed.
    progress.category_assignments.all().delete()
    second = _resolve_categories_for_progress(progress)

    assert first == second


# --- Source 4: profile field -------------------------------------------


@pytest.mark.django_db
def test_resolve_from_profile_field(survey, progress, django_user_model):
    """Profile-field resolution reads from the user's UserProfile."""
    user = django_user_model.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )
    progress.user = user
    progress.save(update_fields=["user"])

    RespondentCategory.objects.create(
        survey=survey,
        name="team",
        allowed_values=["alpha", "beta"],
        resolution_source=RespondentCategory.ResolutionSource.PROFILE,
        profile_field="team",
    )
    # UserProfile is created by a signal; set the field if it exists.
    profile = getattr(user, "userprofile", None)
    if profile is not None:
        profile.team = "alpha"
        profile.save(update_fields=["team"])

    resolved = _resolve_categories_for_progress(progress)

    # The value is read from the profile field if it exists and is set.
    if profile is not None and getattr(profile, "team", None):
        assert resolved == {"team": "alpha"}
    else:
        # UserProfile.team may not exist in this test schema; the dimension
        # is left unset if the field is missing or empty.
        assert "team" not in resolved


# --- Idempotence / resume ---------------------------------------------


@pytest.mark.django_db
def test_resolve_is_idempotent(survey, progress, owner):
    """Calling resolve twice does not re-resolve or duplicate assignments."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    progress.access_token = token
    progress.save(update_fields=["access_token"])

    first = _resolve_categories_for_progress(progress)
    second = _resolve_categories_for_progress(progress)

    assert first == second == {"rater_role": "peer"}
    assert progress.category_assignments.count() == 1


@pytest.mark.django_db
def test_resolve_preserved_on_resume(survey, progress, owner):
    """If the token is later cleared (e.g. token used/expired), the
    previously-resolved value is preserved — same as assigned_arm."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    progress.access_token = token
    progress.save(update_fields=["access_token"])

    _resolve_categories_for_progress(progress)
    # Simulate token being cleared on resume.
    progress.access_token = None
    progress.save(update_fields=["access_token"])

    resolved = _resolve_categories_for_progress(progress)

    assert resolved == {"rater_role": "peer"}
    assert progress.category_assignments.count() == 1


# --- Multiple dimensions ----------------------------------------------


@pytest.mark.django_db
def test_resolve_multiple_dimensions(survey, progress, owner):
    """A survey with rater_role (token) + subject (self_select) resolves
    both independently."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    subject_cat = RespondentCategory.objects.create(
        survey=survey,
        name="subject",
        allowed_values=["self"],
        resolution_source=RespondentCategory.ResolutionSource.SELF_SELECT,
    )
    subject_q = SurveyQuestion.objects.create(
        survey=survey,
        text="Who are you rating?",
        type=SurveyQuestion.Types.TEXT,
    )
    subject_cat.source_question = subject_q
    subject_cat.save(update_fields=["source_question"])

    token = SurveyAccessToken.objects.create(
        survey=survey,
        token="tok-peer",
        created_by=owner,
        category_values={"rater_role": "peer"},
    )
    progress.access_token = token
    progress.partial_answers = {str(subject_q.id): "self"}
    progress.save(update_fields=["access_token", "partial_answers"])

    resolved = _resolve_categories_for_progress(progress)

    assert resolved == {"rater_role": "peer", "subject": "self"}
    assert progress.category_assignments.count() == 2


# --- Preview / simulated values ---------------------------------------


@pytest.mark.django_db
def test_resolve_simulated_values_not_persisted(survey, progress):
    """The preview path uses simulated values and does not persist."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )

    resolved = _resolve_categories_for_progress(
        progress, simulated_values={"rater_role": "supervisor"}
    )

    assert resolved == {"rater_role": "supervisor"}
    assert progress.category_assignments.count() == 0


@pytest.mark.django_db
def test_resolve_simulated_values_partial(survey, progress):
    """Simulated values for a subset of dimensions; the rest are unresolved."""
    RespondentCategory.objects.create(
        survey=survey,
        name="rater_role",
        allowed_values=["peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    RespondentCategory.objects.create(
        survey=survey,
        name="site",
        allowed_values=["clinic_a"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )

    resolved = _resolve_categories_for_progress(
        progress, simulated_values={"rater_role": "supervisor"}
    )

    assert resolved == {"rater_role": "supervisor"}
    assert "site" not in resolved
