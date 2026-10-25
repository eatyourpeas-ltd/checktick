"""Add unconfirmed-account removal warning tracking fields to UserProfile.

Adds ``unconfirmed_warning_sent_at`` and ``unconfirmed_warning_stage`` so the
``prune_unconfirmed_users`` command can send 1-week and 1-day warning emails
idempotently before deactivating or deleting unconfirmed accounts. Both
fields are cleared when the user confirms their email so warnings restart
if the account is later flagged again.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_userprofile_expiry_warning_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="unconfirmed_warning_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "When the most recent unconfirmed-account removal warning "
                    "was sent. Used for idempotency by prune_unconfirmed_users."
                ),
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="unconfirmed_warning_stage",
            field=models.CharField(
                blank=True,
                default="",
                max_length=10,
                help_text=(
                    "Most recent unconfirmed-account warning stage sent "
                    "(1week / 1day). Blank when none sent yet."
                ),
            ),
        ),
    ]
