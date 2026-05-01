import pytest
from pipeline.budget import BudgetTracker, BudgetExhaustedError


class TestBudgetTracker:
    def test_starts_at_zero(self):
        b = BudgetTracker(cap_cents=500)
        assert b.spent_cents == 0
        assert b.remaining_cents == 500

    def test_can_spend_within_cap(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("apify/instagram-scraper", 50)
        assert b.spent_cents == 50
        assert b.remaining_cents == 450

    def test_can_afford(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("x", 400)
        assert b.can_afford(50) is True
        assert b.can_afford(150) is False

    def test_raises_when_debit_exceeds_cap(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("x", 400)
        with pytest.raises(BudgetExhaustedError):
            b.debit("y", 150)

    def test_soft_warning_at_50_percent(self):
        warnings = []
        b = BudgetTracker(cap_cents=1000, on_warning=warnings.append)
        b.debit("x", 400)
        assert warnings == []
        b.debit("y", 150)
        # crossed 500 cents threshold (50%)
        assert any("50%" in w for w in warnings)

    def test_soft_warning_at_80_percent(self):
        warnings = []
        b = BudgetTracker(cap_cents=1000, on_warning=warnings.append)
        b.debit("x", 790)
        assert all("80%" not in w for w in warnings)
        b.debit("y", 20)
        assert any("80%" in w for w in warnings)

    def test_tracks_per_actor(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("apify/instagram-scraper", 40)
        b.debit("apify/instagram-scraper", 30)
        b.debit("clockworks/tiktok-scraper", 50)
        assert b.spent_by_actor == {
            "apify/instagram-scraper": 70,
            "clockworks/tiktok-scraper": 50,
        }
