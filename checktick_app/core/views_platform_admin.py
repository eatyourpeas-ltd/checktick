"""Platform admin views for superuser management of organizations."""

from decimal import Decimal, InvalidOperation
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from checktick_app.core.models import Promotion, UserProfile
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    Team,
)

logger = logging.getLogger(__name__)
User = get_user_model()

PLATFORM_ADMIN_SCOPE_CHOICES = [
    ("all", "All"),
    ("free", "Free"),
    ("pro", "Pro"),
    ("team_small", "Team Small"),
    ("team_medium", "Team Medium"),
    ("team_large", "Team Large"),
    ("organization", "Organisation"),
    ("enterprise", "Enterprise"),
]
PLATFORM_ADMIN_SCOPE_VALUES = {value for value, _label in PLATFORM_ADMIN_SCOPE_CHOICES}
TIER_SCOPE_CHOICES = [
    ("free", "Free"),
    ("pro", "Pro"),
    ("team_small", "Team Small"),
    ("team_medium", "Team Medium"),
    ("team_large", "Team Large"),
    ("organization", "Organisation"),
    ("enterprise", "Enterprise"),
]
TIER_SCOPE_VALUES = {value for value, _label in TIER_SCOPE_CHOICES}


def _get_platform_mode(request: HttpRequest) -> str:
    mode = request.GET.get("mode", "").strip().lower()
    if mode in {"platform", "tier"}:
        request.session["platform_admin_mode"] = mode
        return mode

    stored_mode = request.session.get("platform_admin_mode", "platform")
    if stored_mode not in {"platform", "tier"}:
        return "platform"
    return stored_mode


def _get_platform_scope(request: HttpRequest) -> str:
    scope = request.GET.get("scope", "all").strip().lower()
    if scope not in PLATFORM_ADMIN_SCOPE_VALUES:
        return "all"
    return scope


def _get_tier_scope(request: HttpRequest) -> str:
    scope = request.GET.get("scope", "").strip().lower()
    if scope in TIER_SCOPE_VALUES:
        request.session["platform_admin_tier_scope"] = scope
        return scope

    stored_scope = request.session.get("platform_admin_tier_scope", "pro")
    if stored_scope not in TIER_SCOPE_VALUES:
        return "pro"
    return stored_scope


def _generate_unique_username_from_email(email: str) -> str:
    base = email.split("@", 1)[0] or "user"
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def _render_organization_form(
    request: HttpRequest,
    *,
    editing: bool = False,
    org: Organization | None = None,
    form_data=None,
) -> HttpResponse:
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"
    create_target = (
        "account"
        if not editing and mode == "tier" and scope != "organization"
        else "organization"
    )

    context = {
        "mode": mode,
        "scope": scope,
        "create_target": create_target,
        "selected_scope_label": dict(TIER_SCOPE_CHOICES).get(scope, scope),
        "billing_choices": Organization.BillingType.choices,
    }
    if editing:
        context.update(
            {
                "org": org,
                "status_choices": Organization.SubscriptionStatus.choices,
                "editing": True,
            }
        )
    if form_data is not None:
        context["form_data"] = form_data
    return render(request, "core/platform_admin/organization_form.html", context)


def _parse_decimal_field(value: str, label: str, errors: list[str]) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        errors.append(f"{label} must be a valid number.")
        return None


