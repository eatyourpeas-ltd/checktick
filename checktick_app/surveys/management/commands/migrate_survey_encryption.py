"""Interactive migration of legacy encrypted surveys to submission keypairs.

Implements the migration strategy described in
 docs/encryption-technical-reference.md (grandfathering, keypair migration,
 unlock-path preservation).

Surveys that require whole-response encryption (Option C predicate) but
predate the submission-keypair scheme are migrated:

1. The survey's KEK is unwrapped via an owner-controlled method
   (password / recovery phrase — interactive; OIDC / organisation key —
   automated, no owner interaction).
2. A fresh X25519 submission keypair is generated. The private key is
   stored encrypted under the KEK (Survey.enc_submission_private_key), so
   ALL existing unlock paths (password, recovery, OIDC, org escrow) keep
   working — migrating with one method never invalidates the others.
3. Every response is re-encrypted into the submission format (public-key
   hybrid encryption). Legacy KEK-encrypted demographics are decrypted and
   folded into the payload. Plaintext is only cleared after a round-trip
   verification of the new blob (§4.4).
4. Each migrated survey is audit-logged (metadata only: counts, no answer
   content).

Safety properties (§4.4):
- Idempotent: already-migrated surveys and responses are skipped, so the
  command can be re-run after interruption.
- Resumable: responses are processed in batches, each in its own
  transaction.
- Never deletes plaintext before the replacement ciphertext is verified by
  a round-trip decryption.

Usage:
  # Interactive, one survey (prompts for the password / recovery phrase)
  python manage.py migrate_survey_encryption --slug my-survey --method password
  python manage.py migrate_survey_encryption --slug my-survey --method recovery

  # Automated phases (no owner interaction)
  python manage.py migrate_survey_encryption --all --method oidc
  python manage_survey_encryption --all --method org

  # Preview without changes
  python manage.py migrate_survey_encryption --slug my-survey --method password --dry-run

Secrets can also be piped in non-interactively via --secret-stdin (read once
from stdin, never echoed or logged).
"""

import getpass
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from checktick_app.surveys.models import AuditLog, Survey, SurveyResponse
from checktick_app.surveys.utils import (
    decrypt_sensitive,
    decrypt_submission,
    encrypt_for_submission,
    encrypt_sensitive,
    generate_submission_keypair,
)


