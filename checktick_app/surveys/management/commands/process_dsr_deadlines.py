#!/usr/bin/env python3
"""
Django management command to process data subject request deadlines.

This command should be run daily (e.g., via cron or Northflank scheduled job) to:
1. Send reminder emails at 7 days and 28 days after DSR notification
2. Automatically freeze responses at 30 days if controller hasn't acted
3. Mark surveys with pending DSRs for admin visibility

Usage:
    python manage.py process_dsr_deadlines
    python manage.py process_dsr_deadlines --dry-run
    python manage.py process_dsr_deadlines --verbose
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from checktick_app.surveys.models import DataSubjectRequest


class Command(BaseCommand):
    help = "Process data subject request deadlines (reminders and auto-freeze)"

    # Days after notification to send reminders
    REMINDER_DAYS = [7, 28]
    # Days after notification to auto-freeze
    AUTO_FREEZE_DAYS = 30

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
            self.style.SUCCESS(f"Starting DSR deadline processing at {timezone.now()}")
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Process reminders
        self._process_reminders(dry_run, verbose)

        # Process auto-freeze
        self._process_auto_freeze(dry_run, verbose)

        # Update survey DSR flags
        self._update_survey_dsr_flags(dry_run, verbose)

        self.stdout.write(
            self.style.SUCCESS(f"DSR deadline processing completed at {timezone.now()}")
        )

    def _process_reminders(self, dry_run: bool, verbose: bool) -> None:
        """Send reminder emails for DSRs approaching deadline."""
        self.stdout.write(self.style.HTTP_INFO("\n--- DSR Reminders ---"))

        now = timezone.now()

        for days in self.REMINDER_DAYS:
            # Find DSRs that are exactly N days old (±12 hours to account for timing)
            target_date = now - timezone.timedelta(days=days)
            window_start = target_date - timezone.timedelta(hours=12)
            window_end = target_date + timezone.timedelta(hours=12)

            dsrs = DataSubjectRequest.objects.filter(
                status=DataSubjectRequest.Status.NOTIFIED,
                controller_notified_at__gte=window_start,
                controller_notified_at__lt=window_end,
            ).select_related("response__survey", "response__survey__owner")

            if verbose:
                self.stdout.write(f"\n{days}-day reminders: {dsrs.count()} DSRs")

            for dsr in dsrs:
                survey = dsr.response.survey
                owner = survey.owner

                if verbose:
                    self.stdout.write(
                        f"  - DSR {dsr.id} for survey '{survey.name}' "
                        f"(Owner: {owner.email if owner else 'None'})"
                    )

                if not dry_run and owner and owner.email:
                    self._send_reminder_email(dsr, days)
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    ✓ Sent {days}-day reminder to {owner.email}"
                            )
                        )

    def _process_auto_freeze(self, dry_run: bool, verbose: bool) -> None:
        """Auto-freeze responses for DSRs past the deadline."""
        self.stdout.write(self.style.HTTP_INFO("\n--- Auto-Freeze Processing ---"))

        now = timezone.now()

        # Find DSRs that are past 30 days and still in NOTIFIED status
        overdue_dsrs = DataSubjectRequest.objects.filter(
            status=DataSubjectRequest.Status.NOTIFIED,
            deadline__lt=now,
        ).select_related("response__survey", "response__survey__owner")

        if verbose:
            self.stdout.write(f"\nOverdue DSRs to freeze: {overdue_dsrs.count()}")

        for dsr in overdue_dsrs:
            if verbose:
                self.stdout.write(
                    f"  - DSR {dsr.id}: Response {dsr.response.id} "
                    f"(Deadline was: {dsr.deadline})"
                )

            if not dry_run:
                # Escalate the DSR (this freezes the response with platform source)
                dsr.escalate()

                if verbose:
                    self.stdout.write(
                        self.style.WARNING(
                            "    ⚠ Response frozen by platform due to deadline breach"
                        )
                    )

                # Notify the controller
                survey = dsr.response.survey
                owner = survey.owner
                if owner and owner.email:
                    self._send_escalation_email(dsr)
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    ✓ Sent escalation notice to {owner.email}"
                            )
                        )

    def _update_survey_dsr_flags(self, dry_run: bool, verbose: bool) -> None:
        """Update survey-level DSR warning flags."""
        self.stdout.write(self.style.HTTP_INFO("\n--- Updating Survey DSR Flags ---"))

        from checktick_app.surveys.models import Survey

        # Find surveys with pending (notified but not resolved) DSRs
        surveys_with_pending = (
            DataSubjectRequest.objects.filter(
                status__in=[
                    DataSubjectRequest.Status.NOTIFIED,
                    DataSubjectRequest.Status.ESCALATED,
                ]
            )
            .values_list("response__survey_id", flat=True)
            .distinct()
        )

        # Set warning on surveys with pending DSRs
        pending_count = 0
        for survey_id in surveys_with_pending:
            try:
                survey = Survey.objects.get(id=survey_id)
                pending_dsrs = DataSubjectRequest.objects.filter(
                    response__survey=survey,
                    status__in=[
                        DataSubjectRequest.Status.NOTIFIED,
                        DataSubjectRequest.Status.ESCALATED,
                    ],
                )

                if not survey.has_pending_dsr:
                    pending_count += 1
                    if not dry_run:
                        count = pending_dsrs.count()
                        survey.set_dsr_warning(
                            f"This survey has {count} pending data subject "
                            f"request{'s' if count > 1 else ''}. Please review "
                            "and respond within the statutory deadline."
                        )
                    if verbose:
                        self.stdout.write(
                            f"  + Set DSR warning on survey '{survey.name}'"
                        )
            except Survey.DoesNotExist:
                continue

        # Clear warnings on surveys that no longer have pending DSRs
        cleared_count = 0
        surveys_to_clear = Survey.objects.filter(has_pending_dsr=True).exclude(
            id__in=surveys_with_pending
        )
        for survey in surveys_to_clear:
            cleared_count += 1
            if not dry_run:
                survey.clear_dsr_warning()
            if verbose:
                self.stdout.write(f"  - Cleared DSR warning on survey '{survey.name}'")

        self.stdout.write(
            f"\nSummary: {pending_count} warnings set, {cleared_count} warnings cleared"
        )

    def _send_reminder_email(self, dsr: DataSubjectRequest, days: int) -> None:
        """Send a reminder email to the survey owner."""
        survey = dsr.response.survey
        owner = survey.owner
        days_remaining = 30 - days

        subject = f"[Action Required] Data Subject Request Reminder - {days_remaining} days remaining"

        context = {
            "survey_name": survey.name,
            "days_elapsed": days,
            "days_remaining": days_remaining,
            "request_type": dsr.get_request_type_display(),
            "deadline": dsr.deadline,
            "dsr_id": dsr.id,
        }

        # Try to use a template, fall back to plain text
        try:
            html_message = render_to_string("emails/dsr_reminder.html", context)
        except Exception:
            html_message = None

        plain_message = f"""
