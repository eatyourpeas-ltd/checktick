from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0047_snomed_dataset_fields"),
        ("core", "0016_pricing_override"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Promotion",
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
                ("name", models.CharField(max_length=255)),
                (
                    "code",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        help_text="Optional internal code for support/finance reference",
                        max_length=64,
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                (
                    "scope_type",
                    models.CharField(
                        choices=[
                            ("platform", "Platform"),
                            ("tier", "Tier"),
                            ("account", "Account"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "target_tier",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("free", "Free"),
                            ("pro", "Professional"),
                            ("team_small", "Team Small"),
                            ("team_medium", "Team Medium"),
                            ("team_large", "Team Large"),
                            ("organization", "Organization"),
                            ("enterprise", "Enterprise"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
                (
                    "effect_type",
                    models.CharField(
                        choices=[
                            ("percent_discount", "Percent Discount"),
                            ("fixed_discount", "Fixed Discount"),
                            ("set_price", "Set Price"),
                            ("tier_override", "Tier Override"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "effect_value",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Percent or currency value depending on effect type",
                        max_digits=10,
                    ),
                ),
                (
                    "effect_tier",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("free", "Free"),
                            ("pro", "Professional"),
                            ("team_small", "Team Small"),
                            ("team_medium", "Team Medium"),
                            ("team_large", "Team Large"),
                            ("organization", "Organization"),
                            ("enterprise", "Enterprise"),
                        ],
                        default="",
                        help_text="Required for tier override effects",
                        max_length=20,
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        default=100,
                        help_text="Lower values are applied first within a scope",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, default="")),
                ("internal_notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_promotions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "target_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotions",
                        to="surveys.organization",
                    ),
                ),
                (
                    "target_team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotions",
                        to="surveys.team",
                    ),
                ),
                (
                    "target_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_promotions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["scope_type", "priority", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="promotion",
            index=models.Index(
                fields=["scope_type", "is_active"],
                name="core_promot_scope_t_adfecc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="promotion",
            index=models.Index(
                fields=["target_tier", "is_active"],
                name="core_promot_target__c6fdd4_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="promotion",
            index=models.Index(
                fields=["starts_at", "ends_at"], name="core_promot_starts__e93836_idx"
            ),
        ),
    ]
