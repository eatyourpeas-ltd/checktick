"""Tests for Diary / EMA layout tier gating.

Verifies that:
- Free tier is denied the diary layout (linear only).
- All paid tiers (pro, team_small, team_medium, team_large, organization,
  enterprise) are allowed the diary layout.
- ``check_layout_permission`` and ``get_allowed_layouts`` are the single
  source of truth for layout access checks.
- ``get_feature_availability`` reports the diary layout correctly.

Mirrors the layout-gating tests in ``test_tier_enforcement.py``.
"""

import pytest

from checktick_app.core.tier_limits import (
    check_layout_permission,
    get_allowed_layouts,
    get_feature_availability,
    get_tier_limits,
)


def _set_tier(user, tier):
    """Set the effective tier on a real user's profile."""
    user.profile.account_tier = tier
    user.profile.save(update_fields=["account_tier"])
    return user


PAID_TIERS = [
    "pro",
    "team_small",
    "team_medium",
    "team_large",
    "organization",
    "enterprise",
]


# --- allowed_layouts config ---


@pytest.mark.django_db
def test_diary_in_all_paid_tier_configs():
    for tier in PAID_TIERS:
        limits = get_tier_limits(tier)
        assert "diary" in limits.allowed_layouts, f"{tier} should include diary"


@pytest.mark.django_db
def test_diary_not_in_free_tier_config():
    limits = get_tier_limits("free")
    assert "diary" not in limits.allowed_layouts
    assert limits.allowed_layouts == ["linear"]


@pytest.mark.django_db
def test_all_paid_tiers_have_eight_layouts():
    """Paid tiers should have all eight layouts now."""
    expected = {
        "linear",
        "section_menu",
        "rct",
        "guided",
        "staged",
        "matrix",
        "delphi",
        "diary",
    }
    for tier in PAID_TIERS:
        limits = get_tier_limits(tier)
        assert set(limits.allowed_layouts) == expected, f"{tier} layout set mismatch"


# --- check_layout_permission ---


class _FakeProfile:
    def __init__(self, tier):
        self._tier = tier

    def get_effective_tier(self):
        return self._tier


class _FakeUser:
    def __init__(self, tier):
        self.profile = _FakeProfile(tier)


@pytest.mark.django_db
def test_check_layout_permission_free_denied_diary():
    user = _FakeUser("free")
    can_use, reason = check_layout_permission(user, "diary")
    assert can_use is False
    assert "paid subscription" in reason


@pytest.mark.django_db
def test_check_layout_permission_pro_allowed_diary():
    user = _FakeUser("pro")
    can_use, reason = check_layout_permission(user, "diary")
    assert can_use is True
    assert reason == ""


@pytest.mark.django_db
def test_check_layout_permission_all_paid_tiers_allowed_diary():
    for tier in PAID_TIERS:
        user = _FakeUser(tier)
        can_use, reason = check_layout_permission(user, "diary")
        assert can_use is True, f"{tier} should allow diary"
        assert reason == ""


@pytest.mark.django_db
def test_check_layout_permission_free_allowed_linear():
    user = _FakeUser("free")
    can_use, reason = check_layout_permission(user, "linear")
    assert can_use is True
    assert reason == ""


# --- get_allowed_layouts ---


@pytest.mark.django_db
def test_get_allowed_layouts_free_excludes_diary():
    user = _FakeUser("free")
    layouts = get_allowed_layouts(user)
    assert "diary" not in layouts
    assert layouts == ["linear"]


@pytest.mark.django_db
def test_get_allowed_layouts_pro_includes_diary():
    user = _FakeUser("pro")
    layouts = get_allowed_layouts(user)
    assert "diary" in layouts


@pytest.mark.django_db
def test_get_allowed_layouts_all_paid_tiers_include_diary():
    for tier in PAID_TIERS:
        user = _FakeUser(tier)
        layouts = get_allowed_layouts(user)
        assert "diary" in layouts, f"{tier} should include diary in allowed_layouts"


# --- get_feature_availability ---


@pytest.mark.django_db
def test_feature_availability_free_linear_only(django_user_model):
    user = django_user_model.objects.create_user(
        username="fa_free@example.com", password="x"
    )
    _set_tier(user, "free")
    avail = get_feature_availability(user)
    assert avail["layouts"]["linear_only"] is True
    assert "diary" not in avail["layouts"]["allowed"]


@pytest.mark.django_db
def test_feature_availability_pro_includes_diary(django_user_model):
    user = django_user_model.objects.create_user(
        username="fa_pro@example.com", password="x"
    )
    _set_tier(user, "pro")
    avail = get_feature_availability(user)
    assert avail["layouts"]["linear_only"] is False
    assert "diary" in avail["layouts"]["allowed"]
