import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
    SurveyAccessToken,
    SurveyMembership,
    SurveyResponse,
    TeamMembership,
)

from .forms import (
    BrandingConfigForm,
    SignupForm,
    UserEmailPreferencesForm,
    UserLanguagePreferenceForm,
)
from .models import UserLanguagePreference

logger = logging.getLogger(__name__)

try:
    from .models import SiteBranding, UserEmailPreferences
except ImportError:
    SiteBranding = None
    UserEmailPreferences = None

try:
    from .theme_utils import normalize_daisyui_builder_css
except ImportError:

    def normalize_daisyui_builder_css(s: str) -> str:
        """No-op fallback if theme utils or migrations are unavailable."""
        return s


try:
    from .themes import DARK_THEMES, LIGHT_THEMES, generate_theme_css_for_brand
except ImportError:
    LIGHT_THEMES = []
    DARK_THEMES = []
    generate_theme_css_for_brand = None


# Django's session key for storing language preference
LANGUAGE_SESSION_KEY = "_language"


def home(request):
    return render(request, "core/home.html")


def hosting(request):
    return render(request, "core/hosting.html")


def pricing(request):
    """Display pricing tiers with GoCardless redirect flow integration.

    Self-hosted instances redirect to home as billing is not applicable.
    """
    from django.conf import settings

    # Self-hosted instances don't need pricing - redirect to home
    if getattr(settings, "SELF_HOSTED", False):
        messages.info(
            request,
            "Pricing is not applicable for self-hosted instances. "
            "All features are already enabled.",
        )
        return redirect("core:home")

    # Check if coming from signup with a pending tier selection
    auto_open_checkout = request.session.pop("auto_open_checkout", False)
    pending_tier = request.session.get("pending_tier", "")

    context = {
        "subscription_tiers": settings.SUBSCRIPTION_TIERS,
        "self_hosted": False,  # Always False here since we redirect above
        "auto_open_checkout": auto_open_checkout,
        "pending_tier": pending_tier,
    }
    return render(request, "core/pricing.html", context)


def healthz(request):
    """Lightweight health endpoint for load balancers and readiness probes.
    Returns 200 OK without auth or redirects.
    """
    return HttpResponse("ok", content_type="text/plain")


