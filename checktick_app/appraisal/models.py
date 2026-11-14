"""Appraisal workflow models (GMC-style 360 appraisal).

The appraisal vertical is a thin workflow layer over general survey
primitives (see docs/appraisal-implementation-plan.md §3.2, §4):

- Responsible Officer  → organisation owner / admin (existing oversight)
- Appraiser            → survey **owner** of each appraisee's survey
- Appraisee            → DISTRIBUTOR membership on that survey
- Patient respondent   → anonymous unlisted respondent
- Colleague respondent → token holder (pseudonymous)

``AppraisalRelationship`` is the lightweight appraiser↔appraisee record
that carries the caseload and the RO portfolio. It *carries* the
distributor membership rather than replace it — the membership is what
the permission layer checks.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AppraisalRelationship(models.Model):
    """One appraiser↔appraisee pairing for one appraisal cycle.

    D9: one survey per appraisee per cycle — patient and colleague
    populations are sections of the same survey, separated by
    ``required_categories``. Enforced here by a unique constraint on
    (organization, appraisee, cycle_year).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        # Cycle closed: colleague nominations are discarded (D11),
        # leaving pseudonymous token references.
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(
        "surveys.Organization",
        on_delete=models.CASCADE,
        related_name="appraisal_relationships",
    )
    appraiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appraisals_as_appraiser",
        help_text="Survey owner of the appraisee's appraisal survey",
    )
    appraisee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appraisals_as_appraisee",
        help_text="Clinician being appraised; holds a DISTRIBUTOR membership on the survey",
    )
    survey = models.ForeignKey(
        "surveys.Survey",
        on_delete=models.CASCADE,
        related_name="appraisal_relationships",
        help_text="The appraisee's appraisal survey (created by the wizard)",
    )
    instrument = models.ForeignKey(
        "surveys.PublishedQuestionGroup",
        on_delete=models.PROTECT,
        related_name="appraisal_relationships",
        help_text="Organisation-level instrument the survey was created from",
    )
    cycle_year = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    min_responses = models.PositiveIntegerField(
        default=5,
        help_text=(
            "Minimum responses per rater population before the report can "
            "be released (D5 — anonymity protection; populations below the "
            "threshold are suppressed in the released report)"
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "appraisee", "cycle_year"],
                name="unique_appraisee_per_cycle",
            )
        ]
        ordering = ["-cycle_year", "appraisee__username"]

    def __str__(self) -> str:
        return (
            f"Appraisal {self.cycle_year}: {self.appraisee} "
            f"(appraiser {self.appraiser})"
        )


class AppraisalReportSnapshot(models.Model):
    """An immutable, structured released report (D6).

    Generated at release time from the survey as-built — counts and
    percentages per question, split by rater population, with
    below-threshold populations suppressed. Never regenerated: a
    correction means a new version linked to the old.
    """

    relationship = models.ForeignKey(
        AppraisalRelationship,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    version = models.PositiveIntegerField(default=1)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appraisal_reports_released",
    )
    document = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["relationship", "version"],
                name="unique_snapshot_version_per_relationship",
            )
        ]
        ordering = ["-version"]

    def __str__(self) -> str:
        return f"Report v{self.version} for {self.relationship}"
