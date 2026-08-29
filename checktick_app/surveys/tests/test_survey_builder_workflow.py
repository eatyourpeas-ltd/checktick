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
            "password": PASSWORD,
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
def test_dashboard_cta_points_at_unified_builder(auth_client, owner):
    """The "Add questions" card links to the unified builder (survey_builder)."""
    # Create a survey with the default group (as survey_create now does)
    survey = Survey.objects.create(
        owner=owner,
        name="CTA Test Survey",
        slug="cta-test-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The CTA should link to survey_builder (unified builder), not group_builder
    expected_url = reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
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
    """The Groups page heading now says 'Organise' (commit 3.3 renamed it from 'Sections for')."""
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
        b"Organise" in resp.content
    ), "Groups page heading should say 'Organise {survey}' (commit 3.3 rename)."
    assert (
        b"Sections for" not in resp.content
    ), "The old 'Sections for' heading should no longer appear."
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
def test_groups_page_no_rename_button(auth_client, owner):
    """The Organise page no longer has a rename button — rename is builder-only."""
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
        b"rename-section-btn" not in resp.content
    ), "The Organise page should not have a rename button (it's builder-only now)."
    assert (
        b"rename-section-modal" not in resp.content
    ), "The Organise page should not have a rename modal (it's builder-only now)."


