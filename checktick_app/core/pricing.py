"""Centralised pricing helpers.

This module is the single source of truth for converting the ex-VAT tier prices
defined in ``settings.SUBSCRIPTION_TIERS`` (and any active ``PricingOverride``
rows) into inc-VAT amounts using ``settings.VAT_RATE``.

Why this exists
---------------
Historically ``SUBSCRIPTION_TIERS`` stored both ``amount_ex_vat`` and ``amount``
(inc VAT) as hardcoded pence values. That meant changing ``VAT_RATE`` in the
environment did not flow through to checkout amounts - only to invoice labels.

With the env-driven VAT model, only ``amount_ex_vat`` is canonical. The inc-VAT
``amount`` is computed on demand via :func:`get_tier_amounts` and
:func:`get_effective_tiers` so that updating ``VAT_RATE`` (or
``BASE_SEAT_PRICE_EX_VAT``) in the environment changes every checkout, invoice,
and public pricing display consistently.

Rounding
--------
VAT is rounded to the nearest penny using standard half-up rounding on the
pence amount. This matches how HMRC expects VAT to be calculated per invoice
line for retail pricing.
"""

from __future__ import annotations

import copy
import math
from typing import TypedDict

from django.conf import settings


class TierAmounts(TypedDict):
    """Resolved pricing for a single tier, all in pence."""

    amount_ex_vat: int
    amount: int  # inc VAT
    vat_amount: int


def _vat_rate() -> float:
    """Return the configured VAT rate as a float (e.g. 0.20 for 20%)."""
    return float(getattr(settings, "VAT_RATE", 0.20))


def compute_inc_vat(amount_ex_vat: int, vat_rate: float | None = None) -> int:
    """Compute the inc-VAT amount in pence from an ex-VAT pence amount.

    Uses standard half-up rounding to the nearest penny. Returns 0 when the
    input is 0 (e.g. bespoke tiers like organisation/enterprise).

    Args:
        amount_ex_vat: Price exclusive of VAT in pence.
        vat_rate: Optional VAT rate override (0.20 = 20%). Defaults to
            ``settings.VAT_RATE``.

    Returns:
        Inc-VAT amount in pence, rounded to the nearest penny.
    """
    rate = _vat_rate() if vat_rate is None else float(vat_rate)
    if amount_ex_vat <= 0:
        return 0
    inc = amount_ex_vat * (1.0 + rate)
    return int(math.floor(inc + 0.5))


def get_tier_amounts(tier: str, *, vat_rate: float | None = None) -> TierAmounts:
    """Return the ex-VAT, inc-VAT, and VAT-only amounts for a tier in pence.

    Reads from ``settings.SUBSCRIPTION_TIERS`` directly. For tiers that may be
    affected by Platform Admin overrides, use :func:`get_effective_tiers`
    instead.

    Args:
        tier: Tier key (e.g. ``"pro"``, ``"team_small"``).
        vat_rate: Optional VAT rate override. Defaults to ``settings.VAT_RATE``.

    Returns:
        Dict with ``amount_ex_vat``, ``amount`` (inc VAT), and ``vat_amount``.
        All values are 0 for unknown tiers.
    """
    cfg = getattr(settings, "SUBSCRIPTION_TIERS", {}).get(tier, {})
    amount_ex_vat = int(cfg.get("amount_ex_vat", 0))
    amount = compute_inc_vat(amount_ex_vat, vat_rate=vat_rate)
    return {
        "amount_ex_vat": amount_ex_vat,
        "amount": amount,
        "vat_amount": amount - amount_ex_vat,
    }


def _tier_with_amount(tier_cfg: dict, vat_rate: float | None = None) -> dict:
    """Return a copy of a tier config dict with a computed ``amount`` field."""
    cfg = copy.deepcopy(tier_cfg)
    amount_ex_vat = int(cfg.get("amount_ex_vat", 0))
    cfg["amount_ex_vat"] = amount_ex_vat
    cfg["amount"] = compute_inc_vat(amount_ex_vat, vat_rate=vat_rate)
    return cfg


def get_effective_tiers(*, vat_rate: float | None = None) -> dict:
    """Return all tiers with Platform Admin overrides applied and inc-VAT computed.

    This is the canonical entry point for code that needs the full tier dict
    (e.g. the public pricing page, checkout, and invoice generation). It:

    1. Deep-copies ``settings.SUBSCRIPTION_TIERS``.
    2. Applies any active ``PricingOverride`` rows (replacing ``amount_ex_vat``).
    3. Computes ``amount`` (inc VAT) from ``amount_ex_vat`` and ``VAT_RATE``.

    Args:
        vat_rate: Optional VAT rate override. Defaults to ``settings.VAT_RATE``.

    Returns:
        Dict with the same shape as ``settings.SUBSCRIPTION_TIERS`` but with
        ``amount`` computed from ``amount_ex_vat`` via the configured VAT rate.
    """
    from checktick_app.core.models import PricingOverride

    tiers = copy.deepcopy(settings.SUBSCRIPTION_TIERS)
    for override in PricingOverride.objects.filter(is_active=True):
        if override.tier in tiers:
            tiers[override.tier]["amount_ex_vat"] = int(override.amount_ex_vat)
    return {
        key: _tier_with_amount(cfg, vat_rate=vat_rate) for key, cfg in tiers.items()
    }


def get_effective_tier_amounts(
    tier: str, *, vat_rate: float | None = None
) -> TierAmounts:
    """Like :func:`get_tier_amounts` but honours active ``PricingOverride`` rows."""
    cfg = get_effective_tiers(vat_rate=vat_rate).get(tier, {})
    amount_ex_vat = int(cfg.get("amount_ex_vat", 0))
    amount = int(cfg.get("amount", compute_inc_vat(amount_ex_vat, vat_rate=vat_rate)))
    return {
        "amount_ex_vat": amount_ex_vat,
        "amount": amount,
        "vat_amount": amount - amount_ex_vat,
    }
