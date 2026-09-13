"""Add the Matrix (free navigation) layout: Survey.Layout.MATRIX, the
MatrixMenu model, and SurveyProgress.completed_group_ids.

See docs/survey-layouts-technical.md §Matrix (free navigation) layout.

The matrix layout shows all sections as cards on a landing page. The
participant jumps in and out of any section in any order, with completion
indicators showing which sections are done. Unlike the other layouts (which
filter selected_group_ids and render a single take page), matrix has a
landing page + per-section take pages + a final submit.

SurveyProgress.completed_group_ids tracks which sections the participant has
marked complete (soft UX indicator; final submit re-validates). This is the
reusable ingredient for a future DelphiRound's within-round completion
tracking — same shape, separate field.

BigAutoField is used for the new model's id field to match the project's
DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0063_staged_layout"),
    ]

    operations = [
        # --- Survey: add matrix to layout choices ---
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
                ],
                default="linear",
                help_text=(
                    'High-level shape of the survey. "linear" flows sections in '
                    'authored order; "section_menu" lets the participant pick which '
                    'sections to complete; "rct" system-assigns the participant to '
                    'an arm whose group set they complete; "guided" shows one '
                    'question per screen with Next/Back navigation; "staged" '
                    "unlocks sections over time in defined phase windows; "
                    '"matrix" shows all sections as cards with free navigation '
                    "and completion indicators."
                ),
                max_length=20,
            ),
        ),
        # --- SurveyProgress: add completed_group_ids ---
        migrations.AddField(
            model_name="surveyprogress",
            name="completed_group_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Section IDs the participant has marked complete in a matrix "
                    "survey (soft indicator; final submit re-validates)."
                ),
            ),
        ),
        # --- MatrixMenu model ---
        migrations.CreateModel(
            name="MatrixMenu",
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
                    "prompt_text",
                    models.CharField(
                        default=(
                            "Click a section to begin. You can complete them in "
                            "any order."
                        ),
                        help_text=(
                            "Prompt shown to the participant on the matrix landing "
                            "page."
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "order_mode",
                    models.CharField(
                        choices=[
                            ("authored", "As authored"),
                            ("participant", "In visit order"),
                        ],
                        default="authored",
                        help_text=(
                            "How section cards are ordered on the landing page. "
                            "'authored' uses the Organise page order; 'participant' "
                            "orders by the order the participant first visited each "
                            "section (most-recently-visited last)."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "allow_revisit",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Allow participants to revisit and edit completed "
                            "sections before final submission. Editing a completed "
                            "section un-marks it as complete so the landing page "
                            "shows 'in progress' again."
                        ),
                    ),
                ),
                (
                    "survey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matrix_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
    ]
