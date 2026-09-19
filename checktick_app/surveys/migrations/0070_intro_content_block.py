"""Add intro_content JSONField to SectionMenu and DiaryMenu.

Both the Section menu picker page and the Diary landing page can now
hold an optional landing/intro content block (heading, subtitle, body
markdown, links) stored directly on the menu model. This is edited
inline on the Organise page config card — no separate question needed.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0069_diary_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="sectionmenu",
            name="intro_content",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text=(
                    "Optional landing/intro content block rendered above "
                    "the picker page. Stored as a dict with keys: heading, "
                    "subtitle, body_md (Markdown), links (list of "
                    "{label, url})."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="diarymenu",
            name="intro_content",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text=(
                    "Optional landing/intro content block rendered above "
                    "the diary landing page. Stored as a dict with keys: "
                    "heading, subtitle, body_md (Markdown), links (list of "
                    "{label, url})."
                ),
                null=True,
            ),
        ),
    ]
