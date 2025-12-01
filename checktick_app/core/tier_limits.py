"""Centralized account tier limits and enforcement.

This module provides a single source of truth for all tier-based feature limits.
Adjust thresholds here to change limits across the entire application.
"""

from dataclasses import dataclass
from typing import Any

from django.conf import settings


@dataclass
class TierLimits:
    """Limits for a specific account tier."""

    # Survey limits
    max_surveys: int | None  # None = unlimited

    # Collaboration limits
    can_add_editors: bool
    can_add_viewers: bool
    max_collaborators_per_survey: int | None  # None = unlimited

    # Team features
    can_create_teams: bool
    max_team_members: int | None  # None = unlimited, only for team tiers

    # Organization features
    can_create_organizations: bool
    can_create_sub_organizations: bool
    max_organization_members: int | None  # None = unlimited

    # Branding and customization
    can_customize_branding: bool
    can_use_custom_domain: bool
    can_white_label: bool

    # Advanced features
    can_use_api: bool
    can_export_data: bool
    can_use_webhooks: bool

    # Patient data and encryption
    can_collect_patient_data: bool  # FREE tier cannot collect patient data

    # Support level
    support_level: str  # "community", "email", "priority"


# Define limits for each tier - SINGLE SOURCE OF TRUTH
# Note: Self-hosted instances (SELF_HOSTED=True) automatically get Enterprise features
# but without billing requirements. Enterprise tier is for managed hosting customers.
TIER_LIMITS_CONFIG = {
    "free": TierLimits(
        max_surveys=3,
        can_add_editors=False,
        can_add_viewers=False,
        max_collaborators_per_survey=0,
        can_create_teams=False,
        max_team_members=None,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,  # Basic API access for all
        can_export_data=True,  # Can export own data
        can_use_webhooks=False,
        can_collect_patient_data=False,  # FREE tier cannot collect patient data
        support_level="community",
    ),
    "pro": TierLimits(
        max_surveys=None,  # Unlimited
        can_add_editors=True,
        can_add_viewers=False,
        max_collaborators_per_survey=10,
        can_create_teams=False,
        max_team_members=None,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=False,
        can_collect_patient_data=True,
        support_level="email",
    ),
    "team_small": TierLimits(
        max_surveys=50,
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited within team
        can_create_teams=True,
        max_team_members=5,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=False,
        can_collect_patient_data=True,
        support_level="email",
    ),
    "team_medium": TierLimits(
        max_surveys=50,
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited within team
        can_create_teams=True,
        max_team_members=10,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=False,
        can_collect_patient_data=True,
        support_level="email",
    ),
    "team_large": TierLimits(
        max_surveys=50,
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited within team
        can_create_teams=True,
        max_team_members=20,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=False,
        can_collect_patient_data=True,
        support_level="email",
    ),
    "organization": TierLimits(
        max_surveys=None,  # Unlimited
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited
        can_create_teams=True,
        max_team_members=None,  # Unlimited for org-hosted teams
        can_create_organizations=True,
        can_create_sub_organizations=False,
        max_organization_members=None,  # Unlimited
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=True,
        can_collect_patient_data=True,
        support_level="email",
    ),
    "enterprise": TierLimits(
        # Enterprise: Managed hosting by CheckTick with dedicated infrastructure
        # Billed separately, custom pricing (£200+/month)
        # NOT the same as self-hosted (which is free)
        max_surveys=None,  # Unlimited
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited
        can_create_teams=True,
        max_team_members=None,  # Unlimited
        can_create_organizations=True,
        can_create_sub_organizations=True,
        max_organization_members=None,  # Unlimited
        can_customize_branding=True,
        can_use_custom_domain=True,
        can_white_label=True,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=True,
        can_collect_patient_data=True,
        support_level="priority",
    ),
}


def get_tier_limits(tier: str) -> TierLimits:
    """Get limits for a specific tier.

    Args:
        tier: Account tier name (free, pro, team_small, team_medium, team_large, organization, enterprise)

    Returns:
        TierLimits object with all limits for the tier
    """
    # In self-hosted mode, everyone gets enterprise limits
    if getattr(settings, "SELF_HOSTED", False):
        return TIER_LIMITS_CONFIG["enterprise"]

    return TIER_LIMITS_CONFIG.get(tier.lower(), TIER_LIMITS_CONFIG["free"])


