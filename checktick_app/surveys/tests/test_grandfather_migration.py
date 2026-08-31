"""Tests for migration 0055: grandfather existing surveys as unencrypted.

See docs/security-upgrade-encrypt-all-responses-planning.md §4.1/§4.3:
existing password-user, staff-audience, non-patient surveys are recorded as
having opted out of encryption (legacy declaration) so their plaintext
responses remain readable without the owner's KEK. Going forward, new surveys
get no declaration and the creator's explicit declaration is the determinant.
"""

from importlib import import_module

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.core.models import UserOIDC
from checktick_app.surveys.models import AuditLog, QuestionGroup, Survey

TEST_PASSWORD = "x"  # noqa: S105

# The migration module filename starts with a digit, so import via importlib.
migration_module = import_module(
    "checktick_app.surveys.migrations.0055_grandfather_encryption_opt_out"
)

User = get_user_model()


@pytest.fixture
def password_user(db):
    return User.objects.create_user(
        username="legacyowner", email="legacy@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def sso_user(db):
    u = User.objects.create_user(
        username="ssoowner", email="sso@example.com", password=TEST_PASSWORD
    )
    UserOIDC.objects.create(user=u, provider="google", subject="sub-legacy-1")
    return u


def _make_survey(owner, name, slug, patient_group=None):
    survey = Survey.objects.create(owner=owner, name=name, slug=slug)
    if patient_group is not None:
        survey.question_groups.add(patient_group)
    return survey


@pytest.fixture
def patient_group(db, password_user):
    return QuestionGroup.objects.create(
        name="Patient Details",
        owner=password_user,
        schema={
            "template": "patient_details_encrypted",
            "fields": ["nhs_number"],
        },
    )


def _run_grandfathering():
    # The function only uses get_model() and standard ORM APIs, so the live
    # app registry is interchangeable with the historical one here.
    from django.apps import apps

    migration_module.grandfather_existing_surveys(apps, None)


@pytest.mark.django_db
class TestGrandfatherMigration:
    def test_password_user_survey_gets_legacy_declaration(self, password_user):
        survey = _make_survey(password_user, "Old Survey", "old-survey")
        _run_grandfathering()
        survey.refresh_from_db()
        assert survey.encryption_opt_out_at is not None
        assert survey.encryption_opt_out_by_id == password_user.id
        assert (
            survey.encryption_opt_out_declaration_version
            == migration_module.LEGACY_DECLARATION_VERSION
        )
        # Grandfathered surveys are treated as opted out (plaintext allowed)
        assert survey.requires_whole_response_encryption() is False

    def test_audit_log_records_grandfathered_metadata(self, password_user):
        survey = _make_survey(password_user, "Old Survey", "old-survey-audit")
        _run_grandfathering()
        log = AuditLog.objects.filter(
            survey=survey,
            action=AuditLog.Action.ENCRYPTION_OPT_OUT_DECLARED,
        ).first()
        assert log is not None
        assert log.metadata.get("grandfathered") is True
        assert log.metadata.get("declaration_version") == "legacy-1.0"

    def test_sso_owned_surveys_are_skipped(self, sso_user):
        survey = _make_survey(sso_user, "SSO Survey", "sso-survey")
        _run_grandfathering()
        survey.refresh_from_db()
        assert survey.encryption_opt_out_at is None
        # SSO surveys remain encrypted regardless
        assert survey.requires_whole_response_encryption() is True

    def test_patient_data_surveys_are_skipped(self, password_user, patient_group):
        survey = _make_survey(
            password_user, "Patient Survey", "patient-legacy", patient_group
        )
        _run_grandfathering()
        survey.refresh_from_db()
        assert survey.encryption_opt_out_at is None
        assert survey.requires_whole_response_encryption() is True

    def test_surveys_with_existing_declaration_are_untouched(self, password_user):
        original = timezone.now() - timezone.timedelta(days=30)
        survey = _make_survey(password_user, "Declared Survey", "declared-survey")
        survey.encryption_opt_out_at = original
        survey.encryption_opt_out_by = password_user
        survey.encryption_opt_out_declaration_version = "1.0"
        survey.save()
        _run_grandfathering()
        survey.refresh_from_db()
        assert survey.encryption_opt_out_at == original
        assert survey.encryption_opt_out_declaration_version == "1.0"

    def test_idempotent(self, password_user):
        survey = _make_survey(password_user, "Idempotent", "idempotent-survey")
        _run_grandfathering()
        survey.refresh_from_db()
        first = survey.encryption_opt_out_at
        log_count = AuditLog.objects.filter(
            action=AuditLog.Action.ENCRYPTION_OPT_OUT_DECLARED
        ).count()
        _run_grandfathering()
        survey.refresh_from_db()
        assert survey.encryption_opt_out_at == first
        assert (
            AuditLog.objects.filter(
                action=AuditLog.Action.ENCRYPTION_OPT_OUT_DECLARED
            ).count()
            == log_count
        )
