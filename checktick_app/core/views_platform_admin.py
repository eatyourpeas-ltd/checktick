"""Platform admin views for superuser management of organizations."""

from decimal import Decimal
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from checktick_app.surveys.models import Organization, OrganizationMembership, Survey

logger = logging.getLogger(__name__)
User = get_user_model()


def superuser_required(view_func):
    """Decorator that requires the user to be a superuser."""
    return user_passes_test(
        lambda u: u.is_authenticated and u.is_superuser,
        login_url="login",
    )(view_func)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def platform_admin_dashboard(request: HttpRequest) -> HttpResponse:
    """Platform admin dashboard - overview of organizations and key metrics."""
    # Get organization stats
    org_stats = Organization.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        pending=Count(
            "id", filter=Q(subscription_status=Organization.SubscriptionStatus.PENDING)
        ),
    )

    # Get recent organizations
    recent_orgs = (
        Organization.objects.select_related("owner", "created_by")
        .annotate(member_count=Count("memberships"))
        .order_by("-created_at")[:5]
    )

    # Get organizations needing attention (past due, pending setup)
    attention_orgs = (
        Organization.objects.filter(
            Q(subscription_status=Organization.SubscriptionStatus.PAST_DUE)
            | Q(
                subscription_status=Organization.SubscriptionStatus.PENDING,
                created_at__lt=timezone.now() - timezone.timedelta(days=7),
            )
        )
        .select_related("owner")
        .annotate(member_count=Count("memberships"))[:10]
    )

    # Platform-wide stats
    total_users = User.objects.count()
    total_surveys = Survey.objects.count()

    context = {
        "org_stats": org_stats,
        "recent_orgs": recent_orgs,
        "attention_orgs": attention_orgs,
        "total_users": total_users,
        "total_surveys": total_surveys,
    }

    return render(request, "core/platform_admin/dashboard.html", context)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def organization_list(request: HttpRequest) -> HttpResponse:
    """List all organizations with filtering and search."""
    # Get filter params
    status_filter = request.GET.get("status", "")
    billing_filter = request.GET.get("billing", "")
    search = request.GET.get("q", "").strip()

    # Base queryset
    orgs = (
        Organization.objects.select_related("owner", "created_by")
        .annotate(
            member_count=Count("memberships"),
            survey_count=Count("survey", distinct=True),
        )
        .order_by("-created_at")
    )

    # Apply filters
    if status_filter:
        if status_filter == "active":
            orgs = orgs.filter(is_active=True)
        elif status_filter == "inactive":
            orgs = orgs.filter(is_active=False)
        elif status_filter in dict(Organization.SubscriptionStatus.choices):
            orgs = orgs.filter(subscription_status=status_filter)

    if billing_filter and billing_filter in dict(Organization.BillingType.choices):
        orgs = orgs.filter(billing_type=billing_filter)

    if search:
        orgs = orgs.filter(
            Q(name__icontains=search)
            | Q(owner__email__icontains=search)
            | Q(owner__username__icontains=search)
            | Q(billing_contact_email__icontains=search)
        )

    # Paginate
    paginator = Paginator(orgs, 25)
    page = request.GET.get("page", 1)
    orgs_page = paginator.get_page(page)

    context = {
        "orgs": orgs_page,
        "status_filter": status_filter,
        "billing_filter": billing_filter,
        "search": search,
        "billing_choices": Organization.BillingType.choices,
        "status_choices": Organization.SubscriptionStatus.choices,
    }

    return render(request, "core/platform_admin/organization_list.html", context)


