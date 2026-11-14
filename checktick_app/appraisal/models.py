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
