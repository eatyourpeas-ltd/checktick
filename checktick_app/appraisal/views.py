"""Appraisal workflow views — the ``/appraisal/`` vertical.

Org-scoped URLs gated to organisation accounts (Organisation tier).
Every *mechanism* underneath is general (distributor role, org-key
wrap, tokens, categories); nothing here adds new permission primitives
— see docs/appraisal-implementation-plan.md §4.
"""

from __future__ import annotations

from copy import deepcopy
import secrets
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from checktick_app.surveys.markdown_import import (
    parse_bulk_markdown_with_collections,
)
from checktick_app.surveys.models import (
    AuditLog,
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    QuestionGroup,
    RespondentCategory,
    Survey,
    SurveyMembership,
    SurveyQuestion,
)

from .models import AppraisalRelationship


def _org_role(user, org: Organization) -> str | None:
    """The user's role in the org, or None if not a member."""
    if not user.is_authenticated:
        return None
    mem = OrganizationMembership.objects.filter(user=user, organization=org).first()
    return mem.role if mem else None


def _require_org_creator(user, org: Organization) -> str | None:
    """Appraisal setup requires an org ADMIN or CREATOR (Organisation
    tier account). Returns the role, or None when denied."""
    role = _org_role(user, org)
    if role in (OrganizationMembership.Role.ADMIN, OrganizationMembership.Role.CREATOR):
        return role
    return None


def _user_orgs(user):
    """Orgs where the user is ADMIN or CREATOR (can run appraisals)."""
    return Organization.objects.filter(
        models.Q(owner=user)
        | models.Q(
            memberships__user=user,
            memberships__role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.CREATOR,
            ],
        )
    ).distinct()


def _unique_slug(base: str) -> str:
    slug = slugify(base) or f"appraisal-{secrets.token_hex(4)}"
    if not Survey.objects.filter(slug=slug).exists():
        return slug
    i = 2
    while Survey.objects.filter(slug=f"{slug}-{i}").exists():
        i += 1
    return f"{slug}-{i}"


def _build_survey_from_instrument(*, survey: Survey, markdown: str, owner) -> None:
    """Populate an empty survey from an instrument's markdown.

    Mirrors the bulk-upload import path (groups, questions, grid rows,
    CATEGORIES blocks with ``~ cat:`` rules) but works on an existing
    survey object so the caller controls creation and encryption.
    """
    parsed: dict[str, Any] = parse_bulk_markdown_with_collections(markdown)

    next_order = 0
    created_groups: list[QuestionGroup] = []
    group_ref_map: dict[str, QuestionGroup] = {}
    question_ref_map: dict[str, SurveyQuestion] = {}

    for g in parsed["groups"]:
        grp = QuestionGroup.objects.create(
            name=g["name"],
            description=g.get("description", ""),
            owner=owner,
        )
        survey.question_groups.add(grp)
        created_groups.append(grp)
        if g.get("ref"):
            group_ref_map[g["ref"]] = grp
        for q in g["questions"]:
            question = SurveyQuestion.objects.create(
                survey=survey,
                group=grp,
                text=q["title"],
                type=q["final_type"],
                options=q["final_options"],
                required=q.get("required", False),
                hidden_by_default=q.get("hidden_by_default", False),
                order=next_order,
            )
            next_order += 1
            if q.get("ref"):
                question_ref_map[q["ref"]] = question
            if q["final_type"] == "grid":
                grid_scale = ((q.get("final_options") or {}).get("scale")) or {}
                for row in q.get("grid_rows", []):
                    SurveyQuestion.objects.create(
                        survey=survey,
                        group=grp,
                        parent=question,
                        text=row["title"],
                        type="likert",
                        options=[deepcopy(grid_scale)],
                        required=bool(row.get("required", False)),
                        order=next_order,
                    )
                    next_order += 1

    # CATEGORIES blocks: create dimensions and apply ``~ cat:`` rules to
    # the groups (same contract as the bulk-upload import).
    categories_cfg = parsed.get("categories")
    categories_group_rules = parsed.get("categories_group_rules", {})
    if categories_cfg and categories_cfg.get("dimensions"):
        for i, dim in enumerate(categories_cfg["dimensions"]):
            cat = RespondentCategory.objects.create(
                survey=survey,
                name=dim["name"],
                label=dim.get("label", ""),
                allowed_values=dim.get("allowed_values", []),
                free_text=bool(dim.get("free_text", False)),
                resolution_source=dim.get(
                    "resolution_source",
                    RespondentCategory.ResolutionSource.TOKEN,
                ),
                profile_field=dim.get("profile_field", ""),
                order=i + 1,
            )
            sq_ref = dim.get("source_question")
            if sq_ref:
                sq = question_ref_map.get(sq_ref)
                if sq is not None:
                    cat.source_question = sq
                    cat.save(update_fields=["source_question"])
        for grp in created_groups:
            rules_list = categories_group_rules.get(grp.name, [])
            if rules_list:
                rules: dict[str, list[str]] = {}
                for dim_name, val in rules_list:
                    rules.setdefault(dim_name, []).append(val)
                grp.required_categories = rules
                grp.save(update_fields=["required_categories"])


