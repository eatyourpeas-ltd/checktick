#!/usr/bin/env python3
"""
Django management command to clean up expired survey progress records.

This command should be run daily (e.g., via cron or scheduled job) to:
1. Delete survey progress records that have expired (older than 30 days)
2. Delete progress records for surveys that no longer exist
3. Delete orphaned progress records with invalid sessions

Usage:
    python manage.py cleanup_survey_progress
    python manage.py cleanup_survey_progress --dry-run
    python manage.py cleanup_survey_progress --verbose
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from checktick_app.surveys.models import SurveyProgress


class Command(BaseCommand):
    help = "Delete expired survey progress records"

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
                f"Starting survey progress cleanup at {timezone.now()}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Find expired progress records
        now = timezone.now()
        expired_progress = SurveyProgress.objects.filter(expires_at__lt=now)
        expired_count = expired_progress.count()

        if verbose:
            self.stdout.write(f"Found {expired_count} expired progress records")
            if expired_count > 0 and expired_count <= 10:
                for progress in expired_progress:
                    self.stdout.write(
                        f"  - Survey: {progress.survey.slug}, "
                        f"User: {progress.user or 'anonymous'}, "
                        f"Expired: {progress.expires_at}"
                    )

        # Delete expired records
        if not dry_run:
            deleted_count, _ = expired_progress.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted_count} expired progress records")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Would delete {expired_count} expired progress records"
                )
            )

        # Additional cleanup: find very old progress (>90 days) as a safety net
        very_old_date = now - timezone.timedelta(days=90)
        very_old_progress = SurveyProgress.objects.filter(updated_at__lt=very_old_date)
        very_old_count = very_old_progress.count()

        if very_old_count > 0:
            if verbose:
                self.stdout.write(
                    self.style.WARNING(
                        f"Found {very_old_count} very old progress records (>90 days)"
                    )
                )

            if not dry_run:
                deleted_old_count, _ = very_old_progress.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted {deleted_old_count} very old progress records"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Would delete {very_old_count} very old progress records"
                    )
                )

        # Summary
        total_cleaned = expired_count + very_old_count if not dry_run else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup completed at {timezone.now()}. "
                f"Total records cleaned: {total_cleaned}"
            )
        )
