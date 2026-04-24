import json
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from replay_dead_letter import ReplayResult, replay_dead_letter


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _make_sb(lookup_rows: list[dict], insert_result=None) -> MagicMock:
    """Build a MagicMock Supabase client that supports:
    - sb.table("discovery_runs").select(...).in_(...).execute() → {.data: lookup_rows}
    - sb.table("discovery_runs").insert({...}).execute() → {.data: [{"id": ...}]}
    Differentiates lookup vs insert on whether .select or .insert was called.
    """
    sb = MagicMock()
    table = MagicMock()

    select_chain = MagicMock()
    select_chain.in_.return_value.execute.return_value = MagicMock(data=lookup_rows)
    table.select.return_value = select_chain

    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=insert_result or [{"id": str(uuid4())}])
    table.insert.return_value = insert_chain

    sb.table.return_value = table
    return sb


class TestReplayDeadLetter:
    def test_no_file_returns_empty_result(self, tmp_path):
        path = tmp_path / "missing.jsonl"
        sb = _make_sb([])
        result = replay_dead_letter(sb, path)
        assert result.replayed == 0
        assert result.skipped == 0
        sb.table.assert_not_called()

    def test_empty_file_returns_empty_result(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        sb = _make_sb([])
        result = replay_dead_letter(sb, path)
        assert result.replayed == 0

    def test_replays_each_entry_as_new_pending_run(self, tmp_path):
        path = tmp_path / "dl.jsonl"
        run_id_a = str(uuid4())
        run_id_b = str(uuid4())
        creator_a = str(uuid4())
        creator_b = str(uuid4())
        ws = str(uuid4())

        _write_jsonl(path, [
            {"run_id": run_id_a, "error": "supabase timeout"},
            {"run_id": run_id_b, "error": "supabase timeout"},
        ])

        lookup_rows = [
            {"id": run_id_a, "creator_id": creator_a, "workspace_id": ws,
             "input_handle": "alpha", "input_platform_hint": "instagram",
             "attempt_number": 2},
            {"id": run_id_b, "creator_id": creator_b, "workspace_id": ws,
             "input_handle": "beta", "input_platform_hint": "tiktok",
             "attempt_number": 1},
        ]
        sb = _make_sb(lookup_rows)

        result = replay_dead_letter(sb, path)

        assert result.replayed == 2
        assert result.skipped == 0
        # Two insert calls total
        insert_calls = sb.table.return_value.insert.call_args_list
        assert len(insert_calls) == 2
        payloads = [c.args[0] for c in insert_calls]
        handles = sorted(p["input_handle"] for p in payloads)
        assert handles == ["alpha", "beta"]
        # attempt_number bumped from prior
        for p in payloads:
            assert p["status"] == "pending"
            assert p["attempt_number"] >= 2

    def test_skips_entries_whose_original_run_cannot_be_found(self, tmp_path):
        path = tmp_path / "dl.jsonl"
        run_id = str(uuid4())
        _write_jsonl(path, [{"run_id": run_id, "error": "timeout"}])
        # Lookup returns nothing — original run gone
        sb = _make_sb([])

        result = replay_dead_letter(sb, path)
        assert result.replayed == 0
        assert result.skipped == 1
        sb.table.return_value.insert.assert_not_called()

    def test_truncates_file_on_full_success(self, tmp_path):
        path = tmp_path / "dl.jsonl"
        run_id = str(uuid4())
        creator_id = str(uuid4())
        ws = str(uuid4())
        _write_jsonl(path, [{"run_id": run_id, "error": "timeout"}])
        sb = _make_sb([{
            "id": run_id, "creator_id": creator_id, "workspace_id": ws,
            "input_handle": "x", "input_platform_hint": "instagram",
            "attempt_number": 1,
        }])

        result = replay_dead_letter(sb, path)
        assert result.replayed == 1
        # File still exists but is empty (truncated). Prefer truncate to delete
        # so the path stays stable for future writes.
        assert path.exists()
        assert path.read_text().strip() == ""

    def test_dry_run_does_not_insert(self, tmp_path):
        path = tmp_path / "dl.jsonl"
        run_id = str(uuid4())
        _write_jsonl(path, [{"run_id": run_id, "error": "x"}])
        sb = _make_sb([{
            "id": run_id, "creator_id": str(uuid4()), "workspace_id": str(uuid4()),
            "input_handle": "x", "input_platform_hint": "instagram",
            "attempt_number": 1,
        }])

        result = replay_dead_letter(sb, path, dry_run=True)
        assert result.replayed == 0
        assert result.would_replay == 1
        sb.table.return_value.insert.assert_not_called()
        # File untouched under dry run
        assert path.read_text().strip() != ""

    def test_preserves_file_on_partial_failure(self, tmp_path):
        # If any insert raises, do NOT truncate the file — the operator should
        # see what's unreplayed.
        path = tmp_path / "dl.jsonl"
        run_id = str(uuid4())
        _write_jsonl(path, [{"run_id": run_id, "error": "x"}])
        sb = _make_sb([{
            "id": run_id, "creator_id": str(uuid4()), "workspace_id": str(uuid4()),
            "input_handle": "x", "input_platform_hint": "instagram",
            "attempt_number": 1,
        }])
        sb.table.return_value.insert.return_value.execute.side_effect = Exception("db down")

        result = replay_dead_letter(sb, path)
        assert result.replayed == 0
        assert result.failed == 1
        # File preserved
        assert path.read_text().strip() != ""
