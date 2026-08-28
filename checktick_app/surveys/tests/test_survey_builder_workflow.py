"""Tests for the Survey Builder Workflow redesign (Tier 1).

See docs/survey-builder-workflow-design.md and
docs/survey-builder-workflow-implementation-plan.md.

Tier 1.1 — Auto-create a default QuestionGroup on survey creation so the user
can add their first question without naming a group.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from checktick_app.surveys.models import QuestionGroup, Survey
from checktick_app.surveys.views import DEFAULT_SECTION_NAME, create_default_section


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
PASSWORD = "securepass123"

@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    settings.AXES_ENABLED = False


@pytest.fixture
def owner(django_user_model):
    from checktick_app.core.models import UserProfile

    user = django_user_model.objects.create_user(
        username="builder_workflow@example.com",
        email="builder_workflow@example.com",
        password=PASSWORD,
    )
    UserProfile.objects.filter(user=user).update(
        account_tier=UserProfile.AccountTier.PRO,
        email_confirmed=True,  # Required for creating surveys
    )
    user._state.fields_cache.pop("profile", None)
    return user


@pytest.fixture
def auth_client(client, owner):
    client.force_login(owner)
    return client


# ---------------------------------------------------------------------------
# create_default_section helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_default_section_creates_one_group(owner):
    """The helper creates exactly one QuestionGroup attached to the survey."""
    survey = Survey.objects.create(
        owner=owner,
        name="Helper Test Survey",
        slug="helper-test-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    assert survey.question_groups.count() == 0

    group = create_default_section(survey, owner)

    assert survey.question_groups.count() == 1
    assert group.name == DEFAULT_SECTION_NAME
    assert group.owner == owner
    assert survey.question_groups.first().id == group.id


# ---------------------------------------------------------------------------
# survey_create view — non-encrypted path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_create_creates_default_group(auth_client, owner):
    """POSTing to surveys:create auto-creates exactly one default QuestionGroup."""
    resp = auth_client.post(
        reverse("surveys:create"),
        data={
            "name": "Workflow Test Survey",
            "slug": "workflow-test-survey",
            "description": "",
        },
    )
    assert resp.status_code == 302

    survey = Survey.objects.get(slug="workflow-test-survey")
    assert survey.question_groups.count() == 1, (
        "A newly-created survey must have exactly one auto-created default group, "
        "so the user can add a question without naming a group first."
    )
    group = survey.question_groups.first()
    assert group.name == DEFAULT_SECTION_NAME
    assert group.owner == owner


@pytest.mark.django_db
def test_survey_create_encrypted_path_creates_default_group(auth_client, owner):
    """The encrypted survey-create path also auto-creates the default group."""
    resp = auth_client.post(
        reverse("surveys:create"),
        data={
            "name": "Encrypted Workflow Survey",
            "slug": "encrypted-workflow-survey",
            "description": "",
            "encryption_option": "option2",
            "password": "securepass123",
            "recovery_phrase": "abandon ability able about above absent absorb abstract absurd abuse access accident",
        },
    )
    assert resp.status_code == 302, (
        f"Expected redirect after encrypted survey creation, got {resp.status_code}"
    )

    survey = Survey.objects.get(slug="encrypted-workflow-survey")
    assert survey.question_groups.count() == 1, (
        "An encrypted survey must also get the auto-created default group."
    )
    assert survey.question_groups.first().name == DEFAULT_SECTION_NAME


# ---------------------------------------------------------------------------
# No regression — existing surveys and the default group's behaviour
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_existing_surveys_unaffected(owner):
    """Surveys created without the helper (e.g. fixtures) are not migrated.

    The redesign is presentation-only at the data layer: we do not backfill
    a default group into existing surveys. A survey with N groups keeps N
    groups; a survey with 0 groups keeps 0 (legacy edge case).
    """
    survey = Survey.objects.create(
        owner=owner,
        name="Legacy Survey",
        slug="legacy-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    # No helper called — simulates a survey created before this change.
    assert survey.question_groups.count() == 0


@pytest.mark.django_db
def test_default_group_is_renameable_and_deletable(owner):
    """The auto-created default group behaves like any other group."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rename Test Survey",
        slug="rename-test-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    # Renameable
    group.name = "Demographics"
    group.save(update_fields=["name"])
    group.refresh_from_db()
    assert group.name == "Demographics"

    # Deletable when empty (no questions)
    group_id = group.id
    survey.question_groups.remove(group)
    group.delete()
    assert not QuestionGroup.objects.filter(id=group_id).exists()
    assert survey.question_groups.count() == 0
