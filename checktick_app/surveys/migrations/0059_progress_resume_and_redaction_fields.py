"""Add resume/redaction fields to SurveyProgress and Survey.

Adds the following SurveyProgress fields (see docs/survey-progress-tracking.md):
- resume_token (UUID, unique, nullable) — bearer token for resuming public
  surveys. Authenticated and token surveys resume via their existing
  credential (user FK / access_token FK) and do not need this field.
- status (in_progress / completed / abandoned) — explicit lifecycle.
- current_repeat_index — resume position inside a repeat instance.
- selected_group_ids — section menu selection (for the planned section_menu
  layout; empty list for linear surveys).
- completed_at — when the participant submitted (status=COMPLETED).

Adds the following Survey fields (see docs/survey-layouts.md):
- allow_resume (bool, default True) — creators can disable for surveys with
  a fresh-state requirement.
- allow_response_redaction (bool, default True) — controls whether public-
  survey participants are offered an opt-out token after submission.

The resume_token field is unique with a callable default (uuid.uuid4). To
add it to existing rows we add it nullable first, backfill unique UUIDs,
then add the unique constraint — the standard Django pattern for unique
callable defaults.
"""

import uuid

from django.db import migrations, models


def backfill_resume_tokens(apps, schema_editor):
    """Generate unique UUIDs for existing SurveyProgress rows."""
    SurveyProgress = apps.get_model("surveys", "SurveyProgress")
    for progress in SurveyProgress.objects.filter(resume_token__isnull=True):
        progress.resume_token = uuid.uuid4()
        progress.save(update_fields=["resume_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0058_alter_dataset_category"),
    ]

    operations = [
        # --- SurveyProgress: add resume_token nullable, no unique yet ---
        migrations.AddField(
            model_name="surveyprogress",
            name="resume_token",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Bearer token for resuming a public survey (opt-in only)",
                null=True,
            ),
        ),
        # Backfill unique UUIDs for existing rows
        migrations.RunPython(
            backfill_resume_tokens,
            migrations.RunPython.noop,
        ),
        # Now add the unique constraint
        migrations.AlterField(
            model_name="surveyprogress",
            name="resume_token",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Bearer token for resuming a public survey (opt-in only)",
                null=True,
                unique=True,
            ),
        ),
        # --- SurveyProgress: add status ---
        migrations.AddField(
            model_name="surveyprogress",
            name="status",
            field=models.CharField(
                choices=[
                    ("in_progress", "In progress"),
                    ("completed", "Completed"),
                    ("abandoned", "Abandoned"),
                ],
                default="in_progress",
                help_text="Lifecycle state of this progress record",
                max_length=20,
            ),
        ),
        # --- SurveyProgress: add current_repeat_index ---
        migrations.AddField(
            model_name="surveyprogress",
            name="current_repeat_index",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Index of the repeat instance the participant was on",
                null=True,
            ),
        ),
        # --- SurveyProgress: add selected_group_ids ---
        migrations.AddField(
            model_name="surveyprogress",
            name="selected_group_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Section IDs the participant selected in a section_menu survey",
            ),
        ),
        # --- SurveyProgress: add completed_at ---
        migrations.AddField(
            model_name="surveyprogress",
            name="completed_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the participant submitted the survey (status=COMPLETED)",
                null=True,
            ),
        ),
        # --- Survey: add allow_resume ---
        migrations.AddField(
            model_name="survey",
            name="allow_resume",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Allow participants to save progress and resume later. "
                    "Disable for surveys with a fresh-state requirement."
                ),
            ),
        ),
        # --- Survey: add allow_response_redaction ---
        migrations.AddField(
            model_name="survey",
            name="allow_response_redaction",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Offer public-survey participants an opt-out token after "
                    "submission so they can request deletion later. "
                    "Authenticated/token surveys already issue a receipt_token "
                    "where pseudonymous."
                ),
            ),
        ),
    ]
