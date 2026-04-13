"""Budget store — the ACB query contract.

A BudgetStore is the ACB analogue of ADJ's JournalStore. It indexes
budget_committed, budget_cancelled, and settlement_recorded entries by
deliberation_id and by budget_id so deliberation runners and validators
can answer "what budget funds this deliberation" or "has this budget
been settled yet".
"""
from __future__ import annotations
from .entries import (
    AcbEntry,
    AcbEntryType,
    BudgetCancelled,
    BudgetCommitted,
    BudgetState,
    SettlementRecorded,
)


class InMemoryBudgetStore:
    """In-memory budget store. Append-only. Suitable for tests and prototypes.

    Production deployments will typically back a BudgetStore with the same
    SQLite/Postgres journal that stores ADJ entries — ACB entries follow
    the ADJ common envelope precisely so they share storage.
    """

    def __init__(self) -> None:
        self._entries: list[AcbEntry] = []

    def append(self, entry: AcbEntry) -> None:
        self._entries.append(entry)

    def append_range(self, entries: list[AcbEntry]) -> None:
        self._entries.extend(entries)

    def get_budget_for_deliberation(self, deliberation_id: str) -> BudgetCommitted | None:
        for e in self._entries:
            if isinstance(e, BudgetCommitted) and e.deliberation_id == deliberation_id:
                return e
        return None

    def get_settlement_for_deliberation(self, deliberation_id: str) -> SettlementRecorded | None:
        settlements = [
            e for e in self._entries
            if isinstance(e, SettlementRecorded) and e.deliberation_id == deliberation_id
        ]
        if not settlements:
            return None
        return max(settlements, key=lambda s: s.timestamp)

    def get_cancellation_for_deliberation(self, deliberation_id: str) -> BudgetCancelled | None:
        for e in self._entries:
            if isinstance(e, BudgetCancelled) and e.deliberation_id == deliberation_id:
                return e
        return None

    def get_budget_by_id(self, budget_id: str) -> BudgetCommitted | None:
        for e in self._entries:
            if isinstance(e, BudgetCommitted) and e.budget_id == budget_id:
                return e
        return None

    def get_budget_state(self, budget_id: str) -> BudgetState:
        budget = self.get_budget_by_id(budget_id)
        if budget is None:
            return BudgetState.POSTED

        for e in self._entries:
            if isinstance(e, BudgetCancelled) and e.budget_id == budget_id:
                return BudgetState.CANCELLED

        for e in self._entries:
            if isinstance(e, SettlementRecorded) and e.budget_id == budget_id:
                return BudgetState.SETTLED

        return BudgetState.ACTIVE

    def get_all_entries(self) -> list[AcbEntry]:
        return list(self._entries)
