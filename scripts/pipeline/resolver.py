# scripts/pipeline/resolver.py — Two-stage resolver: fetch seed, then classify+enrich destinations
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from apify_client import ApifyClient

from schemas import (
    InputContext, DiscoveredUrl, DiscoveryResultV2, TextMention,
)
from common import console
from pipeline.canonicalize import canonicalize_url, resolve_short_url
from pipeline.classifier import classify, Classification
from pipeline.budget import BudgetTracker, BudgetExhaustedError

# Fetchers + aggregators dispatch
from fetchers import instagram as fetch_ig
from fetchers import tiktok as fetch_tt
from fetchers import youtube as fetch_yt
from fetchers import patreon as fetch_patreon
from fetchers import onlyfans as fetch_of
from fetchers import fanvue as fetch_fanvue
from fetchers import facebook as fetch_fb
from fetchers import twitter as fetch_twitter
from fetchers import generic as fetch_generic
from fetchers.base import EmptyDatasetError
from aggregators import linktree as aggregators_linktree
from aggregators import beacons as aggregators_beacons
from aggregators import custom_domain as aggregators_custom


# Apify cost table in cents per run. Hand-maintained, err on the high side.
_APIFY_COSTS = {
    "apify/instagram-scraper": 10,
    "clockworks/tiktok-scraper": 8,
    # YouTube (yt-dlp) + Patreon + OF + Fanvue + generic + aggregators: 0 (not Apify)
}

# Defensive max depth so a pathological cycle can't loop. Real-world creator
# networks rarely exceed depth 3.
MAX_DEPTH = int(os.getenv("DISCOVERY_MAX_DEPTH", "6"))

# When True, secondary profiles get a cheap Gemini Flash bio-mentions extraction
# in addition to their explicit external_urls. Default ON — call is ~$0.001.
RECURSIVE_GEMINI = os.getenv("DISCOVERY_RECURSIVE_GEMINI", "1") == "1"


@dataclass
class ResolverResult:
    seed_context: InputContext
    gemini_result: DiscoveryResultV2
    enriched_contexts: dict[str, InputContext]  # {canonical_url: ctx} for fetched secondaries
    discovered_urls: list[DiscoveredUrl] = field(default_factory=list)


def _fetcher_for(platform: str):
    return {
        "instagram": fetch_ig.fetch,
        "tiktok": fetch_tt.fetch,
        "youtube": fetch_yt.fetch,
        "patreon": fetch_patreon.fetch,
        "onlyfans": fetch_of.fetch,
        "fanvue": fetch_fanvue.fetch,
        "facebook": fetch_fb.fetch,
        "twitter": fetch_twitter.fetch,
    }.get(platform)


_SEED_HOST_FOR_PLATFORM = {
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    "youtube": "youtube.com",
    "twitter": "x.com",
    "facebook": "facebook.com",
    "patreon": "patreon.com",
    "onlyfans": "onlyfans.com",
    "fanvue": "fanvue.com",
    "linkedin": "linkedin.com",
}


def _build_seed_url(platform: str, handle: str) -> str | None:
    host = _SEED_HOST_FOR_PLATFORM.get(platform)
    if host is None:
        return None
    h = (handle or "").lstrip("@")
    if not h:
        return None
    if platform in ("tiktok", "youtube"):
        return f"https://{host}/@{h}"
    if platform == "linkedin":
        return f"https://{host}/in/{h}"
    return f"https://{host}/{h}"


def _destination_class_for(account_type: str) -> str:
    return {
        "monetization": "monetization",
        "link_in_bio": "aggregator",
        "social": "social",
    }.get(account_type, "other")


def _apify_cost(platform: str) -> int:
    # map platform to actor cost
    return {
        "instagram": _APIFY_COSTS["apify/instagram-scraper"],
        "tiktok": _APIFY_COSTS["clockworks/tiktok-scraper"],
    }.get(platform, 0)


def _confidence_at_depth(depth: int) -> float:
    """Discovery confidence by hop distance from the seed.

    depth 0 = seed (1.0), depth 1 = direct (0.9 — preserves existing behaviour),
    drops 0.05 per hop, floors at 0.5.
    """
    if depth <= 0:
        return 1.0
    return max(0.5, 0.9 - 0.05 * (depth - 1))


