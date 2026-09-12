"""Add Survey.layout field (see docs/survey-layouts.md step 2).

Adds a single field to ``Survey``:\n- layout (char, choices linear/section_menu, default linear)

This is a no-op behaviour change: the default ``linear`` matches today's\nrendering. The ``section_menu`` layout is implemented in later steps\n(picker page, selection filter, configuration card).\n\nThe prerequisite fields (``Survey.allow_resume``,\n``Survey.allow_response_redaction``, ``SurveyProgress.selected_group_ids``\netc.) were added in migration 0059 (v0.12.0, PR #319) and are NOT\nre-added here.\n
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0059_progress_resume_and_redaction_fields"),
    ]

    operations = [
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
    ]
