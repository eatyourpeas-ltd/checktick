"""Tests for the migrate_survey_encryption management command.

Implements §4.1/§4.3 phase 3/§4.4 of the encryption planning doc: legacy
encrypted surveys are migrated to submission keypairs interactively (owner
password / recovery phrase) or automatically (OIDC / org escrow), with
round-trip verification before plaintext is cleared, idempotent re-runs,
and metadata-only audit logging.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
import pytest

from checktick_app.surveys.models import AuditLog, Survey, SurveyResponse
from checktick_app.surveys.utils import (
    encrypt_kek_with_passphrase,
    generate_submission_keypair,
    is_submission_blob,
)

User = get_user_model()

TEST_PASSWORD = "x"  # noqa: S105
OWNER_PASSWORD = "OwnerPassword123"  # noqa: S105
RECOVERY_PHRASE = (
    "abandon ability able about above absent absorb abstract absurd abuse "
    "access accident"
)  # noqa: S105


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="legacyowner", email="lo@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def legacy_survey(db, owner):
    """Survey in the legacy scheme: symmetric KEK wrapped with password AND
    recovery phrase, with plaintext responses, legacy demographics, and a
    legacy KEK-encrypted answers blob."""
    from checktick_app.surveys.models import SurveyQuestion

    kek = generate_submission_keypair()[0]  # any 32 random bytes
    survey = Survey.objects.create(
        owner=owner,
        name="Legacy Survey",
        slug="legacy-survey",
        encrypted_kek_password=encrypt_kek_with_passphrase(kek, OWNER_PASSWORD),
        encrypted_kek_recovery=encrypt_kek_with_passphrase(kek, RECOVERY_PHRASE),
    )
    SurveyQuestion.objects.create(
        survey=survey,
        text="Pick one",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        options={"choices": ["A", "B"]},
        order=0,
    )
    # Plaintext response (the historical participant-submission gap)
    SurveyResponse.objects.create(
        survey=survey, answers={"1": "A", "2": "B"}, submitted_by=None
    )
    # Legacy KEK-encrypted whole response
    legacy = SurveyResponse(survey=survey)
    legacy.store_answers(kek, {"1": "B"})
    legacy.save()
    # Legacy KEK-encrypted demographics on a plaintext-answers row
    demo_response = SurveyResponse(survey=survey, answers={"1": "A"})
    demo_response.store_demographics(kek, {"nhs_number": "999888777"})
    demo_response.save()
    survey.kek_for_tests = kek  # in-memory only, not persisted
    return survey


def _run_command(monkeypatch, *args, stdin_text=OWNER_PASSWORD + "\n"):
    """Run the command with stdin monkeypatched (for --secret-stdin)."""
    stdout, stderr = StringIO(), StringIO()
    monkeypatch.setattr("sys.stdin", StringIO(stdin_text))
    call_command("migrate_survey_encryption", *args, stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


@pytest.mark.django_db
class TestMigrationCommand:
    def test_full_migration_with_password(self, legacy_survey, monkeypatch):
        kek = legacy_survey.kek_for_tests
        _run_command(
            monkeypatch,
            "--slug",
            "legacy-survey",
            "--method",
            "password",
            "--secret-stdin",
        )
        legacy_survey.refresh_from_db()

        # Keypair created; private key stored encrypted under the KEK
        assert legacy_survey.has_submission_keypair() is True
        assert legacy_survey.enc_submission_private_key is not None
        private_key = legacy_survey.get_submission_private_key(kek)
        assert private_key is not None and len(private_key) == 32

        # All responses re-encrypted into the submission format
        responses = list(legacy_survey.responses.order_by("id"))
        for r in responses:
            assert is_submission_blob(r.enc_answers) is True
            assert r.answers == {}
            assert r.enc_demographics is None

        # Data preserved (round-trip through the new scheme)
        payloads = [r.load_complete_response(private_key) for r in responses]
        assert payloads[0]["answers"] == {"1": "A", "2": "B"}
        assert payloads[1]["answers"] == {"1": "B"}
        assert payloads[2]["answers"] == {"1": "A"}
        assert payloads[2]["demographics"] == {"nhs_number": "999888777"}

        # Audit-logged with metadata only
        log = AuditLog.objects.filter(
            survey=legacy_survey,
            action=AuditLog.Action.RESPONSES_ENCRYPTED_BACKFILL,
        ).first()
        assert log is not None
        assert log.metadata["response_count"] == 3
        assert log.metadata["method"] == "password"

        # All unlock paths preserved: recovery phrase still unwraps the KEK,
        # which still opens the private key
        kek_via_recovery = legacy_survey.unlock_with_recovery(RECOVERY_PHRASE)
        assert kek_via_recovery == kek
        assert legacy_survey.get_submission_private_key(kek_via_recovery) == private_key

    def test_idempotent_rerun(self, legacy_survey, monkeypatch):
        for _ in range(2):
            _run_command(
                monkeypatch,
                "--slug",
                "legacy-survey",
                "--method",
                "password",
                "--secret-stdin",
            )
        logs = AuditLog.objects.filter(
            survey=legacy_survey,
            action=AuditLog.Action.RESPONSES_ENCRYPTED_BACKFILL,
        )
        assert logs.count() == 1
        assert legacy_survey.responses.count() == 3

    def test_dry_run_changes_nothing(self, legacy_survey, monkeypatch):
        stdout, stderr = StringIO(), StringIO()
        monkeypatch.setattr("sys.stdin", StringIO(OWNER_PASSWORD + "\n"))
        call_command(
            "migrate_survey_encryption",
            "--slug",
            "legacy-survey",
            "--method",
            "password",
            "--secret-stdin",
            "--dry-run",
            stdout=stdout,
            stderr=stderr,
        )
        legacy_survey.refresh_from_db()
        assert legacy_survey.has_submission_keypair() is False
        assert legacy_survey.responses.filter(enc_answers__isnull=True).exists()
        assert (
            AuditLog.objects.filter(
                action=AuditLog.Action.RESPONSES_ENCRYPTED_BACKFILL
            ).exists()
            is False
        )

    def test_wrong_password_leaves_survey_unchanged(self, legacy_survey, monkeypatch):
        stdout, stderr = StringIO(), StringIO()
        monkeypatch.setattr("sys.stdin", StringIO("WrongPassword\n"))
        call_command(
            "migrate_survey_encryption",
            "--slug",
            "legacy-survey",
            "--method",
            "password",
            "--secret-stdin",
            stdout=stdout,
            stderr=stderr,
        )
        # Unwrap failure is reported and the survey is left unchanged
        assert "failed=1" in stdout.getvalue()
        legacy_survey.refresh_from_db()
        assert legacy_survey.has_submission_keypair() is False
        assert legacy_survey.responses.filter(enc_answers__isnull=True).exists()
        assert (
            AuditLog.objects.filter(
                action=AuditLog.Action.RESPONSES_ENCRYPTED_BACKFILL
            ).exists()
            is False
        )

    def test_opted_out_survey_is_skipped(self, owner, db, monkeypatch):
        """Surveys with a valid opt-out declaration are left untouched."""
        survey = Survey.objects.create(
            owner=owner,
            name="Opted Out",
            slug="opted-out-survey",
            respondent_audience=Survey.RespondentAudience.STAFF,
            encryption_opt_out_at=timezone.now(),
            encryption_opt_out_by=owner,
            encryption_opt_out_declaration_version="1.0",
        )
        SurveyResponse.objects.create(survey=survey, answers={"1": "plain"})
        stdout, stderr = _run_command(
            monkeypatch,
            "--slug",
            "opted-out-survey",
            "--method",
            "password",
            "--secret-stdin",
        )
        survey.refresh_from_db()
        assert survey.has_submission_keypair() is False
        assert survey.responses.first().answers == {"1": "plain"}
        assert "skipped(opted-out)=1" in stdout

    def test_unlock_session_returns_private_key_after_migration(
        self, legacy_survey, monkeypatch
    ):
        """After migration, an owner unlock must yield the private key (via
        KEK unwrap), so read paths work unchanged."""
        from checktick_app.surveys.views import _submission_key_for_survey

        _run_command(
            monkeypatch,
            "--slug",
            "legacy-survey",
            "--method",
            "password",
            "--secret-stdin",
        )
        legacy_survey.refresh_from_db()
        kek = legacy_survey.unlock_with_password(OWNER_PASSWORD)
        key = _submission_key_for_survey(legacy_survey, kek)
        assert key is not None and key != kek  # private key, not the KEK
        response = legacy_survey.responses.first()
        assert response.load_answers(key) is not None
