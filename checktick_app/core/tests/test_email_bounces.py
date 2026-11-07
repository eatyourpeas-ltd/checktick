"""Tests for email bounce (NDR) processing.

The parser tests are pure (no network, no Django calls). The fetch tests
patch the Graph HTTP layer. The command tests run the consolidated
``prune_unconfirmed_users`` command (bounce reading is a phase of it, not
a separate cron) with ``fetch_bounce_messages`` patched at the command
module namespace and the phase opted in via override_settings — both
EMAIL_BOUNCE_PROCESSING_ENABLED and EMAIL_BACKEND default off/locmem
under pytest, so every other prune test runs with the phase skipped.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
import requests

from checktick_app.core.email_bounces import (
    HARD,
    SOFT,
    UNKNOWN,
    BounceMessage,
    _looks_like_ndr,
    _parse_message,
    fetch_bounce_messages,
    parse_bounce,
)
from checktick_app.core.models import UserOIDC
from checktick_app.surveys.models import AuditLog, Survey

User = get_user_model()
TEST_PASSWORD = "testpass123"

BOUNCES_MODULE = "checktick_app.core.email_bounces"
PRUNE_COMMAND_MODULE = "checktick_app.core.management.commands.prune_unconfirmed_users"

GRAPH_BACKEND = "checktick_app.core.graph_email_backend.GraphEmailBackend"

# Exchange Online-style NDR body (plain text, as Graph returns with the
# Prefer: outlook.body-content-type="text" header).
EXCHANGE_HARD_BOUNCE_BODY = """
Delivery has failed to these recipients or groups:

bot@nonexistent.example.com (bot@nonexistent.example.com)
The email address you entered couldn't be found. Please check the
recipient's email address and try to resend the message.

Diagnostic information for administrators:

Generating server: AM0PR03MB1234.eurprd03.prod.outlook.com

bot@nonexistent.example.com
Remote Server returned '550 5.4.1 Recipient address rejected: access
denied. Unable to relay, AS(4567)'

Original message headers:
Return-Path: <noreply@checktick.example.com>
From: CheckTick <noreply@checktick.example.com>
Subject: Please confirm your email address
"""

# Policy/SPF-style rejection — mailbox may exist, our mail is the problem.
POLICY_BOUNCE_BODY = """
Delivery has failed to these recipients or groups:

realperson@example.com (realperson@example.com)
The message was rejected by the recipient's mail server.

Diagnostic information for administrators:

realperson@example.com
Remote Server returned '550 5.7.26 Unfortunately, messages from this
address were not accepted due to SPF policy'
"""

RFC3464_BODY = """
Reporting-MTA: dns; mail.example.com
Arrival-Date: Sat, 7 Nov 2026 08:00:00 +0000

Final-Recipient: rfc822;stranger@oldmailbox.example.org
Action: failed
Status: 5.1.1 (permanent failure)
"""

DELAYED_BODY = """
Delivery has failed to these recipients or groups:

full@example.com (full@example.com)
The recipient's mailbox is temporarily full.

Generating server: AM0PR03MB9999.eurprd03.prod.outlook.com

