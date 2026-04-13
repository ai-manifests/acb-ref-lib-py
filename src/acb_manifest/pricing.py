"""Pricing model — spec §4 and §5.

The unlock signal is disagreement magnitude, computed mechanically from a
weighted tally:

    magnitude = 1 − |approve − reject| / (approve + reject)

If non_abstaining_weight is 0, magnitude is defined as 1.0 (total abstention
is treated as maximal disagreement: the cheap routine has failed to find
anyone willing to commit).
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .entries import PricingProfile


class Routine(Enum):
    CHEAP = "cheap"
    EXPENSIVE = "expensive"


class TerminationState(Enum):
    CONVERGED = "converged"
    PARTIAL_COMMIT = "partial_commit"
    DEADLOCKED = "deadlocked"


@dataclass(frozen=True)
class Tally:
    approve_weight: float
    reject_weight: float
    abstain_weight: float


def compute_disagreement_magnitude(tally: Tally) -> float:
    """Compute disagreement magnitude from a weighted tally. Spec §5.1."""
    non_abstaining = tally.approve_weight + tally.reject_weight
    if non_abstaining == 0:
        return 1.0
    return 1.0 - abs(tally.approve_weight - tally.reject_weight) / non_abstaining


def select_routine(
    pricing: PricingProfile,
    initial_tally: Tally,
    round_count: int,
    termination: TerminationState,
) -> Routine:
    """Decide which routine applies. Spec §4.1 / §4.2 / §5.2.

    Cheap routine MUST apply when ALL of:
      - round_count == 0
      - disagreement_magnitude(initial_tally) < pricing.unlock_threshold
      - termination == CONVERGED

    Expensive routine MUST apply when ANY of:
      - disagreement_magnitude(initial_tally) >= pricing.unlock_threshold
      - round_count > 0
      - termination is PARTIAL_COMMIT or DEADLOCKED
    """
    if round_count > 0:
        return Routine.EXPENSIVE
    if termination is not TerminationState.CONVERGED:
        return Routine.EXPENSIVE
    magnitude = compute_disagreement_magnitude(initial_tally)
    if magnitude >= pricing.unlock_threshold:
        return Routine.EXPENSIVE
    return Routine.CHEAP


def compute_cheap_draw(
    pricing: PricingProfile,
    participant_count: int,
    habit_discount: float = 0.0,
) -> float:
    """Cheap-routine draw. Spec §4.1.

        draw = cheap_routine_rate × participant_count × (1 − habit_discount)
    """
    return pricing.cheap_routine_rate * participant_count * (1.0 - habit_discount)


def compute_expensive_draw(
    pricing: PricingProfile,
    participant_count: int,
    round_count: int,
    habit_discount: float = 0.0,
) -> float:
    """Expensive-routine draw. Spec §4.2.

        draw = expensive_routine_rate × participant_count
             × round_multiplier^round_count
             × (1 − habit_discount)

    The exponential round multiplier reflects that each additional
    belief-update round addresses, by selection, the disagreement the
    prior round failed to resolve — the remaining work is harder.
    """
    base = pricing.expensive_routine_rate * participant_count
    return base * (pricing.round_multiplier ** round_count) * (1.0 - habit_discount)


def compute_draw(
    pricing: PricingProfile,
    routine: Routine,
    participant_count: int,
    round_count: int,
    habit_discount: float = 0.0,
) -> float:
    """Convenience wrapper around the two routine helpers."""
    if routine is Routine.CHEAP:
        return compute_cheap_draw(pricing, participant_count, habit_discount)
    return compute_expensive_draw(pricing, participant_count, round_count, habit_discount)