def _parse_max_seats(value: str, errors: list[str]) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        errors.append("Maximum seats must be a whole number.")
        return None
    if parsed < 1:
        errors.append("Maximum seats must be at least 1.")
        return None
    return parsed


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
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"

    org_base = Organization.objects.all()
    if mode == "tier" and scope != "organization":
        org_base = org_base.none()

    # Get organization stats
    org_stats = org_base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        pending=Count(
            "id", filter=Q(subscription_status=Organization.SubscriptionStatus.PENDING)
        ),
    )

    # Get recent organizations
    recent_orgs = (
        org_base.select_related("owner", "created_by")
        .annotate(member_count=Count("memberships"))
        .order_by("-created_at")[:5]
    )

    # Get organizations needing attention (past due, pending setup)
    attention_orgs = (
        org_base.filter(
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
    users_qs = User.objects.all()
    surveys_qs = Survey.objects.all()
    if mode == "tier" and scope != "organization":
        users_qs = users_qs.filter(profile__account_tier=scope)
        surveys_qs = surveys_qs.filter(owner__profile__account_tier=scope)

    total_users = users_qs.count()
    total_surveys = surveys_qs.count()

    # Pending setup summary across all tiers, used by quick actions and dashboard table.
    pending_setup_rows = []
    for tier_value, tier_label in TIER_SCOPE_CHOICES:
        if tier_value == "organization":
            pending_count = Organization.objects.filter(
                subscription_status=Organization.SubscriptionStatus.PENDING,
            ).count()
            pending_link = (
                f"{reverse('core:platform_admin_org_list')}"
                "?mode=platform&status=pending"
            )
        else:
            pending_count = User.objects.filter(
                profile__account_tier=tier_value,
                profile__subscription_status=UserProfile.SubscriptionStatus.INCOMPLETE,
            ).count()
            pending_link = (
                f"{reverse('core:platform_admin_org_list')}"
                f"?mode=tier&scope={tier_value}&status=incomplete"
            )

        pending_setup_rows.append(
            {
                "tier": tier_value,
                "label": tier_label,
                "count": pending_count,
                "link": pending_link,
            }
        )

    total_pending_setups = sum(row["count"] for row in pending_setup_rows)

    context = {
        "mode": mode,
        "scope": scope,
        "org_stats": org_stats,
        "recent_orgs": recent_orgs,
        "attention_orgs": attention_orgs,
        "total_users": total_users,
        "total_surveys": total_surveys,
        "tier_scope_choices": TIER_SCOPE_CHOICES,
        "pending_setup_rows": pending_setup_rows,
        "total_pending_setups": total_pending_setups,
    }

    return render(request, "core/platform_admin/dashboard.html", context)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def organization_list(request: HttpRequest) -> HttpResponse:
    """List platform accounts, scoped by mode and tier."""
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"

    # Get filter params
    status_filter = request.GET.get("status", "")
    billing_filter = request.GET.get("billing", "")
    search = request.GET.get("q", "").strip()

    if mode == "tier" and scope != "organization":
        users = User.objects.select_related("profile").annotate(
            survey_count=Count("surveys", distinct=True),
            payment_count=Count("payments", distinct=True),
        )
        users = users.filter(profile__account_tier=scope).order_by("-date_joined")

        if status_filter:
            if status_filter == "active":
                users = users.filter(is_active=True)
            elif status_filter == "inactive":
                users = users.filter(is_active=False)
            else:
                users = users.filter(profile__subscription_status=status_filter)

        if search:
            users = users.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        paginator = Paginator(users, 25)
        page = request.GET.get("page", 1)
        users_page = paginator.get_page(page)

        context = {
            "mode": mode,
            "scope": scope,
            "is_tier_user_view": True,
            "users": users_page,
            "status_filter": status_filter,
            "search": search,
        }
        return render(request, "core/platform_admin/organization_list.html", context)

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
        "mode": mode,
        "scope": scope,
        "is_tier_user_view": False,
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
    """Create a new organization or tier-scoped account."""
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"
    create_tier_account = mode == "tier" and scope != "organization"

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        owner_email = request.POST.get("owner_email", "").strip().lower()

        if create_tier_account:
            errors = []
            if not owner_email:
                errors.append("Account email is required.")

            if errors:
                for error in errors:
                    messages.error(request, error)
                return _render_organization_form(request, form_data=request.POST)

            account = User.objects.filter(email__iexact=owner_email).first()
            created = False
            if not account:
                import secrets

                username = _generate_unique_username_from_email(owner_email)
                account = User.objects.create_user(
                    username=username,
                    email=owner_email,
                    password=secrets.token_urlsafe(32),
                )
                account.is_active = True
                if name:
                    name_parts = name.split(maxsplit=1)
                    account.first_name = name_parts[0]
                    if len(name_parts) > 1:
                        account.last_name = name_parts[1]
                account.save()
                created = True

            profile = UserProfile.get_or_create_for_user(account)
            profile.account_tier = scope
            profile.subscription_status = (
                UserProfile.SubscriptionStatus.NONE
                if scope == UserProfile.AccountTier.FREE
                else UserProfile.SubscriptionStatus.ACTIVE
            )
            profile.tier_changed_at = timezone.now()
            profile.save(
                update_fields=[
                    "account_tier",
                    "subscription_status",
                    "tier_changed_at",
                    "updated_at",
                ]
            )

            if created:
                messages.success(
                    request,
                    f"Account '{account.email}' created in {dict(TIER_SCOPE_CHOICES).get(scope, scope)} tier.",
                )
            else:
                messages.success(
                    request,
                    f"Account '{account.email}' updated to {dict(TIER_SCOPE_CHOICES).get(scope, scope)} tier.",
                )

            return redirect(
                f"{reverse('core:platform_admin_org_list')}?mode=tier&scope={scope}"
            )

        # Extract organization form data
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
        valid_billing_types = {
            choice for choice, _label in Organization.BillingType.choices
        }

        if not name:
            errors.append("Organization name is required.")
        if not owner_email:
            errors.append("Owner email is required.")
        if billing_type not in valid_billing_types:
            errors.append("Invalid billing type selected.")

        if billing_type == Organization.BillingType.PER_SEAT and not price_per_seat:
            errors.append("Price per seat is required for per-seat billing.")
        if billing_type == Organization.BillingType.FLAT_RATE and not flat_rate_price:
            errors.append("Flat rate price is required for flat-rate billing.")

        parsed_price_per_seat = _parse_decimal_field(
            price_per_seat,
            "Price per seat",
            errors,
        )
        parsed_flat_rate_price = _parse_decimal_field(
            flat_rate_price,
            "Flat rate price",
            errors,
        )
        parsed_max_seats = _parse_max_seats(max_seats, errors)

        if errors:
            for error in errors:
                messages.error(request, error)
            return _render_organization_form(request, form_data=request.POST)

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
            price_per_seat=parsed_price_per_seat,
            flat_rate_price=parsed_flat_rate_price,
            max_seats=parsed_max_seats,
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
    return _render_organization_form(request)


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
        name = request.POST.get("name", org.name).strip()
        billing_type = request.POST.get("billing_type", org.billing_type)
        price_per_seat = request.POST.get("price_per_seat", "").strip()
        flat_rate_price = request.POST.get("flat_rate_price", "").strip()
        max_seats = request.POST.get("max_seats", "").strip()
        billing_contact_email = request.POST.get("billing_contact_email", "").strip()
        billing_notes = request.POST.get("billing_notes", "").strip()
        subscription_status = request.POST.get(
            "subscription_status", org.subscription_status
        )
        is_active = request.POST.get("is_active") == "on"

        errors = []
        valid_billing_types = {
            choice for choice, _label in Organization.BillingType.choices
        }
        valid_subscription_statuses = {
            choice for choice, _label in Organization.SubscriptionStatus.choices
        }

        if not name:
            errors.append("Organization name is required.")
        if billing_type not in valid_billing_types:
            errors.append("Invalid billing type selected.")
        if subscription_status not in valid_subscription_statuses:
            errors.append("Invalid subscription status selected.")
        if billing_type == Organization.BillingType.PER_SEAT and not price_per_seat:
            errors.append("Price per seat is required for per-seat billing.")
        if billing_type == Organization.BillingType.FLAT_RATE and not flat_rate_price:
            errors.append("Flat rate price is required for flat-rate billing.")

        parsed_price_per_seat = _parse_decimal_field(
            price_per_seat,
            "Price per seat",
            errors,
        )
        parsed_flat_rate_price = _parse_decimal_field(
            flat_rate_price,
            "Flat rate price",
            errors,
        )
        parsed_max_seats = _parse_max_seats(max_seats, errors)

        if errors:
            for error in errors:
                messages.error(request, error)
            return _render_organization_form(request, editing=True, org=org)

        # Update fields
        org.name = name
        org.billing_type = billing_type
        org.price_per_seat = parsed_price_per_seat
        org.flat_rate_price = parsed_flat_rate_price
        org.max_seats = parsed_max_seats
        org.billing_contact_email = billing_contact_email
        org.billing_notes = billing_notes
        org.subscription_status = subscription_status
        org.is_active = is_active

        org.save()

        logger.info(f"Organization {org.id} updated by {request.user.username}")
        messages.success(request, f"Organization '{org.name}' updated successfully.")
        return redirect("core:platform_admin_org_detail", org_id=org.id)

    return _render_organization_form(request, editing=True, org=org)


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
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"

    if mode == "tier" and scope != "organization":
        users_base = User.objects.select_related("profile").filter(
            profile__account_tier=scope
        )

        status_stats = {
            label: users_base.filter(profile__subscription_status=status).count()
            for status, label in Organization.SubscriptionStatus.choices
        }
        status_stats["Active Users"] = users_base.filter(is_active=True).count()
        status_stats["Inactive Users"] = users_base.filter(is_active=False).count()

        top_by_surveys = users_base.annotate(survey_count=Count("surveys")).order_by(
            "-survey_count", "username"
        )[:10]
        top_by_payments = users_base.annotate(payment_count=Count("payments")).order_by(
            "-payment_count", "username"
        )[:10]

        context = {
            "mode": mode,
            "scope": scope,
            "is_tier_user_stats": True,
            "total_accounts": users_base.count(),
            "active_accounts": users_base.filter(is_active=True).count(),
            "paid_accounts": users_base.exclude(
                profile__subscription_status="free"
            ).count(),
            "survey_total": Survey.objects.filter(owner__in=users_base).count(),
            "status_stats": status_stats,
            "top_by_surveys": top_by_surveys,
            "top_by_payments": top_by_payments,
        }
        return render(request, "core/platform_admin/organization_stats.html", context)

    org_base = Organization.objects.all()
    if mode == "tier" and scope != "organization":
        org_base = org_base.none()

    # Billing breakdown
    billing_stats = {}
    for billing_type, label in Organization.BillingType.choices:
        count = org_base.filter(billing_type=billing_type).count()
        billing_stats[label] = count

    # Status breakdown
    status_stats = {}
    for status, label in Organization.SubscriptionStatus.choices:
        count = org_base.filter(subscription_status=status).count()
        status_stats[label] = count

    # Monthly revenue estimate (active per-seat + flat rate)
    from django.db.models import F, Sum

    per_seat_revenue = org_base.filter(
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

    flat_rate_revenue = org_base.filter(
        billing_type=Organization.BillingType.FLAT_RATE,
        is_active=True,
        subscription_status=Organization.SubscriptionStatus.ACTIVE,
    ).aggregate(total=Sum("flat_rate_price"))["total"] or Decimal("0")

    total_monthly_revenue = per_seat_revenue + flat_rate_revenue

    # Top organizations by members
    top_by_members = (
        org_base.filter(is_active=True)
        .annotate(member_count=Count("memberships"))
        .order_by("-member_count")[:10]
    )

    # Top organizations by surveys
    top_by_surveys = (
        org_base.filter(is_active=True)
        .annotate(survey_count=Count("survey"))
        .order_by("-survey_count")[:10]
    )

    context = {
        "mode": mode,
        "scope": scope,
        "is_tier_user_stats": False,
        "billing_stats": billing_stats,
        "status_stats": status_stats,
        "total_monthly_revenue": total_monthly_revenue,
        "per_seat_revenue": per_seat_revenue,
        "flat_rate_revenue": flat_rate_revenue,
        "top_by_members": top_by_members,
        "top_by_surveys": top_by_surveys,
    }

    return render(request, "core/platform_admin/organization_stats.html", context)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def platform_logs(request: HttpRequest) -> HttpResponse:
    """
    Platform logs dashboard for security auditing.

    Displays:
    - Application audit logs from the AuditLog model
    - Infrastructure logs from hosting provider (if configured)

    This view supports DPST compliance by providing quarterly log review
    capability for the CTO and DPO.
    """
    from django.core.paginator import Paginator

    from checktick_app.core.services.hosting import get_hosting_logs_service
    from checktick_app.surveys.models import AuditLog

    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"

    # Get filter parameters
    log_source = request.GET.get("source", "application")  # application, infrastructure
    severity_filter = request.GET.get("severity", "")
    action_filter = request.GET.get("action", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")
    search_query = request.GET.get("q", "").strip()
    page_number = request.GET.get("page", 1)

    context = {
        "mode": mode,
        "scope": scope,
        "log_source": log_source,
        "severity_filter": severity_filter,
        "action_filter": action_filter,
        "date_from": date_from,
        "date_to": date_to,
        "search_query": search_query,
        "severity_choices": AuditLog.Severity.choices,
        "action_choices": AuditLog.Action.choices,
    }

    if log_source == "infrastructure":
        # Fetch infrastructure logs from hosting provider API
        hosting_service = get_hosting_logs_service()
        context["hosting_available"] = hosting_service.is_available
        if mode == "tier":
            messages.info(
                request,
                "Infrastructure logs are not tier-scoped in this view and remain platform-wide.",
            )

        if hosting_service.is_available:
            # Parse date filters
            since = None
            until = None
            if date_from:
                try:
                    since = timezone.datetime.strptime(date_from, "%Y-%m-%d")
                    since = timezone.make_aware(since)
                except ValueError:
                    pass
            if date_to:
                try:
                    until = timezone.datetime.strptime(date_to, "%Y-%m-%d")
                    until = timezone.make_aware(until)
                    # Include the full day
                    until = until + timezone.timedelta(days=1)
                except ValueError:
                    pass

            logs, error = hosting_service.fetch_logs(
                since=since,
                until=until,
                limit=200,
                log_type=severity_filter or "all",
            )
            context["hosting_logs"] = logs
            context["hosting_error"] = error
        else:
            context["hosting_logs"] = []
            context["hosting_error"] = (
                "Hosting logs API not configured. Set HOSTING_API_TOKEN, "
                "HOSTING_PROJECT_ID, and HOSTING_SERVICE_ID environment variables."
            )
    else:
        # Fetch application audit logs from database
        logs_qs = AuditLog.objects.select_related(
            "actor", "target_user", "organization", "survey"
        ).order_by("-created_at")
        scope_filter = None

        if mode == "tier":
            scope_filter = (
                Q(actor__profile__account_tier=scope)
                | Q(target_user__profile__account_tier=scope)
                | Q(organization__owner__profile__account_tier=scope)
            )
            logs_qs = logs_qs.filter(scope_filter)

        # Apply filters
        if severity_filter:
            logs_qs = logs_qs.filter(severity=severity_filter)

        if action_filter:
            logs_qs = logs_qs.filter(action=action_filter)

        if date_from:
            try:
                from_date = timezone.datetime.strptime(date_from, "%Y-%m-%d")
                from_date = timezone.make_aware(from_date)
                logs_qs = logs_qs.filter(created_at__gte=from_date)
            except ValueError:
                pass

        if date_to:
            try:
                to_date = timezone.datetime.strptime(date_to, "%Y-%m-%d")
                to_date = timezone.make_aware(to_date)
                # Include the full day
                to_date = to_date + timezone.timedelta(days=1)
                logs_qs = logs_qs.filter(created_at__lt=to_date)
            except ValueError:
                pass

        if search_query:
            logs_qs = logs_qs.filter(
                Q(message__icontains=search_query)
                | Q(actor__username__icontains=search_query)
                | Q(actor__email__icontains=search_query)
                | Q(ip_address__icontains=search_query)
                | Q(username_attempted__icontains=search_query)
            )

        # Pagination
        paginator = Paginator(logs_qs, 50)  # 50 logs per page
        page_obj = paginator.get_page(page_number)

        context["logs"] = page_obj
        context["total_logs"] = paginator.count

        # Summary stats for dashboard
        stats_qs = AuditLog.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        )
        if scope_filter is not None:
            stats_qs = stats_qs.filter(scope_filter)

        context["log_stats"] = {
            "total_24h": stats_qs.count(),
            "critical_24h": stats_qs.filter(
                severity=AuditLog.Severity.CRITICAL,
            ).count(),
            "warnings_24h": stats_qs.filter(
                severity=AuditLog.Severity.WARNING,
            ).count(),
            "auth_failures_24h": stats_qs.filter(
                action=AuditLog.Action.LOGIN_FAILED,
            ).count(),
        }

    # Check hosting logs availability for the tab display
    hosting_service = get_hosting_logs_service()
    context["hosting_configured"] = hosting_service.is_available

    return render(request, "core/platform_admin/logs.html", context)


@superuser_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user", rate="30/h", block=True)
def pricing_overrides(request: HttpRequest) -> HttpResponse:
    """Manage per-tier pricing overrides.

    GET  – show current effective prices and any active overrides.
    POST – save updated prices for one or more tiers, or deactivate overrides.
    """
    from django.conf import settings

    from checktick_app.core.models import PricingOverride

    if _get_platform_mode(request) == "tier":
        messages.info(
            request,
            "Pricing overrides are a platform-level control. Switched to Platform mode.",
        )
        return redirect("core:platform_admin_pricing")

    if request.method == "POST":
        for tier, _label in PricingOverride.OVERRIDABLE_TIERS:
            amount_str = request.POST.get(f"{tier}_amount", "").strip()
            amount_ex_vat_str = request.POST.get(f"{tier}_amount_ex_vat", "").strip()
            is_active = request.POST.get(f"{tier}_active") == "on"

            if not amount_str or not amount_ex_vat_str:
                # No value submitted for this tier – deactivate any existing override
                PricingOverride.objects.filter(tier=tier).update(is_active=False)
                continue

            try:
                # Accept either pound (e.g. "6.00") or pence (e.g. "600") input
                amount_raw = float(amount_str)
                amount_ex_vat_raw = float(amount_ex_vat_str)
                # If value looks like pounds (< 1000) convert to pence
                amount = int(amount_raw * 100) if amount_raw < 1000 else int(amount_raw)
                amount_ex_vat = (
                    int(amount_ex_vat_raw * 100)
                    if amount_ex_vat_raw < 1000
                    else int(amount_ex_vat_raw)
                )
            except ValueError:
                messages.error(request, f"Invalid price value for {tier}.")
                continue

            PricingOverride.objects.update_or_create(
                tier=tier,
                defaults={
                    "amount": amount,
                    "amount_ex_vat": amount_ex_vat,
                    "is_active": is_active,
                    "updated_by": request.user,
                },
            )

        logger.info(f"Pricing overrides updated by {request.user.username}")
        messages.success(request, "Pricing overrides saved.")
        return redirect("core:platform_admin_pricing")

    # Build display data: settings defaults alongside any active override
    effective_tiers = PricingOverride.get_effective_tiers()
    overrides_by_tier = {o.tier: o for o in PricingOverride.objects.all()}

    tier_rows = []
    for tier, label in PricingOverride.OVERRIDABLE_TIERS:
        settings_cfg = settings.SUBSCRIPTION_TIERS.get(tier, {})
        effective_cfg = effective_tiers.get(tier, {})
        override = overrides_by_tier.get(tier)
        tier_rows.append(
            {
                "key": tier,
                "label": label,
                "settings_amount": settings_cfg.get("amount", 0),
                "settings_amount_ex_vat": settings_cfg.get("amount_ex_vat", 0),
                "effective_amount": effective_cfg.get("amount", 0),
                "effective_amount_ex_vat": effective_cfg.get("amount_ex_vat", 0),
                "override": override,
                "has_active_override": override is not None and override.is_active,
            }
        )

    def _p(pence: int) -> str:
        return f"{pence / 100:.2f}"

    # Add pre-formatted pound strings so the template doesn't need arithmetic
    for row in tier_rows:
        row["settings_amount_pounds"] = _p(row["settings_amount"])
        row["settings_amount_ex_vat_pounds"] = _p(row["settings_amount_ex_vat"])
        row["effective_amount_pounds"] = _p(row["effective_amount"])
        row["effective_amount_ex_vat_pounds"] = _p(row["effective_amount_ex_vat"])
        if row["override"]:
            row["override_amount_pounds"] = _p(row["override"].amount)
            row["override_amount_ex_vat_pounds"] = _p(row["override"].amount_ex_vat)
        else:
            row["override_amount_pounds"] = ""
            row["override_amount_ex_vat_pounds"] = ""

    context = {"tier_rows": tier_rows}
    return render(request, "core/platform_admin/pricing_overrides.html", context)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def platform_admin_billing(request: HttpRequest) -> HttpResponse:
    """Platform billing view with scope and transaction filters."""
    from checktick_app.core.models import Payment

    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"
    status_filter = request.GET.get("status", "").strip()
    date_from = request.GET.get("from", "").strip()
    date_to = request.GET.get("to", "").strip()
    search_query = request.GET.get("q", "").strip()

    payments_qs = Payment.objects.select_related("user").order_by(
        "-invoice_date", "-created_at"
    )

    if mode == "tier":
        payments_qs = payments_qs.filter(tier=scope)

    valid_statuses = {value for value, _label in Payment.PaymentStatus.choices}
    if status_filter in valid_statuses:
        payments_qs = payments_qs.filter(status=status_filter)

    if date_from:
        try:
            from_date = timezone.datetime.strptime(date_from, "%Y-%m-%d").date()
            payments_qs = payments_qs.filter(invoice_date__gte=from_date)
        except ValueError:
            messages.warning(request, "Invalid 'from' date ignored.")

    if date_to:
        try:
            to_date = timezone.datetime.strptime(date_to, "%Y-%m-%d").date()
            payments_qs = payments_qs.filter(invoice_date__lte=to_date)
        except ValueError:
            messages.warning(request, "Invalid 'to' date ignored.")

    if search_query:
        payments_qs = payments_qs.filter(
            Q(invoice_number__icontains=search_query)
            | Q(customer_email__icontains=search_query)
            | Q(customer_name__icontains=search_query)
            | Q(payment_id__icontains=search_query)
            | Q(subscription_id__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    aggregates = payments_qs.aggregate(
        total_ex_vat=Sum("amount_ex_vat"),
        total_vat=Sum("vat_amount"),
        total_inc_vat=Sum("amount_inc_vat"),
        total_refunded=Sum(
            "amount_inc_vat", filter=Q(status=Payment.PaymentStatus.REFUNDED)
        ),
        tx_count=Count("id"),
    )

    paginator = Paginator(payments_qs, 50)
    page = request.GET.get("page", 1)
    payments_page = paginator.get_page(page)

    context = {
        "mode": mode,
        "scope": scope,
        "scope_choices": TIER_SCOPE_CHOICES,
        "status_filter": status_filter,
        "status_choices": Payment.PaymentStatus.choices,
        "date_from": date_from,
        "date_to": date_to,
        "search_query": search_query,
        "payments": payments_page,
        "totals": {
            "ex_vat": (aggregates.get("total_ex_vat") or 0) / 100,
            "vat": (aggregates.get("total_vat") or 0) / 100,
            "inc_vat": (aggregates.get("total_inc_vat") or 0) / 100,
            "refunded": (aggregates.get("total_refunded") or 0) / 100,
            "tx_count": aggregates.get("tx_count") or 0,
        },
    }

    return render(request, "core/platform_admin/billing.html", context)


@superuser_required
@require_http_methods(["GET"])
@ratelimit(key="user", rate="60/m", block=True)
def platform_admin_promotions(request: HttpRequest) -> HttpResponse:
    """List promotion rules with basic filters for platform admins."""
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"

    scope_filter = request.GET.get("scope_type", "").strip().lower()
    status_filter = request.GET.get("status", "active").strip().lower()
    search = request.GET.get("q", "").strip()
    now = timezone.now()

    promotions = Promotion.objects.select_related(
        "target_user",
        "target_team",
        "target_organization",
        "created_by",
    ).order_by("scope_type", "priority", "-created_at")

    if scope_filter in {choice for choice, _label in Promotion.ScopeType.choices}:
        promotions = promotions.filter(scope_type=scope_filter)

    if status_filter == "active":
        promotions = (
            promotions.filter(is_active=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        )
    elif status_filter == "scheduled":
        promotions = promotions.filter(is_active=True, starts_at__gt=now)
    elif status_filter == "expired":
        promotions = promotions.filter(Q(is_active=False) | Q(ends_at__lt=now))

    if search:
        promotions = promotions.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(description__icontains=search)
        )

    context = {
        "mode": mode,
        "scope": scope,
        "promotions": promotions,
        "scope_filter": scope_filter,
        "status_filter": status_filter,
        "search": search,
        "scope_choices": Promotion.ScopeType.choices,
    }
    return render(request, "core/platform_admin/promotions_list.html", context)


@superuser_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user", rate="30/h", block=True)
def platform_admin_promotion_create(request: HttpRequest) -> HttpResponse:
    """Create a promotion rule (UI scaffold)."""
    mode = _get_platform_mode(request)
    scope = _get_tier_scope(request) if mode == "tier" else "all"

    if request.method == "POST":
        errors = []
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        description = request.POST.get("description", "").strip()
        scope_type = request.POST.get("scope_type", "").strip()
        target_tier = request.POST.get("target_tier", "").strip()
        target_user_email = request.POST.get("target_user_email", "").strip().lower()
        target_team_id = request.POST.get("target_team_id", "").strip()
        target_org_id = request.POST.get("target_organization_id", "").strip()
        effect_type = request.POST.get("effect_type", "").strip()
        effect_value = request.POST.get("effect_value", "0").strip()
        effect_tier = request.POST.get("effect_tier", "").strip()
        priority = request.POST.get("priority", "100").strip()
        is_active = request.POST.get("is_active") == "on"
        starts_at_raw = request.POST.get("starts_at", "").strip()
        ends_at_raw = request.POST.get("ends_at", "").strip()
        reason = request.POST.get("reason", "").strip()
        internal_notes = request.POST.get("internal_notes", "").strip()

        if not name:
            errors.append("Name is required.")

        try:
            effect_value_decimal = Decimal(effect_value)
        except InvalidOperation:
            errors.append("Effect value must be a valid number.")
            effect_value_decimal = Decimal("0")

        try:
            priority_int = int(priority)
        except ValueError:
            errors.append("Priority must be a whole number.")
            priority_int = 100

        starts_at = None
        if starts_at_raw:
            try:
                starts_at = timezone.datetime.fromisoformat(starts_at_raw)
                starts_at = timezone.make_aware(starts_at)
            except ValueError:
                errors.append("Start datetime must be valid.")

        ends_at = None
        if ends_at_raw:
            try:
                ends_at = timezone.datetime.fromisoformat(ends_at_raw)
                ends_at = timezone.make_aware(ends_at)
            except ValueError:
                errors.append("End datetime must be valid.")

        target_user = None
        target_team = None
        target_organization = None

        if target_user_email:
            target_user = User.objects.filter(email__iexact=target_user_email).first()
            if not target_user:
                errors.append("Target user email was not found.")

        if target_team_id:
            try:
                target_team = Team.objects.get(id=int(target_team_id))
            except (ValueError, Team.DoesNotExist):
                errors.append("Target team ID is invalid.")

        if target_org_id:
            try:
                target_organization = Organization.objects.get(id=int(target_org_id))
            except (ValueError, Organization.DoesNotExist):
                errors.append("Target organisation ID is invalid.")

        if not errors:
            promotion = Promotion(
                name=name,
                code=code,
                description=description,
                scope_type=scope_type,
                target_tier=target_tier,
                target_user=target_user,
                target_team=target_team,
                target_organization=target_organization,
                effect_type=effect_type,
                effect_value=effect_value_decimal,
                effect_tier=effect_tier,
                priority=priority_int,
                is_active=is_active,
                starts_at=starts_at,
                ends_at=ends_at,
                reason=reason,
                internal_notes=internal_notes,
                created_by=request.user,
                updated_by=request.user,
            )
            try:
                promotion.full_clean()
                promotion.save()
            except Exception as exc:
                errors.append(str(exc))

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(
                request,
                "core/platform_admin/promotion_form.html",
                {
                    "mode": mode,
                    "scope": scope,
                    "form_data": request.POST,
                    "scope_choices": Promotion.ScopeType.choices,
                    "effect_choices": Promotion.EffectType.choices,
                    "tier_choices": UserProfile.AccountTier.choices,
                },
            )

        messages.success(request, f"Promotion '{name}' created.")
        return redirect("core:platform_admin_promotions")

    return render(
        request,
        "core/platform_admin/promotion_form.html",
        {
            "mode": mode,
            "scope": scope,
            "scope_choices": Promotion.ScopeType.choices,
            "effect_choices": Promotion.EffectType.choices,
            "tier_choices": UserProfile.AccountTier.choices,
        },
    )


@superuser_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="30/h", block=True)
def platform_admin_promotion_toggle(
    request: HttpRequest, promotion_id: int
) -> HttpResponse:
    """Toggle active status for a promotion rule."""
    promotion = get_object_or_404(Promotion, id=promotion_id)
    promotion.is_active = not promotion.is_active
    promotion.updated_by = request.user
    promotion.save(update_fields=["is_active", "updated_by", "updated_at"])

    status_text = "activated" if promotion.is_active else "deactivated"
    messages.success(request, f"Promotion '{promotion.name}' {status_text}.")
    return redirect("core:platform_admin_promotions")
