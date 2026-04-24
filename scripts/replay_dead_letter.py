"""Replay dead-lettered discovery runs as new pending runs.

When `mark_discovery_failed` exhausts its tenacity retries, `discover_creator`
appends an entry `{"run_id": ..., "error": ...}` to `DEAD_LETTER_PATH`
(default: `scripts/discovery_dead_letter.jsonl`).

This script reads that file, looks up each original `discovery_runs` row, and
inserts a new pending run with the same `creator_id`, `workspace_id`,
`input_handle`, and `input_platform_hint`, with `attempt_number` bumped. On
full success, the dead-letter file is truncated (kept at the same path so
future writes append cleanly). On any insert failure the file is preserved
so the operator can inspect.

Usage:
    python3 replay_dead_letter.py                 # replay all entries
    python3 replay_dead_letter.py --dry-run       # show what would replay
    python3 replay_dead_letter.py --path <file>   # custom path
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from common import get_supabase, console
from discover_creator import DEAD_LETTER_PATH


@dataclass
class ReplayResult:
    replayed: int = 0
    skipped: int = 0        # original run no longer exists
    failed: int = 0         # insert raised
    would_replay: int = 0   # dry-run only


def _read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            console.log(f"[yellow]Skipping malformed dead-letter line: {line[:80]}[/yellow]")
    return entries


def _lookup_runs(sb, run_ids: list[str]) -> dict[str, dict]:
    if not run_ids:
        return {}
    resp = sb.table("discovery_runs") \
        .select("id, creator_id, workspace_id, input_handle, input_platform_hint, attempt_number") \
        .in_("id", run_ids) \
        .execute()
    return {row["id"]: row for row in (resp.data or [])}


def replay_dead_letter(sb, path: Path, *, dry_run: bool = False) -> ReplayResult:
    result = ReplayResult()

    entries = _read_entries(path)
    if not entries:
        return result

    runs_by_id = _lookup_runs(sb, [e.get("run_id") for e in entries if e.get("run_id")])

    for entry in entries:
        run_id = entry.get("run_id")
        original = runs_by_id.get(run_id) if run_id else None
        if original is None:
            console.log(f"[yellow]Skipping {run_id}: original discovery_runs row not found[/yellow]")
            result.skipped += 1
            continue

        if dry_run:
            console.log(f"[cyan]Would replay @{original['input_handle']} ({original['input_platform_hint']})[/cyan]")
            result.would_replay += 1
            continue

        try:
            sb.table("discovery_runs").insert({
                "creator_id": original["creator_id"],
                "workspace_id": original["workspace_id"],
                "input_handle": original["input_handle"],
                "input_platform_hint": original["input_platform_hint"],
                "status": "pending",
                "attempt_number": (original.get("attempt_number") or 0) + 1,
            }).execute()
            result.replayed += 1
            console.log(f"[green]Replayed {run_id} → new pending run for @{original['input_handle']}[/green]")
        except Exception as e:
            console.log(f"[red]Failed to replay {run_id}: {e}[/red]")
            result.failed += 1

    if not dry_run and result.replayed > 0 and result.failed == 0:
        path.write_text("")
        console.log(f"[green]Truncated dead-letter file after {result.replayed} successful replays[/green]")
    elif not dry_run and result.failed > 0:
        console.log(f"[yellow]Leaving dead-letter file in place ({result.failed} failures)[/yellow]")

    return result


def main():
    parser = argparse.ArgumentParser(description="Replay dead-lettered discovery runs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would replay without inserting")
    parser.add_argument("--path", type=Path, default=DEAD_LETTER_PATH, help="Dead-letter JSONL file path")
    args = parser.parse_args()

    sb = get_supabase()
    result = replay_dead_letter(sb, args.path, dry_run=args.dry_run)
    console.log(f"[bold]Done: replayed={result.replayed} skipped={result.skipped} failed={result.failed} would_replay={result.would_replay}[/bold]")


if __name__ == "__main__":
    main()