full@example.com
Remote Server returned '452 4.2.2 Mailbox full'
"""


def _bounce(
    recipient="bot@nonexistent.example.com",
    classification=HARD,
    subject="Undeliverable: Please confirm your email address",
    status="550 5.4.1",
    message_id="aaa-111",
):
    return BounceMessage(
        message_id=message_id,
        subject=subject,
        received_at="2026-11-07T08:00:00Z",
        recipient=recipient,
        classification=classification,
        status_code=status,
    )


class ParseBounceTests(TestCase):
    """Unit tests for the pure NDR parser."""

    def test_exchange_hard_bounce_parses_recipient_and_class(self):
        recipient, classification, status = parse_bounce(
            "Undeliverable: Please confirm your email address",
            EXCHANGE_HARD_BOUNCE_BODY,
        )
        self.assertEqual(recipient, "bot@nonexistent.example.com")
        self.assertEqual(classification, HARD)
        self.assertIn("550", status)

    def test_rfc3464_final_recipient_fallback(self):
        recipient, classification, _ = parse_bounce(
            "Delivery Status Notification (Failure)", RFC3464_BODY
        )
        # Final-Recipient is used when the "Delivery has failed" block
        # is absent
        self.assertEqual(recipient, "stranger@oldmailbox.example.org")
        self.assertEqual(classification, HARD)

    def test_delayed_is_soft(self):
        recipient, classification, _ = parse_bounce("Delayed: subject", DELAYED_BODY)
        self.assertEqual(recipient, "full@example.com")
        self.assertEqual(classification, SOFT)

    def test_policy_spf_bounce_is_never_hard(self):
        """5.7.x policy/SPF rejections must not prune — the mailbox may
        exist and our own mail may be the problem (misconfigured SPF
        would otherwise prune every unconfirmed signup)."""
        recipient, classification, _ = parse_bounce(
            "Undeliverable: Please confirm your email address",
            POLICY_BOUNCE_BODY,
        )
        self.assertEqual(recipient, "realperson@example.com")
        self.assertEqual(classification, UNKNOWN)

    def test_undeliverable_subject_without_status_is_unknown(self):
        """No diagnostic status → cannot distinguish a policy bounce,
        so it is never prunable."""
        recipient, classification, status = parse_bounce(
            "Undeliverable: something", "no diagnostic info at all"
        )
        self.assertIsNone(recipient)
        self.assertEqual(classification, UNKNOWN)
        self.assertIsNone(status)

    def test_unparseable_is_unknown(self):
        recipient, classification, _ = parse_bounce(
            "Delivery Status Notification", "nothing useful here"
        )
        self.assertEqual(classification, UNKNOWN)

    @override_settings(
        DEFAULT_FROM_EMAIL="noreply@checktick.example.com",
        EMAIL_HOST_USER="noreply@checktick.example.com",
    )
    def test_own_address_never_extracted(self):
        body = """
Delivery has failed to these recipients or groups:

noreply@checktick.example.com (CheckTick)
...quoting ourselves must never count as the bounced recipient...