@login_required
def profile(request):
    sb = None
    # Handle language preference form submission
    if request.method == "POST" and request.POST.get("action") == "update_language":
        lang_pref, created = UserLanguagePreference.objects.get_or_create(
            user=request.user
        )
        form = UserLanguagePreferenceForm(request.POST, instance=lang_pref)
        if form.is_valid():
            saved_pref = form.save()
            # Immediately activate the new language and store in session
            translation.activate(saved_pref.language)
            request.LANGUAGE_CODE = saved_pref.language
            request.session[LANGUAGE_SESSION_KEY] = saved_pref.language
            request.session.modified = True
            print(f"DEBUG: Saved language: {saved_pref.language}")
            print(
                f"DEBUG: Session key set to: {request.session.get(LANGUAGE_SESSION_KEY)}"
            )
            print(f"DEBUG: request.LANGUAGE_CODE: {request.LANGUAGE_CODE}")
            messages.success(request, _("Language preference updated successfully."))
        else:
            print(f"DEBUG: Form errors: {form.errors}")
            messages.error(
                request, _("There was an error updating your language preference.")
            )
        return redirect("core:profile")
    # Handle email preferences form submission
    if request.method == "POST" and request.POST.get("action") == "update_email_prefs":
        if UserEmailPreferences is not None:
            prefs = UserEmailPreferences.get_or_create_for_user(request.user)
            form = UserEmailPreferencesForm(request.POST, instance=prefs)
            if form.is_valid():
                form.save()
                messages.success(request, _("Email preferences updated successfully."))
            else:
                messages.error(
                    request, _("There was an error updating your email preferences.")
                )
        return redirect("core:profile")
    if request.method == "POST" and request.POST.get("action") == "upgrade_to_org":
        # Create a new organisation owned by this user, and make them ADMIN
        with transaction.atomic():
            org_name = (
                request.POST.get("org_name")
                or f"{request.user.username}'s Organisation"
            )
            org = Organization.objects.create(name=org_name, owner=request.user)
            OrganizationMembership.objects.get_or_create(
                organization=org,
                user=request.user,
                defaults={"role": OrganizationMembership.Role.ADMIN},
            )
        messages.success(
            request,
            _(
                "Organisation created. You are now an organisation admin and can host surveys and build a team."
            ),
        )
        return redirect("surveys:org_users", org_id=org.id)
    if request.method == "POST" and request.POST.get("action") == "reset_org_theme":
        # Handle organization theme reset (org owners only)
        primary_owned_org = Organization.objects.filter(owner=request.user).first()
        if primary_owned_org:
            org = primary_owned_org
            org.default_theme = ""
            org.theme_preset_light = ""
            org.theme_preset_dark = ""
            org.theme_light_css = ""
            org.theme_dark_css = ""
            org.save()
            logger.info(
                f"Organization theme reset to defaults by {request.user.username} (org_id={org.id})"
            )
            messages.success(
                request, _("Organization theme reset to platform defaults.")
            )
        return redirect("core:profile")
    if request.method == "POST" and request.POST.get("action") == "update_org_theme":
        # Handle organization theme update (org owners only)
        primary_owned_org = Organization.objects.filter(owner=request.user).first()
        if primary_owned_org:
            org = primary_owned_org
            org.theme_preset_light = (
                request.POST.get("org_theme_preset_light") or ""
            ).strip()
            org.theme_preset_dark = (
                request.POST.get("org_theme_preset_dark") or ""
            ).strip()

            # Get custom CSS (optional - overrides preset if provided)
            raw_light = request.POST.get("org_theme_light_css") or ""
            raw_dark = request.POST.get("org_theme_dark_css") or ""

            # Generate theme CSS from presets and custom overrides
            if generate_theme_css_for_brand:
                try:
                    generated_light, generated_dark = generate_theme_css_for_brand(
                        org.theme_preset_light or settings.BRAND_THEME_PRESET_LIGHT,
                        org.theme_preset_dark or settings.BRAND_THEME_PRESET_DARK,
                        raw_light,
                        raw_dark,
                    )
                    org.theme_light_css = generated_light
                    org.theme_dark_css = generated_dark
                except Exception as e:
                    logger.error(f"Failed to generate org theme CSS: {e}")
                    # Fall back to normalizing raw CSS
                    org.theme_light_css = normalize_daisyui_builder_css(raw_light)
                    org.theme_dark_css = normalize_daisyui_builder_css(raw_dark)
            else:
                # Fallback if theme generation not available
                org.theme_light_css = normalize_daisyui_builder_css(raw_light)
                org.theme_dark_css = normalize_daisyui_builder_css(raw_dark)

            org.save()
            logger.info(
                f"Organization theme updated by {request.user.username} (org_id={org.id}, "
                f"light={org.theme_preset_light}, dark={org.theme_preset_dark})"
            )
            messages.success(request, _("Organization theme saved."))
        return redirect("core:profile")
    if request.method == "POST" and request.POST.get("action") == "update_branding":
        if not request.user.is_superuser:
            return redirect("core:profile")
        if SiteBranding is not None:
            sb, created = SiteBranding.objects.get_or_create(pk=1)
            sb.default_theme = request.POST.get("default_theme") or sb.default_theme
            sb.icon_url = (request.POST.get("icon_url") or "").strip()
            if request.FILES.get("icon_file"):
                sb.icon_file = request.FILES["icon_file"]
            # Dark icon fields
            sb.icon_url_dark = (request.POST.get("icon_url_dark") or "").strip()
            if request.FILES.get("icon_file_dark"):
                sb.icon_file_dark = request.FILES["icon_file_dark"]
            sb.font_heading = (request.POST.get("font_heading") or "").strip()
            sb.font_body = (request.POST.get("font_body") or "").strip()
            sb.font_css_url = (request.POST.get("font_css_url") or "").strip()

            # Save theme presets
            sb.theme_preset_light = (
                request.POST.get("theme_preset_light")
                or settings.BRAND_THEME_PRESET_LIGHT
            ).strip()
            sb.theme_preset_dark = (
                request.POST.get("theme_preset_dark")
                or settings.BRAND_THEME_PRESET_DARK
            ).strip()

            # Get custom CSS (optional - overrides preset if provided)
            raw_light = request.POST.get("theme_light_css") or ""
            raw_dark = request.POST.get("theme_dark_css") or ""

            # Generate theme CSS from presets and custom overrides
            if generate_theme_css_for_brand:
                try:
                    generated_light, generated_dark = generate_theme_css_for_brand(
                        sb.theme_preset_light, sb.theme_preset_dark, raw_light, raw_dark
                    )
                    sb.theme_light_css = generated_light
                    sb.theme_dark_css = generated_dark
                except Exception as e:
                    logger.error(f"Failed to generate theme CSS: {e}")
                    # Fall back to normalizing raw CSS
                    sb.theme_light_css = normalize_daisyui_builder_css(raw_light)
                    sb.theme_dark_css = normalize_daisyui_builder_css(raw_dark)
            else:
                # Fallback if theme generation not available
                sb.theme_light_css = normalize_daisyui_builder_css(raw_light)
                sb.theme_dark_css = normalize_daisyui_builder_css(raw_dark)

            sb.save()
            logger.info(
                f"Platform theme updated by {request.user.username} (superuser, "
                f"theme={sb.default_theme}, light={sb.theme_preset_light}, dark={sb.theme_preset_dark})"
            )
            messages.success(request, _("Project theme saved."))
        return redirect("core:profile")
    if SiteBranding is not None and sb is None:
        try:
            sb = SiteBranding.objects.first()
        except Exception:
            sb = None
    # Lightweight stats for badges
    user = request.user
    # Pick a primary organisation if present: prefer one the user owns; else first membership
    primary_owned_org = Organization.objects.filter(owner=user).first()
    first_membership = (
        OrganizationMembership.objects.filter(user=user)
        .select_related("organization")
        .first()
    )
    org = primary_owned_org or (
        first_membership.organization if first_membership else None
    )

    # Check if user has any surveys with encryption enabled
    has_encryption_setup = Survey.objects.filter(
        owner=user,
        encrypted_kek_password__isnull=False,
        encrypted_kek_recovery__isnull=False,
    ).exists()

    # Check if user has any surveys with OIDC encryption
    has_oidc_encryption = Survey.objects.filter(
        owner=user,
        encrypted_kek_oidc__isnull=False,
    ).exists()

    stats = {
        "is_superuser": getattr(user, "is_superuser", False),
        "is_staff": getattr(user, "is_staff", False),
        "orgs_owned": Organization.objects.filter(owner=user).count(),
        "org_admin_count": OrganizationMembership.objects.filter(
            user=user, role=OrganizationMembership.Role.ADMIN
        ).count(),
        "org_memberships": OrganizationMembership.objects.filter(user=user).count(),
        "team_admin_count": TeamMembership.objects.filter(
            user=user, role=TeamMembership.Role.ADMIN
        ).count(),
        "team_memberships": TeamMembership.objects.filter(user=user).count(),
        "surveys_owned": Survey.objects.filter(owner=user).count(),
        "survey_creator_count": SurveyMembership.objects.filter(
            user=user, role=SurveyMembership.Role.CREATOR
        ).count(),
        "survey_viewer_count": SurveyMembership.objects.filter(
            user=user, role=SurveyMembership.Role.VIEWER
        ).count(),
        "groups_owned": QuestionGroup.objects.filter(owner=user).count(),
        "question_groups_owned": QuestionGroup.objects.filter(
            owner=user
        ).count(),  # Alias for template clarity
        "responses_submitted": SurveyResponse.objects.filter(submitted_by=user).count(),
        "tokens_created": SurveyAccessToken.objects.filter(created_by=user).count(),
        "has_encryption_setup": has_encryption_setup,
        "has_oidc_encryption": has_oidc_encryption,
    }
    # Prepare language preference form
    lang_pref, created = UserLanguagePreference.objects.get_or_create(user=user)
    language_form = UserLanguagePreferenceForm(instance=lang_pref)
    # Prepare email preferences form
    email_prefs_form = None
    if UserEmailPreferences is not None:
        prefs = UserEmailPreferences.get_or_create_for_user(user)
        email_prefs_form = UserEmailPreferencesForm(instance=prefs)

    # Prepare theme choices for template
    light_theme_choices = (
        [(theme, theme) for theme in LIGHT_THEMES] if LIGHT_THEMES else []
    )
    dark_theme_choices = (
        [(theme, theme) for theme in DARK_THEMES] if DARK_THEMES else []
    )

    # Check if user can manage any users (owns org, is org/team admin, or is staff)
    can_manage_any_users = (
        user.is_staff
        or stats["orgs_owned"] > 0
        or stats["org_admin_count"] > 0
        or stats["team_admin_count"] > 0
    )

    # Get subscription information
    profile = user.profile
    subscription_info = {
        "tier": profile.account_tier,
        "tier_display": profile.get_account_tier_display(),
        "subscription_status": profile.subscription_status,
        "created_at": profile.created_at,
        "payment_provider": profile.payment_provider,
    }

    # 2FA status for password users
    from .views_2fa import check_2fa_required, is_password_user

    is_password_user_flag = is_password_user(user)
    has_2fa = check_2fa_required(user) if is_password_user_flag else False

    return render(
        request,
        "core/profile.html",
        {
            "sb": sb,
            "stats": stats,
            "org": org,
            "language_form": language_form,
            "email_prefs_form": email_prefs_form,
            "can_safely_delete_account": can_user_safely_delete_own_account(user),
            "can_manage_any_users": can_manage_any_users,
            "light_theme_choices": light_theme_choices,
            "dark_theme_choices": dark_theme_choices,
            "subscription_info": subscription_info,
            "is_password_user": is_password_user_flag,
            "has_2fa": has_2fa,
        },
    )


