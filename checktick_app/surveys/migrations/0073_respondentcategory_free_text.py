"""Add RespondentCategory.free_text (issue #353).

A per-dimension "free-text" flag: when set, the token-batch form renders a
text input instead of a <select> over the dimension's allowed_values, so
programmes with large rotating rosters (a deanery with hundreds of trainees
per term, rotating junior doctors) don't have to re-author allowed_values
every intake and the select never becomes unwieldy.

The value is trimmed and stored in category_values as usual — values are
strings either way, so resolution, substitution, reporting, and the
category_* CSV columns need no change. The Organise page keeps the roster
authoring UI for non-free-text dimensions; allowed_values remains the
source for section visibility rules and system assignment either way.

See docs/respondent-categories-implementation-plan.md and
docs/content-block-category-substitution-implementation-plan.md (resolved
decision 1: roster for release 1, free-text as follow-up).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0072_alter_questiongroup_required_categories_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="respondentcategory",
            name="free_text",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When set, the token-batch form accepts any typed value for "
                    "this dimension instead of a select over allowed_values. "
                    "allowed_values is still used for section visibility rules "
                    "and system assignment."
                ),
            ),
        ),
    ]
