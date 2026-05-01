# scripts/worker.py — Polling worker for discovery pipeline v2
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from common import get_supabase, console
from discover_creator import run, DiscoveryInput
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
MAX_CONCURRENT_RUNS = int(os.environ.get("MAX_CONCURRENT_RUNS", "5"))


def _process_single(row: dict) -> Optional[str]:
    inp = DiscoveryInput(
        run_id=row["id"],
        creator_id=row["creator_id"],
        workspace_id=row["workspace_id"],
        input_handle=row["input_handle"],
        input_url=row["input_url"],
        input_platform_hint=row["input_platform_hint"],
    )
    run(inp, bulk_import_id=row.get("bulk_import_id"))
    return row.get("bulk_import_id")


def log_gather_results(results: list, claimed: list[dict], logger=None) -> None:
    log = logger or console.log
    for result, row in zip(results, claimed):
        if isinstance(result, BaseException):
            log(f"[red]Run {row.get('id')} failed in worker: {type(result).__name__}: {result}[/red]")


def _fire_merge_pass_if_bulk_complete(sb, bulk_import_id: str, workspace_id: str) -> None:
    resp = sb.table("discovery_runs").select("id").eq(
        "bulk_import_id", bulk_import_id
    ).in_("status", ["pending", "processing"]).execute()

    if resp.data:
        return  # still seeds running

    console.log(f"[cyan]Bulk {bulk_import_id} terminal — firing cross-workspace merge pass[/cyan]")
    try:
        sb.rpc("run_cross_workspace_merge_pass", {
            "p_workspace_id": workspace_id,
            "p_bulk_import_id": bulk_import_id,
        }).execute()
    except Exception as e:
        console.log(f"[red]Merge pass failed for bulk {bulk_import_id}: {e}[/red]")


async def poll_loop(args=None):
    sb = get_supabase()
    console.log(f"[green]Worker v2 started. Polling every {POLL_INTERVAL_SECONDS}s. "
                f"Max concurrency: {MAX_CONCURRENT_RUNS}.[/green]")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RUNS) as pool:
        while True:
            try:
                resp = sb.table("discovery_runs").select("*").eq(
                    "status", "pending"
                ).limit(MAX_CONCURRENT_RUNS).execute()
                runs = resp.data

                if runs:
                    console.log(f"[cyan]Found {len(runs)} pending runs. Claiming...[/cyan]")
                    claimed = []
                    for r in runs:
                        claim_res = sb.table("discovery_runs").update({"status": "processing"})\
                            .eq("id", r["id"]).eq("status", "pending").execute()
                        if claim_res.data:
                            claimed.append(claim_res.data[0])

                    if claimed:
                        loop = asyncio.get_running_loop()
                        futures = [loop.run_in_executor(pool, _process_single, c) for c in claimed]
                        results = await asyncio.gather(*futures, return_exceptions=True)
                        log_gather_results(results, claimed)

                        seen_bulks: dict[str, str] = {}
                        for row in claimed:
                            bid = row.get("bulk_import_id")
                            if bid:
                                seen_bulks[bid] = row["workspace_id"]
                        for bid, ws_id in seen_bulks.items():
                            _fire_merge_pass_if_bulk_complete(sb, bid, ws_id)

            except Exception as e:
                console.log(f"[red]Error in polling loop: {e}[/red]")

            if getattr(args, "once", False):
                break

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one iteration and exit")
    args = parser.parse_args()
    asyncio.run(poll_loop(args))
