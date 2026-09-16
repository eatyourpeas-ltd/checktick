"""Add Survey.closed_by_downgrade flag.

Distinguishes surveys auto-closed by a tier downgrade (via
UserProfile.force_downgrade_tier) from surveys the user closed manually.
Used by UserProfile.reopen_surveys_on_upgrade to re-open only auto-closed
surveys on re-subscription, leaving user-initiated closures untouched.

See docs/manual-tier-upgrade-expiry-plan.md.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0067_delphi_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="survey",
            name="closed_by_downgrade",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "True if this survey was auto-closed by a tier downgrade "
                    "(not by a user action). Re-opened on re-subscription."
                ),
            ),
        ),
    ]
