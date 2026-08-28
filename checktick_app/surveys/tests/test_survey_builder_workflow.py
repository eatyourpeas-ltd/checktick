"""Tests for the Survey Builder Workflow redesign (Tier 1).

See docs/survey-builder-workflow-design.md and
docs/survey-builder-workflow-implementation-plan.md.

Tier 1.1 — Auto-create a default QuestionGroup on survey creation so the user
can add their first question without naming a group.
"""

from __future__ import annotations

from django.urls import reverse
import pytest

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion
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
    assert (
        resp.status_code == 302
    ), f"Expected redirect after encrypted survey creation, got {resp.status_code}"

    survey = Survey.objects.get(slug="encrypted-workflow-survey")
    assert (
        survey.question_groups.count() == 1
    ), "An encrypted survey must also get the auto-created default group."
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


# ---------------------------------------------------------------------------
# Commit 3 — Dashboard CTA points at per-group builder
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_cta_points_at_group_builder(auth_client, owner):
    """The "Add questions" card links to group_builder for the default group."""
    # Create a survey with the default group (as survey_create now does)
    survey = Survey.objects.create(
        owner=owner,
        name="CTA Test Survey",
        slug="cta-test-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The CTA should link to group_builder for the default group, not to /groups/
    expected_url = reverse(
        "surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id}
    )
    assert expected_url.encode() in resp.content, (
        f"Dashboard 'Add questions' CTA should point at {expected_url}, "
        f"but the URL was not found in the response."
    )
    # The old label "Question Builder" should no longer appear
    assert (
        b"Question Builder" not in resp.content
    ), "The old 'Question Builder' card label should be replaced with 'Add questions'."


@pytest.mark.django_db
def test_dashboard_cta_fallback_for_legacy_survey(auth_client, owner):
    """A survey with no groups (legacy edge case) falls back to the Groups page.

    This must not 404 — it sends the user to the Groups page where they can
    create one. New surveys always have a default group (commit 2), so this
    only affects surveys created before that change.
    """
    survey = Survey.objects.create(
        owner=owner,
        name="Legacy CTA Survey",
        slug="legacy-cta-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    # No group created — simulates a pre-commit-2 survey
    assert survey.question_groups.count() == 0

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # Should fall back to the groups page URL, not a broken group_builder link
    groups_url = reverse("surveys:groups", kwargs={"slug": survey.slug})
    assert groups_url.encode() in resp.content, (
        f"Legacy survey with no groups should fall back to {groups_url}, "
        f"but the URL was not found in the response."
    )


# ---------------------------------------------------------------------------
# Commit 4 — Reframe user-facing templates to "Sections"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_groups_page_heading_says_sections(auth_client, owner):
    """The Groups page heading uses 'Sections', not 'Question Groups'."""
    from checktick_app.surveys.models import Organization

    org = Organization.objects.create(name="Sections Test Org", owner=owner)
    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Sections Heading Survey",
        slug="sections-heading-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"Sections for" in resp.content
    ), "Groups page heading should say 'Sections for {survey}', not 'Question Groups for'."
    assert (
        b"Question Groups for" not in resp.content
    ), "The old 'Question Groups for' heading should no longer appear."


@pytest.mark.django_db
def test_group_builder_breadcrumb_says_sections(auth_client, owner):
    """The group_builder breadcrumb uses 'Sections', not 'Question Groups'."""
    survey = Survey.objects.create(
        owner=owner,
        name="Breadcrumb Test Survey",
        slug="breadcrumb-test-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id})
    )
    assert resp.status_code == 200
    assert (
        b"Section" in resp.content
    ), "group_builder page should use 'Section' as the label, not 'Question Group'."
    assert (
        b"Question Group" not in resp.content
    ), "The old 'Question Group' label should no longer appear in group_builder."


@pytest.mark.django_db
def test_question_bank_page_title(auth_client, owner):
    """The template library page <h1> says 'Question Bank' (aligned with navbar)."""
    resp = auth_client.get(reverse("surveys:published_templates_list"))
    assert resp.status_code == 200
    assert (
        b"Question Bank" in resp.content
    ), "The template library page heading should say 'Question Bank'."
    # The old explainer heading "What are Question Groups?" should be gone
    assert (
        b"What are Question Groups?" not in resp.content
    ), "The old 'What are Question Groups?' explainer should be reframed."


@pytest.mark.django_db
def test_publish_page_heading(auth_client, owner):
    """The publish page heading says 'Share section as template'."""
    survey = Survey.objects.create(
        owner=owner,
        name="Publish Heading Survey",
        slug="publish-heading-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    # The publish view requires at least one question in the group
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="What is your name?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(
        reverse(
            "surveys:question_group_publish",
            kwargs={"slug": survey.slug, "gid": group.id},
        )
    )
    assert resp.status_code == 200
    assert (
        b"Share section as template" in resp.content
    ), "Publish page heading should say 'Share section as template'."
    assert (
        b"Publish Question Group" not in resp.content
    ), "The old 'Publish Question Group' heading should no longer appear."


# ---------------------------------------------------------------------------
# Commit 5 — Rewrite the Groups page empty state
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_groups_empty_state_leads_with_add_question(auth_client, owner):
    """A survey with no groups shows 'Add your first question' as the primary CTA."""
    survey = Survey.objects.create(
        owner=owner,
        name="Empty State Survey",
        slug="empty-state-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    # No groups — simulates a legacy survey or one created before commit 2
    assert survey.question_groups.count() == 0

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    assert (
        b"Add your first question" in resp.content
    ), "The empty state should lead with 'Add your first question' as the primary CTA."
    # The old "Create from scratch" primary action should no longer appear
    assert (
        b"Create from scratch" not in resp.content
    ), "The old 'Create from scratch' primary action should be replaced."


@pytest.mark.django_db
def test_groups_empty_state_keeps_question_bank_link(auth_client, owner):
    """The empty state still shows the 'Browse the Question Bank' link."""
    survey = Survey.objects.create(
        owner=owner,
        name="Bank Link Survey",
        slug="bank-link-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    bank_url = reverse("surveys:published_templates_list")
    assert (
        bank_url.encode() in resp.content
    ), "The 'Browse the Question Bank' link should still be present in the empty state."
    assert (
        b"Browse the Question Bank" in resp.content
    ), "The 'Browse the Question Bank' label should be present."


@pytest.mark.django_db
def test_groups_page_has_rename_button(auth_client, owner):
    """Each section row in the groups page has a 'Rename' button."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rename Button Survey",
        slug="rename-button-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    assert (
        b"rename-section-btn" in resp.content
    ), "Each section row should have a rename button with class 'rename-section-btn'."
    assert (
        b"Rename section" in resp.content
    ), "The rename button tooltip should say 'Rename section'."


@pytest.mark.django_db
def test_rename_section_via_post(auth_client, owner):
    """POSTing to survey_group_edit renames the section and redirects to groups page."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rename POST Survey",
        slug="rename-post-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    assert group.name == DEFAULT_SECTION_NAME

    resp = auth_client.post(
        reverse(
            "surveys:survey_group_edit", kwargs={"slug": survey.slug, "gid": group.id}
        ),
        data={"name": "Demographics", "description": "Patient demographics"},
    )
    assert resp.status_code == 302
    # Should redirect back to the groups page, not the dashboard
    assert reverse("surveys:groups", kwargs={"slug": survey.slug}) in resp["Location"]

    group.refresh_from_db()
    assert group.name == "Demographics"
    assert group.description == "Patient demographics"


# ---------------------------------------------------------------------------
# Commit 6 — One-line "why" hint at first use
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_builder_shows_why_hint_with_questions(auth_client, owner):
    """The group_builder shows the 'why sections exist' hint when there are questions."""
    survey = Survey.objects.create(
        owner=owner,
        name="Hint With Questions Survey",
        slug="hint-with-questions-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="What is your name?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(
        reverse("surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id})
    )
    assert resp.status_code == 200
    assert (
        b"Sections group related questions" in resp.content
    ), "The 'why sections exist' hint should appear when the group has questions."


@pytest.mark.django_db
def test_builder_hides_why_hint_when_empty(auth_client, owner):
    """The group_builder does NOT show the hint when the group has no questions."""
    survey = Survey.objects.create(
        owner=owner,
        name="Hint Empty Survey",
        slug="hint-empty-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    # No questions in this group

    resp = auth_client.get(
        reverse("surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id})
    )
    assert resp.status_code == 200
    assert (
        b"Sections group related questions" not in resp.content
    ), "The 'why sections exist' hint should NOT appear when the group has no questions."


# ---------------------------------------------------------------------------
# Breadcrumb label: "Manage Question" → "Questions"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_group_builder_breadcrumb_says_questions(auth_client, owner):
    """The group_builder breadcrumb and h1 use 'Questions', not 'Manage Question'."""
    survey = Survey.objects.create(
        owner=owner,
        name="Breadcrumb Label Survey",
        slug="breadcrumb-label-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id})
    )
    assert resp.status_code == 200
    assert (
        b"Questions" in resp.content
    ), "The group_builder page should use 'Questions' as the breadcrumb and h1 label."
    assert (
        b"Manage Question" not in resp.content
    ), "The old 'Manage Question' label should no longer appear."


# ---------------------------------------------------------------------------
# Commit 7 — Suppress redundant single-section header in participant view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_participant_view_single_section_no_header(auth_client, owner):
    """A single-section survey renders no section header for the participant.

    Uses the preview route since the owner is redirected from the live detail view.
    The <fieldset> structure is preserved for assistive tech, but the visible
    card-title with the group name is suppressed.
    """
    survey = Survey.objects.create(
        owner=owner,
        name="Single Section Participant Survey",
        slug="single-section-participant-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="What is your name?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The fieldset should still be present (a11y structure preserved)
    assert (
        b"<fieldset" in resp.content
    ), "The <fieldset> structure should be preserved for assistive tech."
    # The section name should NOT appear as a visible header
    assert group.name.encode() not in resp.content, (
        f"The section name '{group.name}' should not be rendered as a visible "
        f"header for a single-section survey."
    )


@pytest.mark.django_db
def test_participant_view_multi_section_shows_headers(auth_client, owner):
    """A multi-section survey still renders section headers for the participant."""
    survey = Survey.objects.create(
        owner=owner,
        name="Multi Section Participant Survey",
        slug="multi-section-participant-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group1,
        text="What is your name?",
        type=SurveyQuestion.Types.TEXT,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=group2,
        text="Do you have any allergies?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # Both section names should appear as visible headers
    assert (
        b"Demographics" in resp.content
    ), "The section name 'Demographics' should be rendered for a multi-section survey."
    assert (
        b"Medical History" in resp.content
    ), "The section name 'Medical History' should be rendered for a multi-section survey."
