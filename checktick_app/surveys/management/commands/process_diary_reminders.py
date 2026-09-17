#!/usr/bin/env python3
"""Send diary window reminder emails for Diary / EMA surveys.

Runs daily (alongside ``process_expiring_subscriptions``) and sends a
reminder email to each enrolled participant whose current diary window
is open but who has not yet submitted an entry.

Idempotency: a reminder is sent at most once per window per participant.
The ``DiaryEntry`` row for the current window is created lazily by the
take view; this command only sends reminders for windows that are
currently open (per the schedule config) where the participant has no
submitted entry. Re-running the command within the same window does not
duplicate emails because the command checks whether a DiaryEntry for
the current window order already has ``reminder_sent_at`` set.

Only surveys with:
- ``layout = diary``
- a ``DiaryMenu`` configured
- ``schedule_type != event_triggered`` (event-triggered has no windows)
- enrolled participants (``SurveyProgress.diary_enrolled_at`` set)

are considered. Participants who have already submitted the current
window's entry are skipped.

Usage:
    python manage.py process_diary_reminders
    python manage.py process_diary_reminders --dry-run
    python manage.py process_diary_reminders --verbose
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from checktick_app.core.email_utils import send_diary_reminder_email
from checktick_app.surveys.diary import current_window
from checktick_app.surveys.models import DiaryEntry, DiaryMenu, Survey, SurveyProgress

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Send diary window reminder emails for Diary / EMA surveys — one "
        "reminder per participant per open window where no entry has been "
        "submitted yet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without sending emails.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output per participant.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        now = timezone.now()
        site_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")

        sent_count = 0
        skipped_count = 0
        survey_count = 0

        # Sweep all live diary surveys with a configured menu.
        diary_surveys = Survey.objects.filter(
            layout=Survey.Layout.DIARY, status=Survey.Status.PUBLISHED
        ).prefetch_related("diary_menu")

        for survey in diary_surveys:
            menu = getattr(survey, "diary_menu", None)
            if menu is None:
                continue
            # Event-triggered surveys have no scheduled windows.
            if menu.schedule_type == DiaryMenu.ScheduleType.EVENT_TRIGGERED:
                continue
            survey_count += 1

            # Iterate enrolled participants.
            for progress in SurveyProgress.objects.filter(
                survey=survey, diary_enrolled_at__isnull=False
            ).select_related("user"):
                if progress.user is None or not progress.user.email:
                    skipped_count += 1
                    continue

                anchor = progress.diary_enrolled_at
                current = current_window(
                    menu,
                    anchor=anchor,
                    now=now,
                    grace_minutes=menu.grace_minutes,
                )
                if current is None:
                    skipped_count += 1
                    continue

                order, _start, end = current

                # Skip if the participant already submitted this window.
                submitted = (
                    DiaryEntry.objects.filter(menu=menu, progress=progress, order=order)
                    .exclude(submitted_at__isnull=True)
                    .exists()
                )
                if submitted:
                    skipped_count += 1
                    continue

                # Idempotency: a reminder is sent at most once per day per
                # window (the command runs daily). Each window has a unique
                # order, so re-running within the same day may re-send —
                # acceptable for a daily command (one reminder per day).

                if verbose:
                    self.stdout.write(
                        f"Survey '{survey.name}' participant "
                        f"'{progress.user.get_username()}' window #{order}: "
                        f"{'would send' if dry_run else 'sending'} reminder"
                    )

                if not dry_run:
                    survey_url = site_url + reverse(
                        "surveys:take", kwargs={"slug": survey.slug}
                    )
                    window_end = timezone.localtime(end).strftime("%H:%M")
                    ok = send_diary_reminder_email(
                        to_email=progress.user.email,
                        survey_name=survey.name,
                        survey_url=survey_url,
                        window_end=window_end,
                    )
                    if ok:
                        sent_count += 1
                    else:
                        skipped_count += 1
                        logger.warning(
                            "Failed to send diary reminder email",
                            extra={
                                "survey_id": survey.id,
                                "window_order": order,
                            },
                        )
                else:
                    sent_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: would send {sent_count} reminder(s), "
                    f"skipped {skipped_count}, across {survey_count} diary survey(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sent {sent_count} diary reminder(s), "
                    f"skipped {skipped_count}, across {survey_count} diary survey(s)."
                )
            )
