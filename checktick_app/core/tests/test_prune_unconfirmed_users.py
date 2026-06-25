"""Tests for the prune_unconfirmed_users management command."""

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from checktick_app.surveys.models import AuditLog, Survey

User = get_user_model()
TEST_PASSWORD = "testpass123"


class PruneUnconfirmedUsersCommandTests(TestCase):
    """Test the prune_unconfirmed_users management command."""

    def setUp(self):
        """Create test data."""
        self.out = StringIO()

    def _create_user(
        self,
        username,
        email,
        email_confirmed=False,
        is_active=True,
        date_joined=None,
    ):
        """Helper to create a user with specific settings."""
        user = User.objects.create_user(
            username=username,
            email=email,
            password=TEST_PASSWORD,
            is_active=is_active,
        )
        if date_joined:
            user.date_joined = date_joined
            user.save(update_fields=["date_joined"])
        user.profile.email_confirmed = email_confirmed
        user.profile.save()
        return user

    def test_command_runs_successfully(self):
        """Test that the command runs without errors when no users match."""
        call_command("prune_unconfirmed_users", stdout=self.out)
        output = self.out.getvalue()
        self.assertIn("Starting unconfirmed user pruning", output)
        self.assertIn("Pruning completed", output)
        self.assertIn("Deactivated: 0", output)
        self.assertIn("Deleted:     0", output)

    def test_dry_run_mode_makes_no_changes(self):
        """Test that dry-run mode doesn't actually delete or deactivate."""
        self._create_user(
            "olduser",
            "old@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )
        initial_count = User.objects.filter(is_active=True).count()

        call_command("prune_unconfirmed_users", "--dry-run", stdout=self.out)

        self.assertEqual(User.objects.filter(is_active=True).count(), initial_count)
        output = self.out.getvalue()
        self.assertIn("DRY RUN MODE", output)
        self.assertIn("DEACTIVATE", output)

    def test_existing_user_deactivated(self):
        """Test that pre-feature unconfirmed users are deactivated."""
        user = self._create_user(
            "existing",
            "existing@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Audit log should be created
        log = AuditLog.objects.filter(
            action=AuditLog.Action.USER_DEACTIVATED,
            target_user=user,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get("reason"), "unconfirmed_email")

    def test_new_user_with_no_data_deleted(self):
        """Test that new unconfirmed users with no data are deleted."""
        user = self._create_user(
            "newfake",
            "newfake@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2026, 4, 1)),
        )
        user_id = user.id

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=user_id).exists())

        # Audit log should be created
        log = AuditLog.objects.filter(
            action=AuditLog.Action.USER_DELETED,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get("reason"), "unconfirmed_email")
        self.assertEqual(log.metadata.get("email"), "newfake@example.com")

    def test_new_user_with_survey_deactivated_not_deleted(self):
        """Test that new users with data are deactivated, not deleted."""
        user = self._create_user(
            "newwithdata",
            "newwithdata@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2026, 4, 1)),
        )
        Survey.objects.create(
            name="Test Survey",
            slug="test-survey",
            owner=user,
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

        # Should be a deactivation log, not deletion
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.USER_DEACTIVATED,
                target_user=user,
            ).exists()
        )
        self.assertFalse(
            AuditLog.objects.filter(
                action=AuditLog.Action.USER_DELETED,
            ).exists()
        )

    def test_confirmed_user_ignored(self):
        """Test that confirmed users are never touched."""
        user = self._create_user(
            "confirmed",
            "confirmed@example.com",
            email_confirmed=True,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    def test_staff_and_superuser_excluded(self):
        """Test that staff and superusers are never pruned."""
        staff = self._create_user(
            "staff",
            "staff@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )
        staff.is_staff = True
        staff.save()

        superuser = User.objects.create_superuser(
            username="super",
            email="super@example.com",
            password=TEST_PASSWORD,
        )
        superuser.profile.email_confirmed = False
        superuser.profile.save()
        superuser.date_joined = timezone.make_aware(timezone.datetime(2024, 1, 1))
        superuser.save()

        call_command("prune_unconfirmed_users", stdout=self.out)

        staff.refresh_from_db()
        superuser.refresh_from_db()
        self.assertTrue(staff.is_active)
        self.assertTrue(superuser.is_active)

    def test_user_inside_grace_period_ignored(self):
        """Test that users within the grace period are not pruned."""
        user = self._create_user(
            "recent",
            "recent@example.com",
            email_confirmed=False,
            date_joined=timezone.now() - timedelta(days=5),
        )

        call_command("prune_unconfirmed_users", "--grace-days=30", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_custom_grace_period(self):
        """Test that custom grace periods are respected."""
        # Create user with date_joined 15 days ago (between 10 and 30 day grace)
        user = self._create_user(
            "custom",
            "custom@example.com",
            email_confirmed=False,
            date_joined=timezone.now() - timedelta(days=15),
        )

        # With default 30 days, should not be pruned (15 < 30)
        call_command("prune_unconfirmed_users", stdout=self.out)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # With 10 days, should be pruned (15 > 10)
        call_command("prune_unconfirmed_users", "--grace-days=10", stdout=self.out)
        self.assertFalse(User.objects.filter(id=user.id).exists())

    def test_verbose_output(self):
        """Test that verbose mode provides detailed output."""
        self._create_user(
            "verbose",
            "verbose@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        call_command("prune_unconfirmed_users", "--verbose", stdout=self.out)
        output = self.out.getvalue()
        self.assertIn("Found 1 unconfirmed users", output)
        self.assertIn("User: verbose", output)
        self.assertIn("Action:", output)

    def test_oidc_user_grandfathered(self):
        """Test that OIDC users with verified emails are not pruned."""
        user = self._create_user(
            "oidc",
            "oidc@example.com",
            email_confirmed=True,  # Simulating grandfathered state
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_multiple_users_processed(self):
        """Test that multiple users are processed in one run."""
        # Existing user -> deactivate
        existing = self._create_user(
            "existing_multi",
            "existing_multi@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        # New user with no data -> delete
        new_fake = self._create_user(
            "new_multi",
            "new_multi@example.com",
            email_confirmed=False,
            date_joined=timezone.make_aware(timezone.datetime(2026, 4, 1)),
        )

        # Confirmed user -> ignored
        confirmed = self._create_user(
            "confirmed_multi",
            "confirmed_multi@example.com",
            email_confirmed=True,
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        existing.refresh_from_db()
        self.assertFalse(existing.is_active)
        self.assertFalse(User.objects.filter(id=new_fake.id).exists())
        confirmed.refresh_from_db()
        self.assertTrue(confirmed.is_active)

        output = self.out.getvalue()
        self.assertIn("Deactivated: 1", output)
        self.assertIn("Deleted:     1", output)

    @override_settings(EMAIL_CONFIRMATION_CUTOFF=timezone.now() - timedelta(days=100))
    def test_feature_cutoff_setting(self):
        """Test that the EMAIL_CONFIRMATION_CUTOFF setting is respected."""
        # User joined after cutoff but before now -> treated as new
        user = self._create_user(
            "cutoff",
            "cutoff@example.com",
            email_confirmed=False,
            date_joined=timezone.now() - timedelta(days=50),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        # Should be deleted (new user, no data)
        self.assertFalse(User.objects.filter(id=user.id).exists())
