"""Settlement — spec §6.

Distributes a draw across substrate providers and agent identities by their
journal-evidenced contribution. ACB v0 ships the `default-v0` profile with
four equal-weight epistemic bonus categories:

  - base_share         (25%)  — equal across all participants
  - falsification_bonus (25%) — proportional to acknowledged falsifications
  - load_bearing_bonus  (25%) — equal across load-bearing voters
  - outcome_correctness_bonus (25%) — inverse Brier delta when outcome known

Plus a dissent_quality_penalty that subtracts up to 25% of a flagged
agent's pre-penalty total and redistributes it to non-flagged agents.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime
from .entries import (
    AcbEntryType,
    ContributionBreakdown,
    EpistemicDistribution,
    SettlementProfileConfig,
    SettlementRecorded,
    SubstrateDistribution,
)


@dataclass(frozen=True)
class ParticipantContribution:
    agent_id: str
    participated: bool
    acknowledged_falsifications: int
    load_bearing: bool
    outcome_brier_delta: float | None
    dissent_quality_flagged: bool


@dataclass(frozen=True)
class SubstrateReport:
    recipient: str
    cycles: float
    report_ref: str | None = None


def _round2(n: float) -> float:
    return round(n * 100) / 100


def distribute_substrate(
    pool: float,
    reports: list[SubstrateReport],
) -> tuple[SubstrateDistribution, ...]:
    """Distribute the substrate share proportional to reported cycles. Spec §6.3."""
    if not reports:
        return ()
    total_cycles = sum(r.cycles for r in reports)
    if total_cycles == 0:
        return ()
    return tuple(
        SubstrateDistribution(
            recipient=r.recipient,
            amount=_round2(pool * r.cycles / total_cycles),
            basis="cycles",
            report_ref=r.report_ref,
        )
        for r in reports
    )


def distribute_epistemic(
    pool: float,
    contributions: list[ParticipantContribution],
) -> tuple[EpistemicDistribution, ...]:
    """Distribute the epistemic share by `default-v0` contribution scoring."""
    participants = [c for c in contributions if c.participated]
    if not participants:
        return ()

    per_bonus = pool / 4.0
    equal_share = per_bonus / len(participants)

    # Base share — equal across all participants
    base_share = equal_share

    # Falsification bonus — proportional to acknowledged falsifications.
    # If nobody acknowledged any falsification, the pool distributes equally
    # so its share is not lost.
    total_falsifications = sum(c.acknowledged_falsifications for c in participants)

    def falsification_for(c: ParticipantContribution) -> float:
        if total_falsifications == 0:
            return equal_share
        return per_bonus * c.acknowledged_falsifications / total_falsifications

    # Load-bearing bonus — equal across load-bearing agents. If nobody is
    # load-bearing, the pool distributes equally across all participants.
    load_bearing_count = sum(1 for c in participants if c.load_bearing)

    def load_bearing_for(c: ParticipantContribution) -> float:
        if load_bearing_count == 0:
            return equal_share
        if not c.load_bearing:
            return 0.0
        return per_bonus / load_bearing_count

    # Outcome correctness — inverse Brier delta, normalized. If no
    # outcomes are reported, the pool distributes equally.
    with_outcomes = [c for c in participants if c.outcome_brier_delta is not None]
    total_inverse = sum(1.0 - (c.outcome_brier_delta or 0.0) for c in with_outcomes)

    def outcome_for(c: ParticipantContribution) -> float:
        if not with_outcomes or total_inverse == 0:
            return equal_share
        if c.outcome_brier_delta is None:
            return 0.0
        return per_bonus * (1.0 - c.outcome_brier_delta) / total_inverse

    pre_records = []
    for c in participants:
        breakdown = ContributionBreakdown(
            base_share=base_share,
            falsification_bonus=falsification_for(c),
            load_bearing_bonus=load_bearing_for(c),
            outcome_correctness_bonus=outcome_for(c),
            dissent_quality_penalty=0.0,
        )
        pre_total = (
            breakdown.base_share
            + breakdown.falsification_bonus
            + breakdown.load_bearing_bonus
            + breakdown.outcome_correctness_bonus
        )
        pre_records.append({
            "agent": c.agent_id,
            "breakdown": breakdown,
            "pre_total": pre_total,
            "flagged": c.dissent_quality_flagged,
        })

    # Dissent-quality penalty — up to 25% of pre-total, redistributed
    flagged_recovered = 0.0
    for rec in pre_records:
        if rec["flagged"]:
            penalty = rec["pre_total"] * 0.25
            rec["breakdown"] = replace(rec["breakdown"], dissent_quality_penalty=penalty)
            flagged_recovered += penalty

    if flagged_recovered > 0:
        non_flagged = [r for r in pre_records if not r["flagged"]]
        non_flagged_total = sum(r["pre_total"] for r in non_flagged)
        if non_flagged_total > 0:
            for rec in non_flagged:
                share = flagged_recovered * rec["pre_total"] / non_flagged_total
                rec["breakdown"] = replace(
                    rec["breakdown"],
                    base_share=rec["breakdown"].base_share + share,
                )

    distributions = []
    for rec in pre_records:
        b = rec["breakdown"]
        amount = (
            b.base_share
            + b.falsification_bonus
            + b.load_bearing_bonus
            + b.outcome_correctness_bonus
            - b.dissent_quality_penalty
        )
        distributions.append(EpistemicDistribution(
            recipient=rec["agent"],
            amount=_round2(amount),
            contribution_breakdown=ContributionBreakdown(
                base_share=_round2(b.base_share),
                falsification_bonus=_round2(b.falsification_bonus),
                load_bearing_bonus=_round2(b.load_bearing_bonus),
                outcome_correctness_bonus=_round2(b.outcome_correctness_bonus),
                dissent_quality_penalty=_round2(b.dissent_quality_penalty),
            ),
        ))

    return tuple(distributions)


@dataclass(frozen=True)
class SettlementInputs:
    entry_id: str
    deliberation_id: str
    timestamp: datetime
    prior_entry_hash: str | None
    budget_id: str
    amount_total: float
    draw_total: float
    settlement: SettlementProfileConfig
    contributions: list[ParticipantContribution]
    substrate_reports: list[SubstrateReport]
    habit_discount_applied: float
    unlock_triggered: bool
    disagreement_magnitude_initial: float
    outcome_referenced: str | None
    signature: str


def build_settlement_record(inputs: SettlementInputs) -> SettlementRecorded:
    """Build a settlement_recorded entry by running the default-v0 distribution
    pipeline. The resulting record is auditable end-to-end via acb-validate."""
    substrate_pool = inputs.draw_total * inputs.settlement.substrate_share
    epistemic_pool = inputs.draw_total * inputs.settlement.epistemic_share

    substrate_distributions = distribute_substrate(substrate_pool, inputs.substrate_reports)
    if not substrate_distributions and substrate_pool > 0:
        # Spec §6.3: if no substrate reports, fold into epistemic pool.
        epistemic_pool += substrate_pool
        substrate_pool = 0.0
        substrate_distributions = ()

    epistemic_distributions = distribute_epistemic(epistemic_pool, inputs.contributions)

    return SettlementRecorded(
        entry_id=inputs.entry_id,
        entry_type=AcbEntryType.SETTLEMENT_RECORDED,
        deliberation_id=inputs.deliberation_id,
        timestamp=inputs.timestamp,
        prior_entry_hash=inputs.prior_entry_hash,
        budget_id=inputs.budget_id,
        settlement_profile=inputs.settlement.profile,
        outcome_referenced=inputs.outcome_referenced,
        draw_total=_round2(inputs.draw_total),
        amount_total=inputs.amount_total,
        amount_returned_to_requester=_round2(inputs.amount_total - inputs.draw_total),
        substrate_distributions=substrate_distributions,
        epistemic_distributions=epistemic_distributions,
        habit_discount_applied=inputs.habit_discount_applied,
        unlock_triggered=inputs.unlock_triggered,
        disagreement_magnitude_initial=inputs.disagreement_magnitude_initial,
        signature=inputs.signature,
    )
