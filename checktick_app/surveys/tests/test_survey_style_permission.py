"""
Tests for the can_change_survey_style granular permission.

Gate rules:
  1. Free-tier users are always denied — style tab hidden, POST → 403.
  2. Survey owner on a paid tier is always allowed.
  3. Organisation admins on a paid tier are always allowed.
  4. Survey members with can_change_survey_style=True are allowed (paid tier).
  5. Survey members with can_change_survey_style=False are denied.
  6. The toggle_style_perm action in survey_users allows admin to flip the flag.
"""

from __future__ import annotations

from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)
from checktick_app.surveys.permissions import can_change_survey_style

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    settings.AXES_ENABLED = False


def _make_user(django_user_model, username, tier):
    user = django_user_model.objects.create_user(
        username=username, email=username, password="x"
    )
    # Use .update() to bypass the UserProfile.post_save signals, then clear
    # the Django ORM reverse-accessor cache on the user instance.  Without
    # this, the save_user_profile signal (which fires on every User.save(),
    # including the one triggered by force_login via update_last_login) calls
    # instance.profile.save() using the stale FREE-tier object that is stored
    # in instance._state.fields_cache, overwriting our desired tier back to FREE.
    UserProfile.objects.filter(user=user).update(account_tier=tier)
    user._state.fields_cache.pop("profile", None)
    return user


@pytest.fixture
def org(django_user_model):
    owner = _make_user(
        django_user_model, "style-org-owner@x.com", UserProfile.AccountTier.PRO
    )
    return Organization.objects.create(name="Style Test Org", owner=owner)


@pytest.fixture
def pro_owner(django_user_model, org):
    """Survey owner with PRO tier."""
    return org.owner


@pytest.fixture
def survey(pro_owner, org):
    return Survey.objects.create(
        owner=pro_owner,
        organization=org,
        name="Style Survey",
        slug="style-survey",
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
    )


@pytest.fixture
def free_user(django_user_model):
    return _make_user(
        django_user_model, "free-user@x.com", UserProfile.AccountTier.FREE
    )


@pytest.fixture
def pro_member(django_user_model, org, survey):
    """A PRO-tier VIEWER member — no style flag, no manage-users rights."""
    user = _make_user(
        django_user_model, "pro-member@x.com", UserProfile.AccountTier.PRO
    )
    SurveyMembership.objects.create(
        survey=survey, user=user, role=SurveyMembership.Role.VIEWER
    )
    return user
    return user


@pytest.fixture
def pro_member_with_style(django_user_model, org, survey):
    """A PRO-tier survey CREATOR member with can_change_survey_style=True."""
    user = _make_user(
        django_user_model, "pro-style-member@x.com", UserProfile.AccountTier.PRO
    )
    SurveyMembership.objects.create(
        survey=survey,
        user=user,
        role=SurveyMembership.Role.CREATOR,
        can_change_survey_style=True,
    )
    return user


@pytest.fixture
def org_admin(django_user_model, org):
    """A PRO-tier user who is an org admin (no direct survey membership)."""
    user = _make_user(django_user_model, "org-admin@x.com", UserProfile.AccountTier.PRO)
    OrganizationMembership.objects.create(
        organization=org, user=user, role=OrganizationMembership.Role.ADMIN
    )
    return user


# ---------------------------------------------------------------------------
# 1. Permission helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_free_tier_owner_denied(free_user, org, survey):
    """Even the survey owner is denied on free tier."""
    survey.owner = free_user
    survey.save(update_fields=["owner"])
    assert can_change_survey_style(free_user, survey) is False


@pytest.mark.django_db
def test_pro_owner_allowed(pro_owner, survey):
    assert can_change_survey_style(pro_owner, survey) is True


@pytest.mark.django_db
def test_org_admin_allowed(org_admin, survey):
    assert can_change_survey_style(org_admin, survey) is True


@pytest.mark.django_db
def test_pro_member_without_flag_denied(pro_member, survey):
    assert can_change_survey_style(pro_member, survey) is False


@pytest.mark.django_db
def test_pro_member_with_flag_allowed(pro_member_with_style, survey):
    assert can_change_survey_style(pro_member_with_style, survey) is True


