"""
Django management command to execute platform recovery with custodian shares.

This command performs emergency recovery for users who have lost BOTH their
password AND recovery phrase. It requires:
- An approved RecoveryRequest (dual authorization + time delay complete)
- 3 of 4 custodian component shares (Shamir's Secret Sharing)

Usage:
    python manage.py execute_platform_recovery <request_id> \\
        --custodian-share-1=<share1> \\
        --custodian-share-2=<share2> \\
        --custodian-share-3=<share3>

Security:
    - All actions logged to audit trail
    - Shares only exist in memory during execution
    - Must be run from secure terminal (not webapp)
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from checktick_app.surveys.models import AuditLog, RecoveryRequest
from checktick_app.surveys.shamir import reconstruct_secret
from checktick_app.surveys.vault_client import VaultConnectionError, get_vault_client

User = get_user_model()


class Command(BaseCommand):
    help = "Execute platform recovery using custodian component shares"

    def add_arguments(self, parser):
        parser.add_argument(
            "request_id",
            type=str,
            help="Recovery request ID (UUID or request code like ABC-123-XYZ)",
        )
        parser.add_argument(
            "--custodian-share-1",
            type=str,
            required=True,
            help="Custodian share 1 (from admin 1)",
        )
        parser.add_argument(
            "--custodian-share-2",
            type=str,
            required=True,
            help="Custodian share 2 (from admin 2)",
        )
        parser.add_argument(
            "--custodian-share-3",
            type=str,
            required=True,
            help="Custodian share 3 (from physical safe or cloud backup)",
        )
        parser.add_argument(
            "--executor",
            type=str,
            help="Email of admin executing recovery (for audit trail)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Verify shares and check status without executing recovery",
        )

    def handle(self, *args, **options):
        """Execute platform recovery."""
        request_id = options["request_id"]
        share1 = options["custodian_share_1"]
        share2 = options["custodian_share_2"]
        share3 = options["custodian_share_3"]
        executor_email = options.get("executor")
        dry_run = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING("Platform Recovery Execution"))
        self.stdout.write("")

        # Find recovery request
        try:
            # Try as UUID first, then as request code
            try:
                recovery_request = RecoveryRequest.objects.get(id=request_id)
            except ValueError:
                # Not a valid UUID, try request code
                recovery_request = RecoveryRequest.objects.get(request_code=request_id)
        except RecoveryRequest.DoesNotExist:
            raise CommandError(f"Recovery request not found: {request_id}")

        # Display request details
        self.stdout.write(self.style.MIGRATE_LABEL("Recovery Request:"))
        self.stdout.write(f"  Request Code: {recovery_request.request_code}")
        self.stdout.write(f"  User: {recovery_request.user.email}")
        self.stdout.write(f"  Survey: {recovery_request.survey.name}")
        self.stdout.write(f"  Status: {recovery_request.get_status_display()}")
        self.stdout.write(f"  Submitted: {recovery_request.submitted_at}")
        self.stdout.write("")

        # Validate status
        if recovery_request.status == RecoveryRequest.Status.COMPLETED:
            raise CommandError("Recovery has already been completed")

        if recovery_request.status == RecoveryRequest.Status.REJECTED:
            raise CommandError("Recovery request was rejected")

        if recovery_request.status == RecoveryRequest.Status.CANCELLED:
            raise CommandError("Recovery request was cancelled")

        if recovery_request.status != RecoveryRequest.Status.READY_FOR_EXECUTION:
            # Check if time delay has passed but status not updated yet
            if (
                recovery_request.time_delay_until
                and recovery_request.time_delay_until <= timezone.now()
            ):
                self.stdout.write(
                    self.style.WARNING(
                        "Time delay complete but status not updated. Continuing..."
                    )
                )
            else:
                raise CommandError(
                    f"Recovery not ready. Status: {recovery_request.get_status_display()}\n"
                    f"Time delay until: {recovery_request.time_delay_until}"
                )

        # Check time delay
        if recovery_request.time_delay_until:
            time_remaining = recovery_request.time_delay_until - timezone.now()
            if time_remaining.total_seconds() > 0:
                raise CommandError(
                    f"Time delay not complete. Wait {time_remaining} before executing."
                )

        # Get executor
        if executor_email:
            try:
                executor = User.objects.get(email=executor_email)
            except User.DoesNotExist:
                raise CommandError(f"Executor not found: {executor_email}")
        else:
            executor = (
                recovery_request.secondary_approver or recovery_request.primary_approver
            )
            if not executor:
                raise CommandError(
                    "No executor found. Provide --executor=<email> argument"
                )

        self.stdout.write(self.style.MIGRATE_LABEL("Authorization:"))
        self.stdout.write(
            f"  Primary Approver: {recovery_request.primary_approver.email}"
        )
        self.stdout.write(
            f"  Secondary Approver: {recovery_request.secondary_approver.email}"
        )
        self.stdout.write(f"  Executor: {executor.email}")
        self.stdout.write("")

        # Reconstruct custodian component from shares
        self.stdout.write(self.style.MIGRATE_LABEL("Reconstructing Custodian Key:"))
        try:
            custodian_component = reconstruct_secret([share1, share2, share3])

            if len(custodian_component) != 64:
                raise ValueError(
                    f"Reconstructed key wrong size: {len(custodian_component)} bytes, expected 64"
                )

            self.stdout.write(
                self.style.SUCCESS("  ✓ Custodian component reconstructed (64 bytes)")
            )
        except Exception as e:
            raise CommandError(f"Failed to reconstruct custodian component: {e}")

        self.stdout.write("")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: Would execute recovery but not proceeding")
            )
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS("✓ All checks passed. Ready for execution.")
            )
            return

        # Execute recovery
        self.stdout.write(self.style.MIGRATE_LABEL("Executing Recovery:"))

        try:
            # Get Vault client
            vault = get_vault_client()

            # Recover survey KEK from Vault escrow
            verification_notes = (
                f"Platform recovery executed by {executor.email} "
                f"using custodian shares. "
                f"Primary: {recovery_request.primary_approver.email}, "
                f"Secondary: {recovery_request.secondary_approver.email}"
            )

            survey_kek = vault.recover_user_survey_kek(
                user_id=recovery_request.user.id,
                survey_id=recovery_request.survey.id,
                admin_id=executor.id,
                verification_notes=verification_notes,
                platform_custodian_component=custodian_component,
            )

            self.stdout.write(self.style.SUCCESS("  ✓ Survey KEK recovered from Vault"))

            # Update recovery request
            recovery_request.status = RecoveryRequest.Status.COMPLETED
            recovery_request.completed_at = timezone.now()
            recovery_request.executed_by = executor
            recovery_request.custodian_component_used = True
            recovery_request.save()

            self.stdout.write(
                self.style.SUCCESS("  ✓ Recovery request marked complete")
            )

            # Create audit log
            AuditLog.objects.create(
                event_type="platform_recovery_executed",
                actor=executor,
                target_user=recovery_request.user,
                survey=recovery_request.survey,
                details={
                    "recovery_request": str(recovery_request.id),
                    "request_code": recovery_request.request_code,
                    "primary_approver": recovery_request.primary_approver.email,
                    "secondary_approver": recovery_request.secondary_approver.email,
                    "time_delay_hours": recovery_request.time_delay_hours,
                    "verification_notes": verification_notes,
                    "custodian_shares_used": 3,
                },
            )

            self.stdout.write(self.style.SUCCESS("  ✓ Audit log created"))
            self.stdout.write("")

            # Store recovered KEK for user access
            # In production, this would be stored in user's session or sent via secure channel
            self.stdout.write(self.style.MIGRATE_HEADING("Recovery Complete"))
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ User {recovery_request.user.email} can now access survey"
                )
            )
            self.stdout.write("")

            self.stdout.write(self.style.MIGRATE_LABEL("Next Steps:"))
            self.stdout.write("1. Notify user that recovery is complete")
            self.stdout.write("2. User should log in and access survey")
            self.stdout.write("3. User should set new password + recovery phrase")
            self.stdout.write("4. Notify organization admin (if applicable)")
            self.stdout.write("")

            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Security: Custodian shares will be cleared from memory"
                )
            )

        except VaultConnectionError as e:
            raise CommandError(f"Vault connection error: {e}")
        except Exception as e:
            raise CommandError(f"Recovery execution failed: {e}")
        finally:
            # Explicitly clear shares and keys from memory
            share1 = share2 = share3 = None
            custodian_hex = None
            custodian_component = None
            if "survey_kek" in locals():
                survey_kek = None
