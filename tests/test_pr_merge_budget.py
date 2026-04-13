"""ACB spec §8 worked example as an executable test.

Same dlb_01HMXJ3E9R PR merge as ADJ §9, with a 12,000 EU budget posted, the
contested deliberation running for one round, the maximum habit discount
applying, and a 180 EU draw distributed across two substrate providers and
three agents per default-v0.
"""
from datetime import datetime
import math
from acb_manifest import (
    AcbEntryType,
    BudgetCommitted,
    BudgetCancelled,
    Denomination,
    PricingProfile,
    SettlementProfileConfig,
    SettlementMode,
    BudgetConstraints,
    BudgetState,
    Tally,
    Routine,
    TerminationState,
    HistoricalDeliberation,
    ParticipantContribution,
    SubstrateReport,
    SettlementInputs,
    InMemoryBudgetStore,
    compute_disagreement_magnitude,
    select_routine,
    compute_cheap_draw,
    compute_expensive_draw,
    compute_habit_discount,
    build_settlement_record,
    MAX_HABIT_DISCOUNT,
)


DLB = "dlb_01HMXJ3E9R"
BGT = "bgt_01HMXJ3E9R"
AUTHORITY = "did:requester:acme-platform"
TEST_RUNNER = "did:adp:test-runner-v2"
SCANNER = "did:adp:security-scanner-v3"
LINTER = "did:adp:style-linter-v1"

PRICING = PricingProfile(
    profile="default-v0",
    cheap_routine_rate=50,
    expensive_routine_rate=200,
    round_multiplier=1.5,
    unlock_threshold=0.30,
    habit_memory_discount="default-v0",
)

SETTLEMENT = SettlementProfileConfig(
    profile="default-v0",
    mode=SettlementMode.DEFERRED,
    substrate_share=0.20,
    epistemic_share=0.80,
    unspent_returns_to=AUTHORITY,
    outcome_window_seconds=604800,
)


def make_budget() -> BudgetCommitted:
    return BudgetCommitted(
        entry_id="adj_01HMXM9A",
        entry_type=AcbEntryType.BUDGET_COMMITTED,
        deliberation_id=DLB,
        timestamp=datetime(2026, 4, 11, 14, 30, 0),
        prior_entry_hash=None,
        budget_id=BGT,
        budget_authority=AUTHORITY,
        posted_at=datetime(2026, 4, 11, 14, 30, 0),
        denomination=Denomination(unit="EU", external_unit="USD", external_rate=0.0001),
        amount_total=12000,
        pricing=PRICING,
        settlement=SETTLEMENT,
        constraints=BudgetConstraints(max_participants=8, max_rounds=4, irrevocable=False),
        signature="ed25519:6f3a",
    )


def test_disagreement_magnitude_50_50_is_one():
    tally = Tally(0.71, 0.71, 0)
    assert math.isclose(compute_disagreement_magnitude(tally), 1.0)


def test_disagreement_magnitude_full_agreement_is_zero():
    tally = Tally(0.89, 0, 0.18)
    assert compute_disagreement_magnitude(tally) == 0.0


def test_disagreement_magnitude_total_abstention_is_one():
    tally = Tally(0, 0, 1.5)
    assert compute_disagreement_magnitude(tally) == 1.0


def test_low_signal_outlier_stays_under_threshold():
    tally = Tally(0.9, 0.1, 0)
    magnitude = compute_disagreement_magnitude(tally)
    assert magnitude < PRICING.unlock_threshold


def test_cheap_routine_on_agreement_no_rounds():
    tally = Tally(0.95, 0.05, 0)
    assert select_routine(PRICING, tally, 0, TerminationState.CONVERGED) is Routine.CHEAP


def test_expensive_routine_on_disagreement():
    tally = Tally(0.71, 0.64, 0.18)
    assert select_routine(PRICING, tally, 0, TerminationState.CONVERGED) is Routine.EXPENSIVE


def test_expensive_routine_when_rounds_run_even_with_low_magnitude():
    tally = Tally(0.95, 0.05, 0)
    assert select_routine(PRICING, tally, 1, TerminationState.CONVERGED) is Routine.EXPENSIVE


def test_expensive_routine_on_deadlock():
    tally = Tally(0.5, 0.5, 0)
    assert select_routine(PRICING, tally, 0, TerminationState.DEADLOCKED) is Routine.EXPENSIVE


def test_cheap_draw_matches_spec_4_3():
    assert compute_cheap_draw(PRICING, 3, 0) == 150


def test_cheap_draw_with_80_pct_discount():
    assert math.isclose(compute_cheap_draw(PRICING, 3, 0.80), 30, abs_tol=1e-6)


def test_expensive_draw_one_round_matches_spec():
    assert compute_expensive_draw(PRICING, 3, 1, 0) == 900


def test_expensive_draw_three_rounds_compounds():
    # 200 × 4 × 1.5^3 = 800 × 3.375 = 2700
    assert compute_expensive_draw(PRICING, 4, 3, 0) == 2700


