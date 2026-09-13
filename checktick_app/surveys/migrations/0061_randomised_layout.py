"""Add the RCT layout: Survey.Layout.RCT, RandomisedMenu/RandomisedArm
models, and the SurveyProgress.randomisation_seed / assigned_arm fields.

See docs/survey-layouts-technical.md §Randomised (RCT) layout.

The RCT layout system-assigns each participant to an arm at first access.
The arm's group set becomes the participant's selected_group_ids, so the
existing runtime hook (_resolved_group_order_ids filtering by
selected_group_ids) is reused unchanged — RCT only changes who populates
selected_group_ids, not how the pipeline consumes it.

SurveyProgress.randomisation_seed and assigned_arm are designed as the
precedent for a future Delphi delphi_round FK: arms and rounds are
orthogonal dimensions.

BigAutoField is used for the new models' id fields to match the project's
DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0060_survey_layouts"),
    ]

    operations = [
        # --- Survey: add rct to layout choices ---
        migrations.AlterField(
            model_name="survey",
            name="layout",
            field=models.CharField(
                choices=[
                    ("linear", "Linear"),
                    ("section_menu", "Section menu"),
                    ("rct", "Randomised (RCT)"),
                ],
                default="linear",
                help_text=(
                    'High-level shape of the survey. "linear" flows sections in '
                    'authored order; "section_menu" lets the participant pick which '
                    'sections to complete; "rct" system-assigns the participant to '
                    "an arm whose group set they complete."
                ),
                max_length=20,
            ),
        ),
        # --- RandomisedMenu model (must exist before RandomisedArm FK) ---
        migrations.CreateModel(
            name="RandomisedMenu",
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
                    "allocation_strategy",
                    models.CharField(
                        choices=[
                            ("balanced", "Balanced (blocked)"),
                            ("simple", "Simple (weighted)"),
                        ],
                        default="balanced",
                        help_text=(
                            "How participants are assigned to arms. 'balanced' uses "
                            "permuted blocks of size sum(ratios) so arm counts stay "
                            "close to the ratios; 'simple' is an independent weighted "
                            "draw per participant."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "seed",
                    models.BigIntegerField(
                        blank=True,
                        help_text=(
                            "Optional fixed seed for deterministic allocation across "
                            "runs (useful for dry-runs). Blank = system-generated per "
                            "participant. Leave blank for real trials to avoid "
                            "predictability."
                        ),
                        null=True,
                    ),
                ),
                (
                    "survey",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="randomised_menu",
                        to="surveys.survey",
                    ),
                ),
            ],
        ),
        # --- RandomisedArm model (must exist before SurveyProgress.assigned_arm FK) ---
        migrations.CreateModel(
            name="RandomisedArm",
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
                    "name",
                    models.CharField(
                        help_text="Arm name (e.g. 'Intervention', 'Control').",
                        max_length=100,
                    ),
                ),
                (
                    "allocation_ratio",
                    models.PositiveIntegerField(
                        default=1,
                        help_text=(
                            "Integer ratio for balanced allocation. 1:1 uses ratio 1 on "
                            "each arm; 2:1 uses ratio 2 on the larger arm."
                        ),
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text=(
                            "Display order on the Organise page and in the arm badges."
                        ),
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text=(
                            "Sections this arm sees. A group may appear in multiple "
                            "arms. Groups not in any arm are unreachable — warned on "
                            "the Organise page."
                        ),
                        related_name="arms",
                        to="surveys.questiongroup",
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="arms",
                        to="surveys.randomisedmenu",
                    ),
                ),
            ],
            options={
                "unique_together": {("menu", "name")},
                "ordering": ["order", "id"],
            },
        ),
        # --- SurveyProgress: RCT arm assignment fields (after RandomisedArm) ---
        migrations.AddField(
            model_name="surveyprogress",
            name="randomisation_seed",
            field=models.BigIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "Stable seed used for RCT arm allocation (set on first access)"
                ),
            ),
        ),
        migrations.AddField(
            model_name="surveyprogress",
            name="assigned_arm",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="progress_records",
                to="surveys.randomisedarm",
                help_text=(
                    "The RCT arm this participant was assigned to at first access. "
                    "Null for non-RCT surveys."
                ),
            ),
        ),
    ]
