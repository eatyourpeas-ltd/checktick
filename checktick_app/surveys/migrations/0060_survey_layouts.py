"""Add Survey.layout field + SectionMenu/SectionMenuItem models.

This is the single migration for the survey layouts feature (see
docs/survey-layouts.md). It combines what was previously three
migrations into one:

1. Survey.layout field (choices: linear/section_menu, default linear)
2. SectionMenu model (OneToOne with Survey): picker-level settings
3. SectionMenuItem model (per-QuestionGroup): mandatory/pickable, order,
   estimated_minutes

The prerequisite fields (Survey.allow_resume,
Survey.allow_response_redaction, SurveyProgress.selected_group_ids
etc.) were added in migration 0059 (v0.12.0, PR #319) and are NOT
re-added here.

BigAutoField is used for the SectionMenu and SectionMenuItem id fields
to match the project's DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0059_progress_resume_and_redaction_fields"),
    ]

    operations = [
        # --- Survey: add layout field ---
        migrations.AddField(
            model_name="survey",
            name="layout",
            field=models.CharField(
                choices=[
                    ("linear", "Linear"),
                    ("section_menu", "Section menu"),
                ],
                default="linear",
                help_text=(
                    'High-level shape of the survey. "linear" flows sections in '
                    'authored order; "section_menu" lets the participant pick which '
                    "sections to complete."
                ),
                max_length=20,
            ),
        ),
        # --- SectionMenu model ---
        migrations.CreateModel(
            name="SectionMenu",
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
                        default="Which sections would you like to complete?",
                        help_text="Prompt shown to the participant on the picker page.",
                        max_length=255,
                    ),
                ),
                (
                    "min_selected",
                    models.PositiveIntegerField(
                        default=1,
                        help_text=(
                            "Minimum number of pickable sections the participant must select. "
                            "May be 0 only if at least one section is mandatory."
                        ),
                    ),
                ),
                (
                    "max_selected",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Maximum number of pickable sections (blank = no cap).",
                        null=True,
                    ),
                ),
                (
                    "order_mode",
                    models.CharField(
                        choices=[
                            ("authored", "As authored"),
                            ("participant", "In pick order"),
                        ],
                        default="authored",
                        help_text=(
                            "How chosen sections are ordered after selection. 'authored' "
                            "uses the Organise page order; 'participant' uses the order the "
                            "participant ticked the boxes."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "show_select_all",
                    models.BooleanField(
                        default=False,
                        help_text='Show a "Select all" button on the picker page.',
                    ),
                ),
                (
                    "show_estimated_time",
                    models.BooleanField(
                        default=False,
                        help_text="Show per-section estimated time on the picker page.",
                    ),
                ),
                (
                    "survey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="section_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
        # --- SectionMenuItem model ---
        migrations.CreateModel(
            name="SectionMenuItem",
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
                    "is_pickable",
                    models.BooleanField(
                        default=True,
                        help_text="False = mandatory (always included, cannot be deselected).",
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Display order on the picker (matches Organise page order).",
                    ),
                ),
                (
                    "estimated_minutes",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text=(
                            "Optional estimated completion time (shown when "
                            "show_estimated_time is on)."
                        ),
                        null=True,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="surveys.questiongroup",
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="surveys.sectionmenu",
                    ),
                ),
            ],
            options={
                "unique_together": {("menu", "group")},
                "ordering": ["order", "id"],
            },
        ),
    ]