@login_required
@require_http_methods(["GET", "POST"])
def caseload(request: HttpRequest) -> HttpResponse:
    """The appraiser's caseload: their appraisees and appraisal status."""
    orgs = _user_orgs(request.user)
    relationships = (
        AppraisalRelationship.objects.filter(
            appraiser=request.user, organization__in=orgs
        )
        .select_related("appraisee", "survey", "instrument", "organization")
        .order_by("-cycle_year")
    )
    # Count-only response figures: no response content, no demographics
    # (§3.1 — completion counts come from a count-only query path).
    for rel in relationships:
        rel.response_count = rel.survey.responses.count() if rel.survey else 0
    return render(
        request,
        "appraisal/caseload.html",
        {"relationships": relationships},
    )


@login_required
@require_http_methods(["GET", "POST"])
def relationship_create(request: HttpRequest) -> HttpResponse:
    """Creation wizard (§6 step 2): create an appraisee's appraisal survey
    from the organisation instrument — subject stamped in, org-key wrapped
    (D2), appraisee added as distributor."""
    orgs = _user_orgs(request.user)
    if not orgs.exists():
        messages.error(
            request,
            "Appraisals are an organisation feature. Ask your organisation "
            "admin to add you as a creator or admin.",
        )
        return redirect("appraisal:caseload")

    org_id = request.POST.get("organization") or request.GET.get("organization")
    org = None
    if org_id:
        try:
            org = orgs.get(pk=org_id)
        except Organization.DoesNotExist:
            org = None
    if org is None:
        org = orgs.first()

    if _require_org_creator(request.user, org) is None:
        messages.error(request, "You do not have permission to create appraisals.")
        return redirect("appraisal:caseload")

    # Org-level instruments only — the RO adopts them from the library
    # (§7.2). Global templates are imported into surveys, not adopted.
    instruments = PublishedQuestionGroup.objects.filter(
        organization=org,
        status=PublishedQuestionGroup.Status.ACTIVE,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
    )
    org_members = (
        OrganizationMembership.objects.filter(
            organization=org,
            role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.CREATOR,
                OrganizationMembership.Role.VIEWER,
            ],
        )
        .select_related("user")
        .order_by("user__username")
    )

    if request.method == "POST":
        appraisee_id = request.POST.get("appraisee")
        instrument_id = request.POST.get("instrument")
        try:
            cycle_year = int(request.POST.get("cycle_year") or timezone.now().year)
        except ValueError:
            cycle_year = timezone.now().year

        appraisee_mem = (
            org_members.filter(user__pk=appraisee_id).first() if appraisee_id else None
        )
        instrument = (
            instruments.filter(pk=instrument_id).first() if instrument_id else None
        )
        if appraisee_mem is None:
            messages.error(request, "Choose an appraisee from the organisation.")
        elif instrument is None:
            messages.error(
                request,
                "Choose an organisation instrument. The Responsible Officer "
                "can adopt one from the Question Bank library.",
            )
        elif AppraisalRelationship.objects.filter(
            organization=org, appraisee=appraisee_mem.user, cycle_year=cycle_year
        ).exists():
            messages.error(
                request,
                f"{appraisee_mem.user} already has an appraisal for {cycle_year} "
                "(one survey per appraisee per cycle).",
            )
        else:
            rel = _create_appraisal(
                org=org,
                appraiser=request.user,
                appraisee=appraisee_mem.user,
                instrument=instrument,
                cycle_year=cycle_year,
            )
            messages.success(
                request,
                f"Appraisal survey created for {appraisee_mem.user}.",
            )
            return redirect("surveys:dashboard", slug=rel.survey.slug)

    return render(
        request,
        "appraisal/relationship_create.html",
        {
            "org": org,
            "orgs": orgs,
            "instruments": instruments,
            "org_members": org_members,
            "current_year": timezone.now().year,
        },
    )


