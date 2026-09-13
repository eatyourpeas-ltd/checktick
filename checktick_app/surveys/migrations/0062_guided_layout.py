"""Add the Guided layout: Survey.Layout.GUIDED.

See docs/survey-layouts-technical.md §Guided layout.

Guided is primarily a rendering change — one question per screen with
Next/Back navigation. The runtime ordering pipeline is reused unchanged
(no new model, no new SurveyProgress field): all questions still render
in the DOM and a client-side ``guided.js`` module shows one at a time.
This keeps guided orthogonal to the selection mechanism (linear,
section_menu, rct, or a future Delphi round allocator) so the guided JS
can be reused for Delphi rounds without touching the pipeline.

This migration only alters the ``layout`` field choices to add ``guided``.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0061_randomised_layout"),
    ]

    operations = [
        migrations.AlterField(
            model_name="survey",
            name="layout",
            field=models.CharField(
                choices=[
                    ("linear", "Linear"),
                    ("section_menu", "Section menu"),
                    ("rct", "Randomised (RCT)"),
                    ("guided", "Guided"),
                ],
                default="linear",
                help_text=(
                    'High-level shape of the survey. "linear" flows sections in '
                    'authored order; "section_menu" lets the participant pick which '
                    'sections to complete; "rct" system-assigns the participant to '
                    'an arm whose group set they complete; "guided" shows one '
                    "question per screen with Next/Back navigation."
                ),
                max_length=20,
            ),
        ),
    ]
