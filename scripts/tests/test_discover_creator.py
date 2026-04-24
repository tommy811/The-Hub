# scripts/tests/test_discover_creator.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from schemas import DiscoveryInput, InputContext
import discover_creator as dc


def _make_input(platform: str = "instagram", handle: str = "gothgirlnatalie") -> DiscoveryInput:
    return DiscoveryInput(
        run_id=uuid4(),
        creator_id=uuid4(),
        workspace_id=uuid4(),
        input_handle=handle,
        input_url=None,
        input_platform_hint=platform,
    )


class TestFetchInputContext:
    def test_instagram_route_calls_ig_fetcher(self):
        expected = InputContext(handle="x", platform="instagram", bio="hi")
        with patch("discover_creator.fetch_instagram_details", return_value=expected) as mock_ig, \
             patch("discover_creator.fetch_tiktok_details") as mock_tt, \
             patch("discover_creator.get_apify_client"):
            ctx = dc.fetch_input_context(_make_input(platform="instagram", handle="x"))
        mock_ig.assert_called_once()
        mock_tt.assert_not_called()
        assert ctx.bio == "hi"

    def test_tiktok_route_calls_tt_fetcher(self):
        expected = InputContext(handle="y", platform="tiktok", bio="hello")
        with patch("discover_creator.fetch_tiktok_details", return_value=expected) as mock_tt, \
             patch("discover_creator.fetch_instagram_details") as mock_ig, \
             patch("discover_creator.get_apify_client"):
            ctx = dc.fetch_input_context(_make_input(platform="tiktok", handle="y"))
        mock_tt.assert_called_once()
        mock_ig.assert_not_called()

    def test_empty_dataset_propagates(self):
        from apify_details import EmptyDatasetError
        with patch("discover_creator.fetch_instagram_details",
                   side_effect=EmptyDatasetError("login wall")), \
             patch("discover_creator.get_apify_client"):
            with pytest.raises(EmptyDatasetError):
                dc.fetch_input_context(_make_input())

    def test_resolves_aggregator_urls_in_external_urls(self):
        ctx = InputContext(
            handle="x", platform="instagram",
            bio="goth",
            external_urls=["https://linktr.ee/x", "https://direct.site/x"],
        )
        with patch("discover_creator.fetch_instagram_details", return_value=ctx), \
             patch("discover_creator.resolve_link_in_bio",
                   return_value=["https://onlyfans.com/x"]) as mock_resolve, \
             patch("discover_creator.get_apify_client"):
            result_ctx = dc.fetch_input_context(_make_input())
        # Only the aggregator URL should be handed to resolve_link_in_bio
        mock_resolve.assert_called_once_with("https://linktr.ee/x")
        assert "https://onlyfans.com/x" in result_ctx.link_in_bio_destinations


class TestGeminiPromptGrounding:
    def test_prompt_includes_bio_follower_and_external_urls(self):
        ctx = InputContext(
            handle="gothgirlnatalie", platform="instagram",
            bio="goth girl", follower_count=48200,
            external_urls=["https://linktr.ee/gothgirlnatalie"],
            link_in_bio_destinations=["https://onlyfans.com/gothgirlnatalie"],
            source_note="apify/instagram-scraper details mode",
        )
        prompt = dc.build_prompt(ctx)
        assert "goth girl" in prompt
        assert "48200" in prompt or "48,200" in prompt
        assert "linktr.ee/gothgirlnatalie" in prompt
        assert "onlyfans.com/gothgirlnatalie" in prompt
        # Grounding instruction present
        assert "provided context" in prompt.lower() or "do not hallucinate" in prompt.lower()


class TestRunEmptyContextFailsFast:
    def test_empty_context_triggers_mark_failed(self):
        from apify_details import EmptyDatasetError

        fake_sb = MagicMock()
        fake_sb.rpc.return_value.execute.return_value = None

        with patch("discover_creator.get_supabase", return_value=fake_sb), \
             patch("discover_creator.fetch_input_context",
                   side_effect=EmptyDatasetError("login wall")), \
             patch("discover_creator.run_gemini_discovery") as mock_gemini:
            dc.run(_make_input())

        # Gemini never called — we bailed before it
        mock_gemini.assert_not_called()
        # mark_discovery_failed was invoked
        called_rpc_names = [c.args[0] for c in fake_sb.rpc.call_args_list]
        assert "mark_discovery_failed" in called_rpc_names


class TestMarkDiscoveryFailedRetries:
    def test_retries_on_transient_failure(self):
        fake_sb = MagicMock()
        # First 2 calls raise, third succeeds
        fake_sb.rpc.return_value.execute.side_effect = [
            Exception("transient"),
            Exception("transient"),
            MagicMock(),
        ]
        with patch("discover_creator.get_supabase", return_value=fake_sb):
            dc.mark_discovery_failed_with_retry(fake_sb, uuid4(), "the error")
        # 3 total execute() calls means 2 retries + 1 success
        assert fake_sb.rpc.return_value.execute.call_count == 3

    def test_writes_dead_letter_after_exhausting_retries(self, tmp_path, monkeypatch):
        fake_sb = MagicMock()
        fake_sb.rpc.return_value.execute.side_effect = Exception("permanent")
        monkeypatch.setattr(dc, "DEAD_LETTER_PATH", tmp_path / "deadletter.jsonl")
        run_id = uuid4()
        with patch("discover_creator.get_supabase", return_value=fake_sb):
            dc.mark_discovery_failed_with_retry(fake_sb, run_id, "the error")
        contents = (tmp_path / "deadletter.jsonl").read_text()
        assert str(run_id) in contents
        assert "the error" in contents