@pytest.mark.django_db
def test_groups_page_no_delete_button(auth_client, owner):
    """The Organise page no longer has a per-row delete button — delete is builder-only."""
    survey = Survey.objects.create(
        owner=owner,
        name="Delete Button Survey",
        slug="delete-button-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Section 1", owner=owner)
    group2 = QuestionGroup.objects.create(name="Section 2", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The delete form action should not appear in the Organise page.
    delete_url = f"/surveys/{survey.slug}/groups/{group2.id}/delete"
    assert (
        delete_url.encode() not in resp.content
    ), "The Organise page should not have a per-row delete form (it's builder-only now)."
    # But the publish button should still be there.
    assert (
        b"Publish" in resp.content
    ), "The Organise page should still have a Publish button."


@pytest.mark.django_db
def test_groups_page_points_to_builder_for_rename_delete(auth_client, owner):
    """The Organise page signposts the Builder for rename/delete."""
    survey = Survey.objects.create(
        owner=owner,
        name="Signpost Survey",
        slug="signpost-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    builder_url = f"/surveys/{survey.slug}/builder/"
    assert (
        builder_url.encode() in resp.content
    ), "The Organise page should link to the Builder for rename/delete."
    assert (
        b"Builder" in resp.content
    ), "The Organise page should mention the Builder by name."


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


# ---------------------------------------------------------------------------
# Commit 2.1 — Unified builder view + route (extract shared partial)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_group_builder_still_works_after_extraction(auth_client, owner):
    """The existing group_builder route still renders the question pane after
    the extraction into builder_question_pane.html."""
    survey = Survey.objects.create(
        owner=owner,
        name="Extraction Test Survey",
        slug="extraction-test-survey",
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
        b"Questions in this group" in resp.content
    ), "group_builder should still render the question list after partial extraction."
    assert (
        b"create-question-form" in resp.content
    ), "group_builder should still render the question-create form after partial extraction."


@pytest.mark.django_db
def test_survey_builder_view_renders(auth_client, owner):
    """The unified builder route renders with the section rail and question pane."""
    survey = Survey.objects.create(
        owner=owner,
        name="Unified Builder Survey",
        slug="unified-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"create-question-form" in resp.content
    ), "The unified builder should render the question-create form."


@pytest.mark.django_db
def test_survey_builder_defaults_to_first_group(auth_client, owner):
    """No gid param → the first group is active and its questions render."""
    survey = Survey.objects.create(
        owner=owner,
        name="Default Group Survey",
        slug="default-group-survey",
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
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    # The survey name is always rendered in the h2
    assert (
        b"Default Group Survey" in resp.content
    ), "The survey name should appear in the builder page."
    # The active group's question should be rendered in the question pane
    assert (
        b"What is your name?" in resp.content
    ), "The first group's questions should be rendered by default."


@pytest.mark.django_db
def test_survey_builder_selects_group_by_gid(auth_client, owner):
    """Passing ?gid=<gid> selects that group as active."""
    survey = Survey.objects.create(
        owner=owner,
        name="GID Select Survey",
        slug="gid-select-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group2,
        text="Allergies?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
        + f"?gid={group2.id}"
    )
    assert resp.status_code == 200
    # group2's question should be visible, and group2 should be the active section
    assert (
        b"Allergies?" in resp.content
    ), "The selected group's questions should be rendered."


@pytest.mark.django_db
def test_survey_builder_mobile_dropdown_present(auth_client, owner):
    """A multi-section survey renders a <select> dropdown for mobile section switching."""
    survey = Survey.objects.create(
        owner=owner,
        name="Mobile Dropdown Survey",
        slug="mobile-dropdown-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"<select" in resp.content
    ), "A <select> dropdown should be present for mobile section switching."
    assert (
        b"md:hidden" in resp.content
    ), "The mobile dropdown should be hidden on desktop via md:hidden."


@pytest.mark.django_db
def test_survey_builder_desktop_rail_present(auth_client, owner):
    """A multi-section survey renders the vertical section rail for desktop."""
    survey = Survey.objects.create(
        owner=owner,
        name="Desktop Rail Survey",
        slug="desktop-rail-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    # The desktop rail should be present (hidden md:block)
    assert (
        b"hidden md:block" in resp.content
    ), "The desktop rail should be present and visible on md+ via hidden md:block."
    assert (
        b"Add section" in resp.content
    ), "The 'Add section' button should be present in the rail."


@pytest.mark.django_db
def test_survey_builder_requires_edit_permission(auth_client, owner, django_user_model):
    """A viewer (not an editor) gets 403 on the unified builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Permission Test Survey",
        slug="permission-test-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    # Create a viewer who is not the owner and has no edit access
    viewer = django_user_model.objects.create_user(
        username="viewer@example.com",
        email="viewer@example.com",
        password=PASSWORD,
    )
    from checktick_app.core.models import UserProfile

    UserProfile.objects.filter(user=viewer).update(
        account_tier=UserProfile.AccountTier.PRO,
        email_confirmed=True,
    )

    client = type(auth_client)()
    client.force_login(viewer)

    resp = client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert (
        resp.status_code == 403
    ), "A viewer without edit access should get 403 on the builder."


# ---------------------------------------------------------------------------
# Section rail drag-reorder (reuses the Organise page's survey_groups_reorder)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_builder_rail_has_drag_handles_for_editors(auth_client, owner):
    """The builder rail renders a drag handle on each section for editors."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail Drag Handle Survey",
        slug="rail-drag-handle-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"drag-handle" in resp.content
    ), "The rail should render a drag handle for editors."
    # The rail list should carry the reorder URL and can-edit flag for the JS.
    assert (
        b'data-reorder-url="/surveys/rail-drag-handle-survey/groups/reorder"'
        in resp.content
    )
    assert b'data-can-edit="true"' in resp.content
    # Each rail item should expose its group id for the reorder JS to collect.
    assert f'data-gid="{group1.id}"'.encode() in resp.content
    assert f'data-gid="{group2.id}"'.encode() in resp.content


@pytest.mark.django_db
def test_builder_rail_reorder_persists_via_existing_endpoint(auth_client, owner):
    """Reordering from the builder rail POSTs to the shared survey_groups_reorder
    endpoint and persists the new order on survey.style.group_order."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail Reorder Survey",
        slug="rail-reorder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="History", owner=owner)
    group3 = QuestionGroup.objects.create(name="Follow-up", owner=owner)
    survey.question_groups.add(group1, group2, group3)

    # The rail JS POSTs order=ids.join(",") — same shape as the Organise page.
    new_order = [group3.id, group1.id, group2.id]
    resp = auth_client.post(
        reverse("surveys:survey_groups_reorder", kwargs={"slug": survey.slug}),
        data={"order": ",".join(str(i) for i in new_order)},
    )
    assert resp.status_code in (302, 200)
    survey.refresh_from_db()
    assert (survey.style or {}).get("group_order") == new_order


@pytest.mark.django_db
def test_builder_rail_oob_swap_preserves_drag_handles(auth_client, owner):
    """After an HTMX section-switch (which OOB-swaps the rail), the rail still
    has drag handles and data attributes — i.e. the OOB swap uses the same
    partial as the initial render, not stale markup."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail OOB Survey",
        slug="rail-oob-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="History", owner=owner)
    survey.question_groups.add(group1, group2)
    SurveyQuestion.objects.create(
        survey=survey, group=group1, text="Q1?", type=SurveyQuestion.Types.TEXT
    )

    # Simulate clicking section 2 via HTMX (the same request the rail <a> fires).
    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug}),
        {"gid": str(group2.id)},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    # The OOB-swapped rail should still have drag handles and the rail list id.
    assert b"drag-handle" in resp.content, "OOB rail should still have drag handles."
    assert (
        b"builder-rail-list" in resp.content
    ), "OOB rail should still have the list id."
    assert f'data-gid="{group2.id}"'.encode() in resp.content


# ---------------------------------------------------------------------------
# Repeat controls in the builder rail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_builder_rail_has_create_repeat_button(auth_client, owner):
    """Non-repeated sections show a 'Make repeatable' button in the rail."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail Repeat Create Survey",
        slug="rail-repeat-create-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"create-repeat-btn" in resp.content
    ), "Rail should have a create-repeat button."
    assert b"Make this section repeatable" in resp.content
    # The repeat create modal should be present.
    assert b"repeat-create-modal" in resp.content
    assert b"repeat-create-form" in resp.content


@pytest.mark.django_db
def test_builder_rail_has_edit_repeat_button_when_repeated(auth_client, owner):
    """Repeated sections show an edit-repeat button instead of create-repeat."""
    from checktick_app.surveys.models import CollectionDefinition, CollectionItem

    survey = Survey.objects.create(
        owner=owner,
        name="Rail Repeat Edit Survey",
        slug="rail-repeat-edit-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Visits", owner=owner)
    group2 = QuestionGroup.objects.create(name="Other", owner=owner)
    survey.question_groups.add(group1, group2)

    # Make group1 a repeat.
    cd = CollectionDefinition.objects.create(
        survey=survey, key="visits", name="Visits", max_count=5
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=group1, order=0
    )

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    # group1 should have an edit-repeat button, not a create-repeat button.
    assert (
        b"edit-repeat-btn" in resp.content
    ), "Repeated section should have edit-repeat button."
    # group2 (non-repeated) should still have create-repeat.
    assert b"create-repeat-btn" in resp.content
    # The repeat edit modal should be present.
    assert b"repeat-edit-modal" in resp.content


@pytest.mark.django_db
def test_create_repeat_from_builder_redirects_to_builder(auth_client, owner):
    """POSTing to survey_groups_repeat_create with next=/builder/ redirects back to the builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Repeat From Builder Survey",
        slug="repeat-from-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Visits", owner=owner)
    survey.question_groups.add(group1)

    builder_url = f"/surveys/{survey.slug}/builder/"
    resp = auth_client.post(
        reverse("surveys:survey_groups_repeat_create", kwargs={"slug": survey.slug}),
        data={
            "name": "Visits",
            "min_count": "0",
            "max_count": "5",
            "group_ids": str(group1.id),
            "next": builder_url,
        },
    )
    assert resp.status_code == 302
    assert resp.url == builder_url, "Should redirect back to the builder."


