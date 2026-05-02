# Generated migration for PricingOverride model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_add_userapikey"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PricingOverride",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tier",
                    models.CharField(
                        choices=[
                            ("pro", "Individual Pro"),
                            ("team_small", "Team (Small)"),
                            ("team_medium", "Team (Medium)"),
                            ("team_large", "Team (Large)"),
                        ],
                        help_text="Subscription tier this override applies to",
                        max_length=20,
                        unique=True,
                    ),
                ),
                (
                    "amount",
                    models.IntegerField(
                        help_text="Price inclusive of VAT in pence (e.g. 600 = £6.00)"
                    ),
                ),
                (
                    "amount_ex_vat",
                    models.IntegerField(
                        help_text="Price exclusive of VAT in pence (e.g. 500 = £5.00)"
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="When inactive, falls back to the value configured in settings.py",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Pricing Override",
                "verbose_name_plural": "Pricing Overrides",
                "ordering": ["tier"],
            },
        ),
    ]