def _create_appraisal(
    *, org: Organization, appraiser, appraisee, instrument, cycle_year: int
) -> AppraisalRelationship:
    """Create the appraisal survey + relationship atomically-ish.

    D1: the survey is owned by the appraiser. D2: the KEK is wrapped
    with the org master key — the appraisee (distributor) holds no key
    path. Subject is stamped in as the ``subject`` category dimension
    (§5) for report headers and content-block substitution.
    """
    subject = appraisee.get_full_name() or appraisee.username
    survey = Survey.objects.create(
        owner=appraiser,
        organization=org,
        name=f"Appraisal {cycle_year}: {subject}",
        slug=_unique_slug(f"appraisal-{cycle_year}-{appraisee.username}"),
        description=(
            f"GMC-style 360 appraisal feedback for {subject} "
            f"({cycle_year}), from the {instrument.name} instrument."
        ),
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.UNLISTED,
        respondent_audience=Survey.RespondentAudience.PATIENT,
        audience_confirmed=True,
    )

    # Submission keypair + org-key wrap (D2). The appraiser's personal
    # unlock may be added later as a convenience path; the org key is
    # the recovery and oversight path.
    survey_kek = survey.setup_submission_keypair()
    survey.save()
    survey.set_org_encryption(survey_kek, org)

    _build_survey_from_instrument(
        survey=survey, markdown=instrument.markdown, owner=appraiser
    )

    # Stamp the subject dimension (§5): a free-text ``subject``
    # category whose value is the appraisee's name, used by token
    # batches and content-block substitution.
    if not survey.respondent_categories.filter(name="subject").exists():
        next_order = (
            survey.respondent_categories.aggregate(m=models.Max("order"))["m"] or 0
        ) + 1
        RespondentCategory.objects.create(
            survey=survey,
            name="subject",
            label="Subject",
            allowed_values=[],
            free_text=True,
            order=next_order,
        )

    # The appraisee distributes: tokens, QR codes, completion counts —
    # never results (D1).
    SurveyMembership.objects.update_or_create(
        survey=survey,
        user=appraisee,
        defaults={"role": SurveyMembership.Role.DISTRIBUTOR},
    )

    rel = AppraisalRelationship.objects.create(
        organization=org,
        appraiser=appraiser,
        appraisee=appraisee,
        survey=survey,
        instrument=instrument,
        cycle_year=cycle_year,
    )
    AuditLog.objects.create(
        actor=appraiser,
        scope=AuditLog.Scope.SURVEY,
        organization=org,
        survey=survey,
        action=AuditLog.Action.CREATE,
        target_user=appraisee,
        severity=AuditLog.Severity.INFO,
        message="Appraisal survey created from organisation instrument.",
        metadata={
            "appraisal_relationship_id": rel.pk,
            "cycle_year": cycle_year,
            "instrument_id": instrument.pk,
        },
    )
    return rel


