"""Promotion resolution helpers.

This service determines the effective promotion for a target and can apply
promotion effects to tier pricing values.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from checktick_app.core.models import PricingOverride, Promotion, UserProfile


@dataclass
class PromotionResolution:
    """Resolved pricing and promotion payload for a target."""

    base_tier: str
    base_amount_pence: int
    base_amount_ex_vat_pence: int
    applied_promotion: Promotion | None
    effective_tier: str
    effective_amount_pence: int
    effective_amount_ex_vat_pence: int


def _to_pence(value: Decimal) -> int:
    return int((value * Decimal("100")).quantize(Decimal("1")))


def _is_active_window(promotion: Promotion, at_time) -> bool:
    if not promotion.is_active:
        return False
    if promotion.starts_at and at_time < promotion.starts_at:
        return False
    if promotion.ends_at and at_time > promotion.ends_at:
        return False
    return True


def _specificity_rank(scope_type: str) -> int:
    if scope_type == Promotion.ScopeType.ACCOUNT:
        return 3
    if scope_type == Promotion.ScopeType.TIER:
        return 2
    return 1


def _select_best_promotion(queryset, at_time) -> Promotion | None:
    active = [p for p in queryset if _is_active_window(p, at_time)]
    if not active:
        return None
    active.sort(
        key=lambda p: (
            -_specificity_rank(p.scope_type),
            p.priority,
            -p.created_at.timestamp(),
        )
    )
    return active[0]


def _get_tier_pricing(tier: str) -> tuple[int, int]:
    tiers = PricingOverride.get_effective_tiers()
    cfg = tiers.get(tier, settings.SUBSCRIPTION_TIERS.get(tier, {}))
    return int(cfg.get("amount", 0)), int(cfg.get("amount_ex_vat", 0))


def _apply_effect(
    promotion: Promotion | None,
    amount_pence: int,
    amount_ex_vat_pence: int,
    tier: str,
) -> tuple[int, int, str]:
    if not promotion:
        return amount_pence, amount_ex_vat_pence, tier

    if promotion.effect_type == Promotion.EffectType.TIER_OVERRIDE and promotion.effect_tier:
        tier_amount, tier_amount_ex_vat = _get_tier_pricing(promotion.effect_tier)
        return tier_amount, tier_amount_ex_vat, promotion.effect_tier

    if promotion.effect_type == Promotion.EffectType.SET_PRICE:
        set_price = max(0, _to_pence(promotion.effect_value))
        return set_price, set_price, tier

    if promotion.effect_type == Promotion.EffectType.FIXED_DISCOUNT:
        discount = max(0, _to_pence(promotion.effect_value))
        return max(0, amount_pence - discount), max(0, amount_ex_vat_pence - discount), tier

    if promotion.effect_type == Promotion.EffectType.PERCENT_DISCOUNT:
        ratio = max(Decimal("0"), min(Decimal("100"), promotion.effect_value)) / Decimal("100")
        discount_inc = int(Decimal(amount_pence) * ratio)
        discount_ex = int(Decimal(amount_ex_vat_pence) * ratio)
        return max(0, amount_pence - discount_inc), max(0, amount_ex_vat_pence - discount_ex), tier

    return amount_pence, amount_ex_vat_pence, tier


def resolve_effective_pricing_for_user(user, at_time=None) -> PromotionResolution:
    """Resolve effective promotion and price for a user account."""
    at = at_time or timezone.now()
    profile = UserProfile.get_or_create_for_user(user)
    tier = profile.account_tier
    base_amount, base_amount_ex_vat = _get_tier_pricing(tier)

    promotions = Promotion.objects.filter(
        Q(scope_type=Promotion.ScopeType.PLATFORM)
        | Q(scope_type=Promotion.ScopeType.TIER, target_tier=tier)
        | Q(scope_type=Promotion.ScopeType.ACCOUNT, target_user=user)
    )

    applied = _select_best_promotion(promotions, at)
    eff_amount, eff_amount_ex_vat, eff_tier = _apply_effect(
        applied,
        base_amount,
        base_amount_ex_vat,
        tier,
    )

    return PromotionResolution(
        base_tier=tier,
        base_amount_pence=base_amount,
        base_amount_ex_vat_pence=base_amount_ex_vat,
        applied_promotion=applied,
        effective_tier=eff_tier,
        effective_amount_pence=eff_amount,
        effective_amount_ex_vat_pence=eff_amount_ex_vat,
    )


def resolve_effective_pricing_for_team(team, at_time=None) -> PromotionResolution:
    """Resolve effective promotion and price for a team account."""
    at = at_time or timezone.now()
    owner_profile = UserProfile.get_or_create_for_user(team.owner)
    tier = owner_profile.account_tier
    base_amount, base_amount_ex_vat = _get_tier_pricing(tier)

    promotions = Promotion.objects.filter(
        Q(scope_type=Promotion.ScopeType.PLATFORM)
        | Q(scope_type=Promotion.ScopeType.TIER, target_tier=tier)
        | Q(scope_type=Promotion.ScopeType.ACCOUNT, target_team=team)
    )

    applied = _select_best_promotion(promotions, at)
    eff_amount, eff_amount_ex_vat, eff_tier = _apply_effect(
        applied,
        base_amount,
        base_amount_ex_vat,
        tier,
    )

    return PromotionResolution(
        base_tier=tier,
        base_amount_pence=base_amount,
        base_amount_ex_vat_pence=base_amount_ex_vat,
        applied_promotion=applied,
        effective_tier=eff_tier,
        effective_amount_pence=eff_amount,
        effective_amount_ex_vat_pence=eff_amount_ex_vat,
    )


def resolve_effective_pricing_for_organization(org, at_time=None) -> PromotionResolution:
    """Resolve effective promotion and price for an organisation account."""
    at = at_time or timezone.now()
    tier = UserProfile.AccountTier.ORGANIZATION
    base_amount, base_amount_ex_vat = _get_tier_pricing(tier)

    promotions = Promotion.objects.filter(
        Q(scope_type=Promotion.ScopeType.PLATFORM)
        | Q(scope_type=Promotion.ScopeType.TIER, target_tier=tier)
        | Q(scope_type=Promotion.ScopeType.ACCOUNT, target_organization=org)
    )

    applied = _select_best_promotion(promotions, at)
    eff_amount, eff_amount_ex_vat, eff_tier = _apply_effect(
        applied,
        base_amount,
        base_amount_ex_vat,
        tier,
    )

    return PromotionResolution(
        base_tier=tier,
        base_amount_pence=base_amount,
        base_amount_ex_vat_pence=base_amount_ex_vat,
        applied_promotion=applied,
        effective_tier=eff_tier,
        effective_amount_pence=eff_amount,
        effective_amount_ex_vat_pence=eff_amount_ex_vat,
    )
