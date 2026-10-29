"""Sync respondent-categories field state with models.py.

Two groups of state-only changes:

1. 0071 was hand-authored with longer help_texts than the model fields ended
   up with (the extra detail lives in code comments above each field
   instead), so Django's migration state no longer matched the models and
   makemigrations --check reported pending model changes for the surveys
   app (four help_text-only AlterField operations).

2. RespondentCategory.resolution_source: the choice labels are user-facing
   (they render in the Organise page select) and read as jargon
   ("Self-select question", "System assignment (RCT allocator)", "Profile
   field"), so they are relabelled in plain English ("I pick it for each
   batch of invitations", "They pick it themselves in the survey",
   "CheckTick assigns it at random", "Read from their profile"). The
   stored values (token / self_select / system / profile) are unchanged —
   they live in the DB and in the outline grammar. The help_text also
   drops the inaccurate "priority order" wording; each dimension has a
   single resolution source.

Neither help_text nor choices is a database-level attribute, so these
operations generate no SQL on any backend — this is a state-only
migration, safe to apply everywhere.
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
        # --- RespondentCategory: plain-language resolution_source labels ---
        migrations.AlterField(
            model_name="respondentcategory",
            name="resolution_source",
            field=models.CharField(
                choices=[
                    ("token", "I pick it for each batch of invitations"),
                    ("self_select", "They pick it themselves in the survey"),
                    ("system", "CheckTick assigns it at random"),
                    ("profile", "Read from their profile"),
                ],
                default="token",
                help_text=("How each respondent's category is decided."),
                max_length=20,
            ),
        ),
    ]
