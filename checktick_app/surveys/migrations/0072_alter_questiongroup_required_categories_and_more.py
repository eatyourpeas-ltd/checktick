"""Sync help_text drift between 0071_respondent_categories and models.py.

0071 was hand-authored with longer help_texts than the model fields ended up
with (the extra detail lives in code comments above each field instead), so
Django's migration state no longer matched the models and makemigrations
--check reported pending model changes for the surveys app.

This migration records the four help_text-only AlterField operations so the
migration state matches models.py exactly. help_text is not a database-level
attribute, so these operations generate no SQL on any backend — this is a
state-only migration, safe to apply everywhere.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0071_respondent_categories"),
    ]

    operations = [
        migrations.AlterField(
            model_name="questiongroup",
            name="required_categories",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Category rules gating this section (dimension -> [allowed values]). Empty/absent = visible to all.",
            ),
        ),
        migrations.AlterField(
            model_name="respondentassignment",
            name="value",
            field=models.CharField(
                help_text="The resolved category value for this participant x dimension.",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="surveyaccesstoken",
            name="category_values",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Category values carried by this token batch (dimension -> value). Blank = no token-borne values; the dimension falls back to its next resolution source.",
            ),
        ),
        migrations.AlterField(
            model_name="surveyquestion",
            name="required_categories",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Category rules gating this question (dimension -> [allowed values]). Empty/absent = visible to all.",
            ),
        ),
    ]