def signup(request):
    # Get the 'next' URL from query params (e.g., from survey invite link)
    next_url = request.GET.get("next") or request.POST.get("next")

    # Validate next_url to prevent open redirect vulnerabilities
    if next_url and not next_url.startswith("/"):
        next_url = None

    # Get selected tier before form validation (not a form field, just POST data)
    # nosemgrep: python.django.security.django-using-request-post-after-is-valid
    selected_tier = (
        request.POST.get("tier", "free").lower() if request.method == "POST" else "free"
    )

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # With multiple AUTHENTICATION_BACKENDS configured (e.g., ModelBackend + Axes),
            # login() requires an explicit backend unless the user was authenticated via authenticate().
            # Since we just created the user, log them in using the default ModelBackend.
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Send welcome email
            try:
                from .email_utils import send_welcome_email

                send_welcome_email(user)
            except Exception as e:
                # Don't block signup if email fails
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send welcome email to {user.username}: {e}")

            # Handle tier-based signup flow
            # FREE: Go straight to surveys (or next_url if provided)
            # PRO/TEAM: Redirect to pricing to complete payment immediately
            # Organisation/Enterprise: Contact sales (shouldn't reach here from form)
            if selected_tier == "free":
                # FREE tier - redirect to next_url if provided, otherwise surveys
                if next_url:
                    messages.success(
                        request,
                        _("Welcome to CheckTick! You can now complete the survey."),
                    )
                    return redirect(next_url)
                messages.success(
                    request,
                    _("Welcome to CheckTick! Start by creating your first survey."),
                )
                return redirect("surveys:list")
            elif selected_tier in ("pro", "team_small", "team_medium", "team_large"):
                # Self-service paid tiers - redirect to pricing for immediate payment
                # Store next_url for after payment completion
                if next_url:
                    request.session["pending_next_url"] = next_url
                request.session["pending_tier"] = selected_tier
                request.session["auto_open_checkout"] = True  # Signal JS to auto-open
                tier_display = selected_tier.upper().replace("_", " ")
                messages.info(
                    request,
                    _(
                        "Welcome to CheckTick! Complete your %(tier)s subscription "
                        "payment to activate all features."
                    )
                    % {"tier": tier_display},
                )
                return redirect("core:pricing")
            else:
                # Organisation, Enterprise, or unknown - fallback to surveys
                # These tiers require contacting sales and shouldn't be selectable in form
                if next_url:
                    messages.success(
                        request,
                        _("Welcome to CheckTick! You can now complete the survey."),
                    )
                    return redirect(next_url)
                messages.success(
                    request,
                    _("Welcome to CheckTick! Start by creating your first survey."),
                )
                return redirect("surveys:list")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form, "next": next_url})


