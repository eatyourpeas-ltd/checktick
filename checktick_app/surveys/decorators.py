"""Decorators for team-based permissions in views.

These decorators enforce team membership and role requirements for views.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from .models import Team, TeamMembership
from .permissions import require_can_add_team_member, require_can_create_survey_in_team


def team_member_required(role: str | None = None):
    """Decorator to require team membership with optional role check.

    Args:
        role: Optional role requirement ('admin', 'creator', 'viewer').
              If None, any team member can access the view.

    Usage:
        @team_member_required()
        def view_team(request, team_id):
            # Any team member can access
            ...

        @team_member_required(role='admin')
        def manage_team(request, team_id):
            # Only team admins can access
            ...

        @team_member_required(role='creator')
        def create_survey(request, team_id):
            # Team admins and creators can access
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            # Get team_id from kwargs
            team_id = kwargs.get("team_id") or kwargs.get("pk")

            if not team_id:
                raise ValueError(
                    "team_member_required decorator requires 'team_id' or 'pk' in URL"
                )

            # Get team object
            team = get_object_or_404(Team, pk=team_id)

            # Check if user is team owner (always has access)
            if team.owner == request.user:
                return view_func(request, *args, **kwargs)

            # Check if user is org admin (if team is in org)
            if team.organization:
                from .permissions import is_org_admin

                if is_org_admin(request.user, team.organization):
                    return view_func(request, *args, **kwargs)

            # Check team membership
            membership = TeamMembership.objects.filter(
                team=team, user=request.user
            ).first()

            if not membership:
                raise PermissionDenied("You are not a member of this team.")

            # If specific role required, check it
            if role:
                # Admin role can access anything
                if membership.role == "admin":
                    return view_func(request, *args, **kwargs)

                # For creator role requirement, accept admin or creator
                if role == "creator" and membership.role in ["admin", "creator"]:
                    return view_func(request, *args, **kwargs)

                # For viewer role, accept any role (all members are at least viewers)
                if role == "viewer":
                    return view_func(request, *args, **kwargs)

                # Role doesn't match
                raise PermissionDenied(
                    f"You need {role} role or higher to access this page."
                )

            # No specific role required, just membership
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def team_admin_required(view_func):
    """Decorator to require team admin role.

    Shorthand for @team_member_required(role='admin')

    Usage:
        @team_admin_required
        def manage_members(request, team_id):
            # Only team admins, org admins, and team owner can access
            ...
    """
    return team_member_required(role="admin")(view_func)


def team_creator_required(view_func):
    """Decorator to require team creator or admin role.

    Shorthand for @team_member_required(role='creator')

    Usage:
        @team_creator_required
        def create_survey(request, team_id):
            # Team creators and admins can access
            ...
    """
    return team_member_required(role="creator")(view_func)


def require_team_survey_capacity(view_func):
    """Decorator to check if team has capacity to create surveys.

    Usage:
        @require_team_survey_capacity
        def create_team_survey(request, team_id):
            # Team has capacity for more surveys
            ...
    """

    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        team_id = kwargs.get("team_id") or kwargs.get("pk")

        if not team_id:
            raise ValueError(
                "require_team_survey_capacity decorator requires 'team_id' or 'pk' in URL"
            )

        team = get_object_or_404(Team, pk=team_id)

        # Check capacity and permissions
        require_can_create_survey_in_team(request.user, team)

        return view_func(request, *args, **kwargs)

    return wrapper


def require_team_member_capacity(view_func):
    """Decorator to check if team has capacity to add members.

    Usage:
        @require_team_member_capacity
        def add_team_member(request, team_id):
            # Team has capacity for more members
            ...
    """

    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        team_id = kwargs.get("team_id") or kwargs.get("pk")

        if not team_id:
            raise ValueError(
                "require_team_member_capacity decorator requires 'team_id' or 'pk' in URL"
            )

        team = get_object_or_404(Team, pk=team_id)

        # Check capacity and management permissions
        require_can_add_team_member(request.user, team)

        return view_func(request, *args, **kwargs)

    return wrapper
