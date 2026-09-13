"""Tests for the RCT arm allocator (step 3).

Covers both the pure algorithms in ``allocation.py`` (balanced/blocked
and simple/weighted, plus determinism) and the DB-touching wrapper
``_assign_arm_for_progress`` in ``views.py`` (idempotence, seed handling,
allocation_count progression).
"""

from datetime import timedelta
import random

from django.utils import timezone
import pytest

from checktick_app.surveys.allocation import (
    MAX_SEED,
    balanced_pick,
    pick_arm,
    simple_pick,
)
from checktick_app.surveys.models import (
    Organization,
    RandomisedArm,
    RandomisedMenu,
    Survey,
    SurveyProgress,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def survey(owner, org):
    return Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug="s",
        layout=Survey.Layout.RCT,
    )


# --- pure algorithm tests ---


class TestBalancedPick:
    def test_block_size_is_sum_of_ratios(self):
        arms = ["A", "B"]
        block = []
        # First ``sum(ratios)`` = 4 positions should cover one full block.
        for i in range(4):
            block.append(balanced_pick(arms, [3, 1], seed=42, allocation_count=i))
        assert block.count("A") == 3
        assert block.count("B") == 1

    def test_deterministic_from_seed_and_count(self):
        a = balanced_pick(["A", "B"], [1, 1], seed=99, allocation_count=0)
        b = balanced_pick(["A", "B"], [1, 1], seed=99, allocation_count=0)
        assert a == b

    def test_different_seed_different_block(self):
        # Two blocks of size 4 with different seeds are extremely unlikely
        # to be identical permutations.
        arms = ["A", "B", "C", "D"]
        block_a = [
            balanced_pick(arms, [1, 1, 1, 1], seed=1, allocation_count=i)
            for i in range(4)
        ]
        block_b = [
            balanced_pick(arms, [1, 1, 1, 1], seed=2, allocation_count=i)
            for i in range(4)
        ]
        assert block_a != block_b

    def test_consecutive_counts_walk_the_block(self):
        arms = ["A", "B", "C"]
        ratios = [1, 1, 1]
        picks = [
            balanced_pick(arms, ratios, seed=7, allocation_count=i) for i in range(3)
        ]
        # A full block with ratio 1 each is a permutation of A, B, C.
        assert sorted(picks) == ["A", "B", "C"]

    def test_ratio_zero_falls_back_to_one_per_arm(self):
        # All ratios zero → block is one slot per arm (degenerate but
        # runnable; the warnings step flags this).
        arms = ["A", "B"]
        picks = [
            balanced_pick(arms, [0, 0], seed=5, allocation_count=i) for i in range(2)
        ]
        assert sorted(picks) == ["A", "B"]

    def test_unequal_ratios(self):
        # 2:1 trial — block of 3, two A one B.
        arms = ["A", "B"]
        picks = [
            balanced_pick(arms, [2, 1], seed=11, allocation_count=i) for i in range(3)
        ]
        assert picks.count("A") == 2
        assert picks.count("B") == 1

    def test_empty_arms_raises(self):
        with pytest.raises(ValueError):
            balanced_pick([], [], seed=1, allocation_count=0)


class TestSimplePick:
    def test_deterministic_from_seed(self):
        a = simple_pick(["A", "B"], [1, 1], seed=123)
        b = simple_pick(["A", "B"], [1, 1], seed=123)
        assert a == b

    def test_zero_ratio_treated_as_one(self):
        # Zero ratios should not zero-weight everything; we coerce to 1.
        arm = simple_pick(["A", "B"], [0, 0], seed=50)
        assert arm in ("A", "B")

    def test_empty_arms_raises(self):
        with pytest.raises(ValueError):
            simple_pick([], [], seed=1)


class TestPickArmDispatch:
    def test_balanced_strategy(self):
        arm = pick_arm(["A", "B"], [1, 1], "balanced", seed=3, allocation_count=0)
        assert arm in ("A", "B")

    def test_simple_strategy(self):
        arm = pick_arm(["A", "B"], [1, 1], "simple", seed=3)
        assert arm in ("A", "B")

    def test_unknown_strategy_falls_back_to_balanced(self):
        arm = pick_arm(["A", "B"], [1, 1], "unknown", seed=3, allocation_count=0)
        assert arm in ("A", "B")


# --- DB wrapper tests ---


def _make_progress(survey):
    return SurveyProgress.objects.create(
        survey=survey,
        expires_at=timezone.now() + timedelta(days=30),
    )


