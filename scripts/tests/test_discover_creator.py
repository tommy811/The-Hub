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

    def test_raises_empty_dataset_when_apify_returns_all_null_fields(self):
        # Apify sometimes returns 1 item with null bio/followers/externalUrls
        # (observed for ariaxswan during 2026-04-24 smoke test). Treat same as
        # 0-item response: fail fast so the run is marked failed, not silently
        # committed with a blank profile.
        from apify_details import EmptyDatasetError
        empty_ctx = InputContext(handle="x", platform="instagram")
        assert empty_ctx.is_empty() is True  # sanity
        with patch("discover_creator.fetch_instagram_details", return_value=empty_ctx), \
             patch("discover_creator.get_apify_client"):
            with pytest.raises(EmptyDatasetError) as exc:
                dc.fetch_input_context(_make_input(handle="x"))
        assert "x" in str(exc.value)


class TestUpdateProfileFromContext:
    def test_writes_non_null_ctx_fields_to_primary_profile(self):
        fake_sb = MagicMock()
        ctx = InputContext(
            handle="gothgirlnatalie", platform="instagram",
            display_name="Natalie Vox",
            bio="21 • Florida",
            follower_count=630000,
            following_count=33,
            post_count=213,
            avatar_url="https://cdn.ig/pic_hd.jpg",
            is_verified=False,
        )
        ws_id = uuid4()
        dc._update_profile_from_context(fake_sb, ws_id, ctx)

        # .table(...).update(...).eq(...).eq(...).eq(...).execute()
        fake_sb.table.assert_called_with("profiles")
        update_call = fake_sb.table.return_value.update
        update_call.assert_called_once()
        payload = update_call.call_args.args[0]
        assert payload["bio"] == "21 • Florida"
        assert payload["follower_count"] == 630000
        assert payload["following_count"] == 33
        assert payload["post_count"] == 213
        assert payload["avatar_url"] == "https://cdn.ig/pic_hd.jpg"
        assert payload["display_name"] == "Natalie Vox"
        assert "last_scraped_at" in payload

    def test_noop_when_ctx_has_no_fields(self):
        fake_sb = MagicMock()
        ctx = InputContext(handle="x", platform="instagram")  # all default/null
        dc._update_profile_from_context(fake_sb, uuid4(), ctx)
        fake_sb.table.assert_not_called()

    def test_skips_null_fields(self):
        fake_sb = MagicMock()
        ctx = InputContext(
            handle="x", platform="instagram",
            bio="hi",  # only bio populated
        )
        dc._update_profile_from_context(fake_sb, uuid4(), ctx)
        payload = fake_sb.table.return_value.update.call_args.args[0]
        assert "bio" in payload
        assert "follower_count" not in payload  # was None
        assert "avatar_url" not in payload


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
        mark_failed_call = next(c for c in fake_sb.rpc.call_args_list if c.args[0] == "mark_discovery_failed")
        assert mark_failed_call.args[1]["p_error"].startswith("empty_context:")


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
        line = (tmp_path / "deadletter.jsonl").read_text().strip()
        parsed = json.loads(line)
        assert parsed["run_id"] == str(run_id)
        assert parsed["error"] == "the error"
