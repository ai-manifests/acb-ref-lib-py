"""Habit memory discount — spec §7.

The default-v0 discount function is:

    habit_discount(d) = min(0.80, similarity(d, history) × stability(history))

A 100% discount would drive familiar decisions to zero cost and remove the
federation's incentive to keep checking, which is the analogue of the
brain's continued (cheap but non-zero) attention to habitual stimuli. The
0.80 cap preserves attention.
"""
from __future__ import annotations
from dataclasses import dataclass


MAX_HABIT_DISCOUNT = 0.80


@dataclass(frozen=True)
class HistoricalDeliberation:
    """A prior deliberation considered by the habit-memory function.

    Implementations supply their own similarity function (string match,
    embedding distance, structured action match) and pass per-prior
    similarity scores in [0, 1] alongside whether the prior's outcome
    was observed AND was successful.
    """
    similarity: float
    successful_outcome: bool


def compute_habit_discount(history: list[HistoricalDeliberation]) -> float:
    """Compute the habit discount for a deliberation given a list of similar
    prior deliberations. Returns a value in [0, MAX_HABIT_DISCOUNT]."""
    if not history:
        return 0.0

    weight_sum = sum(h.similarity for h in history)
    if weight_sum == 0:
        return 0.0

    # Stability is the success fraction weighted by similarity — a prior
    # that is barely similar contributes proportionally less.
    weighted_success = sum(h.similarity for h in history if h.successful_outcome)
    stability = weighted_success / weight_sum

    max_similarity = max(h.similarity for h in history)
    raw = max_similarity * stability
    return min(MAX_HABIT_DISCOUNT, raw)
