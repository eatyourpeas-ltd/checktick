"""Structured released-report builder (D6).

The report is generated from the survey **as-built** — the org's
adopted (and possibly amended) instrument — so amendments are reported
faithfully and nothing an organisation adds is dropped. Content is the
standard aggregate reporting: counts and percentages per question,
split by rater population, with below-threshold populations suppressed
(D5). Q3 resolved: no bespoke per-instrument section spec is needed.

Population attribution is deterministic:

- A response linked to an access token takes the token's
  ``rater_role`` category value (colleagues are pseudonymous token
  holders — D4).
- An anonymous response (no token) can only come from a patient:
  colleague sections carry ``required_categories: {rater_role:
  clinician}`` and are invisible without a token (§5).
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from checktick_app.surveys.models import SurveyResponse
from checktick_app.surveys.services.response_analytics import (
    compute_survey_summary,
)

from .models import AppraisalExceptionReview

# The rater-role dimension name used by the appraisal instrument
# families (docs/question-group-templates/).
RATER_ROLE_DIM = "rater_role"
PATIENT_POPULATION = "patient"
CLINICIAN_POPULATION = "clinician"


def population_for_response(response: SurveyResponse) -> str:
    """Attribute a response to a rater population.

    Token-linked responses take the token's ``rater_role`` value;
    anonymous (tokenless) responses are patients by construction —
    see the module docstring.
    """
    token = response.access_token
    if token is not None:
        role = (token.category_values or {}).get(RATER_ROLE_DIM)
        if role:
            return str(role)
    return PATIENT_POPULATION


def _summary_to_dict(summary) -> dict[str, Any]:
    """Serialise a SurveySummary into a JSON-safe document fragment."""
    distributions = []
    for dist in summary.distributions:
        distributions.append(
            {
                "question_id": dist.question_id,
                "text": dist.question_text,
                "type": dist.question_type,
                "total_responses": dist.total_responses,
                "options": [
                    {
                        "label": opt.get("label"),
                        "count": opt.get("count", 0),
                        "percent": round(opt.get("percent", 0) or 0, 1),
                    }
                    for opt in dist.options
                ],
            }
        )
    texts = [
        {
            "question_id": coll.question_id,
            "text": coll.question_text,
            "type": coll.question_type,
            "answered_count": coll.answered_count,
            "skipped_count": coll.skipped_count,
            # Verbatim comments are part of the released report (GMC
            # style); the release gate is the threshold, and the
            # per-population suppression below keeps small-number
            # populations out of the document entirely.
            "responses": list(coll.responses),
        }
        for coll in summary.text_collations
    ]
    numerics = [
        {
            "question_id": num.question_id,
            "text": num.question_text,
            "type": num.question_type,
            "count": num.count,
            "min": num.min,
            "max": num.max,
            "mean": num.mean,
            "median": num.median,
        }
        for num in summary.numeric_summaries
    ]
    return {
        "total_responses": summary.total_responses,
        "distributions": distributions,
        "texts": texts,
        "numerics": numerics,
    }


def _structure_inventory(survey) -> list[dict[str, Any]]:
    """The survey's groups and questions as-built at release time."""
    from checktick_app.surveys.models import SurveyQuestion

    structure = []
    for group in survey.question_groups.all().order_by("id"):
        questions = [
            {"id": q.id, "text": q.text, "type": q.type}
            for q in SurveyQuestion.objects.filter(survey=survey, group=group).order_by(
                "order", "id"
            )
        ]
        structure.append(
            {
                "group": group.name,
                "required_categories": group.required_categories or {},
                "questions": questions,
            }
        )
    return structure


def build_report_document(rel, survey_key: bytes | None) -> dict[str, Any]:
    """Build the report document for an appraisal relationship.

    ``survey_key`` is the unlocked KEK (org key or personal path) —
    encrypted responses are excluded from aggregates when absent,
    mirroring the summary view's unlock gate.
    """
    survey = rel.survey
    responses = survey.responses.all()

    # Population counts (count-only query path per §3.1).
    populations: dict[str, dict[str, Any]] = {}
    by_population: dict[str, list[SurveyResponse]] = {}
    for response in responses:
        pop = population_for_response(response)
        by_population.setdefault(pop, []).append(response)
    for pop, pop_responses in sorted(by_population.items()):
        populations[pop] = {
            "responses": len(pop_responses),
            "threshold_met": len(pop_responses) >= rel.min_responses,
        }
    # Ensure both canonical populations appear even when empty.
    for pop in (PATIENT_POPULATION, CLINICIAN_POPULATION):
        populations.setdefault(pop, {"responses": 0, "threshold_met": False})

    # Per-population aggregates. Below-threshold populations are
    # suppressed entirely (counts only) — anonymity protection (D5).
    sections: dict[str, Any] = {}
    for pop, info in populations.items():
        if info["threshold_met"]:
            summary = compute_survey_summary(
                survey,
                responses=responses.filter(pk__in=[r.pk for r in by_population[pop]]),
                survey_key=survey_key,
            )
            sections[pop] = _summary_to_dict(summary)
        else:
            sections[pop] = None  # suppressed

    return {
        "generated_at": timezone.now().isoformat(),
        "instrument": {
            "id": rel.instrument_id,
            "name": rel.instrument.name,
            "version": rel.instrument.version,
        },
        "cycle_year": rel.cycle_year,
        "threshold": rel.min_responses,
        "structure": _structure_inventory(survey),
        "populations": populations,
        "sections": sections,
        # §9: the released report records only that an exception review
        # occurred (existence) — never its content, which stays with the
        # appraiser/RO.
        "exception_review_count": rel.exception_reviews.filter(
            status=AppraisalExceptionReview.Status.APPROVED
        ).count(),
    }
