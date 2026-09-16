"""Tests for the lapsed-subscription login signpost and UI badges.

Covers:
1. The user_logged_in signal sets a messages.warning() flash when the
   user's profile indicates a recent tier lapse (CANCELED + FREE +
   tier_changed_at within 14 days).
2. The signpost does not fire for never-subscribed free users or for
   lapses older than 14 days.
3. The base.html navbar shows a "LAPSED" warning badge for lapsed users
   and a "FREE" ghost badge for never-subscribed users.
4. The profile.html page shows a "LAPSED" badge next to the current plan
   for lapsed users.
"""

from datetime import timedelta
import secrets

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile

User = get_user_model()
PASSWORD = "test-password-123"


@pytest.fixture
def lapsed_user(db):
    """A user whose subscription recently lapsed (3 days ago)."""
    from django.utils import timezone

    unique = secrets.token_hex(8)
    email = f"lapsed-{unique}@example.com"
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    user.profile.account_tier = UserProfile.AccountTier.FREE
    user.profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
    user.profile.save()
    # Use .update() to set tier_changed_at bypassing auto_now on updated_at.
    UserProfile.objects.filter(pk=user.profile.pk).update(
        tier_changed_at=timezone.now() - timedelta(days=3)
    )
    user.profile.refresh_from_db()
    return user


@pytest.fixture
def old_lapsed_user(db):
    """A user whose subscription lapsed 20 days ago (outside the window)."""
    unique = secrets.token_hex(8)
    email = f"old-lapsed-{unique}@example.com"
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    user.profile.account_tier = UserProfile.AccountTier.FREE
    user.profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
    user.profile.save()
    from django.utils import timezone

    UserProfile.objects.filter(pk=user.profile.pk).update(
        tier_changed_at=timezone.now() - timedelta(days=20)
    )
    user.profile.refresh_from_db()
    return user


@pytest.fixture
def never_subscribed_user(db):
    """A never-subscribed free user."""
    unique = secrets.token_hex(8)
    email = f"never-{unique}@example.com"
    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    user.profile.account_tier = UserProfile.AccountTier.FREE
    user.profile.subscription_status = UserProfile.SubscriptionStatus.NONE
    user.profile.save()
    return user


@pytest.mark.django_db
class TestLoginSignpost:
    """Test the user_logged_in signal sets a warning message for lapsed users."""

    def test_recent_lapse_shows_warning(self, client, lapsed_user):
        """Login as a recently-lapsed user shows a messages.warning()."""
        response = client.post(
            reverse("login"),
            data={"username": lapsed_user.email, "password": PASSWORD},
        )
        # Follow redirect to the next page.
        if response.status_code in (301, 302):
            response = client.get(response.url)

        # The messages framework stores the warning; check it appears.
        messages = list(response.wsgi_request._messages)
        warning_messages = [m for m in messages if m.level == 30]  # WARNING=30
        assert len(warning_messages) >= 1
        assert "subscription has ended" in warning_messages[0].message.lower()

    def test_old_lapse_no_warning(self, client, old_lapsed_user):
        """Login as a user whose lapse is >14 days old shows no warning."""
        response = client.post(
            reverse("login"),
            data={"username": old_lapsed_user.email, "password": PASSWORD},
        )
        if response.status_code in (301, 302):
            response = client.get(response.url)

        messages = list(response.wsgi_request._messages)
        warning_messages = [m for m in messages if m.level == 30]
        assert len(warning_messages) == 0

    def test_never_subscribed_no_warning(self, client, never_subscribed_user):
        """Login as a never-subscribed free user shows no warning."""
        response = client.post(
            reverse("login"),
            data={
                "username": never_subscribed_user.email,
                "password": PASSWORD,
            },
        )
        if response.status_code in (301, 302):
            response = client.get(response.url)

        messages = list(response.wsgi_request._messages)
        warning_messages = [m for m in messages if m.level == 30]
        assert len(warning_messages) == 0


@pytest.mark.django_db
class TestLapsedBadgeBaseTemplate:
    """Test the base.html navbar shows a LAPSED badge for lapsed users."""

    def test_lapsed_user_sees_lapsed_badge(self, client, lapsed_user):
        """Lapsed user sees 'LAPSED' badge in the navbar."""
        client.login(username=lapsed_user.email, password=PASSWORD)
        response = client.get(reverse("core:home"))
        content = response.content.decode()
        assert "LAPSED" in content
        assert "badge-warning" in content

    def test_never_subscribed_sees_free_badge(self, client, never_subscribed_user):
        """Never-subscribed user sees 'FREE' badge, not 'LAPSED'."""
        client.login(username=never_subscribed_user.email, password=PASSWORD)
        response = client.get(reverse("core:home"))
        content = response.content.decode()
        assert "FREE" in content
        assert "LAPSED" not in content


@pytest.mark.django_db
class TestLapsedBadgeProfileTemplate:
    """Test the profile.html page shows a LAPSED badge for lapsed users."""

    def test_lapsed_user_sees_lapsed_badge_on_profile(self, client, lapsed_user):
        """Lapsed user sees 'LAPSED' badge on the profile page."""
        client.login(username=lapsed_user.email, password=PASSWORD)
        response = client.get(reverse("core:profile"))
        content = response.content.decode()
        assert "LAPSED" in content

    def test_never_subscribed_no_lapsed_badge_on_profile(
        self, client, never_subscribed_user
    ):
        """Never-subscribed user does not see 'LAPSED' on profile."""
        client.login(username=never_subscribed_user.email, password=PASSWORD)
        response = client.get(reverse("core:profile"))
        content = response.content.decode()
        assert "LAPSED" not in content