@login_required
def complete_signup(request):
    """
    Complete signup for users who authenticated via OIDC from login page.
    They're already authenticated but need to choose account type and complete setup.
    """
    # Check if user needs signup completion
    if not request.session.get("needs_signup_completion"):
        # User already completed signup or came here by mistake
        return redirect("core:home")

    if request.method == "POST":
        account_type = request.POST.get("account_type")

        # Get next URL from POST (from hidden field populated via sessionStorage)
        next_url = request.POST.get("next")
        if next_url and next_url.startswith("/"):
            request.session["pending_next_url"] = next_url

        # Mark OIDC signup as completed
        if hasattr(request.user, "oidc"):
            request.user.oidc.signup_completed = True
            request.user.oidc.save()
            logger.info(
                f"Marked OIDC signup as completed for user: {request.user.email}"
            )

        # Send welcome email
        try:
            from .email_utils import send_welcome_email

            send_welcome_email(request.user)
        except Exception as e:
            logger.error(
                f"Failed to send welcome email to {request.user.username}: {e}"
            )

        if account_type == "org":
            with transaction.atomic():
                org_name = (
                    request.POST.get("org_name")
                    or f"{request.user.username}'s Organisation"
                )
                org = Organization.objects.create(name=org_name, owner=request.user)
                OrganizationMembership.objects.create(
                    organization=org,
                    user=request.user,
                    role=OrganizationMembership.Role.ADMIN,
                )
            # Clear the signup completion flag
            pending_next_url = request.session.pop("pending_next_url", None)
            request.session.pop("needs_signup_completion", None)

            if pending_next_url:
                messages.success(
                    request,
                    _("Organisation created. You can now complete the survey."),
                )
                return redirect(pending_next_url)

            messages.success(
                request, _("Organisation created. You are an organisation admin.")
            )
            return redirect("surveys:org_users", org_id=org.id)

        # Individual account - just clear the flag and redirect
        # Check if there's a pending survey URL from invite flow
        pending_next_url = request.session.pop("pending_next_url", None)
        request.session.pop("needs_signup_completion", None)

        if pending_next_url:
            messages.success(
                request,
                _("Account setup complete! You can now complete the survey."),
            )
            return redirect(pending_next_url)

        messages.success(
            request,
            _(
                "Account setup complete! Welcome to CheckTick. Start by creating your first survey."
            ),
        )
        return redirect("surveys:list")

    return render(
        request,
        "registration/complete_signup.html",
        {
            "user": request.user,
        },
    )


