"""Appraisal workflow views — the ``/appraisal/`` vertical.

Org-scoped URLs gated to organisation accounts (Organisation tier).
Every *mechanism* underneath is general (distributor role, org-key
wrap, tokens, categories); nothing here adds new permission primitives
— see docs/appraisal-implementation-plan.md §4.
"""

from __future__ import annotations

from copy import deepcopy
import logging
import secrets
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
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
    SurveyResponse,
)
from checktick_app.surveys.permissions import is_org_admin
from checktick_app.surveys.views import get_survey_key_from_session

from .models import (
    AppraisalExceptionReview,
    AppraisalRelationship,
    AppraisalReportSnapshot,
)
from .reporting import build_report_document

logger = logging.getLogger(__name__)


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
        .annotate(
            pending_exceptions=models.Count(
                "exception_reviews",
                filter=models.Q(
                    exception_reviews__status=AppraisalExceptionReview.Status.REQUESTED
                ),
            )
        )
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


def _ensure_org_master_key(org: Organization, actor) -> bool:
    """Generate the organisation master key if it does not exist yet.

    Orgs onboarded through the platform-admin flow (or self-service
    signup) have no master key until one is generated — the core survey
    views silently skip org-key wrap in that case, but the appraisal
    wizard requires it (D2). Returns True if a key was generated.
    """
    if org.encrypted_master_key:
        return False
    import os as _os

    org.encrypted_master_key = _os.urandom(32)
    org.save(update_fields=["encrypted_master_key"])
    AuditLog.objects.create(
        actor=actor,
        scope=AuditLog.Scope.ORGANIZATION,
        organization=org,
        action=AuditLog.Action.CREATE,
        severity=AuditLog.Severity.INFO,
        message="Organisation master key generated (first appraisal survey).",
        metadata={"reason": "appraisal_wizard"},
    )
    return True


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
    _ensure_org_master_key(org, appraiser)
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
        .annotate(
            pending_exceptions=models.Count(
                "exception_reviews",
                filter=models.Q(
                    exception_reviews__status=AppraisalExceptionReview.Status.REQUESTED
                ),
            )
        )
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


def _can_view_report(user, rel: AppraisalRelationship) -> bool:
    """Appraiser, appraisee, or org owner/admin can view released reports."""
    if not user.is_authenticated:
        return False
    if rel.appraiser_id == user.id or rel.appraisee_id == user.id:
        return True
    return is_org_admin(user, rel.organization) or rel.organization.owner_id == user.id