Data Subject Request Reminder

Survey: {survey.name}
Request Type: {dsr.get_request_type_display()}
Days Since Notification: {days}
Days Remaining: {days_remaining}
Deadline: {dsr.deadline}

A survey respondent has submitted a data subject request that requires your attention.
You have {days_remaining} days remaining to respond before the platform may take action.

Under GDPR/UK GDPR, you must respond to data subject requests within one calendar month.

Please log in to CheckTick to review and resolve this request.
"""

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=True,
        )

    def _send_escalation_email(self, dsr: DataSubjectRequest) -> None:
        """Send an escalation notice when the platform freezes a response."""
        survey = dsr.response.survey
        owner = survey.owner

        subject = "[URGENT] Data Subject Request Deadline Exceeded - Response Frozen"

        context = {
            "survey_name": survey.name,
            "request_type": dsr.get_request_type_display(),
            "deadline": dsr.deadline,
            "dsr_id": dsr.id,
        }

        try:
            html_message = render_to_string("emails/dsr_escalation.html", context)
        except Exception:
            html_message = None

        plain_message = f"""
Data Subject Request - Deadline Exceeded

Survey: {survey.name}
Request Type: {dsr.get_request_type_display()}
Deadline: {dsr.deadline}

The statutory deadline for responding to this data subject request has passed.

As required by our Terms of Service, the affected survey response has been frozen
to protect the data subject's rights. The frozen response will be excluded from
all exports and analysis.

To resolve this matter:
1. Contact the data subject to fulfill their request
2. Document your resolution
3. Contact CheckTick support to unfreeze the response

Continued failure to respond to data subject requests may result in survey suspension.

Please contact support@checktick.com if you have questions.
"""

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=True,
        )