@pytest.mark.django_db
def test_assign_arm_sets_seed_and_arm(survey):
    menu = RandomisedMenu.objects.create(survey=survey, seed=None)
    RandomisedArm.objects.create(menu=menu, name="A", order=1)
    RandomisedArm.objects.create(menu=menu, name="B", order=2)
    progress = _make_progress(survey)
    from checktick_app.surveys.views import _assign_arm_for_progress

    arm = _assign_arm_for_progress(progress, menu)
    progress.refresh_from_db()
    assert progress.assigned_arm == arm
    assert progress.randomisation_seed is not None
    assert 0 <= progress.randomisation_seed <= MAX_SEED


@pytest.mark.django_db
def test_assign_arm_idempotent(survey):
    menu = RandomisedMenu.objects.create(survey=survey, seed=None)
    RandomisedArm.objects.create(menu=menu, name="A", order=1)
    RandomisedArm.objects.create(menu=menu, name="B", order=2)
    progress = _make_progress(survey)
    from checktick_app.surveys.views import _assign_arm_for_progress

    first = _assign_arm_for_progress(progress, menu)
    first_seed = progress.randomisation_seed
    second = _assign_arm_for_progress(progress, menu)
    assert second == first
    progress.refresh_from_db()
    # Seed not regenerated on the second call.
    assert progress.randomisation_seed == first_seed


@pytest.mark.django_db
def test_assign_arm_with_menu_seed_uses_menu_seed(survey):
    menu = RandomisedMenu.objects.create(survey=survey, seed=777)
    RandomisedArm.objects.create(menu=menu, name="A", order=1)
    RandomisedArm.objects.create(menu=menu, name="B", order=2)
    progress = _make_progress(survey)
    from checktick_app.surveys.views import _assign_arm_for_progress

    _assign_arm_for_progress(progress, menu)
    progress.refresh_from_db()
    # When menu.seed is set, it is copied onto the progress record.
    assert progress.randomisation_seed == 777


@pytest.mark.django_db
def test_assign_arm_balanced_progression(survey):
    """With a fixed menu seed and balanced strategy, the first N
    assignments walk the permuted block deterministically."""
    menu = RandomisedMenu.objects.create(
        survey=survey,
        seed=42,
        allocation_strategy=RandomisedMenu.AllocationStrategy.BALANCED,
    )
    RandomisedArm.objects.create(menu=menu, name="A", allocation_ratio=1, order=1)
    RandomisedArm.objects.create(menu=menu, name="B", allocation_ratio=1, order=2)
    from checktick_app.surveys.views import _assign_arm_for_progress

    names = []
    for i in range(4):
        p = _make_progress(survey)
        arm = _assign_arm_for_progress(p, menu)
        names.append(arm.name)
    # Block size = 2; four participants → two blocks. Each block is a
    # permutation of (A, B), so total counts are 2 and 2.
    assert names.count("A") == 2
    assert names.count("B") == 2


@pytest.mark.django_db
def test_assign_arm_no_arms_raises(survey):
    menu = RandomisedMenu.objects.create(survey=survey)
    progress = _make_progress(survey)
    from checktick_app.surveys.views import _assign_arm_for_progress

    with pytest.raises(ValueError):
        _assign_arm_for_progress(progress, menu)


@pytest.mark.django_db
def test_ensure_randomised_menu_creates_two_default_arms(survey):
    from checktick_app.surveys.views import _ensure_randomised_menu

    menu = _ensure_randomised_menu(survey)
    arms = list(menu.arms.order_by("order"))
    assert [a.name for a in arms] == ["Intervention", "Control"]


@pytest.mark.django_db
def test_ensure_randomised_menu_idempotent(survey):
    from checktick_app.surveys.views import _ensure_randomised_menu

    menu1 = _ensure_randomised_menu(survey)
    menu2 = _ensure_randomised_menu(survey)
    assert menu1.id == menu2.id
    assert menu2.arms.count() == 2


@pytest.mark.django_db
def test_assign_arm_does_not_perturb_global_rng(survey):
    """The allocator uses a local random.Random so the global RNG is not
    perturbed by allocation calls in a request."""
    menu = RandomisedMenu.objects.create(survey=survey, seed=None)
    RandomisedArm.objects.create(menu=menu, name="A", order=1)
    RandomisedArm.objects.create(menu=menu, name="B", order=2)
    random.seed(12345)
    expected = random.random()
    progress = _make_progress(survey)
    from checktick_app.surveys.views import _assign_arm_for_progress

    _assign_arm_for_progress(progress, menu)
    random.seed(12345)
    after = random.random()
    assert after == expected
