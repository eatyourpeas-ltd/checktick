"""Tests for UserProfile model and account tier functionality."""

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
import pytest

from checktick_app.core.models import UserProfile

User = get_user_model()


@pytest.mark.django_db
class TestUserProfile:
    """Test UserProfile model functionality."""

    def test_user_profile_created_automatically(self):
        """Test that UserProfile is created automatically when a user is created."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        assert hasattr(user, "profile")
        assert user.profile.account_tier == UserProfile.AccountTier.FREE

    def test_get_or_create_for_user(self):
        """Test get_or_create_for_user class method."""
        user = User.objects.create_user(username="testuser2", email="test2@example.com")
        profile = UserProfile.get_or_create_for_user(user)
        assert profile == user.profile
        assert profile.account_tier == UserProfile.AccountTier.FREE

    def test_get_effective_tier_normal_mode(self):
        """Test get_effective_tier returns actual tier in normal mode."""
        user = User.objects.create_user(username="testuser3", email="test3@example.com")
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()

        assert user.profile.get_effective_tier() == UserProfile.AccountTier.PRO

    @override_settings(SELF_HOSTED=True)
    def test_get_effective_tier_self_hosted_mode(self):
        """Test get_effective_tier returns Enterprise in self-hosted mode."""
        user = User.objects.create_user(username="testuser4", email="test4@example.com")
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()

        assert user.profile.get_effective_tier() == UserProfile.AccountTier.ENTERPRISE

    def test_is_tier_at_least(self):
        """Test tier comparison logic."""
        user = User.objects.create_user(username="testuser5", email="test5@example.com")

        # FREE tier
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.FREE)
        assert not user.profile.is_tier_at_least(UserProfile.AccountTier.PRO)

        # PRO tier
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.FREE)
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.PRO)
        assert not user.profile.is_tier_at_least(UserProfile.AccountTier.ORGANIZATION)

        # ENTERPRISE tier
        user.profile.account_tier = UserProfile.AccountTier.ENTERPRISE
        user.profile.save()
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.FREE)
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.PRO)
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.ORGANIZATION)
        assert user.profile.is_tier_at_least(UserProfile.AccountTier.ENTERPRISE)

    def test_can_create_survey_free_tier(self):
        """Test survey creation limit for FREE tier."""
        from checktick_app.surveys.models import Survey

        user = User.objects.create_user(username="testuser6", email="test6@example.com")
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()

        # Can create up to 3 surveys
        assert user.profile.can_create_survey()[0] is True

        # Create 3 surveys
        for i in range(3):
            Survey.objects.create(
                name=f"Survey {i}",
                slug=f"survey-{i}",
                owner=user,
            )

        # Cannot create 4th survey
        can_create, reason = user.profile.can_create_survey()
        assert can_create is False
        assert "reached the limit" in reason

    def test_can_create_survey_pro_tier(self):
        """Test survey creation for PRO tier (unlimited)."""
        from checktick_app.surveys.models import Survey

        user = User.objects.create_user(username="testuser7", email="test7@example.com")
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()

        # Create many surveys
        for i in range(10):
            Survey.objects.create(
                name=f"Survey {i}",
                slug=f"pro-survey-{i}",
                owner=user,
            )

        # Can still create more
        assert user.profile.can_create_survey()[0] is True

    def test_can_add_collaborators_free_tier(self):
        """Test collaboration restrictions for FREE tier."""
        user = User.objects.create_user(username="testuser8", email="test8@example.com")
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()

        can_add_editor, reason = user.profile.can_add_collaborators("editor")
        assert can_add_editor is False
        assert "Pro tier" in reason

    def test_can_add_collaborators_pro_tier(self):
        """Test collaboration for PRO tier (editors only)."""
        user = User.objects.create_user(username="testuser9", email="test9@example.com")
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()

        # Can add editors
        assert user.profile.can_add_collaborators("editor")[0] is True

        # Cannot add viewers
        can_add_viewer, reason = user.profile.can_add_collaborators("viewer")
        assert can_add_viewer is False
        assert "Organization tier" in reason

    def test_can_add_collaborators_organization_tier(self):
        """Test full collaboration for ORGANIZATION tier."""
        user = User.objects.create_user(
            username="testuser10", email="test10@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.ORGANIZATION
        user.profile.save()

        # Can add both editors and viewers
        assert user.profile.can_add_collaborators("editor")[0] is True
        assert user.profile.can_add_collaborators("viewer")[0] is True

    def test_can_customize_branding_free_tier(self):
        """Test branding restrictions for FREE tier."""
        user = User.objects.create_user(
            username="testuser11", email="test11@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()

        can_customize, reason = user.profile.can_customize_branding()
        assert can_customize is False
        assert "Enterprise tier" in reason

    def test_can_customize_branding_enterprise_tier(self):
        """Test branding for ENTERPRISE tier."""
        user = User.objects.create_user(
            username="testuser12", email="test12@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.ENTERPRISE
        user.profile.save()

        assert user.profile.can_customize_branding()[0] is True

    @override_settings(SELF_HOSTED=True)
    def test_can_customize_branding_self_hosted(self):
        """Test branding is allowed for all tiers in self-hosted mode."""
        user = User.objects.create_user(
            username="testuser13", email="test13@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()

        assert user.profile.can_customize_branding()[0] is True

    def test_can_create_sub_organizations_free_tier(self):
        """Test sub-organization restrictions for FREE tier."""
        user = User.objects.create_user(
            username="testuser14", email="test14@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.FREE
        user.profile.save()

        can_create, reason = user.profile.can_create_sub_organizations()
        assert can_create is False
        assert "Enterprise tier" in reason

    def test_can_create_sub_organizations_enterprise_tier(self):
        """Test sub-organizations for ENTERPRISE tier."""
        user = User.objects.create_user(
            username="testuser15", email="test15@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.ENTERPRISE
        user.profile.save()

        assert user.profile.can_create_sub_organizations()[0] is True

    def test_upgrade_tier(self):
        """Test upgrading account tier."""
        user = User.objects.create_user(
            username="testuser16", email="test16@example.com"
        )
        assert user.profile.account_tier == UserProfile.AccountTier.FREE

        user.profile.upgrade_tier(UserProfile.AccountTier.PRO)
        user.profile.refresh_from_db()

        assert user.profile.account_tier == UserProfile.AccountTier.PRO
        assert user.profile.tier_changed_at is not None

    def test_downgrade_tier(self):
        """Test downgrading account tier."""
        user = User.objects.create_user(
            username="testuser17", email="test17@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.ENTERPRISE
        user.profile.save()

        success, message = user.profile.downgrade_tier(UserProfile.AccountTier.PRO)
        user.profile.refresh_from_db()

        assert success is True
        assert "Successfully downgraded" in message
        assert user.profile.account_tier == UserProfile.AccountTier.PRO
        assert user.profile.tier_changed_at is not None

    def test_downgrade_tier_blocked_by_survey_limit(self):
        """Test that downgrade is blocked if user has too many surveys."""
        from checktick_app.surveys.models import Survey

        user = User.objects.create_user(
            username="testuser_downgrade", email="testdowngrade@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()

        # Create 5 surveys (more than FREE tier limit of 3)
        for i in range(5):
            Survey.objects.create(
                name=f"Survey {i}",
                slug=f"survey-downgrade-{i}",
                owner=user,
            )

        # Attempt to downgrade to FREE
        success, message = user.profile.downgrade_tier(UserProfile.AccountTier.FREE)

        # Should be blocked
        assert success is False
        assert "Cannot downgrade" in message
        assert "5 surveys" in message
        assert "maximum of 3" in message
        assert "delete or archive 2 survey(s)" in message.lower()

        # Verify tier didn't change
        user.profile.refresh_from_db()
        assert user.profile.account_tier == UserProfile.AccountTier.PRO

    def test_downgrade_tier_allowed_within_limit(self):
        """Test that downgrade succeeds if user is within survey limit."""
        from checktick_app.surveys.models import Survey

        user = User.objects.create_user(
            username="testuser_downgrade2", email="testdowngrade2@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()

        # Create 3 surveys (exactly at FREE tier limit)
        for i in range(3):
            Survey.objects.create(
                name=f"Survey {i}",
                slug=f"survey-downgrade2-{i}",
                owner=user,
            )

        # Attempt to downgrade to FREE
        success, message = user.profile.downgrade_tier(UserProfile.AccountTier.FREE)

        # Should succeed
        assert success is True
        assert "Successfully downgraded" in message

        # Verify tier changed
        user.profile.refresh_from_db()
        assert user.profile.account_tier == UserProfile.AccountTier.FREE

    def test_downgrade_tier_invalid_tier(self):
        """Test that downgrade fails with invalid tier."""
        user = User.objects.create_user(
            username="testuser_invalid", email="testinvalid@example.com"
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()

        success, message = user.profile.downgrade_tier("INVALID_TIER")

        assert success is False
        assert "Invalid tier" in message

        # Verify tier didn't change
        user.profile.refresh_from_db()
        assert user.profile.account_tier == UserProfile.AccountTier.PRO

    def test_update_subscription(self):
        """Test updating subscription information."""
        user = User.objects.create_user(
            username="testuser18", email="test18@example.com"
        )

        period_end = timezone.now() + timezone.timedelta(days=30)
        user.profile.update_subscription(
            subscription_id="sub_123456",
            status=UserProfile.SubscriptionStatus.ACTIVE,
            current_period_end=period_end,
        )
        user.profile.refresh_from_db()

        assert user.profile.payment_subscription_id == "sub_123456"
        assert user.profile.subscription_status == UserProfile.SubscriptionStatus.ACTIVE
        assert user.profile.subscription_current_period_end == period_end

    def test_user_profile_str(self):
        """Test UserProfile string representation."""
        user = User.objects.create_user(
            username="testuser19", email="test19@example.com"
        )
        assert str(user.profile) == "testuser19 - Free"

        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()
        assert str(user.profile) == "testuser19 - Professional"
