"""Add the content_block question type.

See docs/survey-layouts-technical.md §Content blocks.

content_block is a SurveyQuestion type that renders static content
(heading, Markdown body, image, hyperlinks) with no answer input. It
goes anywhere a question goes: any group, any position, any layout.
A content block placed first in the first section is a landing page;
one between sections is an interstitial disclosure; one placed last
is a closing acknowledgement.

The ``options`` JSONField holds:
    {
        "body_md": str,           # Markdown body (multiline)
        "links": [{"label": str, "url": str}, ...],
        "image_id": int | None,   # FK to QuestionImage (builder-only)
        "variant": str,           # "text" | "text_image" | "consent_info" | ...
        "render_once": bool,      # default True; render once even in repeatable groups
    }

No new model, no new SurveyProgress field — just the type choice and
the builder/template/parser branches. ``required`` is always False
(enforced in ``SurveyQuestion.clean()``).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0065_long_text"),
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
                    ("content_block", "Content block"),
                    ("template_patient", "Patient details template"),
                    ("template_professional", "Professional details template"),
                ],
                max_length=50,
            ),
        ),
    ]
