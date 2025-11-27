"""Context processors for adding global template context."""

from django.conf import settings


def tier_info(request):
    """Add tier information to template context.

    Makes tier limits and feature availability accessible in all templates.
    """
    if not request.user.is_authenticated:
        return {}

    if not hasattr(request.user, "profile"):
        return {}

    from .tier_limits import get_feature_availability, get_tier_limits

    effective_tier = request.user.profile.get_effective_tier()
    features = get_feature_availability(request.user)
    limits = get_tier_limits(effective_tier)

    # Get current survey count
    from checktick_app.surveys.models import Survey

    survey_count = Survey.objects.filter(owner=request.user, is_original=True).count()

    return {
        "user_tier": effective_tier,
        "user_tier_display": request.user.profile.get_account_tier_display(),
        "tier_features": features,
        "tier_limits": limits,
        "survey_count": survey_count,
        "is_self_hosted": getattr(settings, "SELF_HOSTED", False),
    }
