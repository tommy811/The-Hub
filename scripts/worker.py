# scripts/worker.py — Polling worker for discovery pipeline
import os
import time
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
        input_platform_hint=row["input_platform_hint"]
    )
    run(inp)

async def poll_loop():
    sb = get_supabase()
    console.log(f"[green]Worker started. Polling every {POLL_INTERVAL_SECONDS}s. Max concurrency: {MAX_CONCURRENT_RUNS}.[/green]")
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RUNS) as pool:
        while True:
            try:
                # 1. Fetch pending runs up to MAX_CONCURRENT_RUNS
                resp = sb.table("discovery_runs").select("*").eq("status", "pending").limit(MAX_CONCURRENT_RUNS).execute()
                runs = resp.data
                
                if runs:
                    console.log(f"[cyan]Found {len(runs)} pending runs. Claiming...[/cyan]")
                    
                    claimed = []
                    for r in runs:
                        # Attempt to claim atomically. In a real highly concurrent system 
                        # you might want a more robust queuing system or lock.
                        claim_res = sb.table("discovery_runs").update({"status": "processing"})\
                                    .eq("id", r["id"]).eq("status", "pending").execute()
                        if claim_res.data:
                            claimed.append(claim_res.data[0])
                    
                    if claimed:
                        loop = asyncio.get_running_loop()
                        futures = [loop.run_in_executor(pool, process_single, c) for c in claimed]
                        # We wait for these to complete before polling again to strictly honor max max_workers if sequential is desired.
                        # For true background streaming, you'd yield them and poll again.
                        await asyncio.gather(*futures, return_exceptions=True)
                
            except Exception as e:
                console.log(f"[red]Error in polling loop: {e}[/red]")
            
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(poll_loop())
