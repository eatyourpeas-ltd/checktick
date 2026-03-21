"""
Access control tests for the API key management web UI.

Covers:
- Anonymous users are redirected to login for all three endpoints
- Free-tier users see an upgrade notice and cannot create keys
- Paid-tier users without MFA verification cannot create keys
- Paid-tier users with MFA verification can list, create, and revoke their own keys
- Users cannot revoke keys belonging to other users (404)
- can_manage_any_users context flag is False for survey-only CREATOR role users
"""

from django.contrib.auth import get_user_model
from django_otp.middleware import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_static.models import StaticDevice
import pytest

from checktick_app.core.models import UserAPIKey, UserProfile
from checktick_app.surveys.models import Survey, SurveyMembership

User = get_user_model()

TEST_PASSWORD = "x"

LIST_URL = "/surveys/account/api-keys/"
CREATE_URL = "/surveys/account/api-keys/create/"


def revoke_url(key_id):
    return f"/surveys/account/api-keys/{key_id}/revoke/"


def make_user(username, tier=UserProfile.AccountTier.FREE, password=TEST_PASSWORD):
    user = User.objects.create_user(username=username, password=password)
    user.profile.account_tier = tier
    user.profile.save()
    return user


def make_mfa_verified(client, user):
    """Create a confirmed StaticDevice for the user and store it in the session."""
    device = StaticDevice.objects.create(user=user, name="test-device", confirmed=True)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()


# ---------------------------------------------------------------------------
# Anonymous access — all three endpoints require login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAnonymousAccess:
    def test_list_redirects_to_login(self, client):
        resp = client.get(LIST_URL)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]

    def test_create_redirects_to_login(self, client):
        resp = client.post(CREATE_URL, {"name": "test"})
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]

    def test_revoke_redirects_to_login(self, client):
        import uuid

        resp = client.post(revoke_url(uuid.uuid4()))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]


# ---------------------------------------------------------------------------
# Free-tier users
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFreeTierAccess:
    def test_list_returns_200_with_upgrade_notice(self, client):
        user = make_user("free1", tier=UserProfile.AccountTier.FREE)
        client.force_login(user)
        resp = client.get(LIST_URL)
        assert resp.status_code == 200
        assert resp.context["can_use_api"] is False

    def test_create_redirects_with_error(self, client):
        user = make_user("free2", tier=UserProfile.AccountTier.FREE)
        client.force_login(user)
        resp = client.post(CREATE_URL, {"name": "mykey"}, follow=True)
        assert resp.status_code == 200
        messages = [str(m) for m in resp.context["messages"]]
        assert any("paid account tier" in m for m in messages)


