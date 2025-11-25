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

    # Support level
    support_level: str  # "community", "email", "priority"


# Define limits for each tier - SINGLE SOURCE OF TRUTH
TIER_LIMITS_CONFIG = {
    "free": TierLimits(
        max_surveys=3,
        can_add_editors=False,
        can_add_viewers=False,
        max_collaborators_per_survey=0,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,  # Basic API access for all
        can_export_data=True,  # Can export own data
        can_use_webhooks=False,
        support_level="community",
    ),
    "pro": TierLimits(
        max_surveys=None,  # Unlimited
        can_add_editors=True,
        can_add_viewers=False,
        max_collaborators_per_survey=10,
        can_create_organizations=False,
        can_create_sub_organizations=False,
        max_organization_members=None,
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=False,
        support_level="email",
    ),
    "organization": TierLimits(
        max_surveys=None,  # Unlimited
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited
        can_create_organizations=True,
        can_create_sub_organizations=False,
        max_organization_members=None,  # Unlimited
        can_customize_branding=False,
        can_use_custom_domain=False,
        can_white_label=False,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=True,
        support_level="email",
    ),
    "enterprise": TierLimits(
        max_surveys=None,  # Unlimited
        can_add_editors=True,
        can_add_viewers=True,
        max_collaborators_per_survey=None,  # Unlimited
        can_create_organizations=True,
        can_create_sub_organizations=True,
        max_organization_members=None,  # Unlimited
        can_customize_branding=True,
        can_use_custom_domain=True,
        can_white_label=True,
        can_use_api=True,
        can_export_data=True,
        can_use_webhooks=True,
        support_level="priority",
    ),
}


def get_tier_limits(tier: str) -> TierLimits:
    """Get limits for a specific tier.

    Args:
        tier: Account tier name (free, pro, organization, enterprise)

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

    effective_tier = user.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # No limit
    if limits.max_surveys is None:
        return True, ""

    # Check current count
    from checktick_app.surveys.models import Survey

    survey_count = Survey.objects.filter(owner=user, is_original=True).count()

    if survey_count >= limits.max_surveys:
        return False, (
            f"You've reached the limit of {limits.max_surveys} surveys for your "
            f"{effective_tier.title()} tier. Upgrade to Pro for unlimited surveys."
        )

    return True, ""


def check_collaboration_limit(user, collaboration_type: str = "editor") -> tuple[bool, str]:
    """Check if user can add a collaborator of the specified type.

    Args:
        user: User object with profile
        collaboration_type: "editor" or "viewer"

    Returns:
        (can_add, reason) - Boolean and error message if not allowed
    """
    if not hasattr(user, "profile"):
        return False, "User profile not found"

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


def check_collaborators_per_survey_limit(survey, additional_count: int = 1) -> tuple[bool, str]:
    """Check if survey can have more collaborators added.

    Args:
        survey: Survey object
        additional_count: Number of collaborators to add

    Returns:
        (can_add, reason) - Boolean and error message if limit reached
    """
    if not hasattr(survey.owner, "profile"):
        return False, "Survey owner profile not found"

    effective_tier = survey.owner.profile.get_effective_tier()
    limits = get_tier_limits(effective_tier)

    # No limit
    if limits.max_collaborators_per_survey is None:
        return True, ""

    # Count current collaborators
    from checktick_app.surveys.models import SurveyCollaborator

    current_count = SurveyCollaborator.objects.filter(survey=survey).count()

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
        "support": {
            "level": limits.support_level,
        },
    }
