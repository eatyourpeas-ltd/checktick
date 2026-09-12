"""Add SectionMenu and SectionMenuItem models (docs/survey-layouts.md step 4).

These hold the per-survey configuration for the section_menu layout:
- SectionMenu: OneToOne with Survey, picker-level settings (prompt, min/max,\n  order mode, convenience toggles).\n- SectionMenuItem: per-QuestionGroup row (mandatory vs pickable, order,\n  estimated_minutes).\n\nRows are only created for surveys with layout = section_menu. A linear\nsurvey has no rows and renders exactly as it does today.\n
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0060_survey_layout_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="SectionMenu",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                        on_delete=models.deletion.CASCADE,
                        related_name="section_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SectionMenuItem",
            fields=[
                (
                    "id",
                    models.AutoField(
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
                        on_delete=models.deletion.CASCADE,
                        to="surveys.questiongroup",
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
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