@login_required
@require_http_methods(["GET", "POST"])
def portfolio(request: HttpRequest) -> HttpResponse:
    """RO portfolio oversight (§6 step 8): every appraisal in the
    organisation — status, response counts vs threshold, release state."""
    orgs = Organization.objects.filter(
        models.Q(owner=request.user)
        | models.Q(
            memberships__user=request.user,
            memberships__role=OrganizationMembership.Role.ADMIN,
        )
    ).distinct()
    if not orgs.exists():
        messages.error(
            request,
            "The portfolio is available to organisation owners and admins.",
        )
        return redirect("appraisal:caseload")

    org_id = request.POST.get("organization") or request.GET.get("organization")
    org = None
    if org_id:
        try:
            org = orgs.get(pk=org_id)
        except Organization.DoesNotExist:
            org = None
    if org is None:
        org = orgs.first()

    relationships = (
        AppraisalRelationship.objects.filter(organization=org)
        .select_related("appraisee", "appraiser", "survey", "instrument")
        .order_by("-cycle_year")
    )
    for rel in relationships:
        rel.response_count = rel.survey.responses.count() if rel.survey else 0
    return render(
        request,
        "appraisal/portfolio.html",
        {"org": org, "orgs": orgs, "relationships": relationships},
    )


@login_required
@require_http_methods(["GET", "POST"])
def adopt_instrument(request: HttpRequest) -> HttpResponse:
    """'Adopt as organisation instrument' (§7.2).

    Offered on global library templates to org admins / ROs. Creates an
    org-level ``PublishedQuestionGroup`` directly from the template's
    markdown — no intermediate survey, so the ``imported_from``
    copyright guard is never engaged. Attribution is carried forward.
    """
    orgs = Organization.objects.filter(
        models.Q(owner=request.user)
        | models.Q(
            memberships__user=request.user,
            memberships__role=OrganizationMembership.Role.ADMIN,
        )
    ).distinct()
    if not orgs.exists():
        messages.error(
            request,
            "Adopting instruments requires an organisation admin account.",
        )
        return redirect("surveys:published_templates_list")

    org_id = request.POST.get("organization") or request.GET.get("organization")
    org = None
    if org_id:
        try:
            org = orgs.get(pk=org_id)
        except Organization.DoesNotExist:
            org = None
    if org is None:
        org = orgs.first()

    library = PublishedQuestionGroup.objects.filter(
        status=PublishedQuestionGroup.Status.ACTIVE,
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
    ).order_by("name")

    if request.method == "POST":
        template = library.filter(pk=request.POST.get("template")).first()
        if template is None:
            messages.error(request, "Choose a template from the library.")
        else:
            publication = PublishedQuestionGroup.objects.create(
                publisher=request.user,
                organization=org,
                publication_level=(
                    PublishedQuestionGroup.PublicationLevel.ORGANIZATION
                ),
                name=template.name,
                description=template.description,
                markdown=template.markdown,
                attribution=template.attribution,
                show_publisher_credit=template.show_publisher_credit,
                tags=template.tags,
                language=template.language,
                version=template.version,
                status=PublishedQuestionGroup.Status.ACTIVE,
            )
            AuditLog.objects.create(
                actor=request.user,
                scope=AuditLog.Scope.ORGANIZATION,
                organization=org,
                action=AuditLog.Action.CREATE,
                severity=AuditLog.Severity.INFO,
                message="Instrument adopted from the Question Bank library.",
                metadata={
                    "publication_id": publication.pk,
                    "source_template_id": template.pk,
                },
            )
            messages.success(
                request,
                f"'{template.name}' adopted as an organisation instrument.",
            )
            return redirect("appraisal:relationship_create")

    return render(
        request,
        "appraisal/adopt_instrument.html",
        {"org": org, "orgs": orgs, "library": library},
    )
