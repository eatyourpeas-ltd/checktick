"""Tests for DNS email deliverability validation and its use in
prune_unconfirmed_users and the signup form.

The validator tests inject a fake resolver so no network access happens.
The command tests patch check_email_deliverability at the command module
namespace and opt in via override_settings(EMAIL_VALIDATION_ENABLED=True)
— the setting defaults to False under pytest (see settings.py).
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
import dns.exception
import dns.resolver

from checktick_app.core.email_validation import (
    DELIVERABLE,
    INVALID,
    UNKNOWN,
    DomainCheckResult,
    check_email_deliverability,
    clear_domain_check_cache,
)
from checktick_app.core.models import UserOIDC
from checktick_app.surveys.models import AuditLog, Survey

User = get_user_model()
TEST_PASSWORD = "testpass123"

COMMAND_MODULE = "checktick_app.core.management.commands.prune_unconfirmed_users"


class FakeResolver:
    """Minimal dns.resolver.Resolver stand-in.

    ``mx``/``a`` are either a non-empty list (records found), an exception
    instance to raise, or None (raise NoAnswer).
    """

    def __init__(self, mx=None, a=None):
        self.mx = mx
        self.a = a
        self.queries = []

    def resolve(self, qname, rdtype):
        self.queries.append((str(qname), str(rdtype)))
        answer = self.mx if str(rdtype).upper() == "MX" else self.a
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            raise dns.resolver.NoAnswer()
        return answer


class EmailValidationTests(TestCase):
    """Unit tests for check_email_deliverability."""

    def setUp(self):
        clear_domain_check_cache()

    def tearDown(self):
        clear_domain_check_cache()

    def test_mx_record_found_is_deliverable(self):
        result = check_email_deliverability(
            "user@example.com", resolver=FakeResolver(mx=["10 mail.example.com"])
        )
        self.assertEqual(result.status, DELIVERABLE)
        self.assertTrue(result.is_deliverable)
        self.assertFalse(result.is_invalid)

    def test_nxdomain_is_invalid(self):
        result = check_email_deliverability(
            "user@nonexistent.invalid",
            resolver=FakeResolver(mx=dns.resolver.NXDOMAIN()),
        )
        self.assertEqual(result.status, INVALID)
        self.assertIn("does not exist", result.reason)

    def test_no_mx_but_a_record_is_deliverable(self):
        """RFC 5321 implicit MX: with no MX record, mail routes to the A record."""
        resolver = FakeResolver(mx=None, a=["93.184.216.34"])
        result = check_email_deliverability("user@example.com", resolver=resolver)
        self.assertEqual(result.status, DELIVERABLE)
        # Both queries must have been made
        self.assertEqual(len(resolver.queries), 2)

    def test_no_mx_and_no_a_record_is_invalid(self):
        result = check_email_deliverability(
            "user@example.com", resolver=FakeResolver(mx=None, a=None)
        )
        self.assertEqual(result.status, INVALID)
        self.assertTrue(result.is_invalid)
        self.assertIn("no mail exchanger", result.reason)

    def test_dns_timeout_is_unknown_not_invalid(self):
        """Resolver timeouts must fail open — never prune on a flaky resolver."""
        result = check_email_deliverability(
            "user@example.com",
            resolver=FakeResolver(mx=dns.exception.Timeout()),
        )
        self.assertEqual(result.status, UNKNOWN)
        self.assertFalse(result.is_invalid)

    def test_lifetime_timeout_is_unknown_not_invalid(self):
        result = check_email_deliverability(
            "user@example.com",
            resolver=FakeResolver(mx=dns.resolver.LifetimeTimeout()),
        )
        self.assertEqual(result.status, UNKNOWN)

    def test_servfail_is_unknown_not_invalid(self):
        result = check_email_deliverability(
            "user@example.com",
            resolver=FakeResolver(mx=dns.resolver.NoNameservers()),
        )
        self.assertEqual(result.status, UNKNOWN)

    def test_a_record_timeout_is_unknown_not_invalid(self):
        result = check_email_deliverability(
            "user@example.com",
            resolver=FakeResolver(mx=None, a=dns.exception.Timeout()),
        )
        self.assertEqual(result.status, UNKNOWN)

    def test_unexpected_error_is_unknown_not_invalid(self):
        result = check_email_deliverability(
            "user@example.com", resolver=FakeResolver(mx=RuntimeError("boom"))
        )
        self.assertEqual(result.status, UNKNOWN)

    def test_malformed_email_no_at_sign_is_invalid(self):
        result = check_email_deliverability("not-an-email")
        self.assertEqual(result.status, INVALID)
        self.assertEqual(result.reason, "malformed email address")

    def test_malformed_email_empty_domain_is_invalid(self):
        result = check_email_deliverability("user@")
        self.assertEqual(result.status, INVALID)

    def test_malformed_domain_label_is_invalid(self):
        result = check_email_deliverability("user@example..com")
        self.assertEqual(result.status, INVALID)

    def test_unicode_domain_is_idna_encoded(self):
        resolver = FakeResolver(mx=["10 mail.example.com"])
        result = check_email_deliverability("user@café.com", resolver=resolver)
        self.assertEqual(result.status, DELIVERABLE)
        queried = [q[0] for q in resolver.queries]
        self.assertIn("xn--caf-dma.com", queried)

    def test_domain_result_is_cached_per_domain(self):
        resolver = FakeResolver(mx=["10 mail.example.com"])
        check_email_deliverability("a@example.com", resolver=resolver)
        check_email_deliverability("b@example.com", resolver=resolver)
        # Only one MX query despite two emails on the same domain
        self.assertEqual(len(resolver.queries), 1)

    def test_clear_domain_check_cache_forces_requery(self):
        resolver = FakeResolver(mx=["10 mail.example.com"])
        check_email_deliverability("a@example.com", resolver=resolver)
        clear_domain_check_cache()
        check_email_deliverability("a@example.com", resolver=resolver)
        self.assertEqual(len(resolver.queries), 2)


@override_settings(EMAIL_VALIDATION_ENABLED=True)
class PruneInvalidEmailTests(TestCase):
    """Test the invalid-signup-email phase of prune_unconfirmed_users."""

    def setUp(self):
        self.out = StringIO()

    def _create_user(
        self,
        username,
        email,
        email_confirmed=False,
        is_active=True,
        date_joined=None,
    ):
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

    def _invalid_result(self):
        return DomainCheckResult(INVALID, "email domain does not exist")

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    @patch(f"{COMMAND_MODULE}.send_unconfirmed_account_warning_email")
    def test_invalid_email_new_signup_deleted_immediately(self, mock_warn, mock_check):
        """A bot signup with a non-existent domain is deleted without waiting
        out the grace period, and never receives a warning email."""
        mock_check.return_value = self._invalid_result()
        mock_warn.return_value = True
        # 25 days old: inside the 30-day grace period AND inside the
        # 7-days-before-removal warning window
        user = self._create_user(
            "botfake",
            "bot@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )
        user_id = user.id

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=user_id).exists())
        # The warning email must never be sent to an undeliverable address
        mock_warn.assert_not_called()

        log = AuditLog.objects.filter(action=AuditLog.Action.USER_DELETED).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get("reason"), "invalid_signup_email")
        self.assertEqual(log.metadata.get("email"), "bot@nonexistent.invalid")
        self.assertEqual(log.metadata.get("dns_reason"), "email domain does not exist")

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_invalid_email_user_with_data_deactivated_not_deleted(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "botwithdata",
            "bot@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )
        Survey.objects.create(name="Bot Survey", slug="bot-survey", owner=user)

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.USER_DEACTIVATED,
                target_user=user,
                metadata__reason="invalid_signup_email",
            ).exists()
        )

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_invalid_email_existing_user_deactivated(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "oldbot",
            "oldbot@nonexistent.invalid",
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_unknown_dns_result_leaves_user_in_normal_flow(self, mock_check):
        """Ambiguous DNS answers must fail open — the user keeps the grace period."""
        mock_check.return_value = DomainCheckResult(UNKNOWN, "DNS lookup failed")
        user = self._create_user(
            "unknownstatus",
            "unknown@flaky.example",
            date_joined=timezone.now() - timedelta(days=5),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_deliverable_email_not_pruned_by_validation(self, mock_check):
        mock_check.return_value = DomainCheckResult(DELIVERABLE, "MX record found")
        user = self._create_user(
            "realuser",
            "real@example.com",
            date_joined=timezone.now() - timedelta(days=5),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_skip_email_validation_flag_leaves_user_untouched(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "skipped",
            "bot@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )

        call_command(
            "prune_unconfirmed_users", "--skip-email-validation", stdout=self.out
        )

        mock_check.assert_not_called()
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        output = self.out.getvalue()
        self.assertIn("Email validation: off", output)

    @override_settings(EMAIL_VALIDATION_ENABLED=False)
    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_setting_disabled_leaves_user_untouched(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "disabled",
            "bot@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        mock_check.assert_not_called()
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_user_newer_than_min_age_untouched(self, mock_check):
        """Brand-new signups keep the 24h minimum age before invalid-email
        pruning, so not-yet-propagated DNS for a new domain is safe."""
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "freshbot",
            "bot@brandnew.invalid",
            date_joined=timezone.now() - timedelta(hours=1),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_oidc_verified_user_with_invalid_email_untouched(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "oidcbot",
            "oidc@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )
        UserOIDC.objects.create(
            user=user,
            provider="azure",
            subject="az-invalid-1",
            email_verified=True,
            key_derivation_salt=b"s" * 32,
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_staff_user_with_invalid_email_untouched(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "staffbot",
            "staff@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )
        user.is_staff = True
        user.save(update_fields=["is_staff"])

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_confirmed_user_with_invalid_email_untouched(self, mock_check):
        """A confirmed email proves deliverability — never re-check it."""
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "confirmedbot",
            "confirmed@nonexistent.invalid",
            email_confirmed=True,
            date_joined=timezone.now() - timedelta(days=25),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        mock_check.assert_not_called()
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_dry_run_makes_no_changes(self, mock_check):
        mock_check.return_value = self._invalid_result()
        user = self._create_user(
            "drybot",
            "bot@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )

        call_command("prune_unconfirmed_users", "--dry-run", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())
        output = self.out.getvalue()
        self.assertIn("DRY RUN MODE", output)
        self.assertIn("Invalid email pruned: 1", output)

    @patch(f"{COMMAND_MODULE}.check_email_deliverability")
    def test_check_exception_fails_open(self, mock_check):
        """An unexpected error from the check itself must never prune."""
        mock_check.side_effect = RuntimeError("resolver exploded")
        user = self._create_user(
            "explodingbot",
            "bot@nonexistent.invalid",
            date_joined=timezone.now() - timedelta(days=25),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())


@override_settings(EMAIL_VALIDATION_ENABLED=True)
class SignupEmailValidationTests(TestCase):
    """Test the DNS deliverability check on the signup form.

    Signups with a provably undeliverable domain are rejected before any
    account is created. Ambiguous DNS answers fail open.
    """

    def setUp(self):
        self.client = Client()

    def _signup_post_data(self, email):
        return {
            "email": email,
            "email_confirm": email,
            "password1": "complexpassword123!",
            "password2": "complexpassword123!",
        }

    @patch("checktick_app.core.forms.check_email_deliverability")
    def test_signup_with_invalid_domain_rejected_no_account_created(self, mock_check):
        """A signup whose email domain cannot receive mail is rejected at the
        form — no account, no confirmation email, no redirect."""
        mock_check.return_value = DomainCheckResult(
            INVALID, "email domain does not exist"
        )

        response = self.client.post(
            reverse("core:signup"), self._signup_post_data("bot@nonexistent.invalid")
        )

        self.assertEqual(response.status_code, 200)  # form re-rendered with error
        self.assertFalse(User.objects.filter(email="bot@nonexistent.invalid").exists())
        self.assertContains(response, "its domain cannot receive email")

    @patch("checktick_app.core.forms.check_email_deliverability")
    def test_signup_with_unknown_dns_result_allowed(self, mock_check):
        """DNS timeouts must not block real signups (fail open)."""
        mock_check.return_value = DomainCheckResult(UNKNOWN, "DNS lookup failed")

        response = self.client.post(
            reverse("core:signup"), self._signup_post_data("real@flaky.example")
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="real@flaky.example").exists())

    @patch("checktick_app.core.forms.check_email_deliverability")
    def test_signup_with_deliverable_domain_allowed(self, mock_check):
        mock_check.return_value = DomainCheckResult(DELIVERABLE, "MX record found")

        response = self.client.post(
            reverse("core:signup"), self._signup_post_data("real@example.com")
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="real@example.com").exists())

    @override_settings(EMAIL_VALIDATION_ENABLED=False)
    @patch("checktick_app.core.forms.check_email_deliverability")
    def test_signup_validation_disabled_skips_check(self, mock_check):
        mock_check.return_value = DomainCheckResult(
            INVALID, "email domain does not exist"
        )

        response = self.client.post(
            reverse("core:signup"), self._signup_post_data("bot@nonexistent.invalid")
        )

        mock_check.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="bot@nonexistent.invalid").exists())

    @patch("checktick_app.core.forms.check_email_deliverability")
    def test_signup_check_exception_fails_open(self, mock_check):
        """An unexpected error from the check must never block signup."""
        mock_check.side_effect = RuntimeError("resolver exploded")

        response = self.client.post(
            reverse("core:signup"), self._signup_post_data("real@example.com")
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="real@example.com").exists())