@pytest.mark.django_db
def test_remove_repeat_from_builder_redirects_to_builder(auth_client, owner):
    """POSTing to survey_group_repeat_remove with next=/builder/ redirects back to the builder."""
    from checktick_app.surveys.models import CollectionDefinition, CollectionItem

    survey = Survey.objects.create(
        owner=owner,
        name="Remove Repeat Builder Survey",
        slug="remove-repeat-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Visits", owner=owner)
    survey.question_groups.add(group1)
    cd = CollectionDefinition.objects.create(
        survey=survey, key="visits", name="Visits", max_count=5
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=group1, order=0
    )

    builder_url = f"/surveys/{survey.slug}/builder/"
    resp = auth_client.post(
        reverse(
            "surveys:survey_group_repeat_remove",
            kwargs={"slug": survey.slug, "gid": group1.id},
        ),
        data={"next": builder_url},
    )
    assert resp.status_code == 302
    assert resp.url == builder_url, "Should redirect back to the builder."
    # The group should no longer be in a repeat.
    assert not CollectionItem.objects.filter(
        collection__survey=survey, group=group1
    ).exists()


@pytest.mark.django_db
def test_edit_repeat_from_builder_redirects_to_builder(auth_client, owner):
    """POSTing to survey_groups_repeat_edit with next=/builder/ redirects back to the builder."""
    from checktick_app.surveys.models import CollectionDefinition, CollectionItem

    survey = Survey.objects.create(
        owner=owner,
        name="Edit Repeat Builder Survey",
        slug="edit-repeat-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Visits", owner=owner)
    survey.question_groups.add(group1)
    cd = CollectionDefinition.objects.create(
        survey=survey, key="visits", name="Visits", max_count=5
    )
    CollectionItem.objects.create(
        collection=cd, item_type=CollectionItem.ItemType.GROUP, group=group1, order=0
    )

    builder_url = f"/surveys/{survey.slug}/builder/"
    resp = auth_client.post(
        reverse("surveys:survey_groups_repeat_edit", kwargs={"slug": survey.slug}),
        data={
            "collection_id": str(cd.id),
            "name": "Updated Visits",
            "min_count": "1",
            "max_count": "3",
            "next": builder_url,
        },
    )
    assert resp.status_code == 302
    assert resp.url == builder_url, "Should redirect back to the builder."
    cd.refresh_from_db()
    assert cd.name == "Updated Visits"
    assert cd.max_count == 3


