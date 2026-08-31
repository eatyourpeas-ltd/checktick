"""Grandfather existing password-user surveys as unencrypted (legacy opt-out).

One-time data migration for the encrypt-all-responses security upgrade
(see docs/encryption-technical-reference.md):

Every survey that exists at deploy time, owned by a password (non-SSO) user,
without a patient_details_encrypted question group, and without a recorded
opt-out declaration, gets a `legacy-1.0` opt-out declaration recorded on its
behalf. This keeps existing plaintext surveys readable without requiring the
owner's KEK (owners may have lost their password / recovery phrase).

Surveys created after this migration runs get no declaration: going forward
the creator's explicit declaration is the sole determinant of plaintext
storage (§3.3). If a grandfathered owner later confirms a patient/public
audience at the publish prompt, the declaration stops applying because
Survey.has_encryption_opt_out() only honours it for staff-audience surveys.

Idempotent: re-running matches nothing (declarations already recorded).
"""

from django.db import migrations
from django.utils import timezone

LEGACY_DECLARATION_VERSION = "legacy-1.0"
BATCH_SIZE = 500


def grandfather_existing_surveys(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    UserOIDC = apps.get_model("core", "UserOIDC")
    AuditLog = apps.get_model("surveys", "AuditLog")

    sso_user_ids = set(UserOIDC.objects.values_list("user_id", flat=True))
    now = timezone.now()

    to_update = []
    logs = []
    candidates = (
        Survey.objects.filter(encryption_opt_out_at__isnull=True)
        .exclude(owner_id__in=sso_user_ids)
        .iterator()
    )
    for survey in candidates:
        if survey.question_groups.filter(
            schema__template="patient_details_encrypted"
        ).exists():
            continue
        survey.encryption_opt_out_at = now
        survey.encryption_opt_out_by_id = survey.owner_id
        survey.encryption_opt_out_declaration_version = LEGACY_DECLARATION_VERSION
        to_update.append(survey)
        logs.append(
            AuditLog(
                actor_id=survey.owner_id,
                scope="survey",
                survey=survey,
                action="encryption_opt_out_declared",
                severity="info",
                message=(
                    "Encryption opt-out recorded automatically for pre-existing "
                    "survey (grandfathered plaintext storage)."
                ),
                metadata={
                    "grandfathered": True,
                    "declaration_version": LEGACY_DECLARATION_VERSION,
                    "survey_id": survey.pk,
                },
            )
        )
        if len(to_update) >= BATCH_SIZE:
            _flush_batch(Survey, AuditLog, to_update, logs)
            to_update, logs = [], []
    if to_update or logs:
        _flush_batch(Survey, AuditLog, to_update, logs)


def _flush_batch(Survey, AuditLog, to_update, logs):
    AuditLog.objects.bulk_create(logs, batch_size=BATCH_SIZE)
    Survey.objects.bulk_update(
        to_update,
        [
            "encryption_opt_out_at",
            "encryption_opt_out_by",
            "encryption_opt_out_declaration_version",
        ],
        batch_size=BATCH_SIZE,
    )


def revert_grandfathering(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    AuditLog = apps.get_model("surveys", "AuditLog")
    AuditLog.objects.filter(
        action="encryption_opt_out_declared",
        metadata__grandfathered=True,
    ).delete()
    Survey.objects.filter(
        encryption_opt_out_declaration_version=LEGACY_DECLARATION_VERSION
    ).update(
        encryption_opt_out_at=None,
        encryption_opt_out_by=None,
        encryption_opt_out_declaration_version="",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0054_survey_audience_confirmed_and_more"),
    ]

    operations = [
        migrations.RunPython(grandfather_existing_surveys, revert_grandfathering),
    ]
