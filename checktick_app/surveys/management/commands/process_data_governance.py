#!/usr/bin/env python3
"""
Django management command to process data governance tasks.

This command should be run daily (e.g., via cron or a Kubernetes CronJob) to:
1. Send deletion warning emails (30 days, 7 days, 1 day before deletion)
2. Automatically soft-delete surveys that have passed their retention period
3. Automatically hard-delete surveys that have passed their grace period

Usage:
    python manage.py process_data_governance
    python manage.py process_data_governance --dry-run
    python manage.py process_data_governance --verbose
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from checktick_app.surveys.services.retention_service import RetentionService


class Command(BaseCommand):
    help = "Process data governance tasks (deletion warnings and automatic deletions)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting data governance processing at {timezone.now()}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Process deletion warnings
        self._process_deletion_warnings(dry_run, verbose)

        # Process automatic deletions
        if not dry_run:
            self._process_automatic_deletions(verbose)
        else:
            self.stdout.write(
                self.style.WARNING("Skipping automatic deletions in dry-run mode")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Data governance processing completed at {timezone.now()}"
            )
        )

    def _process_deletion_warnings(self, dry_run, verbose):
        """Send deletion warning emails for surveys approaching deletion."""
        self.stdout.write(self.style.HTTP_INFO("\n--- Deletion Warnings ---"))

        warning_counts = {}
        for days in RetentionService.WARNING_DAYS:
            surveys = RetentionService.get_surveys_pending_deletion_warning(days)
            warning_counts[days] = len(surveys)

            if verbose or dry_run:
                self.stdout.write(f"\n{days}-day warnings: {len(surveys)} surveys")

            if surveys and verbose:
                for survey in surveys:
                    self.stdout.write(
                        f"  - {survey.name} (ID: {survey.id}, "
                        f"Deletion: {survey.deletion_date})"
                    )

            if not dry_run:
                for survey in surveys:
                    try:
                        RetentionService.send_deletion_warning(survey, days)
                        if verbose:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ Sent {days}-day warning for: {survey.name}"
                                )
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ Failed to send warning for {survey.name}: {e}"
                            )
                        )

        # Summary
        total_warnings = sum(warning_counts.values())
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'Would send' if dry_run else 'Sent'} {total_warnings} "
                f"deletion warnings:"
            )
        )
        for days in sorted(warning_counts.keys(), reverse=True):
            self.stdout.write(f"  - {days}-day warnings: {warning_counts[days]}")

    def _process_automatic_deletions(self, verbose):
        """Process automatic soft and hard deletions."""
        self.stdout.write(self.style.HTTP_INFO("\n--- Automatic Deletions ---"))

        try:
            stats = RetentionService.process_automatic_deletions()

            # Report results
            self.stdout.write(
                self.style.SUCCESS(f"Soft deleted: {stats['soft_deleted']} surveys")
            )
            self.stdout.write(
                self.style.SUCCESS(f"Hard deleted: {stats['hard_deleted']} surveys")
            )

            if stats["skipped_legal_hold"] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped (legal hold): {stats['skipped_legal_hold']} surveys"
                    )
                )

            # Alert if any deletions occurred
            total_deletions = stats["soft_deleted"] + stats["hard_deleted"]
            if total_deletions > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n⚠️  {total_deletions} surveys were deleted. "
                        "Check audit logs for details."
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error processing automatic deletions: {e}")
            )
            raise