def _handle_from_url(url: str, platform: str) -> str | None:
    """Extract a handle from a URL. Returns None if the URL shape is unrecognized."""
    parts = urlparse(url).path.strip("/").split("/")
    if not parts or not parts[0]:
        return None
    first = parts[0]
    if platform in ("tiktok", "youtube") and first.startswith("@"):
        return first
    return first


def fetch_seed(handle: str, platform_hint: str, apify_client) -> InputContext:
    """Stage A: fetch the seed profile via the platform fetcher."""
    fetcher = _fetcher_for(platform_hint)
    if fetcher is None:
        raise ValueError(f"Unsupported platform_hint={platform_hint!r}")

    if platform_hint in ("instagram", "tiktok"):
        ctx = fetcher(apify_client, handle)
    else:
        ctx = fetcher(handle)

    if ctx.is_empty():
        raise EmptyDatasetError(
            f"Seed fetch for @{handle} on {platform_hint} produced empty context."
        )
    return ctx


def run_gemini_discovery_v2(ctx: InputContext) -> DiscoveryResultV2:
    """Call Gemini for canonicalization + niche + text_mentions ONLY.

    No URL classification, no account proposals — those are the resolver's job.
    Implemented in discover_creator.py (see Task 17). Kept as a module-level
    symbol here so test_resolver.py can mock at this import site.
    """
    from discover_creator import run_gemini_discovery_v2 as _impl
    return _impl(ctx)


def run_gemini_bio_mentions(ctx: InputContext) -> list[TextMention]:
    """Cheap Gemini Flash bio-mentions extraction.

    Re-exported here so tests can patch at this import site, matching the
    pattern used for run_gemini_discovery_v2.
    """
    from discover_creator import run_gemini_bio_mentions as _impl
    return _impl(ctx)


def fetch_highlights(client: ApifyClient, handle: str) -> list:
    """Re-exported from fetchers.instagram_highlights so tests can patch at this site.

    Imported lazily inside the function to avoid eager Apify client init at
    module load time — same pattern as run_gemini_bio_mentions.
    """
    from fetchers.instagram_highlights import fetch_highlights as _impl
    return _impl(client, handle)


def _synthesize_url(mention: TextMention) -> str | None:
    host_for = {
        "instagram": "instagram.com",
        "tiktok": "tiktok.com",
        "youtube": "youtube.com",
        "twitter": "x.com",
        "facebook": "facebook.com",
        "patreon": "patreon.com",
        "onlyfans": "onlyfans.com",
        "fanvue": "fanvue.com",
    }.get(mention.platform)
    if not host_for:
        return None
    handle = mention.handle.lstrip("@")
    if mention.platform in ("tiktok", "youtube"):
        return f"https://{host_for}/@{handle}"
    return f"https://{host_for}/{handle}"


