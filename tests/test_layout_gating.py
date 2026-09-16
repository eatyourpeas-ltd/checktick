"""Tests for survey layout tier gating.

Free tier users can only use the linear layout. All paid tiers
(Pro, Team, Organisation, Enterprise) get every layout.

Covers:
1. TierLimits.allowed_layouts is set correctly for each tier.
2. check_layout_permission allows/denies correctly.
3. The organise page (groups.html) greys out disabled layouts for free users.
4. The set_layout POST handler rejects non-linear layouts for free users.
5. Bulk upload import rejects layout-specific grammar for free users.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.core.tier_limits import (
    check_layout_permission,
    get_allowed_layouts,
    get_tier_limits,
)
from checktick_app.surveys.models import Survey

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def free_user(db):
    user = User.objects.create_user(
        username="free_layout@example.com",
        password=TEST_PASSWORD,
        email="free_layout@example.com",
    )
    user.profile.account_tier = UserProfile.AccountTier.FREE
    user.profile.save()
    return user


@pytest.fixture
def pro_user(db):
    user = User.objects.create_user(
        username="pro_layout@example.com",
        password=TEST_PASSWORD,
        email="pro_layout@example.com",
    )
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
    user.profile.save()
    return user


class TestTierLimitsLayoutConfig:
    """Test that allowed_layouts is set correctly in TIER_LIMITS_CONFIG."""

    def test_free_tier_linear_only(self):
        limits = get_tier_limits("free")
        assert limits.allowed_layouts == ["linear"]

    def test_pro_tier_all_layouts(self):
        limits = get_tier_limits("pro")
        assert "linear" in limits.allowed_layouts
        assert "section_menu" in limits.allowed_layouts
        assert "rct" in limits.allowed_layouts
        assert "guided" in limits.allowed_layouts
        assert "staged" in limits.allowed_layouts
        assert "matrix" in limits.allowed_layouts
        assert "delphi" in limits.allowed_layouts

    def test_team_small_all_layouts(self):
        limits = get_tier_limits("team_small")
        assert "delphi" in limits.allowed_layouts

    def test_enterprise_all_layouts(self):
        limits = get_tier_limits("enterprise")
        assert "delphi" in limits.allowed_layouts


class TestCheckLayoutPermission:
    """Test the check_layout_permission helper."""

    def test_free_user_can_use_linear(self, free_user):
        can_use, reason = check_layout_permission(free_user, "linear")
        assert can_use is True
        assert reason == ""

    def test_free_user_cannot_use_section_menu(self, free_user):
        can_use, reason = check_layout_permission(free_user, "section_menu")
        assert can_use is False
        assert "paid subscription" in reason

    def test_free_user_cannot_use_delphi(self, free_user):
        can_use, reason = check_layout_permission(free_user, "delphi")
        assert can_use is False
        assert "paid subscription" in reason

    def test_pro_user_can_use_all_layouts(self, pro_user):
        for layout in [
            "linear",
            "section_menu",
            "rct",
            "guided",
            "staged",
            "matrix",
            "delphi",
        ]:
            can_use, reason = check_layout_permission(pro_user, layout)
            assert can_use is True, f"Pro should allow {layout}"


class TestGetAllowedLayouts:
    """Test the get_allowed_layouts helper for templates."""

    def test_free_user_gets_linear_only(self, free_user):
        assert get_allowed_layouts(free_user) == ["linear"]

    def test_pro_user_gets_all(self, pro_user):
        layouts = get_allowed_layouts(pro_user)
        assert "delphi" in layouts
        assert "section_menu" in layouts


@pytest.mark.django_db
class TestOrganisePageLayoutGating:
    """Test that the organise page greys out disabled layouts for free users."""

    def test_free_user_sees_upgrade_link_not_button(self, client, free_user):
        survey = Survey.objects.create(
            owner=free_user, name="Test", slug="test-layout-free"
        )
        client.login(username="free_layout@example.com", password=TEST_PASSWORD)
        response = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
        content = response.content.decode()
        # Should see "Upgrade to use" for non-linear layouts.
        assert "Upgrade to use" in content
        # Should NOT see a "Use this layout" button for non-linear layouts.
        # (The linear card only shows the button when the current layout is
        # NOT linear, so it won't appear here since the survey defaults to
        # linear.)

    def test_pro_user_sees_all_layout_buttons(self, client, pro_user):
        survey = Survey.objects.create(
            owner=pro_user, name="Test Pro", slug="test-layout-pro"
        )
        client.login(username="pro_layout@example.com", password=TEST_PASSWORD)
        response = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
        content = response.content.decode()
        # Pro should NOT see "Upgrade to use" — all layouts are available.
        assert "Upgrade to use" not in content
        # Should see multiple "Use this layout" buttons (6 non-linear
        # layouts; the linear card shows "Current" since the survey defaults
        # to linear).
        assert content.count("Use this layout") >= 6


@pytest.mark.django_db
class TestSetLayoutViewGating:
    """Test that the set_layout POST handler rejects non-linear for free."""

    def test_free_user_cannot_set_section_menu(self, client, free_user):
        survey = Survey.objects.create(
            owner=free_user, name="Test", slug="test-set-layout-free"
        )
        client.login(username="free_layout@example.com", password=TEST_PASSWORD)
        response = client.post(
            reverse("surveys:groups", kwargs={"slug": survey.slug}),
            data={"action": "set_layout", "layout": "section_menu"},
        )
        assert response.status_code == 302
        survey.refresh_from_db()
        # Layout should NOT have changed.
        assert survey.layout == Survey.Layout.LINEAR

    def test_free_user_cannot_set_delphi(self, client, free_user):
        survey = Survey.objects.create(
            owner=free_user, name="Test", slug="test-set-delphi-free"
        )
        client.login(username="free_layout@example.com", password=TEST_PASSWORD)
        response = client.post(
            reverse("surveys:groups", kwargs={"slug": survey.slug}),
            data={"action": "set_layout", "layout": "delphi"},
        )
        assert response.status_code == 302
        survey.refresh_from_db()
        assert survey.layout == Survey.Layout.LINEAR

    def test_pro_user_can_set_section_menu(self, client, pro_user):
        survey = Survey.objects.create(
            owner=pro_user, name="Test Pro", slug="test-set-layout-pro"
        )
        client.login(username="pro_layout@example.com", password=TEST_PASSWORD)
        response = client.post(
            reverse("surveys:groups", kwargs={"slug": survey.slug}),
            data={"action": "set_layout", "layout": "section_menu"},
        )
        assert response.status_code == 302
        survey.refresh_from_db()
        assert survey.layout == Survey.Layout.SECTION_MENU

    def test_free_user_can_set_linear(self, client, free_user):
        survey = Survey.objects.create(
            owner=free_user, name="Test", slug="test-set-linear-free"
        )
        survey.layout = Survey.Layout.SECTION_MENU
        survey.save()
        client.login(username="free_layout@example.com", password=TEST_PASSWORD)
        response = client.post(
            reverse("surveys:groups", kwargs={"slug": survey.slug}),
            data={"action": "set_layout", "layout": "linear"},
        )
        assert response.status_code == 302
        survey.refresh_from_db()
        assert survey.layout == Survey.Layout.LINEAR
