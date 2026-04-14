# acb-manifest

A Python reference implementation of the **Agent Cognitive Budget (ACB)** protocol — the metabolic-budget layer for deliberative multi-agent systems. ACB provides append-only journal entries, pricing models, habit-memory discounts, and settlement distribution that mirror the brain's resource allocation for routine vs. contested decisions.

This library is one of several reference implementations ([C#](https://git.marketally.com/ai-manifests/acb-ref-lib), [TypeScript](https://git.marketally.com/ai-manifests/acb-ref-lib-ts)) of the same spec. The spec itself is at [adp-manifest.dev](https://adp-manifest.dev) and is the source of truth; this library implements what the spec says.

Zero runtime dependencies. Requires Python 3.10+.

## Install

```bash
pip install acb-manifest
```

Or from source:

```bash
git clone https://git.marketally.com/ai-manifests/acb-ref-lib-py.git
cd acb-ref-lib-py
pip install -e .
```

## Quick example

```python
from acb_manifest import (
    InMemoryBudgetStore,
    Tally,
    TerminationState,
    Routine,
    compute_disagreement_magnitude,
    select_routine,
    compute_expensive_draw,
    build_settlement_record,
)

initial_tally = Tally(approve_weight=0.71, reject_weight=0.64, abstain_weight=0.18)
magnitude = compute_disagreement_magnitude(initial_tally)  # ≈ 0.948 (contested)

routine = select_routine(pricing_profile, initial_tally, round_count=1, termination=TerminationState.CONVERGED)
# routine == Routine.EXPENSIVE (unlock threshold exceeded)

draw = compute_expensive_draw(pricing_profile, participant_count=3, round_count=1, habit_discount=0.80)
# draw = 200 × 3 × 1.5^1 × (1 − 0.80) = 180 EU
```

## API

All public symbols are exported from the `acb_manifest` package root.

### Entry types

`AcbEntry`, `AcbEntryType`, `BudgetCommitted`, `BudgetCancelled`, `SettlementRecorded`

### Value types

`Denomination`, `PricingProfile`, `SettlementProfileConfig`, `SettlementMode`, `BudgetConstraints`, `SubstrateDistribution`, `EpistemicDistribution`, `ContributionBreakdown`, `Tally`, `HistoricalDeliberation`, `ParticipantContribution`, `SubstrateReport`, `SettlementInputs`, `BudgetState`

### Enums

`Routine`, `TerminationState`, `SettlementMode`

### Pricing

- `compute_disagreement_magnitude(tally)` — `1 − |approve − reject| / (approve + reject)`, in [0, 1]
- `select_routine(pricing, tally, round_count, termination)` — returns `Routine.CHEAP` when the decision is an agreed-on routine; `Routine.EXPENSIVE` when contested
- `compute_cheap_draw(pricing, participant_count, habit_discount=0.0)` — cheap-routine draw
- `compute_expensive_draw(pricing, participant_count, round_count, habit_discount=0.0)` — expensive-routine draw with round multiplier
- `compute_draw(pricing, tally, participant_count, round_count, termination, habit_discount=0.0)` — convenience wrapper that picks a routine and computes the draw
- `compute_habit_discount(history)` — habit-memory discount function, capped at `MAX_HABIT_DISCOUNT` (0.80)
- `MAX_HABIT_DISCOUNT` — exported constant

### Settlement

- `distribute_substrate(pool, reports)` — substrate pool distribution proportional to reported cycles
- `distribute_epistemic(pool, contributions)` — default-v0 epistemic scoring with the four equal-weight bonuses (base, falsification, load-bearing, outcome correctness) plus dissent-quality penalty
- `build_settlement_record(inputs)` — builds a complete `SettlementRecorded` entry from contributions and substrate reports

### Store

- `InMemoryBudgetStore` — thread-safe in-memory budget store suitable for tests and prototypes

## Testing

```bash
pip install -e .[dev]
pytest
```

## Spec

This library implements the Agent Cognitive Budget protocol specification. Read the spec at [adp-manifest.dev](https://adp-manifest.dev). If the spec and this library disagree, the spec is correct and this is a bug.

## License

Apache-2.0 — see [`LICENSE`](LICENSE) for the full license text and [`NOTICE`](NOTICE) for attribution.
