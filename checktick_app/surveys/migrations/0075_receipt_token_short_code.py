"""Widen the receipt token into a short, participant-friendly code.

Issue #376: every participant of a redaction-enabled survey is shown the
token once on the thank-you page, so it must be short and typeable (like
a 2FA code) rather than a 36-character UUID. The column becomes a plain
CharField: existing UUID values are kept as strings and keep working,
while new responses get 8-character Crockford base32 codes (see
SurveyResponse._new_receipt_token).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0074_grid_subquestions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="surveyresponse",
            name="receipt_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Receipt token for data subject requests — short code "
                    "shown once after submission"
                ),
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="datasubjectrequest",
            name="receipt_token",
            field=models.CharField(
                blank=True,
                help_text="Receipt token provided by respondent (if available)",
                max_length=64,
                null=True,
            ),
        ),
    ]