class BrandedPasswordResetView(auth_views.PasswordResetView):
    """Password reset view that ensures brand context is available to email templates.

    We pass extra_email_context on each request so templates like
    registration/password_reset_subject.txt can use {{ brand.title }}.
    Additionally, we ensure an HTML alternative is attached via
    html_email_template_name.
    """

    template_name = "registration/password_reset_form.html"
    subject_template_name = "registration/password_reset_subject.txt"
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"

    def get_email_options(self):
        opts = super().get_email_options()
        # Merge in brand context so email templates can use {{ brand.* }}.
        try:
            from checktick_app.context_processors import branding as _branding

            ctx = _branding(self.request)
            brand = ctx.get("brand", {})
        except Exception:
            brand = {"title": getattr(settings, "BRAND_TITLE", "CheckTick")}
        extra = opts.get("extra_email_context") or {}
        # Avoid mutating the original dict in place across requests
        merged = {**extra, "brand": brand}
        opts["extra_email_context"] = merged
        return opts


## Removed DirectPasswordResetConfirmView to use Django's standard confirm flow.


# Note: User and organization deletion is handled through Django Admin interface
# by superusers only. Regular users cannot delete accounts for security reasons.
# This protects against accidental data loss and maintains audit trails.


def can_user_safely_delete_own_account(user):
    """
    Check if a user can safely delete their own account without affecting others.

    Users can delete their account if:
    - They are not in any organizations
    - None of their surveys have collaborators
    - They are not collaborators on others' surveys
    """
    if not user.is_authenticated:
        return False

    # Check org memberships
    has_org_memberships = OrganizationMembership.objects.filter(user=user).exists()
    if has_org_memberships:
        return False

    # Check if any of their surveys have collaborators
    user_surveys = Survey.objects.filter(owner=user)
    for survey in user_surveys:
        has_collaborators = (
            SurveyMembership.objects.filter(survey=survey).exclude(user=user).exists()
        )
        if has_collaborators:
            return False

    # Check if they are a collaborator on others' surveys
    is_collaborator = SurveyMembership.objects.filter(user=user).exists()
    if is_collaborator:
        return False

    return True


