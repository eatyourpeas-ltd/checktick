"""Add the Diary / EMA layout: Survey.Layout.DIARY, the DiaryMenu /
DiaryEntry models, and the SurveyProgress.diary_enrolled_at field.

See docs/diary-ema-implementation-plan.md §3 Data model.

The Diary layout adds high-frequency repeated-measures surveys to
CheckTick: short surveys triggered on a fixed schedule (daily, 4×/day)
or by events (symptom onset). Used for pain diaries, mood tracking,
medication adherence, and symptom monitoring in clinical trials.

SurveyProgress.diary_enrolled_at is the participant's enrolment anchor
(first access time) — used to compute window start/end times when
DiaryMenu.anchor = 'enrolment' (the default). The precedent is
``created_at`` (used by Staged/Delphi as the enrolment anchor); diary
uses a dedicated field so the enrolment time is stable.

DiaryEntry is the compliance audit trail: one row per (participant,
scheduled window) tracking the expected time, the actual submission
time, and a link to the SurveyProgress row carrying the responses.

BigAutoField is used for the new models' id field to match the project's
DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0068_survey_closed_by_downgrade"),
    ]

    operations = [
        # --- Survey: add diary to layout choices ---
        migrations.AlterField(
            model_name="survey",
            name="layout",
            field=models.CharField(
                choices=[
                    ("linear", "Linear"),
                    ("section_menu", "Section menu"),
                    ("rct", "Randomised (RCT)"),
                    ("guided", "Guided"),
                    ("staged", "Staged (longitudinal)"),
                    ("matrix", "Matrix (free navigation)"),
                    ("delphi", "Delphi (consensus rounds)"),
                    ("diary", "Diary / EMA"),
                ],
                default="linear",
                help_text=(
                    'High-level shape of the survey. "linear" flows sections in '
                    'authored order; "section_menu" lets the participant pick which '
                    'sections to complete; "rct" system-assigns the participant to '
                    'an arm whose group set they complete; "guided" shows one '
                    'question per screen with Next/Back navigation; "staged" unlocks '
                    "sections over time in defined phase windows; "
                    '"matrix" shows all sections as cards with free navigation '
                    'and completion indicators; "delphi" runs multi-round '
                    "consensus workflows where participants complete rounds, see "
                    "aggregate feedback between rounds, and revise their answers; "
                    '"diary" runs high-frequency repeated-measures surveys on a '
                    "schedule with compliance tracking."
                ),
                max_length=20,
            ),
        ),
        # --- SurveyProgress: add diary_enrolled_at ---
        migrations.AddField(
            model_name="surveyprogress",
            name="diary_enrolled_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "When the participant first accessed a diary survey. Used as "
                    "the anchor for window calculations when DiaryMenu.anchor = "
                    "'enrolment'. Null for non-diary surveys."
                ),
            ),
        ),
        # --- DiaryMenu model ---
        migrations.CreateModel(
            name="DiaryMenu",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "schedule_type",
                    models.CharField(
                        choices=[
                            ("fixed_interval", "Fixed interval (e.g. every 6 hours)"),
                            (
                                "event_triggered",
                                "Event-triggered (participant-initiated)",
                            ),
                            ("burst", "Burst (e.g. 7 days on, 7 days off)"),
                        ],
                        default="fixed_interval",
                        help_text=(
                            "How diary windows are scheduled. 'fixed_interval' opens a "
                            "window every `interval_hours` hours (e.g. every 6 hours = "
                            "4×/day). 'event_triggered' has no scheduled windows — the "
                            "participant initiates entries from the landing page. 'burst' "
                            "cycles between on-periods (daily entries) and off-periods "
                            "(no entries)."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "interval_hours",
                    models.PositiveIntegerField(
                        null=True,
                        blank=True,
                        help_text=(
                            "For fixed_interval: hours between windows (e.g. 6 = 4×/day). "
                            "For burst: hours per on-day window (default 24 = one daily "
                            "entry). Ignored for event_triggered."
                        ),
                    ),
                ),
                (
                    "burst_on_days",
                    models.PositiveIntegerField(
                        null=True,
                        blank=True,
                        help_text="For burst: number of on-days in each cycle (e.g. 7).",
                    ),
                ),
                (
                    "burst_off_days",
                    models.PositiveIntegerField(
                        null=True,
                        blank=True,
                        help_text="For burst: number of off-days in each cycle (e.g. 7).",
                    ),
                ),
                (
                    "anchor",
                    models.CharField(
                        choices=[
                            ("enrolment", "From participant enrolment"),
                            ("survey_open", "From survey open date"),
                        ],
                        default="enrolment",
                        help_text=(
                            "Reference point for window start times. 'enrolment' offsets "
                            "from the participant's first access (SurveyProgress."
                            "diary_enrolled_at); 'survey_open' offsets from Survey.start_at. "
                            "Use 'survey_open' when all participants should be on the same "
                            "calendar schedule."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "compliance_threshold_pct",
                    models.PositiveIntegerField(
                        default=80,
                        help_text=(
                            "Warn on the compliance dashboard if a participant submits "
                            "fewer than this percentage of expected entries."
                        ),
                    ),
                ),
                (
                    "grace_minutes",
                    models.PositiveIntegerField(
                        default=30,
                        help_text=(
                            "A window stays submittable for this many minutes after its "
                            "scheduled end. Prevents edge-case missed entries when the "
                            "participant is a few minutes late."
                        ),
                    ),
                ),
                (
                    "show_progress",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Show participants which window they are in and their "
                            "compliance summary on the diary landing page."
                        ),
                    ),
                ),
                (
                    "survey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="diary_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
        # --- DiaryEntry model ---
        # (after DiaryMenu and SurveyProgress so the FKs can resolve)
        migrations.CreateModel(
            name="DiaryEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Window order (0 = first window from the anchor).",
                    ),
                ),
                (
                    "expected_start",
                    models.DateTimeField(
                        help_text="When the window was scheduled to open (UTC).",
                    ),
                ),
                (
                    "expected_end",
                    models.DateTimeField(
                        help_text="When the window was scheduled to close (UTC, exclusive).",
                    ),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(
                        null=True,
                        blank=True,
                        help_text=(
                            "When the participant submitted this entry. Null if the window "
                            "closed without a submission."
                        ),
                    ),
                ),
                (
                    "is_missed",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "True if the window closed (past grace) without a submission. "
                            "Set by the runtime when the next access finds an unsent entry "
                            "past its grace period."
                        ),
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="surveys.diarymenu",
                    ),
                ),
                (
                    "progress",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="diary_entries",
                        to="surveys.surveyprogress",
                    ),
                ),
            ],
            options={
                "unique_together": {("menu", "progress", "order")},
                "ordering": ["progress", "order", "id"],
            },
        ),
    ]
