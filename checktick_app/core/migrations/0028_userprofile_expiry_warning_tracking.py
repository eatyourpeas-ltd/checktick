"""Add pre-expiry warning tracking fields to UserProfile.

Adds ``last_expiry_warning_sent_at`` and ``last_expiry_warning_stage`` so the
daily ``process_expiring_subscriptions`` command can send 1-month / 1-week /
1-day warning emails idempotently without re-sending within a window. Both
fields are cleared on renewal/extension so warnings restart for the new
expiry date.

See docs/manual-tier-upgrade-expiry-plan.md.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_payment_provider_payment_id_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="last_expiry_warning_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "When the most recent pre-expiry warning email was sent. "
                    "Used for idempotency by process_expiring_subscriptions."
                ),
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_expiry_warning_stage",
            field=models.CharField(
                blank=True,
                default="",
                max_length=10,
                help_text=(
                    "Most recent pre-expiry warning stage sent "
                    "(1month / 1week / 1day). Blank when none sent yet."
                ),
            ),
        ),
    ]