@login_required
def my_surveys(request):
    """
    Show surveys the user has participated in (completed).
    Displays survey name, completion date, and survey open/close period.
    """
    from checktick_app.surveys.models import SurveyResponse

    # Get all responses by this user, with related survey data
    responses = (
        SurveyResponse.objects.filter(submitted_by=request.user)
        .select_related("survey", "survey__organization")
        .order_by("-submitted_at")
    )

    # Build participation list with relevant info
    participations = []
    for response in responses:
        survey = response.survey
        participations.append(
            {
                "survey_name": survey.name,
                "organization_name": (
                    survey.organization.name if survey.organization else None
                ),
                "submitted_at": response.submitted_at,
                "survey_start_at": survey.start_at,
                "survey_end_at": survey.end_at,
                "survey_status": survey.status,
                "survey_slug": survey.slug,
                "is_live": survey.is_live() if hasattr(survey, "is_live") else False,
            }
        )

    return render(
        request,
        "core/my_surveys.html",
        {
            "participations": participations,
            "total_count": len(participations),
        },
    )


@login_required
def delete_account(request):
    """
    Allow individual users to delete their own account if it's safe to do so.
    Safe deletion means no impact on other users or shared data.
    """
    if request.method != "POST":
        return redirect("core:profile")

    user = request.user

    # Check if user can safely delete their account
    if not can_user_safely_delete_own_account(user):
        messages.error(
            request,
            _(
                "Cannot delete account. You are either part of an organization, "
                "have surveys with collaborators, or are a collaborator on other surveys. "
                "Please contact an administrator for assistance."
            ),
        )
        return redirect("core:profile")

    try:
        with transaction.atomic():
            # Get count of surveys for confirmation message
            survey_count = Survey.objects.filter(owner=user).count()

            # Delete user (CASCADE will handle owned surveys and responses)
            user.delete()

            # Add success message to session
            messages.success(
                request,
                _(
                    f"Your account and {survey_count} survey(s) have been permanently deleted. "
                    "Thank you for using CheckTick."
                ),
            )

        # Redirect to home page after successful deletion
        return redirect("/")

    except Exception as e:
        messages.error(
            request,
            _(
                "An error occurred while deleting your account. Please try again or contact support."
            ),
        )
        logger.error(f"Error deleting user account {user.id}: {e}")
        return redirect("core:profile")


def can_configure_branding(user):
    """Check if user can access branding configuration.

    Returns:
        bool: True if user can configure branding
    """
    if not user.is_authenticated:
        return False

    # Self-hosted: superusers can configure
    if getattr(settings, "SELF_HOSTED", False):
        return user.is_superuser

    # Hosted: Enterprise tier users can configure
    if hasattr(user, "profile"):
        can_customize, _ = user.profile.can_customize_branding()
        return can_customize

    return False


