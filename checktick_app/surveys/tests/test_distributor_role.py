"""Distributor role — survey-level distribution access.

Covers docs/appraisal-implementation-plan.md §3.1 and §11:

- ``SurveyMembership.Role.DISTRIBUTOR``: one notch below EDITOR — can
  generate token batches / QR codes and see completion counts, but never
  edit the survey or read results.
- ``can_distribute_survey`` / ``require_can_distribute`` permission
  helpers.
- Tokens page (view, batch generation, CSV export) accepts distributors;
  per-token category overrides and results views do not.
- Dashboard: distributor memberships surface in a distinct "Distributing"
  group with ``can_edit=False`` / ``can_manage=False``.
- Auto-redirect guard: users whose only access is a distributor
  membership are not swallowed by the pure-participant redirect.
"""

from __future__ import annotations

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyAccessToken,
    SurveyMembership,
    SurveyQuestion,
)
from checktick_app.surveys.permissions import (
    can_distribute_survey,
    can_view_survey,
)
from checktick_app.surveys.views import create_default_section

PASSWORD = "securepass123"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    settings.AXES_ENABLED = False


def _make_user(django_user_model, username):
    from checktick_app.core.models import UserProfile

    user = django_user_model.objects.create_user(
        username=username, email=username, password=PASSWORD
    )
    UserProfile.objects.filter(user=user).update(
        account_tier=UserProfile.AccountTier.PRO, email_confirmed=True
    )
    user._state.fields_cache.pop("profile", None)
    return user


@pytest.fixture
def owner(django_user_model):
    return _make_user(django_user_model, "dist_owner@example.com")


@pytest.fixture
def distributor(django_user_model):
    return _make_user(django_user_model, "dist_distributor@example.com")


@pytest.fixture
def viewer(django_user_model):
    return _make_user(django_user_model, "dist_viewer@example.com")


@pytest.fixture
def survey(owner):
    s = Survey.objects.create(
        owner=owner,
        name="Distributor Survey",
        slug="distributor-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
    )
    create_default_section(s, owner)
    SurveyQuestion.objects.create(
        survey=s,
        group=s.question_groups.first(),
        text="What is your name?",
        type=SurveyQuestion.Types.TEXT,
    )
    return s


@pytest.fixture
def dist_membership(distributor, survey):
    return SurveyMembership.objects.create(
        survey=survey, user=distributor, role=SurveyMembership.Role.DISTRIBUTOR
    )


@pytest.fixture
def dist_client(client, distributor):
    client.force_login(distributor)
    return client


@pytest.fixture
def viewer_client(client, viewer):
    client.force_login(viewer)
    return client


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_can_distribute_survey(owner, distributor, viewer, survey, dist_membership):
    assert can_distribute_survey(owner, survey), "owner can distribute"
    assert can_distribute_survey(distributor, survey), "distributor can distribute"
    assert not can_distribute_survey(viewer, survey), "viewer cannot distribute"


@pytest.mark.django_db
def test_can_distribute_survey_editor_and_anonymous(django_user_model, survey, owner):
    editor = _make_user(django_user_model, "dist_editor@example.com")
    SurveyMembership.objects.create(
        survey=survey, user=editor, role=SurveyMembership.Role.EDITOR
    )
    assert can_distribute_survey(editor, survey), "editor can distribute"

    from django.contrib.auth.models import AnonymousUser

    assert not can_distribute_survey(AnonymousUser(), survey)


@pytest.mark.django_db
def test_can_distribute_survey_org_admin(owner, django_user_model):
    org_admin = _make_user(django_user_model, "dist_orgadmin@example.com")
    org = Organization.objects.create(name="Dist Org", owner=org_admin)
    OrganizationMembership.objects.create(
        organization=org, user=org_admin, role=OrganizationMembership.Role.ADMIN
    )
    s = Survey.objects.create(
        owner=owner, organization=org, name="Org Dist Survey", slug="org-dist-survey"
    )
    assert can_distribute_survey(org_admin, s), "org admin can distribute"


@pytest.mark.django_db
def test_distributor_cannot_view_survey(owner, distributor, survey, dist_membership):
    """A distributor-only membership does not grant results access —
    can_view_survey excludes it so summary/export views stay closed."""
    assert not can_view_survey(distributor, survey)


