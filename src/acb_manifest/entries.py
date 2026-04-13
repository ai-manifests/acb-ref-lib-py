"""ACB entry types — extend the ADJ common envelope (spec §3.0) so they live
in the same journal as ADJ entries and inherit hash chaining, append-only
guarantees, and replay verification."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AcbEntryType(Enum):
    BUDGET_COMMITTED = "budget_committed"
    BUDGET_CANCELLED = "budget_cancelled"
    SETTLEMENT_RECORDED = "settlement_recorded"


class SettlementMode(Enum):
    IMMEDIATE = "immediate"
    DEFERRED = "deferred"
    TWO_PHASE = "two_phase"


class BudgetState(Enum):
    POSTED = "posted"
    ACTIVE = "active"
    AWAITING_OUTCOME = "awaiting_outcome"
    SETTLED = "settled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Denomination:
    unit: str = "EU"
    external_unit: str | None = None
    external_rate: float | None = None
    rate_source: str | None = None


@dataclass(frozen=True)
class PricingProfile:
    profile: str
    cheap_routine_rate: float
    expensive_routine_rate: float
    round_multiplier: float
    unlock_threshold: float
    habit_memory_discount: str | None = None


@dataclass(frozen=True)
class SettlementProfileConfig:
    profile: str
    mode: SettlementMode
    substrate_share: float
    epistemic_share: float
    unspent_returns_to: str
    outcome_window_seconds: int | None = None


@dataclass(frozen=True)
class BudgetConstraints:
    max_participants: int | None = None
    max_rounds: int | None = None
    irrevocable: bool = False


@dataclass(frozen=True)
class SubstrateDistribution:
    recipient: str
    amount: float
    basis: str
    report_ref: str | None = None


@dataclass(frozen=True)
class ContributionBreakdown:
    base_share: float
    falsification_bonus: float
    load_bearing_bonus: float
    outcome_correctness_bonus: float
    dissent_quality_penalty: float


@dataclass(frozen=True)
class EpistemicDistribution:
    recipient: str
    amount: float
    contribution_breakdown: ContributionBreakdown | None = None


@dataclass(frozen=True)
class AcbEntry:
    """Common envelope. Mirrors ADJ §3.0."""
    entry_id: str
    entry_type: AcbEntryType
    deliberation_id: str
    timestamp: datetime
    prior_entry_hash: str | None = None


@dataclass(frozen=True)
class BudgetCommitted(AcbEntry):
    budget_id: str = ""
    budget_authority: str = ""
    posted_at: datetime | None = None
    denomination: Denomination = field(default_factory=Denomination)
    amount_total: float = 0.0
    pricing: PricingProfile | None = None
    settlement: SettlementProfileConfig | None = None
    constraints: BudgetConstraints | None = None
    signature: str = ""

    def __post_init__(self):
        object.__setattr__(self, "entry_type", AcbEntryType.BUDGET_COMMITTED)


@dataclass(frozen=True)
class BudgetCancelled(AcbEntry):
    budget_id: str = ""
    budget_authority: str = ""
    reason: str = ""
    signature: str = ""

    def __post_init__(self):
        object.__setattr__(self, "entry_type", AcbEntryType.BUDGET_CANCELLED)


@dataclass(frozen=True)
class SettlementRecorded(AcbEntry):
    budget_id: str = ""
    settlement_profile: str = "default-v0"
    outcome_referenced: str | None = None
    draw_total: float = 0.0
    amount_total: float = 0.0
    amount_returned_to_requester: float = 0.0
    substrate_distributions: tuple[SubstrateDistribution, ...] = ()
    epistemic_distributions: tuple[EpistemicDistribution, ...] = ()
    habit_discount_applied: float = 0.0
    unlock_triggered: bool = False
    disagreement_magnitude_initial: float = 0.0
    signature: str = ""

    def __post_init__(self):
        object.__setattr__(self, "entry_type", AcbEntryType.SETTLEMENT_RECORDED)
