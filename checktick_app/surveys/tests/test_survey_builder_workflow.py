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
    assert b"Questions in this group" in resp.content, (
        "group_builder should still render the question list after partial extraction."
    )
    assert b"create-question-form" in resp.content, (
        "group_builder should still render the question-create form after partial extraction."
    )


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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert b"create-question-form" in resp.content, (
        "The unified builder should render the question-create form."
    )


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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The survey name is always rendered in the h2
    assert b"Default Group Survey" in resp.content, (
        "The survey name should appear in the builder page."
    )
    # The active group's question should be rendered in the question pane
    assert b"What is your name?" in resp.content, (
        "The first group's questions should be rendered by default."
    )


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
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug}) + f"?gid={group2.id}"
    )
    assert resp.status_code == 200
    # group2's question should be visible, and group2 should be the active section
    assert b"Allergies?" in resp.content, (
        "The selected group's questions should be rendered."
    )


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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert b'<select' in resp.content, (
        "A <select> dropdown should be present for mobile section switching."
    )
    assert b'md:hidden' in resp.content, (
        "The mobile dropdown should be hidden on desktop via md:hidden."
    )


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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The desktop rail should be present (hidden md:block)
    assert b'hidden md:block' in resp.content, (
        "The desktop rail should be present and visible on md+ via hidden md:block."
    )
    assert b'Add section' in resp.content, (
        "The 'Add section' button should be present in the rail."
    )


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
    assert resp.status_code == 403, (
        "A viewer without edit access should get 403 on the builder."
    )


# ---------------------------------------------------------------------------
# Commit 2.2 — Hide section rail for single-section surveys
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_builder_single_section_hides_rail(auth_client, owner):
    """A single-section survey renders no section rail or dropdown."""
    survey = Survey.objects.create(
        owner=owner,
        name="Single Section Builder Survey",
        slug="single-section-builder-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(survey, owner)

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The mobile dropdown should NOT be present
    assert b'md:hidden' not in resp.content, (
        "The mobile dropdown should not be present for a single-section survey."
    )
    # The desktop rail should NOT be present
    assert b'hidden md:block' not in resp.content, (
        "The desktop rail should not be present for a single-section survey."
    )


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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The section name should be present in a visually-hidden heading
    assert b'sr-only' in resp.content, (
        "A visually-hidden (sr-only) heading should be present for a11y."
    )
    assert group.name.encode() in resp.content, (
        f"The section name '{group.name}' should be present in the visually-hidden heading."
    )


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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    # The desktop rail should be present
    assert b'hidden md:block' in resp.content, (
        "The desktop rail should be present for a multi-section survey."
    )
    # The visually-hidden single-section heading should NOT be present
    assert b'sr-only' not in resp.content, (
        "The visually-hidden heading should only appear for single-section surveys."
    )


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
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug}) + f"?gid={group2.id}",
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    # The partial should contain the question pane but NOT the full page chrome
    assert b"create-question-form" in resp.content, (
        "The HTMX partial should contain the question-create form."
    )
    assert b"Allergies?" in resp.content, (
        "The selected group's questions should be in the partial."
    )
    # The full-page breadcrumbs should NOT be in the partial
    assert b"breadcrumbs" not in resp.content.lower(), (
        "The HTMX partial should not include the full page chrome (breadcrumbs)."
    )


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
        reverse("surveys:survey_builder", kwargs={"slug": survey.slug}) + f"?gid={group2.id}"
    )
    assert resp.status_code == 200
    # The full page should contain breadcrumbs
    assert b"breadcrumbs" in resp.content.lower() or b"crumb" in resp.content.lower(), (
        "The non-HTMX response should include the full page chrome."
    )


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
    assert f"/surveys/{survey.slug}/builder/" in resp["Location"], (
        "The redirect should point at the builder, not the Groups page."
    )
    assert "gid=" in resp["Location"], (
        "The redirect should include the new group's gid."
    )
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

    resp = auth_client.get(reverse("surveys:survey_builder", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # The dropdown should have hx-trigger="change"
    assert b'hx-trigger="change"' in resp.content, (
        "The mobile dropdown should have hx-trigger=change for HTMX swapping."
    )
    assert b'hx-target="#builder-main"' in resp.content, (
        "The mobile dropdown should target #builder-main for the swap."
    )
