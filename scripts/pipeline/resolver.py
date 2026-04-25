# scripts/pipeline/resolver.py — Two-stage resolver: fetch seed, then classify+enrich destinations
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
    Stage B: classify + enrich every discovered URL. Aggregators expanded once.
    Gemini pass: canonicalization + niche + text_mentions. Text mentions fed
    back into Stage B once per seed (no further recursion).

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

    def _classify_and_enrich(url: str, is_aggregator_child: bool = False):
        """Classify URL, optionally enrich profile, record in discovered list."""
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
                _classify_and_enrich(child, is_aggregator_child=True)
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
                pass
            except Exception as e:
                console.log(f"[yellow]enrichment failed for {canon}: {e}[/yellow]")

    # Stage B for seed's externalUrls
    for url in seed_ctx.external_urls:
        try:
            _classify_and_enrich(url)
        except BudgetExhaustedError:
            break

    # Gemini pass
    _emit(70, "Analyzing")
    gemini_result = run_gemini_discovery_v2(seed_ctx)

    # Stage B for text_mentions (one-shot expansion only, no further recursion)
    for mention in gemini_result.text_mentions:
        synth = _synthesize_url(mention)
        if synth:
            try:
                _classify_and_enrich(synth)
            except BudgetExhaustedError:
                break

    return ResolverResult(
        seed_context=seed_ctx,
        gemini_result=gemini_result,
        enriched_contexts=enriched,
        discovered_urls=discovered,
    )
