"""Add grid subquestions (parent FK + grid type).

A grid question ("How good was your doctor at each of the following?")
has a stem with no answer of its own plus a set of rows sharing one
scale. Rows are real SurveyQuestion rows (usually likert) with ``parent``
pointing at the stem, so answers stay flat — keyed by row id exactly like
any other question. Submissions, partial answers, progress tracking,
branching, analytics, and CSV export therefore need no nested shape;
each row aggregates as its own series.

The stem carries the shared column scale in ``options`` and renders as
the table header; rows render inline under it and never appear as
top-level questions.

See docs/respondent-categories-implementation-plan.md for the 360°
assessment background this unblocks.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0073_respondentcategory_free_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="surveyquestion",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Grid this row belongs to (NULL for top-level questions)",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subquestions",
                to="surveys.surveyquestion",
            ),
        ),
        migrations.AlterField(
            model_name="surveyquestion",
            name="type",
            field=models.CharField(
                choices=[
                    ("text", "Free text"),
                    ("mc_single", "Multiple choice (single)"),
                    ("mc_multi", "Multiple choice (multi)"),
                    ("likert", "Likert scale"),
                    ("orderable", "Orderable list"),
                    ("yesno", "Yes/No"),
                    ("dropdown", "Dropdown"),
                    ("image", "Image choice"),
                    ("long_text", "Long text (textarea)"),
                    ("content_block", "Content block"),
                    ("template_patient", "Patient details template"),
                    ("template_professional", "Professional details template"),
                    ("grid", "Grid of sub-questions"),
                ],
                max_length=50,
            ),
        ),
    ]
