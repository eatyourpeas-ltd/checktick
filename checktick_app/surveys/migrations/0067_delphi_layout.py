"""Add the Delphi (consensus rounds) layout: Survey.Layout.DELPHI, the
DelphiMenu / DelphiRound / DelphiRoundFeedback models, and the
SurveyProgress.delphi_round / delphi_completed_rounds fields.

See docs/survey-layouts-technical.md §Delphi (consensus rounds) — full design.

The Delphi layout implements a structured multi-round consensus workflow.
Participants complete a series of rounds; between rounds they see aggregate
feedback from the previous round (quantitative distributions + optional
qualitative themes) and revise their answers. The author controls the
number of rounds, the section set per round, the round windows, and when
to generate inter-round feedback.

SurveyProgress.delphi_round (FK to DelphiRound) is the round the participant
is currently on — the precedent is ``assigned_arm`` (RCT). Same shape,
separate field; arms and rounds are orthogonal dimensions.

SurveyProgress.delphi_completed_rounds (JSONField, list of round IDs) tracks
which rounds the participant has completed — the precedent is
``completed_group_ids`` (Matrix). Same shape (list of IDs, soft indicator).

DelphiRoundFeedback caches the pre-computed inter-round feedback so
participant views don't re-run the aggregation or the LLM. Quantitative
stats are always cached; LLM theme markdown is only cached when the author
opts into the LLM path.

BigAutoField is used for the new models' id field to match the project's
DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0066_content_block"),
    ]

    operations = [
        # --- Survey: add delphi to layout choices ---
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
                    "aggregate feedback between rounds, and revise their answers."
                ),
                max_length=20,
            ),
        ),
        # --- DelphiMenu model ---
        migrations.CreateModel(
            name="DelphiMenu",
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
                            "Reference point for round windows. 'enrolment' offsets from "
                            "the participant's first access (SurveyProgress.created_at); "
                            "'survey_open' offsets from Survey.start_at. Use 'survey_open' "
                            "when all participants should move through rounds on the same "
                            "calendar schedule."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "min_rounds",
                    models.PositiveIntegerField(
                        default=2,
                        help_text="Minimum number of rounds before the survey can complete.",
                    ),
                ),
                (
                    "max_rounds",
                    models.PositiveIntegerField(
                        default=3,
                        help_text=(
                            "Maximum number of rounds. After the last round closes, "
                            "the survey is complete."
                        ),
                    ),
                ),
                (
                    "show_progress",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Show participants which round they are in and how many remain."
                        ),
                    ),
                ),
                (
                    "allow_revision",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Allow participants to revise their previous-round answers in "
                            "the current round. When False, previous-round questions render "
                            "blank in subsequent rounds."
                        ),
                    ),
                ),
                (
                    "survey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delphi_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
        # --- DelphiRound model ---
        migrations.CreateModel(
            name="DelphiRound",
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
                        help_text="Display order. Round 1, Round 2, etc.",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        default="Round 1",
                        help_text=(
                            "Round name (e.g. 'Round 1', 'Initial survey', "
                            "'Revision round')."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "start_offset_days",
                    models.PositiveIntegerField(
                        default=0,
                        help_text=(
                            "Days after the anchor when this round opens. 0 = opens at the "
                            "anchor time."
                        ),
                    ),
                ),
                (
                    "end_offset_days",
                    models.PositiveIntegerField(
                        null=True,
                        blank=True,
                        help_text=(
                            "Days after the anchor when this round closes (exclusive). "
                            "Blank = open-ended (never closes automatically)."
                        ),
                    ),
                ),
                (
                    "opened_at",
                    models.DateTimeField(
                        null=True,
                        blank=True,
                        help_text=(
                            "When the author manually opened this round. Overrides the "
                            "window offset. Null = use the window offset."
                        ),
                    ),
                ),
                (
                    "closed_at",
                    models.DateTimeField(
                        null=True,
                        blank=True,
                        help_text=(
                            "When the author manually closed this round. Once set, the "
                            "round is closed regardless of the window offset."
                        ),
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rounds",
                        to="surveys.delphimenu",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "Sections that are active during this round. A group may appear "
                            "in multiple rounds (e.g. a demographics section open in every "
                            "round). Groups not in any round are unreachable — warned "
                            "on the Organise page."
                        ),
                        related_name="delphi_rounds",
                        to="surveys.questiongroup",
                    ),
                ),
            ],
            options={
                "unique_together": {("menu", "order")},
                "ordering": ["order", "id"],
            },
        ),
        # --- SurveyProgress: add delphi_round FK ---
        # (after DelphiRound model is created so the FK can resolve)
        migrations.AddField(
            model_name="surveyprogress",
            name="delphi_round",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="progress_rows",
                to="surveys.delphiround",
                help_text=(
                    "The Delphi round this participant is currently on. Null for "
                    "non-Delphi surveys."
                ),
            ),
        ),
        # --- SurveyProgress: add delphi_completed_rounds ---
        migrations.AddField(
            model_name="surveyprogress",
            name="delphi_completed_rounds",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Round IDs the participant has completed in a Delphi survey "
                    "(soft indicator; round advancement gates on this)."
                ),
            ),
        ),
        # --- DelphiRoundFeedback model ---
        migrations.CreateModel(
            name="DelphiRoundFeedback",
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
                    "stats_json",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Aggregated quantitative stats "
                            "(median/IQR/distribution/etc.)."
                        ),
                    ),
                ),
                (
                    "theme_markdown",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Sanitised LLM theme summary (qualitative questions, opt-in "
                            "only). Blank when the author chose manual analysis only."
                        ),
                    ),
                ),
                (
                    "llm_generated",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "True if the LLM theme summary was generated for this question. "
                            "False if the author chose manual analysis only or the LLM failed."
                        ),
                    ),
                ),
                (
                    "generated_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "llm_model",
                    models.CharField(blank=True, max_length=100),
                ),
                (
                    "llm_token_count",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "llm_success",
                    models.BooleanField(default=False),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="surveys.surveyquestion",
                    ),
                ),
                (
                    "round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feedback",
                        to="surveys.delphiround",
                    ),
                ),
            ],
            options={
                "unique_together": {("round", "question")},
            },
        ),
    ]
