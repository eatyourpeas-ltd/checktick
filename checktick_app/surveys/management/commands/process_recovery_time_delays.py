#!/usr/bin/env python3
"""
Django management command to process recovery request time delays.

This command should be run frequently (e.g., every 5 minutes via cron) to:
1. Check for recovery requests where the time delay has expired
2. Update their status to READY_FOR_EXECUTION
3. Send notification emails to administrators

Usage:
    python manage.py process_recovery_time_delays
    python manage.py process_recovery_time_delays --dry-run
    python manage.py process_recovery_time_delays --verbose
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from checktick_app.surveys.models import RecoveryRequest

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process recovery request time delays and update status when expired"

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

        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting recovery time delay processing at {timezone.now()}"
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Find all requests in time delay that have expired
        expired_requests = RecoveryRequest.objects.filter(
            status=RecoveryRequest.Status.IN_TIME_DELAY,
            time_delay_until__lte=timezone.now(),
        )

        count = expired_requests.count()

        if count == 0:
            if verbose:
                self.stdout.write(self.style.SUCCESS("No expired time delays found"))
            return

        if verbose or dry_run:
            self.stdout.write(
                f"Found {count} recovery request(s) with expired time delays"
            )

        processed = 0
        errors = 0

        for request in expired_requests:
            try:
                if verbose:
                    self.stdout.write(
                        f"  Processing: {request.request_code} "
                        f"(User: {request.user.email}, Survey: {request.survey.name})"
                    )
                    self.stdout.write(
                        f"    Time delay expired: {request.time_delay_until}"
                    )

                if not dry_run:
                    # Use the model's method which handles status update and audit entry
                    completed = request.check_time_delay_complete()

                    if completed:
                        processed += 1

                        # Send notification email
                        self._send_ready_notification(request, verbose)

                        if verbose:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    "    ✓ Status updated to READY_FOR_EXECUTION"
                                )
                            )
                    else:
                        # This shouldn't happen given our query, but log it
                        self.stdout.write(
                            self.style.WARNING(
                                "    ⚠ Time delay not complete (unexpected)"
                            )
                        )
                else:
                    processed += 1
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "    [DRY RUN] Would update to READY_FOR_EXECUTION"
                            )
                        )

            except Exception as e:
                errors += 1
                logger.exception(
                    f"Error processing recovery request {request.request_code}: {e}"
                )
                self.stdout.write(
                    self.style.ERROR(
                        f"    ✗ Error processing {request.request_code}: {e}"
                    )
                )

        # Summary
        action = "Would process" if dry_run else "Processed"
        self.stdout.write(
            self.style.SUCCESS(f"\n{action} {processed} recovery request(s)")
        )

        if errors > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {errors}"))

        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovery time delay processing completed at {timezone.now()}"
                )
            )

    def _send_ready_notification(self, request: RecoveryRequest, verbose: bool):
        """Send notification that recovery is ready for execution."""
        try:
            from checktick_app.surveys.notifications import (
                send_recovery_ready_for_execution_notification,
            )

            send_recovery_ready_for_execution_notification(request)

            if verbose:
                self.stdout.write(
                    self.style.SUCCESS("    ✓ Sent ready-for-execution notification")
                )

        except ImportError:
            # Notification function doesn't exist yet
            if verbose:
                self.stdout.write(
                    self.style.WARNING("    ⚠ Notification function not available")
                )
        except Exception as e:
            logger.warning(
                f"Failed to send ready notification for {request.request_code}: {e}"
            )
            if verbose:
                self.stdout.write(
                    self.style.WARNING(f"    ⚠ Failed to send notification: {e}")
                )