@pytest.mark.django_db
def test_unauthenticated_user_denied(survey):
    from django.contrib.auth.models import AnonymousUser

    anon = AnonymousUser()
    assert can_change_survey_style(anon, survey) is False


# ---------------------------------------------------------------------------
# 2. survey_style_update view — HTTP-level gating
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_style_update_free_tier_returns_403(client, free_user, survey):
    """Free-tier users receive 403 when POSTing to style/update."""
    client.force_login(free_user)
    # Give them edit rights on the survey so the edit check passes, only the
    # style check should block them.
    SurveyMembership.objects.create(
        survey=survey, user=free_user, role=SurveyMembership.Role.CREATOR
    )
    resp = client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_heading": "Arial, sans-serif"},
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_style_update_pro_owner_succeeds(client, pro_owner, survey):
    """Survey owner on a paid tier can POST to style/update (redirect = 302)."""
    client.force_login(pro_owner)
    resp = client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_heading": "Arial, sans-serif"},
    )
    assert resp.status_code == 302
    survey.refresh_from_db()
    assert (survey.style or {}).get("font_heading") == "Arial, sans-serif"


@pytest.mark.django_db
def test_style_update_member_with_flag_succeeds(client, pro_member_with_style, survey):
    """A survey member who has the can_change_survey_style flag can update style."""
    client.force_login(pro_member_with_style)
    resp = client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_heading": "Georgia, serif"},
    )
    assert resp.status_code == 302
    survey.refresh_from_db()
    assert (survey.style or {}).get("font_heading") == "Georgia, serif"


@pytest.mark.django_db
def test_style_update_member_without_flag_returns_403(client, pro_member, survey):
    """A survey member without the style flag receives 403."""
    client.force_login(pro_member)
    resp = client.post(
        reverse("surveys:style_update", kwargs={"slug": survey.slug}),
        data={"font_heading": "Arial, sans-serif"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. Dashboard context — can_change_style flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_sets_can_change_style_false_for_free_user(client, free_user, survey):
    """Free-tier owner sees can_change_style=False in context (style panel hidden)."""
    survey.owner = free_user
    survey.save(update_fields=["owner"])
    client.force_login(free_user)
    resp = client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert resp.context["can_change_style"] is False


@pytest.mark.django_db
def test_dashboard_sets_can_change_style_true_for_pro_owner(client, pro_owner, survey):
    """PRO-tier owner sees can_change_style=True in context (style panel visible)."""
    client.force_login(pro_owner)
    resp = client.get(reverse("surveys:dashboard", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    assert resp.context["can_change_style"] is True


# ---------------------------------------------------------------------------
# 4. toggle_style_perm action in survey_users view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_toggle_style_perm_grants_permission(client, pro_owner, pro_member, survey):
    """Admin (survey owner) can grant style permission to a member."""
    client.force_login(pro_owner)
    mem = SurveyMembership.objects.get(survey=survey, user=pro_member)
    assert mem.can_change_survey_style is False

    client.post(
        reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
        data={"action": "toggle_style_perm", "user_id": pro_member.id},
    )
    mem.refresh_from_db()
    assert mem.can_change_survey_style is True


@pytest.mark.django_db
def test_toggle_style_perm_revokes_permission(
    client, pro_owner, pro_member_with_style, survey
):
    """Admin can revoke style permission from a member who previously had it."""
    client.force_login(pro_owner)
    mem = SurveyMembership.objects.get(survey=survey, user=pro_member_with_style)
    assert mem.can_change_survey_style is True

    client.post(
        reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
        data={"action": "toggle_style_perm", "user_id": pro_member_with_style.id},
    )
    mem.refresh_from_db()
    assert mem.can_change_survey_style is False


@pytest.mark.django_db
def test_toggle_style_perm_non_admin_returns_404(
    client, pro_member, pro_member_with_style, survey
):
    """A VIEWER-role member (no manage rights) gets 404 on survey_users."""
    client.force_login(pro_member)  # pro_member has VIEWER role → no manage access
    resp = client.post(
        reverse("surveys:survey_users", kwargs={"slug": survey.slug}),
        data={
            "action": "toggle_style_perm",
            "user_id": pro_member_with_style.id,
        },
    )
    # survey_users raises Http404 unless the user can manage survey users
    assert resp.status_code == 404