# ---------------------------------------------------------------------------
# Tokens page access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_distributor_can_view_tokens_page(dist_client, survey, dist_membership):
    resp = dist_client.get(reverse("surveys:tokens", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    # Completion counts (used_at) are visible; the per-token category
    # edit form is not (edit-level only).
    assert b"token_categories_edit" not in resp.content


@pytest.mark.django_db
def test_distributor_can_generate_token_batch(dist_client, survey, dist_membership):
    resp = dist_client.post(
        reverse("surveys:tokens", kwargs={"slug": survey.slug}),
        {"count": "5", "note": "dist batch"},
    )
    assert resp.status_code == 302
    assert SurveyAccessToken.objects.filter(survey=survey).count() == 5


@pytest.mark.django_db
def test_distributor_can_export_token_csv(dist_client, survey, dist_membership):
    resp = dist_client.get(
        reverse("surveys:tokens_export_csv", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_distributor_cannot_edit_token_categories(
    dist_client, survey, dist_membership, owner
):
    token = SurveyAccessToken.objects.create(survey=survey, created_by=owner)
    resp = dist_client.post(
        reverse(
            "surveys:token_categories_edit",
            kwargs={"slug": survey.slug, "token_id": token.id},
        ),
        {},
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_access_tokens_page(client, survey):
    resp = client.get(reverse("surveys:tokens", kwargs={"slug": survey.slug}))
    assert resp.status_code == 302  # login_required redirect


@pytest.mark.django_db
def test_viewer_membership_cannot_access_tokens_page(viewer_client, viewer, survey):
    SurveyMembership.objects.create(
        survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )
    resp = viewer_client.get(reverse("surveys:tokens", kwargs={"slug": survey.slug}))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Results access denied
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_distributor_cannot_view_summary(dist_client, survey, dist_membership):
    resp = dist_client.get(
        reverse("surveys:survey_summary", kwargs={"slug": survey.slug})
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Dashboard grouping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_list_distributing_group(client, distributor, survey, dist_membership):
    client.force_login(distributor)
    resp = client.get(reverse("surveys:list"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Distributing" in html
    assert "distributor-survey" in html


@pytest.mark.django_db
def test_survey_list_distributor_not_redirected_to_invite(
    client, distributor, survey, dist_membership, owner
):
    """A user whose only access is a distributor membership must not be
    swallowed by the pure-participant auto-redirect when a live invite
    exists."""
    SurveyAccessToken.objects.create(
        survey=survey,
        created_by=owner,
        for_authenticated=True,
        note=f"Invited: {distributor.email}",
    )
    client.force_login(distributor)
    resp = client.get(reverse("surveys:list"))
    assert resp.status_code == 200, "should render the list, not redirect to take"
    assert b"Distributing" in resp.content


@pytest.mark.django_db
def test_survey_list_pure_participant_still_redirected(
    client, django_user_model, survey, owner
):
    """Without a distributor membership the existing auto-redirect
    behaviour is unchanged."""
    from checktick_app.core.models import UserProfile

    participant = django_user_model.objects.create_user(
        username="dist_participant@example.com",
        email="dist_participant@example.com",
        password=PASSWORD,
    )
    UserProfile.objects.filter(user=participant).update(email_confirmed=True)
    SurveyAccessToken.objects.create(
        survey=survey,
        created_by=owner,
        for_authenticated=True,
        note=f"Invited: {participant.email}",
    )
    client.force_login(participant)
    resp = client.get(reverse("surveys:list"))
    assert resp.status_code == 302
    assert resp.url == reverse("surveys:take", kwargs={"slug": survey.slug})


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_survey_users_can_add_distributor(client, owner, survey, django_user_model):
    # Adding a distributor is tier-gated like adding a viewer (Organization
    # tier), so the managing user needs an org-tier effective account.
    from checktick_app.core.models import UserProfile

    UserProfile.objects.filter(user=owner).update(
        account_tier=UserProfile.AccountTier.ORGANIZATION
    )
    owner._state.fields_cache.pop("profile", None)
    # can_manage_survey_users requires org context for the managing user
    org = Organization.objects.create(name="Dist Users Org", owner=owner)
    OrganizationMembership.objects.create(
        organization=org, user=owner, role=OrganizationMembership.Role.ADMIN
    )
    org_survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Dist Users Survey",
        slug="dist-users-survey",
    )
    target = _make_user(django_user_model, "dist_target@example.com")
    client.force_login(owner)
    resp = client.post(
        reverse("surveys:survey_users", kwargs={"slug": org_survey.slug}),
        {"action": "add", "email": "dist_target@example.com", "role": "distributor"},
    )
    assert resp.status_code == 302
    assert SurveyMembership.objects.filter(
        survey=org_survey, user=target, role=SurveyMembership.Role.DISTRIBUTOR
    ).exists()