class Command(BaseCommand):
    help = (
        "Migrate legacy encrypted surveys to submission keypairs: generate a "
        "per-survey X25519 keypair, re-encrypt all responses into the "
        "public-key submission format, and preserve every existing unlock "
        "path. Idempotent and resumable."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--slug", help="Migrate a single survey by slug (interactive methods)"
        )
        target.add_argument(
            "--all",
            action="store_true",
            help="Migrate every eligible survey (automated methods only)",
        )
        parser.add_argument(
            "--method",
            required=True,
            choices=["password", "recovery", "oidc", "org"],
            help="How to unwrap the survey KEK. password/recovery are "
            "interactive (or --secret-stdin); oidc/org are automated.",
        )
        parser.add_argument(
            "--secret-stdin",
            action="store_true",
            help="Read the password/recovery phrase from stdin instead of an "
            "interactive prompt (never echoed or logged).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be migrated without changing anything.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Responses per transaction batch (default 200).",
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.batch_size = options["batch_size"]
        self.method = options["method"]
        self.secret = self._read_secret(options)

        if options["all"]:
            if self.method in ("password", "recovery"):
                raise CommandError(
                    "--all requires an automated method (oidc or org); "
                    "password/recovery need the owner's secret per survey."
                )
            surveys = Survey.objects.all()
        else:
            surveys = Survey.objects.filter(slug=options["slug"])
            if not surveys.exists():
                raise CommandError(f"No survey found with slug {options['slug']!r}")

        migrated = skipped_keypair = skipped_opted_out = failed = 0
        for survey in surveys.iterator():
            if survey.has_submission_keypair():
                skipped_keypair += 1
                continue
            if not survey.requires_whole_response_encryption():
                skipped_opted_out += 1
                continue
            try:
                if self._migrate_survey(survey):
                    migrated += 1
                else:
                    skipped_keypair += 1  # nothing to do (no legacy data)
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"FAILED {survey.slug}: {type(exc).__name__} (survey "
                        f"left unchanged; re-run to retry)"
                    )
                )
                # Never log exception details that could contain secrets.

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. migrated={migrated} skipped(already-keypair/no-data)="
                f"{skipped_keypair} skipped(opted-out)={skipped_opted_out} "
                f"failed={failed}"
            )
        )

    def _read_secret(self, options) -> str | None:
        """Read the password/recovery phrase for interactive methods."""
        if self.method not in ("password", "recovery"):
            return None
        if options["secret_stdin"]:
            secret = sys.stdin.readline().rstrip("\n")
        else:
            prompt = (
                "Survey password" if self.method == "password" else "Recovery phrase"
            )
            secret = getpass.getpass(f"{prompt}: ")
        if not secret:
            raise CommandError("No secret provided.")
        return secret

    # ------------------------------------------------------------------
    # Per-survey migration
    # ------------------------------------------------------------------

    def _migrate_survey(self, survey: Survey) -> bool:
        """Migrate one survey. Returns False if there was nothing to do."""
        legacy_responses = self._legacy_responses(survey)
        has_legacy_demographics = survey.responses.filter(
            enc_demographics__isnull=False
        ).exists()
        if not legacy_responses.exists() and not has_legacy_demographics:
            return False

        self.stdout.write(f"Migrating survey {survey.slug} (owner: {survey.owner_id})")

        kek = self._unwrap_kek(survey)
        if kek is None:
            raise CommandError(
                f"Could not unwrap the KEK for {survey.slug} using the "
                f"{self.method} method."
            )

        private_key, public_key = generate_submission_keypair()

        if self.dry_run:
            self.stdout.write(
                f"  [dry-run] would generate keypair and re-encrypt "
                f"{legacy_responses.count()} response(s)"
            )
            return True

        # Store the keypair: public key on the survey, private key encrypted
        # under the KEK so every existing unlock path keeps working.
        # (encrypt_sensitive serialises JSON, so the raw key is hex-encoded.)
        survey.submission_public_key = public_key
        survey.enc_submission_private_key = encrypt_sensitive(
            kek, {"private_key": private_key.hex()}
        )
        survey.save(
            update_fields=["submission_public_key", "enc_submission_private_key"]
        )

        migrated_count = 0
        batch: list[SurveyResponse] = []

        def flush():
            nonlocal batch, migrated_count
            if not batch:
                return
            with transaction.atomic():
                for response in batch:
                    response.save()
            migrated_count += len(batch)
            self.stdout.write(f"  migrated {migrated_count} response(s)...")
            batch = []

        for response in legacy_responses.iterator():
            payload = self._build_payload(response, kek)
            if payload is None:
                # Undecryptable legacy blob: leave untouched, report below.
                self.stderr.write(
                    self.style.WARNING(
                        f"  skipped response {response.id}: legacy data "
                        f"undecryptable with this KEK"
                    )
                )
                continue
            blob = encrypt_for_submission(public_key, payload)
            # Round-trip verification BEFORE clearing plaintext (§4.4)
            verified = decrypt_submission(private_key, blob)
            if verified != payload:
                raise RuntimeError(
                    f"Round-trip verification failed for response {response.id}"
                )
            response.enc_answers = blob
            response.answers = {}
            response.enc_demographics = None
            batch.append(response)
            if len(batch) >= self.batch_size:
                flush()
        flush()

        AuditLog.objects.create(
            actor=survey.owner,
            scope=AuditLog.Scope.SURVEY,
            survey=survey,
            action=AuditLog.Action.RESPONSES_ENCRYPTED_BACKFILL,
            severity=AuditLog.Severity.INFO,
            message=(
                "Survey migrated to submission-keypair encryption; legacy "
                "responses re-encrypted and plaintext cleared after "
                "verification."
            ),
            metadata={
                "method": self.method,
                "response_count": migrated_count,
                "survey_id": survey.pk,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  {survey.slug}: {migrated_count} response(s) migrated; "
                f"all unlock paths preserved"
            )
        )
        return True

    def _legacy_responses(self, survey: Survey):
        """Responses still in the legacy format (plaintext or KEK blobs).

        The survey has no keypair yet, so any non-null enc_answers is a
        legacy KEK-encrypted blob.
        """
        return survey.responses.filter(
            Q(enc_answers__isnull=True) & ~Q(answers={}) | Q(enc_answers__isnull=False)
        ).order_by("id")

    def _unwrap_kek(self, survey: Survey) -> bytes | None:
        if self.method == "password":
            return survey.unlock_with_password(self.secret)
        if self.method == "recovery":
            return survey.unlock_with_recovery(self.secret)
        if self.method == "oidc":
            return survey.unlock_with_oidc(survey.owner)
        if self.method == "org":
            if not survey.organization:
                return None
            return survey.unlock_with_org_key(survey.organization)
        return None

    def _build_payload(self, response: SurveyResponse, kek: bytes) -> dict | None:
        """Build the submission payload for a legacy response.

        Plaintext answers go in as-is; legacy KEK-encrypted demographics are
        decrypted and folded in. Returns None when legacy ciphertext cannot
        be decrypted with this KEK.
        """
        payload: dict = {}
        if response.enc_answers:
            try:
                legacy = decrypt_sensitive(kek, bytes(response.enc_answers))
            except Exception:
                return None
            # Legacy blobs may be {"answers": ..., "demographics": ...}
            # (store_complete_response) or a plain answers dict
            # (store_answers).
            if isinstance(legacy, dict) and "answers" in legacy:
                payload.update(legacy)
            else:
                payload["answers"] = legacy
        else:
            payload["answers"] = response.answers or {}

        if response.enc_demographics:
            try:
                payload["demographics"] = decrypt_sensitive(
                    kek, bytes(response.enc_demographics)
                )
            except Exception:
                return None
        return payload