def test_habit_discount_caps_at_080():
    history = [HistoricalDeliberation(1.0, True) for _ in range(100)]
    assert compute_habit_discount(history) == MAX_HABIT_DISCOUNT


def test_habit_discount_unstable_history_shrinks():
    history = [HistoricalDeliberation(0.9, i < 50) for i in range(100)]
    discount = compute_habit_discount(history)
    # 0.9 max similarity × 0.5 stability = 0.45
    assert math.isclose(discount, 0.45, abs_tol=0.01)


def test_habit_discount_zero_when_empty():
    assert compute_habit_discount([]) == 0.0


def test_full_spec_8_worked_example():
    budget = make_budget()
    initial_tally = Tally(0.71, 0.64, 0.18)
    round_count = 1

    magnitude = compute_disagreement_magnitude(initial_tally)
    assert magnitude > budget.pricing.unlock_threshold

    routine = select_routine(budget.pricing, initial_tally, round_count, TerminationState.CONVERGED)
    assert routine is Routine.EXPENSIVE

    history = [HistoricalDeliberation(0.85, i < 45) for i in range(47)]
    habit_discount = compute_habit_discount(history)
    assert habit_discount == MAX_HABIT_DISCOUNT

    draw = compute_expensive_draw(budget.pricing, 3, round_count, habit_discount)
    assert math.isclose(draw, 180, abs_tol=1e-6)


def test_settlement_record_returns_unspent_to_requester():
    budget = make_budget()
    draw_total = 180.0

    contributions = [
        ParticipantContribution(TEST_RUNNER, True, 2, True, 0.0196, False),
        ParticipantContribution(SCANNER, True, 1, False, 0.0441, False),
        ParticipantContribution(LINTER, True, 0, False, 0.1444, False),
    ]
    reports = [
        SubstrateReport("did:substrate:acme-cluster-eu", 200, "cluster/8821443"),
        SubstrateReport("did:substrate:openai-azure", 100, "openai/run-9912"),
    ]

    record = build_settlement_record(SettlementInputs(
        entry_id="adj_01HMZQ7K",
        deliberation_id=DLB,
        timestamp=datetime(2026, 4, 14, 9, 30, 0),
        prior_entry_hash=None,
        budget_id=BGT,
        amount_total=budget.amount_total,
        draw_total=draw_total,
        settlement=budget.settlement,
        contributions=contributions,
        substrate_reports=reports,
        habit_discount_applied=0.80,
        unlock_triggered=True,
        disagreement_magnitude_initial=0.948,
        outcome_referenced="adj_01HMZP2D",
        signature="ed25519:7a4b",
    ))

    assert record.amount_returned_to_requester == 11820
    assert record.draw_total == 180

    assert len(record.substrate_distributions) == 2
    assert record.substrate_distributions[0].amount == 24
    assert record.substrate_distributions[1].amount == 12

    sub_sum = sum(d.amount for d in record.substrate_distributions)
    epi_sum = sum(d.amount for d in record.epistemic_distributions)
    assert abs(sub_sum + epi_sum - draw_total) < 0.5

    tr = next(d for d in record.epistemic_distributions if d.recipient == TEST_RUNNER)
    lt = next(d for d in record.epistemic_distributions if d.recipient == LINTER)
    assert tr.amount > lt.amount


def test_store_tracks_lifecycle_states():
    store = InMemoryBudgetStore()
    store.append(make_budget())
    assert store.get_budget_state(BGT) is BudgetState.ACTIVE

    settlement = build_settlement_record(SettlementInputs(
        entry_id="adj_01HMZQ7K",
        deliberation_id=DLB,
        timestamp=datetime(2026, 4, 14, 9, 30, 0),
        prior_entry_hash=None,
        budget_id=BGT,
        amount_total=12000,
        draw_total=150,
        settlement=SETTLEMENT,
        contributions=[
            ParticipantContribution(TEST_RUNNER, True, 0, True, 0.05, False),
        ],
        substrate_reports=[],
        habit_discount_applied=0,
        unlock_triggered=False,
        disagreement_magnitude_initial=0.1,
        outcome_referenced=None,
        signature="ed25519:7a4b",
    ))
    store.append(settlement)
    assert store.get_budget_state(BGT) is BudgetState.SETTLED
    assert store.get_settlement_for_deliberation(DLB) is not None


def test_cancellation_locks_budget():
    store = InMemoryBudgetStore()
    store.append(BudgetCancelled(
        entry_id="adj_cancel",
        entry_type=AcbEntryType.BUDGET_CANCELLED,
        deliberation_id=DLB,
        timestamp=datetime(2026, 4, 11, 14, 31, 0),
        prior_entry_hash=None,
        budget_id=BGT,
        budget_authority=AUTHORITY,
        reason="no longer needed",
        signature="ed25519:9c8d",
    ))
    store.append(make_budget())
    assert store.get_budget_state(BGT) is BudgetState.CANCELLED
