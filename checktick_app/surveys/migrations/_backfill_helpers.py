"""
Helpers shared between migration 0052 (hidden_by_default + rename skip->hide)
and the tests that reproduce the migration logic.

Kept in a stable, non-migration module so tests can import the functions
without depending on a specific migration file's import path.
"""

from __future__ import annotations


def rename_skip_to_hide(apps, schema_editor):
    """Rename the stored action value 'skip' -> 'hide' on existing conditions."""
    SurveyQuestionCondition = apps.get_model("surveys", "SurveyQuestionCondition")
    SurveyQuestionCondition.objects.filter(action="skip").update(action="hide")


def reverse_rename_hide_to_skip(apps, schema_editor):
    SurveyQuestionCondition = apps.get_model("surveys", "SurveyQuestionCondition")
    SurveyQuestionCondition.objects.filter(action="hide").update(action="skip")


def backfill_hidden_by_default(apps, schema_editor):
    """
    Set hidden_by_default=True on any question that currently has an incoming
    SHOW condition. Those questions are already hidden by default today (as a
    side-effect of the SHOW condition); this makes the default explicit on the
    question itself, preserving existing behaviour.
    """
    SurveyQuestion = apps.get_model("surveys", "SurveyQuestion")
    SurveyQuestionCondition = apps.get_model("surveys", "SurveyQuestionCondition")

    show_target_ids = (
        SurveyQuestionCondition.objects.filter(action="show")
        .exclude(target_question__isnull=True)
        .values_list("target_question_id", flat=True)
        .distinct()
    )
    SurveyQuestion.objects.filter(id__in=list(show_target_ids)).update(
        hidden_by_default=True
    )


def reverse_backfill_hidden_by_default(apps, schema_editor):
    # No-op reverse: we cannot reliably know which questions were backfilled
    # vs. explicitly set, and the field defaults to False anyway. Leaving
    # backfilled questions as hidden_by_default=True on reverse is safe
    # because the SHOW conditions that justified the backfill still exist.
    pass
