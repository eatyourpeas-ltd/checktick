"""Add the long_text question type (textarea).

See docs/survey-layouts-technical.md §Long text (prerequisite PR).

long_text is a textarea version of text — same answer storage (string),
same export, but rendered as a multi-line <textarea> in the builder and
the take view. It is the prerequisite for the content_block type, which
reuses the builder's textarea component for its body_md field.

No new model, no new SurveyProgress field — just the type choice and the
builder/template/parser branches.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0064_matrix_layout"),
    ]

    operations = [
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
                    ("template_patient", "Patient details template"),
                    ("template_professional", "Professional details template"),
                ],
                max_length=50,
            ),
        ),
    ]
