"""Add the Staged (longitudinal) layout: Survey.Layout.STAGED plus the
StagedMenu / StagedPhase models.

See docs/survey-layouts-technical.md §Staged (longitudinal) layout.

The staged layout unlocks sections over time in defined phase windows
(baseline now, follow-up in 2 weeks, 6-month review later). Each phase has
integer-day offsets from an anchor (participant enrolment or survey open).
At runtime the take view recomputes the currently-open phases on each
access and resolves selected_group_ids from their union, reusing the same
hook (_resolved_group_order_ids filtering by selected_group_ids) as
section_menu and rct.

No new SurveyProgress field is needed: unlike rct (fixed arm assignment),
staged recomputes the open set each access. StagedPhase is the precedent
for a future DelphiRound model.

BigAutoField is used for the new models' id fields to match the project's
DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0062_guided_layout"),
    ]

    operations = [
        # --- Survey: add staged to layout choices ---
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
                ],
                default="linear",
                help_text=(
                    'High-level shape of the survey. "linear" flows sections in '
                    'authored order; "section_menu" lets the participant pick which '
                    'sections to complete; "rct" system-assigns the participant to '
                    'an arm whose group set they complete; "guided" shows one '
                    'question per screen with Next/Back navigation; "staged" '
                    "unlocks sections over time in defined phase windows."
                ),
                max_length=20,
            ),
        ),
        # --- StagedMenu model (must exist before StagedPhase FK) ---
        migrations.CreateModel(
            name="StagedMenu",
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
                    "anchor",
                    models.CharField(
                        choices=[
                            ("enrolment", "From participant enrolment"),
                            ("survey_open", "From survey open date"),
                        ],
                        default="enrolment",
                        help_text=(
                            "Reference point for phase windows. 'enrolment' offsets "
                            "from the participant's first access "
                            "(SurveyProgress.created_at); 'survey_open' offsets from "
                            "Survey.start_at. Use 'survey_open' when all participants "
                            "should move through phases on the same calendar schedule."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "survey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staged_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
        # --- StagedPhase model ---
        migrations.CreateModel(
            name="StagedPhase",
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
                    "name",
                    models.CharField(
                        help_text="Phase name (e.g. 'Baseline', 'Follow-up').",
                        max_length=100,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text=(
                            "Display order on the Organise page and in the phase "
                            "badges."
                        ),
                    ),
                ),
                (
                    "start_offset_days",
                    models.PositiveIntegerField(
                        default=0,
                        help_text=(
                            "Days after the anchor when this phase opens. 0 = opens "
                            "at the anchor time."
                        ),
                    ),
                ),
                (
                    "end_offset_days",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text=(
                            "Days after the anchor when this phase closes (exclusive). "
                            "Blank = open-ended (never closes)."
                        ),
                        null=True,
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "Sections that unlock during this phase. A group may "
                            "appear in multiple phases (e.g. a demographics section "
                            "open in every phase). Groups not in any phase are "
                            "unreachable — warned on the Organise page."
                        ),
                        related_name="phases",
                        to="surveys.questiongroup",
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phases",
                        to="surveys.stagedmenu",
                    ),
                ),
            ],
            options={
                "unique_together": {("menu", "name")},
                "ordering": ["order", "id"],
            },
        ),
    ]
