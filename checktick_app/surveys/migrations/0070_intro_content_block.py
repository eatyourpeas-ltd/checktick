"""Add intro_content_block FK to SectionMenu and DiaryMenu.

Both the Section menu picker page and the Diary landing page can now
reference a content_block question to render as a landing/intro above
the layout-specific UI (welcome text, consent, privacy notice, etc.).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0069_diary_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="sectionmenu",
            name="intro_content_block",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "An optional content block rendered above the picker "
                    "page as a landing/intro (e.g. welcome text, consent, "
                    "privacy notice). Must be a content_block question "
                    "belonging to this survey."
                ),
                null=True,
                on_delete=models.SET_NULL,
                related_name="section_menu_intro",
                to="surveys.surveyquestion",
            ),
        ),
        migrations.AddField(
            model_name="diarymenu",
            name="intro_content_block",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "An optional content block rendered above the diary "
                    "landing page as a landing/intro (e.g. welcome text, "
                    "consent, privacy notice). Must be a content_block "
                    "question belonging to this survey."
                ),
                null=True,
                on_delete=models.SET_NULL,
                related_name="diary_menu_intro",
                to="surveys.surveyquestion",
            ),
        ),
    ]
