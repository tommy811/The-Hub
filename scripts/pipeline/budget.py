# scripts/pipeline/budget.py — Per-bulk-import Apify spend tracker
from typing import Callable, Optional


class BudgetExhaustedError(RuntimeError):
    """Raised by BudgetTracker.debit() when a spend would exceed the cap."""


class BudgetTracker:
    """Tracks Apify actor spend in cents against a hard cap.

    Fires soft warnings at 50% and 80% via the on_warning callback. Raises
    BudgetExhaustedError when a debit would push spend over the cap.
    """

    def __init__(self, cap_cents: int, on_warning: Optional[Callable[[str], None]] = None):
        self.cap_cents = cap_cents
        self.spent_cents = 0
        self.spent_by_actor: dict[str, int] = {}
        self._on_warning = on_warning or (lambda _msg: None)
        self._warned_50 = False
        self._warned_80 = False

    @property
    def remaining_cents(self) -> int:
        return max(0, self.cap_cents - self.spent_cents)

    def can_afford(self, cents: int) -> bool:
        return self.spent_cents + cents <= self.cap_cents

    def debit(self, actor_id: str, cents: int) -> None:
        if self.spent_cents + cents > self.cap_cents:
            raise BudgetExhaustedError(
                f"Spend of {cents}¢ on {actor_id} would exceed cap "
                f"(already spent {self.spent_cents}¢ of {self.cap_cents}¢)"
            )
        self.spent_cents += cents
        self.spent_by_actor[actor_id] = self.spent_by_actor.get(actor_id, 0) + cents

        pct = self.spent_cents / self.cap_cents * 100
        if pct >= 50 and not self._warned_50:
            self._warned_50 = True
            self._on_warning(f"[budget] crossed 50% ({self.spent_cents}¢ of {self.cap_cents}¢)")
        if pct >= 80 and not self._warned_80:
            self._warned_80 = True
            self._on_warning(f"[budget] crossed 80% ({self.spent_cents}¢ of {self.cap_cents}¢)")
