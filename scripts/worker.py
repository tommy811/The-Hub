# scripts/worker.py — Polling worker for discovery pipeline
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from common import get_supabase, console
from discover_creator import run, DiscoveryInput
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
MAX_CONCURRENT_RUNS = int(os.environ.get("MAX_CONCURRENT_RUNS", "5"))


def process_single(row: dict):
    inp = DiscoveryInput(
        run_id=row["id"],
        creator_id=row["creator_id"],
        workspace_id=row["workspace_id"],
        input_handle=row["input_handle"],
        input_url=row["input_url"],
        input_platform_hint=row["input_platform_hint"],
    )
    run(inp)


def log_gather_results(results: list, claimed: list[dict], logger=None) -> None:
    """Surface exceptions from asyncio.gather(..., return_exceptions=True).

    Without this, per-task crashes are silently absorbed. Logs one line per error
    that includes the run id so we can correlate back to discovery_runs.
    """
    log = logger or console.log
    for result, row in zip(results, claimed):
        if isinstance(result, BaseException):
            log(f"[red]Run {row.get('id')} failed in worker: {type(result).__name__}: {result}[/red]")


async def poll_loop(args=None):
    sb = get_supabase()
    console.log(f"[green]Worker started. Polling every {POLL_INTERVAL_SECONDS}s. Max concurrency: {MAX_CONCURRENT_RUNS}.[/green]")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RUNS) as pool:
        while True:
            try:
                resp = sb.table("discovery_runs").select("*").eq("status", "pending").limit(MAX_CONCURRENT_RUNS).execute()
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
                        futures = [loop.run_in_executor(pool, process_single, c) for c in claimed]
                        results = await asyncio.gather(*futures, return_exceptions=True)
                        log_gather_results(results, claimed)

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