@superuser_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user", rate="30/h", block=True)
def organization_create(request: HttpRequest) -> HttpResponse:
    """Create a new organization."""
    if request.method == "POST":
        # Extract form data
        name = request.POST.get("name", "").strip()
        owner_email = request.POST.get("owner_email", "").strip().lower()
        billing_type = request.POST.get(
            "billing_type", Organization.BillingType.PER_SEAT
        )
        price_per_seat = request.POST.get("price_per_seat", "").strip()
        flat_rate_price = request.POST.get("flat_rate_price", "").strip()
        max_seats = request.POST.get("max_seats", "").strip()
        billing_contact_email = request.POST.get("billing_contact_email", "").strip()
        billing_notes = request.POST.get("billing_notes", "").strip()

        # Validation
        errors = []
        if not name:
            errors.append("Organization name is required.")
        if not owner_email:
            errors.append("Owner email is required.")

        if billing_type == Organization.BillingType.PER_SEAT and not price_per_seat:
            errors.append("Price per seat is required for per-seat billing.")
        if billing_type == Organization.BillingType.FLAT_RATE and not flat_rate_price:
            errors.append("Flat rate price is required for flat-rate billing.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(
                request,
                "core/platform_admin/organization_form.html",
                {
                    "billing_choices": Organization.BillingType.choices,
                    "form_data": request.POST,
                },
            )

        # Find or create owner
        owner = User.objects.filter(email__iexact=owner_email).first()
        if not owner:
            # Create placeholder user - they'll set password via setup link
            import secrets

            owner = User.objects.create_user(
                username=owner_email,
                email=owner_email,
                password=secrets.token_urlsafe(32),  # Random password, they'll reset
            )
            owner.is_active = True  # They'll activate via setup link
            owner.save()
            logger.info(f"Created placeholder user for org owner: {owner_email}")

        # Create organization
        org = Organization.objects.create(
            name=name,
            owner=owner,
            billing_type=billing_type,
            price_per_seat=Decimal(price_per_seat) if price_per_seat else None,
            flat_rate_price=Decimal(flat_rate_price) if flat_rate_price else None,
            max_seats=int(max_seats) if max_seats else None,
            billing_contact_email=billing_contact_email or owner_email,
            billing_notes=billing_notes,
            created_by=request.user,
            subscription_status=Organization.SubscriptionStatus.PENDING,
        )

        # Create admin membership for owner
        OrganizationMembership.objects.create(
            organization=org,
            user=owner,
            role=OrganizationMembership.Role.ADMIN,
        )

        # Generate setup token
        org.generate_setup_token()

        logger.info(
            f"Organization '{name}' created by {request.user.username} for owner {owner_email}"
        )

        messages.success(
            request,
            f"Organization '{name}' created successfully. Setup link generated.",
        )
        return redirect("core:platform_admin_org_detail", org_id=org.id)

    # GET - show form
    return render(
        request,
        "core/platform_admin/organization_form.html",
        {
            "billing_choices": Organization.BillingType.choices,
        },
    )


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def organization_detail(request: HttpRequest, org_id: int) -> HttpResponse:
    """View organization details."""
    org = get_object_or_404(
        Organization.objects.select_related("owner", "created_by").annotate(
            member_count=Count("memberships"),
            survey_count=Count("survey", distinct=True),
        ),
        id=org_id,
    )

    # Get members
    members = org.memberships.select_related("user").order_by("-created_at")

    # Get surveys
    surveys = org.survey_set.select_related("owner").order_by("-created_at")[:10]

    # Get teams
    teams = org.teams.annotate(member_count=Count("memberships")).order_by(
        "-created_at"
    )

    # Build invite URL if token exists
    invite_url = None
    if org.setup_token:
        from django.urls import reverse

        invite_url = request.build_absolute_uri(
            reverse("core:org_setup", kwargs={"token": org.setup_token})
        )

    context = {
        "org": org,
        "members": members,
        "surveys": surveys,
        "teams": teams,
        "invite_url": invite_url,
    }

    return render(request, "core/platform_admin/organization_detail.html", context)


@superuser_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user", rate="30/h", block=True)
def organization_edit(request: HttpRequest, org_id: int) -> HttpResponse:
    """Edit organization details."""
    org = get_object_or_404(Organization, id=org_id)

    if request.method == "POST":
        # Update fields
        org.name = request.POST.get("name", org.name).strip()
        org.billing_type = request.POST.get("billing_type", org.billing_type)

        price_per_seat = request.POST.get("price_per_seat", "").strip()
        org.price_per_seat = Decimal(price_per_seat) if price_per_seat else None

        flat_rate_price = request.POST.get("flat_rate_price", "").strip()
        org.flat_rate_price = Decimal(flat_rate_price) if flat_rate_price else None

        max_seats = request.POST.get("max_seats", "").strip()
        org.max_seats = int(max_seats) if max_seats else None

        org.billing_contact_email = request.POST.get(
            "billing_contact_email", ""
        ).strip()
        org.billing_notes = request.POST.get("billing_notes", "").strip()
        org.subscription_status = request.POST.get(
            "subscription_status", org.subscription_status
        )
        org.is_active = request.POST.get("is_active") == "on"

        org.save()

        logger.info(f"Organization {org.id} updated by {request.user.username}")
        messages.success(request, f"Organization '{org.name}' updated successfully.")
        return redirect("core:platform_admin_org_detail", org_id=org.id)

    return render(
        request,
        "core/platform_admin/organization_form.html",
        {
            "org": org,
            "billing_choices": Organization.BillingType.choices,
            "status_choices": Organization.SubscriptionStatus.choices,
            "editing": True,
        },
    )