# ---------------------------------------------------------------------------
# Pro-tier users, MFA NOT verified
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProTierNoMfa:
    def test_list_shows_mfa_warning(self, client):
        user = make_user("pro_nomfa", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        resp = client.get(LIST_URL)
        assert resp.status_code == 200
        assert resp.context["can_use_api"] is True
        assert resp.context["mfa_verified"] is False
        assert resp.context["can_create"] is False

    def test_create_redirects_with_mfa_error(self, client):
        user = make_user("pro_nomfa2", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        resp = client.post(CREATE_URL, {"name": "mykey"}, follow=True)
        assert resp.status_code == 200
        messages = [str(m) for m in resp.context["messages"]]
        assert any("two-factor" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# Pro-tier users, MFA verified
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProTierWithMfa:
    def test_list_shows_can_create(self, client):
        user = make_user("pro_mfa1", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        resp = client.get(LIST_URL)
        assert resp.status_code == 200
        assert resp.context["can_use_api"] is True
        assert resp.context["mfa_verified"] is True
        assert resp.context["can_create"] is True

    def test_create_key_succeeds(self, client):
        user = make_user("pro_mfa2", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        resp = client.post(CREATE_URL, {"name": "CI pipeline"}, follow=True)
        assert resp.status_code == 200
        assert UserAPIKey.objects.filter(user=user, name="CI pipeline").exists()

    def test_create_key_stores_raw_key_in_session(self, client):
        user = make_user("pro_mfa3", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        client.post(CREATE_URL, {"name": "dashboard"})
        # Follow to list view and check raw key surfaces in context
        resp = client.get(LIST_URL)
        assert resp.context["new_raw_key"] is not None
        assert resp.context["new_raw_key"].startswith("ct_live_")

    def test_create_key_without_name_shows_error(self, client):
        user = make_user("pro_mfa4", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        resp = client.post(CREATE_URL, {"name": ""}, follow=True)
        messages = [str(m) for m in resp.context["messages"]]
        assert any("name" in m.lower() for m in messages)
        assert not UserAPIKey.objects.filter(user=user).exists()

    def test_revoke_own_key(self, client):
        user = make_user("pro_mfa5", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        key, _ = UserAPIKey.generate(user=user, name="to revoke")
        resp = client.post(revoke_url(key.id), follow=True)
        assert resp.status_code == 200
        key.refresh_from_db()
        assert key.revoked is True

    def test_revoke_already_revoked_key_shows_info(self, client):
        from django.utils import timezone

        user = make_user("pro_mfa6", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        key, _ = UserAPIKey.generate(user=user, name="already gone")
        key.revoked = True
        key.revoked_at = timezone.now()
        key.save()
        resp = client.post(revoke_url(key.id), follow=True)
        messages = [str(m) for m in resp.context["messages"]]
        assert any("already been revoked" in m for m in messages)

    def test_raw_key_shown_only_once(self, client):
        """Second visit to list page after key creation should NOT show the raw key again."""
        user = make_user("pro_mfa7", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        client.post(CREATE_URL, {"name": "one-time"})
        # First visit surfaces the key
        resp1 = client.get(LIST_URL)
        assert resp1.context["new_raw_key"] is not None
        # Second visit: session var has been popped
        resp2 = client.get(LIST_URL)
        assert resp2.context["new_raw_key"] is None


# ---------------------------------------------------------------------------
# Cross-user security: cannot revoke another user's key
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCrossUserSecurity:
    def test_cannot_revoke_other_users_key(self, client):
        owner = make_user("owner_k", tier=UserProfile.AccountTier.PRO)
        attacker = make_user("attacker_k", tier=UserProfile.AccountTier.PRO)
        key, _ = UserAPIKey.generate(user=owner, name="owners key")

        client.force_login(attacker)
        make_mfa_verified(client, attacker)
        resp = client.post(revoke_url(key.id))
        assert resp.status_code == 404
        key.refresh_from_db()
        assert key.revoked is False


# ---------------------------------------------------------------------------
# Key limits per tier
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestKeyLimits:
    def test_pro_limit_enforced(self, client):
        """PRO tier limit is 5 active keys; 6th creation should be blocked."""
        user = make_user("pro_limit", tier=UserProfile.AccountTier.PRO)
        client.force_login(user)
        make_mfa_verified(client, user)
        for i in range(5):
            UserAPIKey.generate(user=user, name=f"key{i}")
        resp = client.post(CREATE_URL, {"name": "overflow"}, follow=True)
        messages = [str(m) for m in resp.context["messages"]]
        assert any("limit" in m.lower() for m in messages)
        assert UserAPIKey.objects.filter(user=user).count() == 5


# ---------------------------------------------------------------------------
# Context processor: can_manage_any_users
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCanManageAnyUsers:
    def test_survey_only_creator_has_no_manage_flag(self, client):
        """
        A user who is only a SurveyMembership CREATOR (no org/team admin role)
        should NOT get can_manage_any_users=True.
        """
        owner = make_user("survey_owner", tier=UserProfile.AccountTier.PRO)
        creator = make_user("survey_creator", tier=UserProfile.AccountTier.PRO)
        survey = Survey.objects.create(
            name="test survey", slug="test-survey", owner=owner
        )
        SurveyMembership.objects.create(
            user=creator, survey=survey, role=SurveyMembership.Role.CREATOR
        )
        client.force_login(creator)
        resp = client.get("/surveys/")
        assert resp.context["can_manage_any_users"] is False

    def test_team_admin_has_manage_flag(self, client):
        """A team admin should get can_manage_any_users=True."""
        from checktick_app.surveys.models import Team, TeamMembership

        admin = make_user("team_admin", tier=UserProfile.AccountTier.PRO)
        team = Team.objects.create(name="My Team", owner=admin)
        TeamMembership.objects.create(
            user=admin, team=team, role=TeamMembership.Role.ADMIN
        )
        client.force_login(admin)
        resp = client.get("/surveys/")
        assert resp.context["can_manage_any_users"] is True