@login_required
def configure_branding(request):
    """View to configure site branding.

    Available to:
    - Self-hosted: Superusers
    - Hosted SaaS: Enterprise tier users

    Allows customization of themes, logos, and typography.
    """
    # Check permission
    if not can_configure_branding(request.user):
        messages.error(
            request,
            _(
                "You don't have permission to configure branding. "
                "This feature requires Enterprise tier."
            ),
        )
        return redirect("core:profile")

    # Get or create singleton SiteBranding instance
    branding, created = SiteBranding.objects.get_or_create(pk=1)

    if request.method == "POST":
        form = BrandingConfigForm(request.POST, request.FILES, instance=branding)
        if form.is_valid():
            form.save()
            messages.success(request, _("Branding configuration updated successfully!"))
            logger.info(
                f"Branding configuration updated by {request.user.username} "
                f"(theme={branding.default_theme})"
            )
            return redirect("core:configure_branding")
        else:
            messages.error(
                request, _("There was an error updating the branding configuration.")
            )
    else:
        form = BrandingConfigForm(instance=branding)

    return render(
        request,
        "core/configure_branding.html",
        {
            "form": form,
            "branding": branding,
        },
    )


def org_setup(request, token: str):
    """Organization setup/onboarding view.

    This view handles the setup flow for organization owners:
    1. Validates the setup token
    2. Shows organization details and T&Cs
    3. Creates user account if needed (or logs in existing)
    4. Makes user the org owner/admin
    5. Redirects to payment (if self-service) or dashboard (if invoiced)

    Args:
        token: The setup token from the invite link
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Find organization by setup token
    try:
        org = Organization.objects.get(setup_token=token, is_active=True)
    except Organization.DoesNotExist:
        messages.error(
            request,
            _(
                "Invalid or expired organization setup link. Please contact your administrator."
            ),
        )
        return redirect("core:home")

    # Check if already set up
    if org.setup_completed_at:
        messages.info(
            request,
            _(
                "This organization has already been set up. Please sign in to access it."
            ),
        )
        return redirect("login")

    if request.method == "POST":
        # Handle form submission
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        accept_terms = request.POST.get("accept_terms")

        if not accept_terms:
            messages.error(request, _("You must accept the terms and conditions."))
            return render(request, "core/org_setup.html", {"org": org, "email": email})

        if not email:
            messages.error(request, _("Email is required."))
            return render(request, "core/org_setup.html", {"org": org})

        # Check if user exists
        existing_user = User.objects.filter(email__iexact=email).first()

        if existing_user:
            # Existing user - check password
            from django.contrib.auth import authenticate

            user = authenticate(request, username=email, password=password)
            if not user:
                messages.error(
                    request,
                    _(
                        "An account with this email already exists. Please enter your password to continue."
                    ),
                )
                return render(
                    request,
                    "core/org_setup.html",
                    {"org": org, "email": email, "existing_user": True},
                )
        else:
            # New user - create account
            if not password or len(password) < 8:
                messages.error(request, _("Password must be at least 8 characters."))
                return render(
                    request, "core/org_setup.html", {"org": org, "email": email}
                )

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
            )

        # Update organization ownership and complete setup
        org.owner = user
        org.complete_setup()

        # Ensure user is an admin member
        OrganizationMembership.objects.get_or_create(
            organization=org,
            user=user,
            defaults={"role": OrganizationMembership.Role.ADMIN},
        )

        # Update user's profile to organization tier
        from checktick_app.core.models import UserProfile

        profile = UserProfile.get_or_create_for_user(user)
        profile.account_tier = UserProfile.AccountTier.ORGANIZATION
        profile.save(update_fields=["account_tier", "updated_at"])

        # Log the user in
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        # Send welcome email
        try:
            from .email_utils import send_welcome_email

            send_welcome_email(user)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")

        messages.success(
            request,
            _("Welcome to %(org_name)s! Your organization account is now active.")
            % {"org_name": org.name},
        )

        # Redirect based on billing type
        if org.billing_type == Organization.BillingType.INVOICE:
            # Invoice billing - no payment needed, go to dashboard
            return redirect("surveys:list")
        else:
            # Self-service payment - redirect to checkout
            # TODO: Implement payment checkout with custom price
            return redirect("surveys:list")

    # GET request - show setup form
    return render(
        request,
        "core/org_setup.html",
        {
            "org": org,
        },
    )