@login_required
@require_http_methods(["GET"])
def report_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Released report snapshots for an appraisal (D6).

    Appraisees see exactly what was released — the immutable snapshot —
    never the live aggregate.
    """
    rel = get_object_or_404(
        AppraisalRelationship.objects.select_related(
            "survey", "instrument", "appraisee", "appraiser", "organization"
        ),
        pk=pk,
    )
    if not _can_view_report(request.user, rel):
        raise PermissionDenied("You do not have permission to view this report.")
    snapshots = rel.snapshots.select_related("released_by").order_by("-version")
    version = request.GET.get("version")
    selected = None
    if version:
        try:
            selected = snapshots.filter(version=int(version)).first()
        except ValueError:
            selected = None
    if selected is None:
        selected = snapshots.first()
    return render(
        request,
        "appraisal/report.html",
        {
            "rel": rel,
            "snapshots": snapshots,
            "snapshot": selected,
            "doc": selected.document if selected else None,
        },
    )


@login_required
@require_http_methods(["POST"])
def report_release(request: HttpRequest, pk: int) -> HttpResponse:
    """Release a structured report snapshot (D6, §6 step 7).

    Appraiser-only (org admins may also release). The survey must be
    unlocked when responses are encrypted — the aggregates are computed
    through the same unlock-gated path as the summary view. The snapshot
    is immutable: releasing again creates a new version.
    """
    rel = get_object_or_404(
        AppraisalRelationship.objects.select_related(
            "survey", "instrument", "organization"
        ),
        pk=pk,
    )
    is_appraiser = rel.appraiser_id == request.user.id
    if not (
        is_appraiser
        or is_org_admin(request.user, rel.organization)
        or rel.organization.owner_id == request.user.id
    ):
        raise PermissionDenied("Only the appraiser can release the report.")

    survey = rel.survey
    survey_key = get_survey_key_from_session(request, survey.slug)
    has_encrypted = survey.responses.filter(enc_answers__isnull=False).exists()
    if has_encrypted and not survey_key:
        messages.error(
            request,
            "Unlock the survey before releasing the report — encrypted "
            "responses cannot be aggregated while locked.",
        )
        return redirect("appraisal:report_view", pk=rel.pk)

    total = survey.responses.count()
    if total < rel.min_responses:
        messages.error(
            request,
            f"Cannot release: {total} responses is below the minimum "
            f"threshold of {rel.min_responses} (D5).",
        )
        return redirect("appraisal:report_view", pk=rel.pk)

    document = build_report_document(rel, survey_key)
    last_version = (
        rel.snapshots.order_by("-version").values_list("version", flat=True).first()
    )
    snapshot = AppraisalReportSnapshot.objects.create(
        relationship=rel,
        version=(last_version or 0) + 1,
        released_by=request.user,
        document=document,
    )
    AuditLog.objects.create(
        actor=request.user,
        scope=AuditLog.Scope.SURVEY,
        organization=rel.organization,
        survey=survey,
        action=AuditLog.Action.CREATE,
        target_user=rel.appraisee,
        severity=AuditLog.Severity.INFO,
        message="Structured appraisal report released.",
        metadata={
            "snapshot_id": snapshot.pk,
            "version": snapshot.version,
            "total_responses": total,
        },
    )
    messages.success(request, f"Report v{snapshot.version} released to the appraisee.")
    return redirect("appraisal:report_view", pk=rel.pk)


def _is_ro(user, org: Organization) -> bool:
    """Responsible Officer: organisation owner or admin."""
    return org.owner_id == user.id or is_org_admin(user, org)


@login_required
@require_http_methods(["GET"])
def exception_reviews(request: HttpRequest, pk: int) -> HttpResponse:
    """Exception review list for an appraisal (§9).

    Appraiser and RO only — never the appraisee, whose lack of results
    access is the control (nothing to hide behind a flag).
    """
    rel = get_object_or_404(
        AppraisalRelationship.objects.select_related(
            "survey", "organization", "appraisee", "appraiser"
        ),
        pk=pk,
    )
    is_appraiser = rel.appraiser_id == request.user.id
    if not (is_appraiser or _is_ro(request.user, rel.organization)):
        raise PermissionDenied(
            "Only the appraiser and the Responsible Officer can view "
            "exception reviews."
        )
    reviews = rel.exception_reviews.select_related(
        "response", "raised_by", "decided_by"
    ).order_by("-created_at")
    # Count-only response metadata for the raise form — no answer content
    # is ever listed here (§3.1).
    responses = rel.survey.responses.order_by("-submitted_at").only(
        "id", "submitted_at", "access_token"
    )
    return render(
        request,
        "appraisal/exceptions.html",
        {
            "rel": rel,
            "reviews": reviews,
            "responses": responses,
            "is_appraiser": is_appraiser,
            "is_ro": _is_ro(request.user, rel.organization),
        },
    )


@login_required
@require_http_methods(["POST"])
def exception_review_raise(request: HttpRequest, pk: int) -> HttpResponse:
    """Appraiser raises an exception review for one response (§9)."""
    rel = get_object_or_404(
        AppraisalRelationship.objects.select_related("survey", "organization"),
        pk=pk,
    )
    if rel.appraiser_id != request.user.id:
        raise PermissionDenied("Only the appraiser can raise an exception review.")
    response = get_object_or_404(
        SurveyResponse, survey=rel.survey, pk=request.POST.get("response")
    )
    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "A reason is required to raise an exception review.")
        return redirect("appraisal:exception_reviews", pk=rel.pk)
    review = AppraisalExceptionReview.objects.create(
        relationship=rel,
        response=response,
        raised_by=request.user,
        reason=reason,
    )
    AuditLog.objects.create(
        actor=request.user,
        scope=AuditLog.Scope.SURVEY,
        organization=rel.organization,
        survey=rel.survey,
        action=AuditLog.Action.CREATE,
        severity=AuditLog.Severity.WARNING,
        message="Exception review raised (rater linkage requested).",
        metadata={
            "exception_review_id": review.pk,
            "response_id": response.pk,
            # Never the reason text or any response content — the reason
            # may quote the response (house logging rules).
        },
    )
    # Notify the Responsible Officers at distance (§9): the RO and the
    # appraiser are rarely co-located. Email every org owner/admin
    # except the raiser; the reason is deliberately not emailed.
    from checktick_app.core.email_utils import (
        send_exception_review_raised_email,
    )

    ros = (
        get_user_model()
        .objects.filter(
            models.Q(organizations=rel.organization)
            | models.Q(
                org_memberships__organization=rel.organization,
                org_memberships__role=OrganizationMembership.Role.ADMIN,
            ),
            is_active=True,
        )
        .exclude(pk=request.user.pk)
    )
    for ro in ros:
        try:
            send_exception_review_raised_email(ro, review)
        except Exception:
            logger.exception(
                "Failed to send exception review notification",
                extra={
                    "review_id": review.pk,
                    "ro_id": ro.pk,
                },
            )
    messages.success(request, "Exception review raised — awaiting RO co-signature.")
    return redirect("appraisal:exception_reviews", pk=rel.pk)


@login_required
@require_http_methods(["POST"])
def exception_review_decide(
    request: HttpRequest, pk: int, review_id: int
) -> HttpResponse:
    """RO co-signature (D10): approve or reject a raised exception review.

    The approver must be an org owner/admin and must not be the raiser —
    two-party control protects the appraiser as well as the process.
    """
    rel = get_object_or_404(
        AppraisalRelationship.objects.select_related("survey", "organization"),
        pk=pk,
    )
    review = get_object_or_404(AppraisalExceptionReview, relationship=rel, pk=review_id)
    if not _is_ro(request.user, rel.organization):
        raise PermissionDenied(
            "Only the Responsible Officer can co-sign an exception review."
        )
    if review.raised_by_id == request.user.id:
        raise PermissionDenied(
            "Two-party control: the raiser cannot co-sign their own request."
        )
    if review.status != AppraisalExceptionReview.Status.REQUESTED:
        messages.error(request, "This exception review has already been decided.")
        return redirect("appraisal:exception_reviews", pk=rel.pk)

    decision = request.POST.get("decision")
    note = (request.POST.get("decision_note") or "").strip()
    if decision == "approve":
        review.status = AppraisalExceptionReview.Status.APPROVED
        review.decided_by = request.user
        review.decided_at = timezone.now()
        review.decision_note = note
        review.save(
            update_fields=["status", "decided_by", "decided_at", "decision_note"]
        )
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.SURVEY,
            organization=rel.organization,
            survey=rel.survey,
            action=AuditLog.Action.UPDATE,
            severity=AuditLog.Severity.WARNING,
            message="Exception review approved — rater linkage disclosed.",
            metadata={"exception_review_id": review.pk},
        )
        messages.success(
            request,
            "Exception review approved. The rater linkage is now visible "
            "to the appraiser and the RO.",
        )
    elif decision == "reject":
        review.status = AppraisalExceptionReview.Status.REJECTED
        review.decided_by = request.user
        review.decided_at = timezone.now()
        review.decision_note = note
        review.save(
            update_fields=["status", "decided_by", "decided_at", "decision_note"]
        )
        AuditLog.objects.create(
            actor=request.user,
            scope=AuditLog.Scope.SURVEY,
            organization=rel.organization,
            survey=rel.survey,
            action=AuditLog.Action.UPDATE,
            severity=AuditLog.Severity.INFO,
            message="Exception review rejected.",
            metadata={"exception_review_id": review.pk},
        )
        messages.info(request, "Exception review rejected.")
    else:
        messages.error(request, "Unknown decision.")
        return redirect("appraisal:exception_reviews", pk=rel.pk)

    # Close the loop at distance: tell the appraiser the decision.
    from checktick_app.core.email_utils import (
        send_exception_review_decided_email,
    )

    try:
        send_exception_review_decided_email(review)
    except Exception:
        logger.exception(
            "Failed to send exception review decision email",
            extra={"review_id": review.pk},
        )
    return redirect("appraisal:exception_reviews", pk=rel.pk)


@login_required
@require_http_methods(["GET"])
def exception_review_linkage(
    request: HttpRequest, pk: int, review_id: int
) -> HttpResponse:
    """The disclosed rater linkage for an APPROVED exception review (§9).

    Visible to the appraiser and the RO only, and only once the RO has
    co-signed. Shows the pseudonymous linkage the data model already
    holds: the token, its category values (subject, rater role), and the
    response's submission metadata — no crypto change, permission and
    audit only.
    """
    rel = get_object_or_404(
        AppraisalRelationship.objects.select_related(
            "survey", "organization", "appraiser", "appraisee"
        ),
        pk=pk,
    )
    review = get_object_or_404(
        AppraisalExceptionReview.objects.select_related(
            "response__access_token", "raised_by", "decided_by"
        ),
        relationship=rel,
        pk=review_id,
    )
    is_appraiser = rel.appraiser_id == request.user.id
    is_ro = _is_ro(request.user, rel.organization)
    if not (is_appraiser or is_ro):
        raise PermissionDenied(
            "Only the appraiser and the Responsible Officer can view the "
            "disclosed linkage."
        )
    if review.status != AppraisalExceptionReview.Status.APPROVED:
        messages.error(
            request,
            "The rater linkage is only visible once the Responsible "
            "Officer has co-signed the exception review.",
        )
        return redirect("appraisal:exception_reviews", pk=rel.pk)

    response = review.response
    token = response.access_token
    linkage = {
        "response_id": response.pk,
        "submitted_at": response.submitted_at,
        "token": token.token if token else None,
        "category_values": (token.category_values if token else {}) or {},
        "token_note": token.note if token else "",
        "token_created_at": token.created_at if token else None,
        "token_used_at": token.used_at if token else None,
        "authenticated_user": (
            response.submitted_by.get_full_name() or response.submitted_by.username
            if response.submitted_by
            else None
        ),
    }
    return render(
        request,
        "appraisal/exception_linkage.html",
        {"rel": rel, "review": review, "linkage": linkage},
    )
