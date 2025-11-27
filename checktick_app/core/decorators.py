"""Decorators for enforcing account tier limits in views.

These decorators check tier permissions before allowing access to features.
They work with the centralized tier_limits configuration.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

from .tier_limits import (
    check_branding_permission,
    check_collaboration_limit,
    check_collaborators_per_survey_limit,
    check_sub_organization_permission,
    check_survey_creation_limit,
    check_webhook_permission,
)


def require_tier_permission(check_function, redirect_to: str = "core:home"):
    """Generic decorator factory for tier permission checks.

    Args:
        check_function: Function that returns (allowed, reason) tuple
        redirect_to: URL name to redirect to if permission denied

    Returns:
        Decorator function
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            # Check permission
            allowed, reason = check_function(request.user)

            if not allowed:
                # Handle AJAX/API requests differently
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": reason}, status=403)

                # Regular request - show message and redirect
                messages.error(request, reason)
                return redirect(redirect_to)

            # Permission granted - proceed with view
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_can_create_survey(view_func):
    """Require user to be within survey creation limits.

    Usage:
        @require_can_create_survey
        def survey_create(request):
            # User has permission to create surveys
            ...
    """
    return require_tier_permission(
        check_survey_creation_limit,
        redirect_to="surveys:list",
    )(view_func)


def require_can_add_collaborators(collaboration_type: str = "editor"):
    """Require user to be able to add collaborators of the specified type.

    Args:
        collaboration_type: "editor" or "viewer"

    Usage:
        @require_can_add_collaborators("editor")
        def add_editor(request, slug):
            # User has permission to add editors
            ...
    """

    def check_func(user):
        return check_collaboration_limit(user, collaboration_type)

    return require_tier_permission(
        check_func,
        redirect_to="surveys:list",
    )


def require_can_customize_branding(view_func):
    """Require user to have branding customization permission.

    Usage:
        @require_can_customize_branding
        def customize_branding(request):
            # User has Enterprise tier
            ...
    """
    return require_tier_permission(
        check_branding_permission,
        redirect_to="core:home",
    )(view_func)


def require_can_create_sub_organizations(view_func):
    """Require user to have sub-organization creation permission.

    Usage:
        @require_can_create_sub_organizations
        def create_sub_org(request):
            # User has Enterprise tier
            ...
    """
    return require_tier_permission(
        check_sub_organization_permission,
        redirect_to="core:home",
    )(view_func)


def require_can_use_webhooks(view_func):
    """Require user to have webhook access.

    Usage:
        @require_can_use_webhooks
        def manage_webhooks(request):
            # User has Organization tier or higher
            ...
    """
    return require_tier_permission(
        check_webhook_permission,
        redirect_to="core:home",
    )(view_func)


def check_survey_collaborator_limit(view_func):
    """Check survey collaborator limit before adding.

    This decorator expects the view to have a 'slug' parameter for the survey.
    It checks the limit but doesn't enforce it - view can handle the response.

    Usage:
        @check_survey_collaborator_limit
        def add_collaborator(request, slug):
            # Check if request has 'tier_limit_exceeded' flag
            if getattr(request, 'tier_limit_exceeded', False):
                # Handle limit exceeded
                ...
    """

    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        from checktick_app.surveys.models import Survey

        # Get survey from slug
        slug = kwargs.get("slug")
        if not slug:
            # No slug - can't check limit
            return view_func(request, *args, **kwargs)

        try:
            survey = Survey.objects.get(slug=slug)
        except Survey.DoesNotExist:
            # Survey doesn't exist - let view handle it
            return view_func(request, *args, **kwargs)

        # Check limit
        allowed, reason = check_collaborators_per_survey_limit(survey)

        if not allowed:
            # Set flag on request for view to check
            request.tier_limit_exceeded = True  # type: ignore[attr-defined]
            request.tier_limit_reason = reason  # type: ignore[attr-defined]
        else:
            request.tier_limit_exceeded = False  # type: ignore[attr-defined]

        return view_func(request, *args, **kwargs)

    return wrapper


def add_tier_context(view_func):
    """Add tier information to template context.

    Adds 'tier_info' to the context with feature availability.
    Useful for displaying tier status and upgrade prompts in templates.

    Usage:
        @add_tier_context
        def my_view(request):
            # Template will have access to {{ tier_info }}
            return render(request, 'template.html', context)
    """

    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        from .tier_limits import get_feature_availability

        # Get the response from the view
        response = view_func(request, *args, **kwargs)

        # If it's a TemplateResponse, we can modify the context
        if hasattr(response, "context_data"):
            tier_info = get_feature_availability(request.user)
            if response.context_data is None:
                response.context_data = {}
            response.context_data["tier_info"] = tier_info

        return response

    return wrapper


# Convenience function for checking permissions in views without decorators
def check_tier_permission(request: HttpRequest, permission_check) -> tuple[bool, str]:
    """Check tier permission in a view without using a decorator.

    Args:
        request: HTTP request with authenticated user
        permission_check: Function that returns (allowed, reason) tuple

    Returns:
        (allowed, reason) tuple

    Usage:
        def my_view(request):
            allowed, reason = check_tier_permission(
                request,
                lambda u: check_survey_creation_limit(u)
            )
            if not allowed:
                messages.error(request, reason)
                return redirect('surveys:list')
            # Continue with view logic
    """
    if not request.user.is_authenticated:
        return False, "Authentication required"

    return permission_check(request.user)