@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="10/h", block=True)
def organization_generate_invite(request: HttpRequest, org_id: int) -> HttpResponse:
    """Generate a new setup/invite link for an organization."""
    org = get_object_or_404(Organization, id=org_id)

    # Generate new token
    org.generate_setup_token()

    # Reset setup completed if regenerating
    if org.setup_completed_at:
        org.setup_completed_at = None
        org.subscription_status = Organization.SubscriptionStatus.PENDING
        org.save(
            update_fields=["setup_completed_at", "subscription_status", "updated_at"]
        )

    logger.info(
        f"New invite link generated for org {org.id} by {request.user.username}"
    )
    messages.success(request, "New invite link generated successfully.")

    return redirect("core:platform_admin_org_detail", org_id=org.id)


@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="20/h", block=True)
def organization_send_invite_email(request: HttpRequest, org_id: int) -> HttpResponse:
    """Send the setup invite email to the organization owner."""
    org = get_object_or_404(Organization, id=org_id)

    if not org.setup_token:
        org.generate_setup_token()

    # Build invite URL
    from django.urls import reverse

    invite_url = request.build_absolute_uri(
        reverse("core:org_setup", kwargs={"token": org.setup_token})
    )

    # Send email
    try:
        from checktick_app.core.email_utils import send_org_setup_email

        send_org_setup_email(org.owner, org, invite_url)
        logger.info(f"Setup email sent to {org.owner.email} for org {org.id}")
        messages.success(request, f"Setup email sent to {org.owner.email}.")
    except Exception as e:
        logger.error(f"Failed to send org setup email: {e}")
        messages.error(request, "Failed to send email. Please try again.")

    return redirect("core:platform_admin_org_detail", org_id=org.id)


@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="20/h", block=True)
def organization_toggle_active(request: HttpRequest, org_id: int) -> HttpResponse:
    """Toggle organization active status."""
    org = get_object_or_404(Organization, id=org_id)

    org.is_active = not org.is_active
    org.save(update_fields=["is_active", "updated_at"])

    status = "activated" if org.is_active else "deactivated"
    logger.info(f"Organization {org.id} {status} by {request.user.username}")
    messages.success(request, f"Organization '{org.name}' {status}.")

    return redirect("core:platform_admin_org_detail", org_id=org.id)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def organization_stats(request: HttpRequest) -> HttpResponse:
    """Organization statistics and analytics page."""
    # Billing breakdown
    billing_stats = {}
    for billing_type, label in Organization.BillingType.choices:
        count = Organization.objects.filter(billing_type=billing_type).count()
        billing_stats[label] = count

    # Status breakdown
    status_stats = {}
    for status, label in Organization.SubscriptionStatus.choices:
        count = Organization.objects.filter(subscription_status=status).count()
        status_stats[label] = count

    # Monthly revenue estimate (active per-seat + flat rate)
    from django.db.models import F, Sum

    per_seat_revenue = Organization.objects.filter(
        billing_type=Organization.BillingType.PER_SEAT,
        is_active=True,
        subscription_status=Organization.SubscriptionStatus.ACTIVE,
    ).annotate(member_count=Count("memberships")).aggregate(
        total=Sum(F("price_per_seat") * F("member_count"))
    )[
        "total"
    ] or Decimal(
        "0"
    )

    flat_rate_revenue = Organization.objects.filter(
        billing_type=Organization.BillingType.FLAT_RATE,
        is_active=True,
        subscription_status=Organization.SubscriptionStatus.ACTIVE,
    ).aggregate(total=Sum("flat_rate_price"))["total"] or Decimal("0")

    total_monthly_revenue = per_seat_revenue + flat_rate_revenue

    # Top organizations by members
    top_by_members = (
        Organization.objects.filter(is_active=True)
        .annotate(member_count=Count("memberships"))
        .order_by("-member_count")[:10]
    )

    # Top organizations by surveys
    top_by_surveys = (
        Organization.objects.filter(is_active=True)
        .annotate(survey_count=Count("survey"))
        .order_by("-survey_count")[:10]
    )

    context = {
        "billing_stats": billing_stats,
        "status_stats": status_stats,
        "total_monthly_revenue": total_monthly_revenue,
        "per_seat_revenue": per_seat_revenue,
        "flat_rate_revenue": flat_rate_revenue,
        "top_by_members": top_by_members,
        "top_by_surveys": top_by_surveys,
    }

    return render(request, "core/platform_admin/organization_stats.html", context)
