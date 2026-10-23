"""Add respondent categories: RespondentCategory / RespondentAssignment
models, category_values on SurveyAccessToken, and required_categories on
QuestionGroup and SurveyQuestion.

See docs/respondent-categories-implementation-plan.md.

Respondent categories is a cross-cutting feature (not a layout) that lets a
survey author categorise respondents along one or more author-defined
dimensions (rater_role, site, cohort, ...) within a single published survey,
so different respondents see different subsets of the same survey without
cloning it. It generalises the per-layout FK pattern the codebase already
uses (assigned_arm for RCT, delphi_round for Delphi, access_token for token
visibility) and unblocks the 360 / multi-rater assessment pattern.

category_values on SurveyAccessToken carries the dimension values for a
token batch (e.g. {"rater_role": "peer"} for a peer-rater batch).

required_categories on QuestionGroup and SurveyQuestion gates visibility by
category dimension (e.g. {"rater_role": ["peer", "supervisor"]} = show this
section/question only to peer and supervisor raters). Empty/absent = visible
to all. The runtime hook (commit 3) filters at group level first; the
question-level field exists on the model but is not enforced by the runtime
hook in this release (see docs/respondent-categories-implementation-plan.md
Resolved decisions 4).

BigAutoField is used for the new models' id fields to match the project's
DEFAULT_AUTO_FIELD setting.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0070_intro_content_block"),
    ]

    operations = [
        # --- RespondentCategory model ---
        migrations.CreateModel(
            name="RespondentCategory",
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
                        help_text=(
                            "Dimension key, e.g. 'rater_role', 'site', 'cohort'. "
                            "Slug-like. Used as the key in required_categories "
                            "rules and category_values maps."
                        ),
                        max_length=50,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Human label for the Organise page (defaults to name)."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "allowed_values",
                    models.JSONField(
                        default=list,
                        help_text=(
                            "List of allowed values for this dimension, e.g. "
                            "['self', 'peer', 'supervisor', 'patient']. Author-"
                            "defined; there is no fixed enum."
                        ),
                    ),
                ),
                (
                    "resolution_source",
                    models.CharField(
                        choices=[
                            ("token", "Invite token"),
                            ("self_select", "Self-select question"),
                            ("system", "System assignment (RCT allocator)"),
                            ("profile", "Profile field"),
                        ],
                        default="token",
                        help_text=(
                            "How the value for this dimension is resolved for a "
                            "participant, in priority order: token > self_select "
                            "> system > profile."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "source_question",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "For self_select resolution: the question whose answer "
                            "populates this dimension."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resolved_categories",
                        to="surveys.surveyquestion",
                    ),
                ),
                (
                    "profile_field",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "For profile resolution: the UserProfile/Org field key "
                            "to read the value from."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Display order on the Organise page.",
                    ),
                ),
                (
                    "survey",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="respondent_categories",
                        to="surveys.survey",
                    ),
                ),
            ],
            options={
                "unique_together": {("survey", "name")},
                "ordering": ["order", "id"],
            },
        ),
        # --- RespondentAssignment model (after SurveyProgress + RespondentCategory) ---
        migrations.CreateModel(
            name="RespondentAssignment",
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
                    "value",
                    models.CharField(
                        help_text=(
                            "The resolved category value for this participant x "
                            "dimension. Resolved once at first access and preserved "
                            "on resume (same lifecycle as assigned_arm / delphi_round)."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="surveys.respondentcategory",
                    ),
                ),
                (
                    "progress",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="category_assignments",
                        to="surveys.surveyprogress",
                    ),
                ),
            ],
            options={
                "unique_together": {("progress", "category")},
            },
        ),
        # --- SurveyAccessToken: category_values for token batches ---
        migrations.AddField(
            model_name="surveyaccesstoken",
            name="category_values",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Category values carried by this token batch (dimension -> "
                    'value), e.g. {"rater_role": "peer"}. Blank = no token-'
                    "borne values; the dimension falls back to its next "
                    "resolution source."
                ),
            ),
        ),
        # --- QuestionGroup: required_categories (group-level visibility) ---
        migrations.AddField(
            model_name="questiongroup",
            name="required_categories",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Category rules gating this section (dimension -> [allowed "
                    'values]), e.g. {"rater_role": ["peer", "supervisor"]}. '
                    "Empty/absent = visible to all. Enforced by the runtime hook "
                    "as a static pre-step filter on _resolved_group_order_ids."
                ),
            ),
        ),
        # --- SurveyQuestion: required_categories (question-level visibility) ---
        migrations.AddField(
            model_name="surveyquestion",
            name="required_categories",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Category rules gating this question (dimension -> [allowed "
                    "values]). Empty/absent = visible to all. The field exists on "
                    "the model but is not enforced by the runtime hook in this "
                    "release; group-level filtering ships first."
                ),
            ),
        ),
    ]