def check_survey_creation_limit(user) -> tuple[bool, str]:
    """Check if user can create another survey.

    Args:
        user: User object with profile

    Returns:
        (can_create, reason) - Boolean and error message if limit reached
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    # Refresh profile from database to ensure we have latest tier
    user.profile.refresh_from_db()

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # No limit
    if limits.max_surveys is None:
        return True, ""

    # Check current count
    from checktick_app.surveys.models import Survey

    survey_count = Survey.objects.filter(owner=user, is_original=True).count()

    if survey_count >= limits.max_surveys:
        # Customize message based on current tier
        if effective_tier == "free":
            upgrade_msg = "Upgrade to Pro (£5/mo) for unlimited surveys or Team Small (£25/mo) for team collaboration."
        elif effective_tier.startswith("team_"):
            upgrade_msg = "Upgrade to Organization tier for unlimited surveys."
        else:
            upgrade_msg = "Upgrade to Pro for unlimited surveys."

        return False, (
            f"You've reached the limit of {limits.max_surveys} surveys for your "
            f"{effective_tier.replace('_', ' ').title()} tier. {upgrade_msg}"
        )

    return True, ""


def check_collaboration_limit(
    user, collaboration_type: str = "editor"
) -> tuple[bool, str]:
    """Check if user can add a collaborator of the specified type.

    Args:
        user: User object with profile
        collaboration_type: "editor" or "viewer"

    Returns:
        (can_add, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    # Refresh profile from database to ensure we have latest tier
    user.profile.refresh_from_db()

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    if collaboration_type == "editor":
        if not limits.can_add_editors:
            return False, (
                "Adding editors requires Pro tier or higher. "
                "Upgrade to enable team collaboration."
            )
    elif collaboration_type == "viewer":
        if not limits.can_add_viewers:
            return False, (
                "Adding viewers requires Organization tier. "
                "Pro tier supports editors only."
            )

    return True, ""


def check_collaborators_per_survey_limit(
    survey, additional_count: int = 1
) -> tuple[bool, str]:
    """Check if survey can have more collaborators added.

    Args:
        survey: Survey object
        additional_count: Number of collaborators to add

    Returns:
        (can_add, reason) - Boolean and error message if limit reached
    """
    if not hasattr(survey.owner, "profile"):
        return False, "Survey owner profile not found"

    # Refresh profile from database to ensure we have latest tier
    survey.owner.profile.refresh_from_db()

    effective_tier = survey.owner.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # No limit
    if limits.max_collaborators_per_survey is None:
        return True, ""

    # Count current collaborators
    from checktick_app.surveys.models import SurveyMembership

    current_count = SurveyMembership.objects.filter(survey=survey).count()

    if current_count + additional_count > limits.max_collaborators_per_survey:
        return False, (
            f"Survey has reached the limit of {limits.max_collaborators_per_survey} "
            f"collaborators for {effective_tier.title()} tier. "
            f"Upgrade to Organization for unlimited collaboration."
        )

    return True, ""


def check_branding_permission(user) -> tuple[bool, str]:
    """Check if user can customize platform branding.

    Args:
        user: User object with profile

    Returns:
        (can_customize, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    if not limits.can_customize_branding:
        return False, (
            "Custom branding requires Enterprise tier. "
            "Contact us for Enterprise pricing."
        )

    return True, ""


def check_sub_organization_permission(user) -> tuple[bool, str]:
    """Check if user can create sub-organizations.

    Args:
        user: User object with profile

    Returns:
        (can_create, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    if not limits.can_create_sub_organizations:
        return False, (
            "Sub-organizations require Enterprise tier. "
            "Contact us for Enterprise pricing."
        )

    return True, ""


def check_webhook_permission(user) -> tuple[bool, str]:
    """Check if user can use webhooks.

    Args:
        user: User object with profile

    Returns:
        (can_use, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    if not limits.can_use_webhooks:
        return False, (
            "Webhooks require Organization tier or higher. "
            "Upgrade to enable webhook integrations."
        )

    return True, ""


def check_patient_data_permission(user) -> tuple[bool, str]:
    """Check if user can collect patient data in surveys.

    Args:
        user: User object with profile

    Returns:
        (can_collect, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    if not limits.can_collect_patient_data:
        return False, (
            "Collecting patient data requires a paid subscription. "
            "Upgrade to Pro (£5/mo) or higher to enable encrypted patient data collection."
        )

    return True, ""


def get_feature_availability(user) -> dict[str, Any]:
    """Get complete feature availability for a user.

    Useful for displaying in UI (account settings, upgrade prompts, etc.)

    Args:
        user: User object with profile

    Returns:
        Dictionary with all feature availability and limits
    """
    if not hasattr(user, "profile"):
        return {}

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # Count current usage
    from checktick_app.surveys.models import Survey

    survey_count = Survey.objects.filter(owner=user, is_original=True).count()

    return {
        "tier": effective_tier,
        "tier_display": effective_tier.title(),
        "is_self_hosted": getattr(settings, "SELF_HOSTED", False),
        "surveys": {
            "current": survey_count,
            "limit": limits.max_surveys,
            "unlimited": limits.max_surveys is None,
            "remaining": (
                limits.max_surveys - survey_count
                if limits.max_surveys is not None
                else None
            ),
        },
        "collaboration": {
            "can_add_editors": limits.can_add_editors,
            "can_add_viewers": limits.can_add_viewers,
            "max_per_survey": limits.max_collaborators_per_survey,
            "unlimited_per_survey": limits.max_collaborators_per_survey is None,
        },
        "teams": {
            "can_create": limits.can_create_teams,
            "max_members": limits.max_team_members,
            "unlimited_members": limits.max_team_members is None,
        },
        "organizations": {
            "can_create": limits.can_create_organizations,
            "can_create_sub_organizations": limits.can_create_sub_organizations,
        },
        "branding": {
            "can_customize": limits.can_customize_branding,
            "can_use_custom_domain": limits.can_use_custom_domain,
            "can_white_label": limits.can_white_label,
        },
        "advanced": {
            "can_use_api": limits.can_use_api,
            "can_export_data": limits.can_export_data,
            "can_use_webhooks": limits.can_use_webhooks,
        },
        "patient_data": {
            "can_collect": limits.can_collect_patient_data,
        },
        "support": {
            "level": limits.support_level,
        },
    }


def check_team_creation_permission(user) -> tuple[bool, str]:
    """Check if user can create a team.

    Args:
        user: User object with profile

    Returns:
        (can_create, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    if not limits.can_create_teams:
        return False, (
            "Creating teams requires Team tier or higher. "
            "Upgrade to Team Small (£25/mo) to enable team collaboration."
        )

    return True, ""


def check_team_member_limit(team, additional_count: int = 1) -> tuple[bool, str]:
    """Check if team can have more members added.

    Args:
        team: Team object
        additional_count: Number of members to add

    Returns:
        (can_add, reason) - Boolean and error message if limit reached
    """
    if not hasattr(team.owner, "profile"):
        return False, "Team owner profile not found"

    # Refresh profile from database to ensure we have latest tier
    team.owner.profile.refresh_from_db()

    effective_tier = team.owner.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # No limit (org-hosted teams or enterprise)
    if limits.max_team_members is None:
        return True, ""

    # Count current members
    from checktick_app.surveys.models import TeamMembership

    current_count = TeamMembership.objects.filter(team=team).count()

    if current_count + additional_count > limits.max_team_members:
        return False, (
            f"Team has reached the limit of {limits.max_team_members} "
            f"members for {effective_tier.replace('_', ' ').title()} tier. "
            f"Upgrade to a larger team size or Organization tier for unlimited members."
        )

    return True, ""


def check_team_survey_limit(team) -> tuple[bool, str]:
    """Check if team can create another survey.

    Args:
        team: Team object

    Returns:
        (can_create, reason) - Boolean and error message if limit reached
    """
    if not hasattr(team.owner, "profile"):
        return False, "Team owner profile not found"

    # Refresh profile from database to ensure we have latest tier
    team.owner.profile.refresh_from_db()

    effective_tier = team.owner.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # No limit (organization or enterprise)
    if limits.max_surveys is None:
        return True, ""

    # Count current team surveys
    from checktick_app.surveys.models import Survey

    survey_count = Survey.objects.filter(team=team, is_original=True).count()

    if survey_count >= team.max_surveys:
        return False, (
            f"Team has reached the limit of {team.max_surveys} surveys. "
            f"Upgrade to Organization tier for unlimited surveys."
        )

    return True, ""