Original message headers:
From: CheckTick <noreply@checktick.example.com>
"""
        recipient, _, _ = parse_bounce("Undeliverable: x", body)
        self.assertIsNone(recipient)


class LooksLikeNdrTests(TestCase):
    def test_subject_prefixes(self):
        for subject in (
            "Undeliverable: hello",
            "Delivery Status Notification (Failure)",
            "Delivery has failed to these recipients",
            "Returned mail: see transcript",
        ):
            self.assertTrue(_looks_like_ndr(subject, "anyone@x.com"), subject)

    def test_system_sender(self):
        for sender in (
            "postmaster@contoso.com",
            "MAILER-DAEMON@contoso.com",
            "MicrosoftExchange329e71ec88ae4615a36e280f507ac2b4@contoso.com",
        ):
            self.assertTrue(_looks_like_ndr("some subject", sender), sender)

    def test_out_of_office_reply_is_not_ndr(self):
        self.assertFalse(_looks_like_ndr("Out of office: I am away", "joe@x.com"))
        self.assertFalse(_looks_like_ndr("Re: hello", "joe@x.com"))


class ParseMessageTests(TestCase):
    def test_graph_message_object_parsed(self):
        message = {
            "id": "aaa-111",
            "subject": "Undeliverable: hello",
            "receivedDateTime": "2026-11-07T08:00:00Z",
            "from": {
                "emailAddress": {
                    "address": (
                        "MicrosoftExchange329e71ec88ae4615a36e280f507ac2b4@c.com"
                    )
                }
            },
            "body": {"content": EXCHANGE_HARD_BOUNCE_BODY},
        }
        parsed = _parse_message(message)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.recipient, "bot@nonexistent.example.com")
        self.assertTrue(parsed.is_hard)

    def test_non_ndr_returns_none(self):
        message = {
            "id": "bbb-222",
            "subject": "Out of office",
            "receivedDateTime": "2026-11-07T08:00:00Z",
            "from": {"emailAddress": {"address": "joe@example.com"}},
            "body": {"content": "I am away until Monday"},
        }
        self.assertIsNone(_parse_message(message))


@override_settings(
    DEFAULT_FROM_EMAIL="noreply@checktick.example.com",
    EMAIL_HOST_USER="noreply@checktick.example.com",
)
class FetchBounceMessagesTests(TestCase):
    """Test the Graph mailbox read (HTTP layer patched)."""

    def _graph_response(self, messages, next_link=None):
        payload = {"value": messages}
        if next_link:
            payload["@odata.nextLink"] = next_link
        resp = MagicMock()
        resp.json.return_value = payload
        resp.raise_for_status.return_value = None
        return resp

    @patch(f"{BOUNCES_MODULE}._get_access_token", return_value="fake-token")
    @patch(f"{BOUNCES_MODULE}.requests.get")
    def test_fetch_returns_only_ndrs(self, mock_get, mock_token):
        ndr = {
            "id": "aaa-111",
            "subject": "Undeliverable: hello",
            "receivedDateTime": "2026-11-07T08:00:00Z",
            "from": {"emailAddress": {"address": "postmaster@c.com"}},
            "body": {"content": EXCHANGE_HARD_BOUNCE_BODY},
        }
        chatter = {
            "id": "bbb-222",
            "subject": "Out of office",
            "receivedDateTime": "2026-11-07T08:00:00Z",
            "from": {"emailAddress": {"address": "joe@example.com"}},
            "body": {"content": "away"},
        }
        mock_get.return_value = self._graph_response([ndr, chatter])

        bounces = fetch_bounce_messages("noreply@checktick.example.com", 168)

        self.assertEqual(len(bounces), 1)
        self.assertEqual(bounces[0].recipient, "bot@nonexistent.example.com")
        # Graph request shape: token, text body preference, lookback filter
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer fake-token")
        self.assertIn("outlook.body-content-type", kwargs["headers"]["Prefer"])
        self.assertIn("receivedDateTime ge", kwargs["params"]["$filter"])

    @patch(f"{BOUNCES_MODULE}._get_access_token", return_value="fake-token")
    @patch(f"{BOUNCES_MODULE}.requests.get")
    def test_fetch_follows_pagination(self, mock_get, mock_token):
        first = MagicMock()
        first.json.return_value = {
            "value": [],
            "@odata.nextLink": "https://graph.microsoft.com/next",
        }
        first.raise_for_status.return_value = None
        second = MagicMock()
        second.json.return_value = {"value": []}
        second.raise_for_status.return_value = None
        mock_get.side_effect = [first, second]

        fetch_bounce_messages("noreply@checktick.example.com", 24)

        self.assertEqual(mock_get.call_count, 2)
        # Second page must NOT re-send the filter params (nextLink has them)
        second_call = mock_get.call_args_list[1]
        self.assertIsNone(second_call.kwargs.get("params"))


# Settings shared by every command test: bounce phase opted in and the
# Graph backend active (both default off/locmem under pytest, which is
# what keeps every other prune test untouched).
COMMAND_OVERRIDES = override_settings(
    EMAIL_BOUNCE_PROCESSING_ENABLED=True,
    EMAIL_BACKEND=GRAPH_BACKEND,
    EMAIL_HOST_USER="noreply@checktick.example.com",
    DEFAULT_FROM_EMAIL="noreply@checktick.example.com",
)


@COMMAND_OVERRIDES
class PruneBouncePhaseTests(TestCase):
    """Test the bounce phase of the prune_unconfirmed_users command."""

    def setUp(self):
        self.out = StringIO()

    def _create_user(
        self,
        username,
        email,
        email_confirmed=False,
        date_joined=None,
    ):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=TEST_PASSWORD,
            is_active=True,
        )
        if date_joined:
            user.date_joined = date_joined
            user.save(update_fields=["date_joined"])
        user.profile.email_confirmed = email_confirmed
        user.profile.save()
        return user

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_hard_bounce_prunes_unconfirmed_new_signup(self, mock_fetch):
        """A hard bounce for an unconfirmed, data-free signup deletes the
        account immediately — no grace period, no minimum age (the remote
        server itself rejected the mailbox)."""
        user = self._create_user("botfake", "bot@nonexistent.example.com")
        user_id = user.id
        mock_fetch.return_value = [_bounce()]

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=user_id).exists())
        log = AuditLog.objects.filter(action=AuditLog.Action.USER_DELETED).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get("reason"), "email_bounced")
        self.assertEqual(log.metadata.get("email"), "bot@nonexistent.example.com")
        self.assertEqual(log.metadata.get("bounce_status"), "550 5.4.1")
        self.assertIn("Bounce pruned: 1", self.out.getvalue())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_hard_bounce_deactivates_user_with_data(self, mock_fetch):
        user = self._create_user(
            "botdata",
            "bot@nonexistent.example.com",
            date_joined=timezone.now() - timedelta(days=1),
        )
        Survey.objects.create(name="Bot", slug="bot", owner=user)
        mock_fetch.return_value = [_bounce()]

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_hard_bounce_deactivates_existing_user(self, mock_fetch):
        user = self._create_user(
            "oldbot",
            "bot@nonexistent.example.com",
            date_joined=timezone.make_aware(timezone.datetime(2024, 1, 1)),
        )
        mock_fetch.return_value = [_bounce()]

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_hard_bounce_confirmed_user_untouched(self, mock_fetch):
        """A confirmed account is never pruned on a bounce — but the event
        is surfaced (the account can no longer receive password resets)."""
        user = self._create_user(
            "confirmed", "gone@nonexistent.example.com", email_confirmed=True
        )
        mock_fetch.return_value = [_bounce(recipient="gone@nonexistent.example.com")]

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())
        self.assertFalse(
            AuditLog.objects.filter(
                action__in=[
                    AuditLog.Action.USER_DELETED,
                    AuditLog.Action.USER_DEACTIVATED,
                ]
            ).exists()
        )
        self.assertIn("CONFIRMED", self.out.getvalue())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_soft_bounce_never_prunes(self, mock_fetch):
        user = self._create_user("full", "full@example.com")
        mock_fetch.return_value = [
            _bounce(
                recipient="full@example.com",
                classification=SOFT,
                subject="Delayed: subject",
                status="452 4.2.2",
            )
        ]

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_policy_spf_bounce_never_prunes(self, mock_fetch):
        """A 5.7.x policy/SPF bounce must never prune the account."""
        user = self._create_user("spfb", "realperson@example.com")
        mock_fetch.return_value = [
            _bounce(
                recipient="realperson@example.com",
                classification=UNKNOWN,  # how the parser classifies 5.7.26
                subject="Undeliverable: Please confirm your email address",
                status="550 5.7.26",
            )
        ]

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(User.objects.filter(id=user.id).exists())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_hard_bounce_without_recipient_skipped(self, mock_fetch):
        user = self._create_user("noparse", "bot@nonexistent.example.com")
        mock_fetch.return_value = [_bounce(recipient=None)]

        call_command("prune_unconfirmed_users", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_duplicate_bounces_prune_once(self, mock_fetch):
        user = self._create_user("dupbot", "bot@nonexistent.example.com")
        mock_fetch.return_value = [
            _bounce(),
            _bounce(message_id="aaa-222"),
        ]

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=user.id).exists())
        self.assertIn("Bounce pruned: 1", self.out.getvalue())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_bounce_for_stranger_no_account(self, mock_fetch):
        """A bounce for an address with no account at all (e.g. a survey
        invite) is reported and skipped."""
        mock_fetch.return_value = [_bounce(recipient="stranger@oldmailbox.example.org")]

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertIn("No unconfirmed account found", self.out.getvalue())
        self.assertIn("Bounce pruned: 0", self.out.getvalue())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_oidc_and_staff_users_untouched(self, mock_fetch):
        oidc_user = self._create_user("oidcbot", "oidc@nonexistent.example.com")
        UserOIDC.objects.create(
            user=oidc_user,
            provider="azure",
            subject="az-bounce-1",
            email_verified=True,
            key_derivation_salt=b"s" * 32,
        )
        staff_user = self._create_user("staffbot", "staff@nonexistent.example.com")
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        mock_fetch.return_value = [
            _bounce(recipient="oidc@nonexistent.example.com"),
            _bounce(recipient="staff@nonexistent.example.com"),
        ]

        call_command("prune_unconfirmed_users", stdout=self.out)

        oidc_user.refresh_from_db()
        staff_user.refresh_from_db()
        self.assertTrue(oidc_user.is_active)
        self.assertTrue(staff_user.is_active)

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_dry_run_makes_no_changes(self, mock_fetch):
        user = self._create_user("drybot", "bot@nonexistent.example.com")
        mock_fetch.return_value = [_bounce()]

        call_command("prune_unconfirmed_users", "--dry-run", stdout=self.out)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIn("DRY RUN MODE", self.out.getvalue())
        self.assertIn("Bounce pruned: 1", self.out.getvalue())

    # --- Graceful failure: the phase must never abort the prune run ---

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_missing_permission_403_logs_and_continues(self, mock_fetch):
        """A 403 from Graph (Mail.Read not granted) is logged with
        actionable guidance; the rest of the prune run continues and
        still prunes grace-expired users."""
        response = MagicMock(status_code=403)
        mock_fetch.side_effect = requests.HTTPError("403 Forbidden", response=response)
        # A user past the grace period proves phase 2 still ran
        graced = self._create_user(
            "graced",
            "graced@example.com",
            date_joined=timezone.now() - timedelta(days=40),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=graced.id).exists())
        self.assertIn("Mail.Read", self.out.getvalue())
        self.assertIn("Deleted:       1", self.out.getvalue())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_network_error_logs_and_continues(self, mock_fetch):
        """A network outage is logged; the prune run continues."""
        mock_fetch.side_effect = requests.ConnectionError("connection refused")
        graced = self._create_user(
            "graced",
            "graced@example.com",
            date_joined=timezone.now() - timedelta(days=40),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=graced.id).exists())
        self.assertIn("Network error", self.out.getvalue())

    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_unexpected_error_logs_and_continues(self, mock_fetch):
        """Any unexpected error from the mailbox read is logged and the
        prune run continues — never a hard exit."""
        mock_fetch.side_effect = RuntimeError("totally unexpected")
        graced = self._create_user(
            "graced",
            "graced@example.com",
            date_joined=timezone.now() - timedelta(days=40),
        )

        call_command("prune_unconfirmed_users", stdout=self.out)

        self.assertFalse(User.objects.filter(id=graced.id).exists())
        self.assertIn("Unexpected error", self.out.getvalue())

    @override_settings(EMAIL_HOST_USER="")
    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_missing_mailbox_skips_gracefully(self, mock_fetch):
        """No EMAIL_HOST_USER → the phase skips with a warning, no fetch."""
        call_command("prune_unconfirmed_users", stdout=self.out)

        mock_fetch.assert_not_called()
        self.assertIn("bounce processing skipped", self.out.getvalue())

    @override_settings(EMAIL_BOUNCE_PROCESSING_ENABLED=False)
    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_disabled_setting_skips_phase(self, mock_fetch):
        user = self._create_user("offbot", "bot@nonexistent.example.com")

        call_command("prune_unconfirmed_users", stdout=self.out)

        mock_fetch.assert_not_called()
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIn("Bounce processing: off", self.out.getvalue())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
    @patch(f"{PRUNE_COMMAND_MODULE}.fetch_bounce_messages")
    def test_non_graph_backend_skips_phase(self, mock_fetch):
        """SMTP deployments have no Graph mailbox to read — the phase
        is skipped without touching the network."""
        user = self._create_user("smtpbot", "bot@nonexistent.example.com")

        call_command("prune_unconfirmed_users", stdout=self.out)

        mock_fetch.assert_not_called()
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIn("Bounce processing: off", self.out.getvalue())
