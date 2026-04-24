# scripts/tests/pipeline/test_classifier.py
import pytest
from unittest.mock import MagicMock, patch
from pipeline.classifier import classify, Classification


class TestClassifyRuleMatches:
    def test_onlyfans_returns_monetization(self):
        result = classify("https://onlyfans.com/alice", supabase=None)
        assert result.platform == "onlyfans"
        assert result.account_type == "monetization"
        assert result.reason.startswith("rule:")
        assert result.confidence == 1.0

    def test_instagram_returns_social(self):
        result = classify("https://instagram.com/alice", supabase=None)
        assert result.platform == "instagram"
        assert result.account_type == "social"

    def test_linktree_returns_link_in_bio(self):
        result = classify("https://linktr.ee/alice", supabase=None)
        assert result.account_type == "link_in_bio"


class TestClassifyLLMFallback:
    @patch("pipeline.classifier._classify_via_llm")
    def test_unknown_url_falls_through_to_llm(self, mock_llm):
        mock_llm.return_value = ("other", "monetization", 0.85, "gemini-2.5-flash")
        # Supabase mock so cache lookup misses + insert succeeds
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = None
        sb.table.return_value.upsert.return_value.execute.return_value = None

        result = classify("https://unknown-coaching-site.example/alice", supabase=sb)

        mock_llm.assert_called_once()
        assert result.platform == "other"
        assert result.account_type == "monetization"
        assert result.reason == "llm:high_confidence"
        assert result.confidence == 0.85

    @patch("pipeline.classifier._classify_via_llm")
    def test_llm_low_confidence_returns_other(self, mock_llm):
        mock_llm.return_value = ("other", "other", 0.5, "gemini-2.5-flash")
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = None
        sb.table.return_value.upsert.return_value.execute.return_value = None

        result = classify("https://weird.example/x", supabase=sb)

        assert result.platform == "other"
        assert result.account_type == "other"
        assert result.reason == "llm:low_confidence"

    def test_cache_hit_skips_llm(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = {
                "platform_guess": "patreon",
                "account_type_guess": "monetization",
                "confidence": 0.9,
                "model_version": "gemini-2.5-flash",
            }

        result = classify("https://cached.example/alice", supabase=sb)

        assert result.platform == "patreon"
        assert result.reason == "llm:cache_hit"

    @patch("pipeline.classifier._classify_via_llm")
    def test_llm_timeout_returns_other_other(self, mock_llm):
        mock_llm.side_effect = TimeoutError("gemini slow")
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = None

        result = classify("https://timeout.example/x", supabase=sb)

        assert result.platform == "other"
        assert result.account_type == "other"
        assert result.reason == "llm:timeout"
        assert result.confidence == 0.0


class TestClassifyNoSupabase:
    """When classifier is used without DB (e.g. unit tests), rule matches still work."""
    def test_rule_match_works_without_supabase(self):
        result = classify("https://onlyfans.com/alice", supabase=None)
        assert result.platform == "onlyfans"

    def test_unknown_url_without_supabase_returns_other_other(self):
        # No DB = no LLM call (classifier needs DB to cache guesses)
        result = classify("https://unknown.example/alice", supabase=None)
        assert result.platform == "other"
        assert result.account_type == "other"
        assert result.reason == "llm:no_cache_context"