def resolve_seed(
    handle: str, platform_hint: str,
    supabase, apify_client: ApifyClient,
    budget: BudgetTracker,
    progress=None,
) -> ResolverResult:
    """Two-stage resolver for one seed.

    Stage A: fetch seed, debit budget.
    Stage B: classify + enrich every discovered URL via _expand recursion.
    Aggregators expanded once. Gemini canonicalization runs on seed only.
    Recursion terminates naturally when no new URLs/mentions surface; bounded
    defensively by MAX_DEPTH.

    progress: optional callable(pct, label) — invoked at stage boundaries so
    the UI can render a real progress bar. Decoupled from supabase to keep
    the resolver mockable in tests.
    """
    def _emit(pct: int, label: str) -> None:
        if progress is not None:
            progress(pct, label)

    # Stage A
    _emit(10, "Fetching profile")
    budget.debit(f"apify/{platform_hint}-scraper", _apify_cost(platform_hint))
    seed_ctx = fetch_seed(handle, platform_hint, apify_client)
    console.log(f"[cyan]Stage A: @{handle} on {platform_hint} — "
                f"bio={bool(seed_ctx.bio)} followers={seed_ctx.follower_count} "
                f"external={len(seed_ctx.external_urls)}[/cyan]")
    _emit(35, "Resolving links")

    discovered: list[DiscoveredUrl] = []
    enriched: dict[str, InputContext] = {}
    visited_canonical: set[str] = set()
    aggregator_expanded: set[str] = set()
    mapping_label_emitted = False

    # Pre-seed visited set so a secondary that mentions us back doesn't re-fetch
    seed_self_url = _build_seed_url(platform_hint, handle)
    if seed_self_url:
        visited_canonical.add(canonicalize_url(seed_self_url))

    def _classify_and_enrich(url: str, depth: int, is_aggregator_child: bool = False):
        """Classify URL, optionally enrich profile, record in discovered list.

        depth = the depth the URL itself sits at. Seed.external_urls items are
        depth=1. Aggregator children inherit depth from the aggregator + 1.
        """
        nonlocal mapping_label_emitted
        if depth > MAX_DEPTH:
            return  # defensive cap

        # Resolve short URLs, then canonicalize
        expanded = resolve_short_url(url)
        canon = canonicalize_url(expanded)
        if canon in visited_canonical:
            return
        visited_canonical.add(canon)

        cls: Classification = classify(canon, supabase=supabase)
        discovered.append(DiscoveredUrl(
            canonical_url=canon,
            platform=cls.platform,
            account_type=cls.account_type,
            destination_class=_destination_class_for(cls.account_type),
            reason=cls.reason,
            depth=depth,
        ))

        # If aggregator, expand one level (only if not already a child — no chaining)
        if cls.account_type == "link_in_bio" and not is_aggregator_child:
            if canon in aggregator_expanded:
                return
            aggregator_expanded.add(canon)
            children: list[str] = []
            if aggregators_linktree.is_linktree(canon):
                children = aggregators_linktree.resolve(canon)
            elif aggregators_beacons.is_beacons(canon):
                children = aggregators_beacons.resolve(canon)
            else:
                children = aggregators_custom.resolve(canon)
            for child in children:
                _classify_and_enrich(child, depth=depth + 1, is_aggregator_child=True)
            return

        # If profile, try to enrich (if budget allows + fetcher exists)
        if cls.account_type == "social" or cls.account_type == "monetization":
            enrich_cost = _apify_cost(cls.platform)
            if enrich_cost > 0 and not budget.can_afford(enrich_cost):
                return
            fetcher = _fetcher_for(cls.platform)
            if fetcher is None:
                return
            h = _handle_from_url(canon, cls.platform)
            if not h:
                return
            try:
                if enrich_cost > 0:
                    budget.debit(f"apify/{cls.platform}-scraper", enrich_cost)
                if cls.platform in ("instagram", "tiktok"):
                    ctx = fetcher(apify_client, h)
                else:
                    ctx = fetcher(h)
                enriched[canon] = ctx
            except (EmptyDatasetError, BudgetExhaustedError):
                return
            except Exception as e:
                console.log(f"[yellow]enrichment failed for {canon}: {e}[/yellow]")
                return

            # NEW: recurse into the freshly-enriched ctx
            if not mapping_label_emitted:
                _emit(50, "Mapping secondary funnels")
                mapping_label_emitted = True
            try:
                _expand(ctx, depth=depth)
            except BudgetExhaustedError:
                return

    def _expand(ctx: InputContext, depth: int) -> None:
        """Expand ctx's outbound links + bio mentions one hop further.

        ctx is at `depth`; its external_urls are processed at depth+1. Bio
        mentions (cheap Gemini extraction) are also processed at depth+1
        when RECURSIVE_GEMINI is on. The seed (depth 0) skips bio extraction
        because the full Gemini canonicalization call covers it.
        """
        if depth >= MAX_DEPTH:
            return
        for url in ctx.external_urls:
            try:
                _classify_and_enrich(url, depth=depth + 1)
            except BudgetExhaustedError:
                return
        if depth >= 1 and RECURSIVE_GEMINI:
            mentions = run_gemini_bio_mentions(ctx)
            for m in mentions:
                synth = _synthesize_url(m)
                if synth:
                    try:
                        _classify_and_enrich(synth, depth=depth + 1)
                    except BudgetExhaustedError:
                        return

    # Stage B for seed (depth 0 → expand to depth 1)
    try:
        _expand(seed_ctx, depth=0)
    except BudgetExhaustedError:
        pass

    # Gemini full pass (canonicalization + niche + text_mentions)
    _emit(70, "Analyzing")
    gemini_result = run_gemini_discovery_v2(seed_ctx)

    # Stage B for seed text_mentions (depth 1, since they're 1 hop from seed)
    for mention in gemini_result.text_mentions:
        synth = _synthesize_url(mention)
        if synth:
            try:
                _classify_and_enrich(synth, depth=1)
            except BudgetExhaustedError:
                break

    return ResolverResult(
        seed_context=seed_ctx,
        gemini_result=gemini_result,
        enriched_contexts=enriched,
        discovered_urls=discovered,
    )