# ---------------------------------------------------------------------------
# Commit 2.2 — Hide section rail for single-section surveys
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_builder_single_section_hides_rail(auth_client, owner):
    """A single-section survey now renders the rail (commit 3.2 changed this).

    Previously the rail was hidden for single-section surveys. Commit 3.2
    always renders the rail so users can see that sections exist and add more.
    The mobile dropdown is still hidden for single-section surveys.
    """
    survey = Survey.objects.create(
        owner=owner,
        name="Single Section Builder Survey",
        slug="single-section-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200

    # The mobile dropdown should NOT be present (single section)
    assert (
        b"md:hidden" not in resp.content
    ), "The mobile dropdown should not be present for a single-section survey."
    # The desktop rail SHOULD now be present (commit 3.2 — always render)
    assert (
        b'id="builder-rail"' in resp.content
    ), "The desktop rail should now be present for a single-section survey."


@pytest.mark.django_db
def test_survey_builder_single_section_has_visually_hidden_heading(auth_client, owner):
    """A single-section survey has a visually-hidden h2 with the section name for screen readers."""
    survey = Survey.objects.create(
        owner=owner,
        name="Hidden Heading Survey",
        slug="hidden-heading-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200

    # The section name should be present in a visually-hidden heading
    assert (
        b"sr-only" in resp.content
    ), "A visually-hidden (sr-only) heading should be present for a11y."
    assert (
        group.name.encode() in resp.content
    ), f"The section name '{group.name}' should be present in the visually-hidden heading."


@pytest.mark.django_db
def test_survey_builder_multi_section_shows_rail(auth_client, owner):
    """A multi-section survey renders the section rail (already tested in 2.1,
    but this confirms the rail is NOT hidden when single_section is false)."""
    survey = Survey.objects.create(
        owner=owner,
        name="Multi Section Rail Survey",
        slug="multi-section-rail-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200

    # The desktop rail should be present
    assert (
        b"hidden md:block" in resp.content
    ), "The desktop rail should be present for a multi-section survey."
    # The visually-hidden single-section heading should NOT be present
    assert (
        b"sr-only" not in resp.content
    ), "The visually-hidden heading should only appear for single-section surveys."


# ---------------------------------------------------------------------------
# Commit 2.3 — HTMX section switching + inline "Add section"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_section_switch_via_htmx_returns_partial(auth_client, owner):
    """HTMX GET to the builder with ?gid= returns just the question pane partial."""
    survey = Survey.objects.create(
        owner=owner,
        name="HTMX Switch Survey",
        slug="htmx-switch-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group2,
        text="Allergies?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
        + f"?gid={group2.id}",
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    # The partial should contain the question pane but NOT the full page chrome
    assert (
        b"create-question-form" in resp.content
    ), "The HTMX partial should contain the question-create form."
    assert (
        b"Allergies?" in resp.content
    ), "The selected group's questions should be in the partial."
    # The full-page breadcrumbs should NOT be in the partial
    assert (
        b"breadcrumbs" not in resp.content.lower()
    ), "The HTMX partial should not include the full page chrome (breadcrumbs)."


@pytest.mark.django_db
def test_section_switch_non_htmx_returns_full_page(auth_client, owner):
    """A non-HTMX GET to the builder with ?gid= returns the full page."""
    survey = Survey.objects.create(
        owner=owner,
        name="Non-HTMX Survey",
        slug="non-htmx-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
        + f"?gid={group2.id}"
    )
    assert resp.status_code == 200
    # The full page should contain breadcrumbs
    assert (
        b"breadcrumbs" in resp.content.lower() or b"crumb" in resp.content.lower()
    ), "The non-HTMX response should include the full page chrome."


@pytest.mark.django_db
def test_add_section_via_htmx_redirects_to_builder(auth_client, owner):
    """Posting to survey_group_create with a next= param redirects to the builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Add Section Survey",
        slug="add-section-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.post(
        reverse("surveys:survey_group_create", kwargs={"slug": survey.slug}),
        data={
            "name": "New Section",
            "next": f"/surveys/{survey.slug}/builder/",
        },
    )
    assert resp.status_code == 302
    # Should redirect to the builder with the new group's gid
    assert (
        f"/surveys/{survey.slug}/builder/" in resp["Location"]
    ), "The redirect should point at the builder, not the Groups page."
    assert (
        "gid=" in resp["Location"]
    ), "The redirect should include the new group's gid."
    # Verify the new group was created
    assert survey.question_groups.count() == 2


@pytest.mark.django_db
def test_mobile_dropdown_triggers_htmx_swap(auth_client, owner):
    """The mobile <select> has hx-get and hx-trigger=change for HTMX swapping."""
    survey = Survey.objects.create(
        owner=owner,
        name="Mobile HTMX Survey",
        slug="mobile-htmx-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    group2 = QuestionGroup.objects.create(name="Medical History", owner=owner)
    survey.question_groups.add(group1, group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    # The dropdown should have hx-trigger="change"
    assert (
        b'hx-trigger="change"' in resp.content
    ), "The mobile dropdown should have hx-trigger=change for HTMX swapping."
    assert (
        b'hx-target="#builder-main"' in resp.content
    ), "The mobile dropdown should target #builder-main for the swap."


# ---------------------------------------------------------------------------
# Commit 2.6 — Reimagine orientation strip as "How to build" explainer
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_how_to_build_explainer_present_on_survey_list(auth_client, owner):
    """The survey list page shows the 'How to build' explainer for new users."""
    resp = auth_client.get(reverse("surveys:list"))
    assert resp.status_code == 200
    assert (
        b"How it works" in resp.content
    ), "The 'How it works' heading should be present on the survey list page."
    assert (
        b"Add questions" in resp.content
    ), "The explainer should mention 'Add questions' as step 2."
    assert (
        b"Organise" in resp.content
    ), "The explainer should mention 'Organise (optional)' as step 3."
    # The old 3-step hierarchy (Survey → Sections → Questions) should not appear
    assert (
        b"top-level container" not in resp.content
    ), "The old 'top-level container' description should be gone."


@pytest.mark.django_db
def test_how_to_build_explainer_present_in_builder_empty_state(auth_client, owner):
    """The builder empty state no longer shows the generic 'How to build' explainer.

    Commit 3.1 replaced the `how_to_build.html` include in the builder empty
    state with a builder-specific `builder_empty_state.html` partial. The
    survey list page still uses `how_to_build.html`, so we only assert the
    builder no longer surfaces it here.
    """
    survey = Survey.objects.create(
        owner=owner,
        name="Empty Builder Explainer Survey",
        slug="empty-builder-explainer-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"How it works" not in resp.content
    ), "The generic 'How to build' explainer should no longer appear in the builder empty state."
    assert (
        b"No questions yet" in resp.content
    ), "The empty state should still say 'No questions yet'."


# ---------------------------------------------------------------------------
# Commit 3.1 — Replace builder empty state with question-type signposting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_builder_empty_state_signposts_question_types(auth_client, owner):
    """The builder empty state signposts the available question types."""
    survey = Survey.objects.create(
        owner=owner,
        name="Empty State Question Types Survey",
        slug="empty-state-question-types-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    # The empty state should mention at least a few of the question types.
    assert (
        b"Likert scale" in resp.content
    ), "The empty state should signpost the Likert scale question type."
    assert (
        b"Multiple choice" in resp.content
    ), "The empty state should signpost the multiple choice question type."
    assert (
        b"Dropdown" in resp.content
    ), "The empty state should signpost the dropdown question type."


@pytest.mark.django_db
def test_builder_empty_state_signposts_special_templates(auth_client, owner):
    """The builder empty state signposts the Special Templates tab."""
    survey = Survey.objects.create(
        owner=owner,
        name="Empty State Special Templates Survey",
        slug="empty-state-special-templates-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"Special Templates" in resp.content
    ), "The empty state should signpost the Special Templates tab."


@pytest.mark.django_db
def test_builder_empty_state_signposts_question_bank(auth_client, owner):
    """The builder empty state links to the Question Bank."""
    survey = Survey.objects.create(
        owner=owner,
        name="Empty State Question Bank Survey",
        slug="empty-state-question-bank-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    bank_url = reverse("surveys:published_templates_list")
    assert (
        bank_url.encode() in resp.content
    ), "The empty state should link to the Question Bank."
    assert (
        b"Browse the Question Bank" in resp.content
    ), "The empty state should mention the Question Bank by name."


@pytest.mark.django_db
def test_builder_empty_state_signposts_sections(auth_client, owner):
    """The builder empty state links to the Sections guide."""
    survey = Survey.objects.create(
        owner=owner,
        name="Empty State Sections Survey",
        slug="empty-state-sections-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"/docs/groups-view/" in resp.content
    ), "The empty state should link to the Sections guide."
    assert (
        b"Sections guide" in resp.content
    ), "The empty state should mention the Sections guide by name."


# ---------------------------------------------------------------------------
# Commit 2.7 — De-emphasise building cards when survey has questions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_building_cards_prominent_when_no_questions(auth_client, owner):
    """When a survey has no questions, the 3 building cards are prominent (not collapsed)."""
    survey = Survey.objects.create(
        owner=owner,
        name="No Questions Dashboard Survey",
        slug="no-questions-dashboard-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The heading should be a visible <h3>, not inside a <details> summary
    assert (
        b"<h3" in resp.content
    ), "The 'Add or edit questions' heading should be a visible h3 when no questions exist."
    assert (
        b"<details" not in resp.content or b"survey-style-collapse" in resp.content
    ), "The building cards should NOT be wrapped in a <details> element when no questions exist."


@pytest.mark.django_db
def test_dashboard_building_cards_collapsed_when_has_questions(auth_client, owner):
    """When a survey has questions, the 3 building cards are collapsed behind a caret."""
    survey = Survey.objects.create(
        owner=owner,
        name="Has Questions Dashboard Survey",
        slug="has-questions-dashboard-survey",
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

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The building cards should be wrapped in a <details> element
    assert (
        b"<details" in resp.content
    ), "The building cards should be collapsed in a <details> element when questions exist."
    # The summary should be present (i18n-safe: check for the <summary> tag, not the translated text)
    assert (
        b"<summary" in resp.content
    ), "A <summary> element should be present as the caret for the collapsed cards."


# ---------------------------------------------------------------------------
# Commit 2.8 — Builder toolbar (links to Sections page, Preview, Dashboard)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_builder_toolbar_present_when_has_questions(auth_client, owner):
    """The builder shows a toolbar with links to Organise sections, Preview, and Dashboard."""
    survey = Survey.objects.create(
        owner=owner,
        name="Toolbar Survey",
        slug="toolbar-survey",
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
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200

    # The "Organise sections" link should point at the Groups page
    groups_url = reverse("surveys:groups", kwargs={"slug": survey.slug})
    assert (
        groups_url.encode() in resp.content
    ), "The builder toolbar should link to the Sections (Groups) page."
    # The Preview link should be present
    assert (
        b"/preview/" in resp.content
    ), "The builder toolbar should link to the preview page."
    # The Back to dashboard link should be present
    assert (
        b"/dashboard/" in resp.content
    ), "The builder toolbar should link back to the dashboard."


@pytest.mark.django_db
def test_builder_toolbar_absent_when_no_questions(auth_client, owner):
    """The builder does NOT show the toolbar when the survey has no questions."""
    survey = Survey.objects.create(
        owner=owner,
        name="No Toolbar Survey",
        slug="no-toolbar-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200

    # The Groups page link should NOT be in the toolbar (no questions = no need to organise)
    _ = reverse("surveys:groups", kwargs={"slug": survey.slug})
    # The groups URL might appear in the rail's "Add section" form action, so we
    # check that it's not in a btn-outline toolbar link by checking for the toolbar
    # pattern specifically.
    assert (
        b"Organise sections" not in resp.content
    ), "The 'Organise sections' toolbar button should not appear when there are no questions."


# ---------------------------------------------------------------------------
# Commit 2.9 — Quick links back to builder from Sections page and Preview
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_groups_page_has_back_to_builder_link(auth_client, owner):
    """The Sections page has a 'Back to builder' link."""
    survey = Survey.objects.create(
        owner=owner,
        name="Groups Back Link Survey",
        slug="groups-back-link-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    builder_url = f"/surveys/{survey.slug}/builder/"
    assert (
        builder_url.encode() in resp.content
    ), "The Sections page should have a 'Back to builder' link."


# ---------------------------------------------------------------------------
# Commit 3.2 — Always render the section rail + add rename/delete to rail items
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rail_always_renders_for_single_section(auth_client, owner):
    """A single-section survey now shows the rail (previously hidden)."""
    survey = Survey.objects.create(
        owner=owner,
        name="Single Section Rail Survey",
        slug="single-section-rail-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b'id="builder-rail"' in resp.content
    ), "The section rail should always render when the survey has at least one group."


@pytest.mark.django_db
def test_rail_has_rename_button(auth_client, owner):
    """Each rail item has a rename button."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail Rename Survey",
        slug="rail-rename-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"rename-section-btn" in resp.content
    ), "Each rail item should have a rename button."


@pytest.mark.django_db
def test_rail_has_delete_button_for_second_section(auth_client, owner):
    """A multi-section survey shows a delete button on the second and subsequent rail items."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail Delete Multi Survey",
        slug="rail-delete-multi-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)
    # Add a second section
    group2 = QuestionGroup.objects.create(name="Second Section", owner=owner)
    survey.question_groups.add(group2)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"delete-section-btn" in resp.content
    ), "The second and subsequent rail items should have a delete button."


@pytest.mark.django_db
def test_rail_first_section_has_no_delete_button(auth_client, owner):
    """The first (or only) section's rail item does not show a delete button."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rail Delete Single Survey",
        slug="rail-delete-single-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert (
        b"delete-section-btn" not in resp.content
    ), "The first/only section should not have a delete button."


@pytest.mark.django_db
def test_rename_from_builder_redirects_to_builder(auth_client, owner):
    """POSTing to survey_group_edit with next=/surveys/<slug>/builder/ redirects back to the builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rename Redirect Survey",
        slug="rename-redirect-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.post(
        reverse(
            "surveys:survey_group_edit",
            kwargs={"slug": survey.slug, "gid": group.id},
        ),
        data={
            "name": "Renamed Section",
            "description": "",
            "next": f"/surveys/{survey.slug}/builder/",
        },
    )
    assert resp.status_code == 302
    assert resp.url == f"/surveys/{survey.slug}/builder/"
    group.refresh_from_db()
    assert group.name == "Renamed Section"


@pytest.mark.django_db
def test_rename_from_builder_strips_xss(auth_client, owner):
    """A group name with <script> tags is sanitised."""
    survey = Survey.objects.create(
        owner=owner,
        name="Rename XSS Survey",
        slug="rename-xss-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    auth_client.post(
        reverse(
            "surveys:survey_group_edit",
            kwargs={"slug": survey.slug, "gid": group.id},
        ),
        data={
            "name": "<script>alert('xss')</script>Evil",
            "description": "",
            "next": f"/surveys/{survey.slug}/builder/",
        },
    )
    group.refresh_from_db()
    assert "<script>" not in group.name
    assert "</script>" not in group.name
    assert group.name == "alert('xss')Evil"


@pytest.mark.django_db
def test_delete_section_from_builder_redirects_to_builder(auth_client, owner):
    """POSTing to survey_group_delete with next=/surveys/<slug>/builder/ deletes the section and redirects back to the builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Delete Redirect Survey",
        slug="delete-redirect-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    _ = create_default_section(survey, owner)
    group2 = QuestionGroup.objects.create(name="Second Section", owner=owner)
    survey.question_groups.add(group2)

    resp = auth_client.post(
        reverse(
            "surveys:survey_group_delete",
            kwargs={"slug": survey.slug, "gid": group2.id},
        ),
        data={"next": f"/surveys/{survey.slug}/builder/"},
    )
    assert resp.status_code == 302
    assert resp.url == f"/surveys/{survey.slug}/builder/"
    assert not QuestionGroup.objects.filter(id=group2.id).exists()


@pytest.mark.django_db
def test_delete_last_section_rejected(auth_client, owner):
    """Attempting to delete the only remaining section is rejected."""
    survey = Survey.objects.create(
        owner=owner,
        name="Delete Last Section Survey",
        slug="delete-last-section-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.post(
        reverse(
            "surveys:survey_group_delete",
            kwargs={"slug": survey.slug, "gid": group.id},
        ),
        data={"next": f"/surveys/{survey.slug}/builder/"},
    )
    assert resp.status_code == 302
    # The section should still exist
    assert QuestionGroup.objects.filter(id=group.id).exists()
    # The redirect should go back to the builder (via next)
    assert resp.url == f"/surveys/{survey.slug}/builder/"


# ---------------------------------------------------------------------------
# Commit 3.2a — Match builder card styling in Outline and AI Assistant views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_outline_card_has_primary_border(auth_client, owner):
    """The Outline (format reference) card has the border-primary accent."""
    survey = Survey.objects.create(
        owner=owner,
        name="Outline Styling Survey",
        slug="outline-styling-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The format reference card should have the primary border accent
    assert (
        b"border-l-4 border-primary" in resp.content
    ), "The Outline format reference card should have a border-primary left accent."


@pytest.mark.django_db
def test_ai_assistant_card_has_primary_border(auth_client, owner):
    """The AI Assistant conversation card has the border-primary accent."""
    survey = Survey.objects.create(
        owner=owner,
        name="AI Styling Survey",
        slug="ai-styling-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The AI conversation card should have the primary border accent
    assert (
        b"border-l-4 border-primary" in resp.content
    ), "The AI Assistant card should have a border-primary left accent."


@pytest.mark.django_db
def test_outline_secondary_panel_has_secondary_border(auth_client, owner):
    """Secondary panels (session history, live preview) have the border-secondary accent."""
    survey = Survey.objects.create(
        owner=owner,
        name="Secondary Panel Styling Survey",
        slug="secondary-panel-styling-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The session history card and live preview should have the secondary border accent
    assert (
        b"border-l-4 border-secondary" in resp.content
    ), "Secondary panels should have a border-secondary left accent."


# ---------------------------------------------------------------------------
# Commit 3.3 — Rename "Sections" page to "Organise" + replace orientation strip
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_organise_page_heading(auth_client, owner):
    """The heading says 'Organise', not 'Sections for'."""
    survey = Survey.objects.create(
        owner=owner,
        name="Organise Heading Survey",
        slug="organise-heading-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert b"Organise" in resp.content, "The heading should say 'Organise'."
    assert (
        b"Sections for" not in resp.content
    ), "The old 'Sections for' heading should be gone."


@pytest.mark.django_db
def test_organise_page_explainer(auth_client, owner):
    """The explainer mentions reordering, repeats, branching, visualising, and publishing."""
    survey = Survey.objects.create(
        owner=owner,
        name="Organise Explainer Survey",
        slug="organise-explainer-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"reorder" in resp.content.lower() or b"Reorder" in resp.content
    ), "The explainer should mention reordering."
    assert b"repeat" in resp.content.lower(), "The explainer should mention repeats."
    assert b"branch" in resp.content.lower(), "The explainer should mention branching."
    assert (
        b"visualis" in resp.content.lower() or b"visualiz" in resp.content.lower()
    ), "The explainer should mention visualising."
    assert (
        b"publish" in resp.content.lower()
    ), "The explainer should mention publishing."


@pytest.mark.django_db
def test_organise_page_links_to_builder(auth_client, owner):
    """The explainer links back to the builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Organise Link Survey",
        slug="organise-link-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    builder_url = f"/surveys/{survey.slug}/builder/"
    assert (
        builder_url.encode() in resp.content
    ), "The explainer should link back to the builder."
    assert (
        b"Builder" in resp.content
    ), "The explainer should mention the Builder by name."


@pytest.mark.django_db
def test_organise_page_no_orientation_strip(auth_client, owner):
    """The old 3-step orientation strip should be gone."""
    survey = Survey.objects.create(
        owner=owner,
        name="No Orientation Strip Survey",
        slug="no-orientation-strip-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"Where you are" not in resp.content
    ), "The old 'Where you are' orientation strip should be gone."
    assert (
        b"you are here" not in resp.content
    ), "The old 'you are here' badge should be gone."


@pytest.mark.django_db
def test_builder_toolbar_says_organise(auth_client, owner):
    """The builder toolbar button says 'Organise', not 'Organise sections'."""
    survey = Survey.objects.create(
        owner=owner,
        name="Toolbar Organise Survey",
        slug="toolbar-organise-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Test question?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    assert b"Organise" in resp.content, "The toolbar button should say 'Organise'."
    assert (
        b"Organise sections" not in resp.content
    ), "The old 'Organise sections' label should be gone."


# ---------------------------------------------------------------------------
# Commit 3.4 — Deprecate group_builder route
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_groups_page_section_links_to_unified_builder(auth_client, owner):
    """The Organise page section rows link to survey_builder?gid=<gid>, not group_builder."""
    survey = Survey.objects.create(
        owner=owner,
        name="Deprecate Group Builder Survey",
        slug="deprecate-group-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The section row link should point at the unified builder with ?gid=
    unified_url = f"/surveys/{survey.slug}/builder/?gid={group.id}"
    assert (
        unified_url.encode() in resp.content
    ), "Section rows should link to survey_builder?gid=<gid>, not group_builder."
    # The old group_builder URL should NOT appear in section row links
    old_url = f"/surveys/{survey.slug}/builder/groups/{group.id}/"
    assert (
        old_url.encode() not in resp.content
    ), "Section rows should not link to the deprecated group_builder route."


@pytest.mark.django_db
def test_group_builder_route_still_works(auth_client, owner):
    """The old group_builder route still returns 200 (for bookmarked URLs)."""
    survey = Survey.objects.create(
        owner=owner,
        name="Bookmark Route Survey",
        slug="bookmark-route-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)

    resp = auth_client.get(
        reverse(
            "surveys:group_builder",
            kwargs={"slug": survey.slug, "gid": group.id},
        )
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Survey Map — standalone route for the branching visualiser
# (deferred item: "Extract the Survey Map visualiser to its own route")
# See docs/survey-builder-workflow-implementation-plan.md.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_map_view_renders(auth_client, owner):
    """The /<slug>/survey-map/ route renders the standalone visualiser page."""
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Renders Survey",
        slug="survey-map-renders-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="First question?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert b"Survey Map" in resp.content, "The page should be titled 'Survey Map'."
    # The visualiser partial is included when there are questions.
    assert (
        b"branching-visualizer" in resp.content
    ), "The branching visualiser partial should be rendered."
    assert b"flow-canvas" in resp.content, "The visualiser canvas should be present."


@pytest.mark.django_db
def test_survey_map_empty_state_without_questions(auth_client, owner):
    """A survey with no questions shows the empty-state signpost, not the canvas."""
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Empty Survey",
        slug="survey-map-empty-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"flow-canvas" not in resp.content
    ), "An empty survey should not render the visualiser canvas."
    builder_url = f"/surveys/{survey.slug}/builder/"
    assert (
        builder_url.encode() in resp.content
    ), "The empty state should signpost the Builder."


@pytest.mark.django_db
def test_survey_map_links_back_to_builder_and_organise(auth_client, owner):
    """The Survey Map toolbar links back to the Builder, Organise, and dashboard."""
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Links Survey",
        slug="survey-map-links-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Link question?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert f"/surveys/{survey.slug}/builder/".encode() in resp.content
    assert f"/surveys/{survey.slug}/groups/".encode() in resp.content
    assert f"/surveys/{survey.slug}/dashboard/".encode() in resp.content


@pytest.mark.django_db
def test_survey_map_requires_edit_permission(auth_client, owner, django_user_model):
    """A viewer (not an editor) gets 403 on the Survey Map — it is a builder tool."""
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Permission Survey",
        slug="survey-map-permission-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    viewer = django_user_model.objects.create_user(
        username="survey-map-viewer@example.com",
        email="survey-map-viewer@example.com",
        password=PASSWORD,
    )
    from checktick_app.core.models import UserProfile

    UserProfile.objects.filter(user=viewer).update(
        account_tier=UserProfile.AccountTier.PRO,
        email_confirmed=True,
    )

    client = type(auth_client)()
    client.force_login(viewer)

    resp = client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert (
        resp.status_code == 403
    ), "A viewer without edit access should get 403 on the Survey Map."


@pytest.mark.django_db
def test_survey_map_get_only(auth_client, owner):
    """POST to the Survey Map returns 405 — the route is GET-only."""
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Method Survey",
        slug="survey-map-method-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.post(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert resp.status_code == 405, "The Survey Map route should be GET-only."


@pytest.mark.django_db
def test_survey_map_requires_login(client, django_user_model):
    """An anonymous request to the Survey Map redirects to login (not 200)."""
    owner = django_user_model.objects.create_user(
        username="survey-map-anon-owner@example.com",
        email="survey-map-anon-owner@example.com",
        password=PASSWORD,
    )
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Anon Survey",
        slug="survey-map-anon-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    # @login_required redirects anonymous users to the login page (302).
    assert resp.status_code in (
        302,
        403,
    ), "Anonymous access to the Survey Map should redirect to login or deny."


# ---------------------------------------------------------------------------
# Survey Map wiring — surface the route from the builder toolbar, dashboard,
# and Organise page; remove the embedded visualiser from the Organise page.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_map_breadcrumb_uses_map_icon(auth_client, owner):
    """The Survey Map breadcrumb crumb uses the survey-map icon, not the default group icon."""
    survey = Survey.objects.create(
        owner=owner,
        name="Survey Map Breadcrumb Survey",
        slug="survey-map-breadcrumb-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:survey_map", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The survey-map icon renders a distinctive <circle cx="18" cy="6" r="3" />.
    # The h1 already uses the survey-map icon, so with the breadcrumb also using
    # it, this marker should appear at least twice (breadcrumb + h1).
    marker = b'<circle cx="18" cy="6" r="3"'
    assert (
        resp.content.count(marker) >= 2
    ), "The Survey Map breadcrumb and h1 should both use the survey-map icon."


@pytest.mark.django_db
def test_organise_page_no_embedded_survey_map(auth_client, owner):
    """The Organise page no longer embeds the visualiser canvas (it has its own route)."""
    survey = Survey.objects.create(
        owner=owner,
        name="Organise No Map Survey",
        slug="organise-no-map-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="A question?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert (
        b"flow-canvas" not in resp.content
    ), "The Organise page should not embed the visualiser canvas anymore."
    assert (
        b"branching-visualizer" not in resp.content
    ), "The Organise page should not embed the visualiser anymore."


@pytest.mark.django_db
def test_organise_page_links_to_survey_map(auth_client, owner):
    """The Organise page quick-nav links to the Survey Map route."""
    survey = Survey.objects.create(
        owner=owner,
        name="Organise Map Link Survey",
        slug="organise-map-link-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    map_url = f"/surveys/{survey.slug}/survey-map/"
    assert (
        map_url.encode() in resp.content
    ), "The Organise page should link to the Survey Map route."
    assert b"Survey Map" in resp.content


@pytest.mark.django_db
def test_builder_toolbar_links_to_survey_map(auth_client, owner):
    """The builder toolbar links to the Survey Map route."""
    survey = Survey.objects.create(
        owner=owner,
        name="Builder Map Link Survey",
        slug="builder-map-link-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    group = create_default_section(survey, owner)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Toolbar question?",
        type=SurveyQuestion.Types.TEXT,
    )

    resp = auth_client.get(
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200
    map_url = f"/surveys/{survey.slug}/survey-map/"
    assert (
        map_url.encode() in resp.content
    ), "The builder toolbar should link to the Survey Map route."


@pytest.mark.django_db
def test_dashboard_links_to_survey_map_when_can_edit(auth_client, owner):
    """The dashboard shows a Survey Map link for editors (the route requires edit)."""
    survey = Survey.objects.create(
        owner=owner,
        name="Dashboard Map Link Survey",
        slug="dashboard-map-link-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    map_url = f"/surveys/{survey.slug}/survey-map/"
    assert (
        map_url.encode() in resp.content
    ), "The dashboard should link to the Survey Map route for editors."


@pytest.mark.django_db
def test_dashboard_no_survey_map_link_for_viewer(auth_client, owner, django_user_model):
    """A view-only member sees the dashboard but not the Survey Map link (route requires edit)."""
    from checktick_app.core.models import UserProfile
    from checktick_app.surveys.models import SurveyMembership

    survey = Survey.objects.create(
        owner=owner,
        name="Dashboard Map Viewer Survey",
        slug="dashboard-map-viewer-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    viewer = django_user_model.objects.create_user(
        username="dash-map-viewer@example.com",
        email="dash-map-viewer@example.com",
        password=PASSWORD,
    )
    UserProfile.objects.filter(user=viewer).update(
        account_tier=UserProfile.AccountTier.PRO,
        email_confirmed=True,
    )
    # Grant view-only access: can_view_survey is True, can_edit_survey is False.
    SurveyMembership.objects.create(
        survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )

    client = type(auth_client)()
    client.force_login(viewer)

    resp = client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200, "A view-only member should reach the dashboard."
    map_url = f"/surveys/{survey.slug}/survey-map/"
    assert (
        map_url.encode() not in resp.content
    ), "A view-only member should not see the Survey Map link (the route requires edit)."
