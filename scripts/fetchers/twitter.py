# scripts/fetchers/twitter.py — STUB: Apify actor not yet provisioned (SP1.1 follow-up)
from schemas import InputContext
from common import console


def fetch(handle: str) -> InputContext:
    console.log(f"[yellow]twitter fetcher stub — no enrichment for @{handle}[/yellow]")
    return InputContext(
        handle=handle,
        platform="twitter",
        source_note="stub:not_implemented",
    )
