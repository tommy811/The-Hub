# scripts/fetchers/facebook.py — STUB: Apify actor not yet provisioned (SP1.1 follow-up)
from schemas import InputContext
from common import console


def fetch(handle: str) -> InputContext:
    """Stub. Returns an empty InputContext so resolver Stage B keeps flowing.

    Classifier will classify FB URLs and dispatch here; the resolver treats
    is_empty() contexts as "recorded but not enriched" (same as unknown-
    platform URLs). SP1.1 adds the live Apify actor.
    """
    console.log(f"[yellow]facebook fetcher stub — no enrichment for @{handle}[/yellow]")
    return InputContext(
        handle=handle,
        platform="facebook",
        source_note="stub:not_implemented",
    )
