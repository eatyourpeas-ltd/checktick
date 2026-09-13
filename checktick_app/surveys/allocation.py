"""RCT arm allocation algorithms.

Pure, deterministic functions used by ``_assign_arm_for_progress`` in
``views.py``. Kept separate from the runtime pipeline so a future Delphi
round allocator can sit next to it without touching RCT (see
docs/survey-layouts-technical.md §Randomised (RCT) layout §Delphi
compatibility).

Two strategies (``RandomisedMenu.AllocationStrategy``):

- ``balanced`` — permuted blocks of size ``sum(ratios)``. Each block is a
  permutation of the arms repeated by their ratios; the permutation is
  deterministic from ``(seed, block_index)``. The participant is assigned
  the arm at position ``allocation_count % block_size`` within block
  ``allocation_count // block_size``. This keeps arm counts close to the
  ratios across consecutive assignments.
- ``simple`` — a single weighted random draw per participant,
  deterministic from ``seed`` alone.

All functions accept a ``seed`` (int) and return a deterministic result.
``random.Random`` is used with a local instance so the global RNG is not
perturbed — important in a web request where other code may rely on it.
"""

from __future__ import annotations

import random
from typing import Sequence

# Upper bound for system-generated seeds (2**63 - 1, matching a signed
# BigIntegerField). Used by the wrapper in views.py; exported here so the
# tests and the wrapper share the same constant.
MAX_SEED = (2**63) - 1


def _build_block(
    arms: Sequence, ratios: Sequence[int], block_index: int, seed: int
) -> list:
    """Build a permuted block for ``balanced`` allocation.

    The block contains each arm repeated ``ratios[i]`` times, then shuffled
    deterministically with a seed derived from ``(seed, block_index)`` so
    successive blocks differ but the whole sequence is reproducible from
    the menu seed.
    """
    block: list = []
    for arm, ratio in zip(arms, ratios):
        block.extend([arm] * max(0, int(ratio)))
    if not block:
        # Degenerate: every ratio is zero. Fall back to one slot per arm
        # so the survey is still runnable; the warnings step flags this.
        block = list(arms)
    rng = random.Random(seed + block_index)
    rng.shuffle(block)
    return block


def balanced_pick(
    arms: Sequence,
    ratios: Sequence[int],
    seed: int,
    allocation_count: int,
):
    """Return the arm at ``allocation_count`` for balanced (blocked) allocation.

    Deterministic from ``(seed, allocation_count)``. ``arms`` and
    ``ratios`` must be the same length; ``allocation_count`` is the
    number of assignments already made for this survey (0 for the first
    participant). Block size is ``sum(ratios)`` (or ``len(arms)`` if all
    ratios are zero).
    """
    if not arms:
        raise ValueError("balanced_pick requires at least one arm")
    block_size = sum(int(r) for r in ratios) or len(arms)
    block_index, position = divmod(int(allocation_count), block_size)
    block = _build_block(arms, ratios, block_index, seed)
    return block[position]


def simple_pick(arms: Sequence, ratios: Sequence[int], seed: int):
    """Return a weighted random arm for ``simple`` allocation.

    Deterministic from ``seed`` alone. ``allocation_count`` is not used:
    each participant draws independently. With a fixed menu seed this
    would assign every participant to the same arm — real trials leave
    ``RandomisedMenu.seed`` blank so the per-participant
    ``SurveyProgress.randomisation_seed`` drives the draw.
    """
    if not arms:
        raise ValueError("simple_pick requires at least one arm")
    weights = [max(1, int(r) or 1) for r in ratios]
    rng = random.Random(seed)
    return rng.choices(arms, weights=weights, k=1)[0]


def pick_arm(
    arms: Sequence,
    ratios: Sequence[int],
    strategy: str,
    seed: int,
    allocation_count: int = 0,
):
    """Dispatch to the configured strategy.

    ``strategy`` is one of ``RandomisedMenu.AllocationStrategy`` values
    (``"balanced"`` or ``"simple"``). Unknown strategies fall back to
    ``balanced``.
    """
    if strategy == "simple":
        return simple_pick(arms, ratios, seed)
    return balanced_pick(arms, ratios, seed, allocation_count)
