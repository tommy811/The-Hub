# scripts/discover_creator.py — Discovery and network analysis logic
import json
import argparse
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import google.generativeai as genai
from pydantic import ValidationError
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from common import get_supabase, get_gemini_key, console
from schemas import (
    DiscoveryInput,
    DiscoveryResult,
    InputContext,
)
from apify_details import (
    EmptyDatasetError,
    fetch_instagram_details,
    fetch_tiktok_details,
)
from apify_scraper import get_apify_client, scrape_instagram_profile
from link_in_bio import is_aggregator_url, resolve_link_in_bio

DEAD_LETTER_PATH = Path(os.environ.get(
    "DISCOVERY_DEAD_LETTER_PATH",
    str(Path(__file__).resolve().parent / "discovery_dead_letter.jsonl"),
))


def _clean_schema(obj):
    if isinstance(obj, dict):
        if "anyOf" in obj or "oneOf" in obj:
            variants = obj.get("anyOf") or obj.get("oneOf")
            non_null = [v for v in variants if not (isinstance(v, dict) and v.get("type") == "null")]
            if len(non_null) == 1:
                return _clean_schema({
                    **non_null[0],
                    **{k: v for k, v in obj.items() if k not in ("anyOf", "oneOf", "default", "title")},
                })
        return {
            k: _clean_schema(v)
            for k, v in obj.items()
            if k not in ("default", "title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
        }
    if isinstance(obj, list):
        return [_clean_schema(i) for i in obj]
    return obj


def _inline_refs(schema: dict) -> dict:
    defs = schema.get("$defs", {})

    def resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                return resolve(defs.get(ref_name, obj))
            return {k: resolve(v) for k, v in obj.items() if k != "$defs"}
        if isinstance(obj, list):
            return [resolve(i) for i in obj]
        return obj

    return resolve(schema)


GEMINI_DISCOVERY_SCHEMA = _clean_schema(_inline_refs(DiscoveryResult.model_json_schema()))


def fetch_input_context(inp: DiscoveryInput) -> InputContext:
    """Fetch structured profile context via Apify. Raises EmptyDatasetError on login wall."""
    if not inp.input_handle:
        raise ValueError("input_handle is required — legacy input_url-only path removed")

    platform = (inp.input_platform_hint or "").lower()
    client = get_apify_client()

    if platform == "instagram":
        ctx = fetch_instagram_details(client, inp.input_handle)
    elif platform == "tiktok":
        ctx = fetch_tiktok_details(client, inp.input_handle)
    else:
        raise ValueError(
            f"Unsupported input_platform_hint={platform!r}. "
            f"Supported: instagram, tiktok."
        )

    # Apify occasionally returns 1 item with all-null fields (private / restricted /
    # shape-valid-but-empty). Treat it identically to a 0-item response so the run
    # fails cleanly instead of being committed with a blank profile.
    if ctx.is_empty():
        raise EmptyDatasetError(
            f"Apify returned a shape-valid but empty item for @{inp.input_handle} on "
            f"{platform} (no bio, no follower count, no external URLs). Likely private, "
            f"restricted, or the actor could not resolve the profile."
        )

    # Resolve aggregator URLs (Linktree/Beacons) found in the bio
    destinations: list[str] = []
    for url in ctx.external_urls:
        if is_aggregator_url(url):
            destinations.extend(resolve_link_in_bio(url))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_destinations: list[str] = []
    for d in destinations:
        if d not in seen:
            seen.add(d)
            unique_destinations.append(d)

    ctx.link_in_bio_destinations = unique_destinations
    return ctx


def build_prompt(ctx: InputContext) -> str:
    ctx_json = ctx.model_dump_json(indent=2)
    return f"""
You are analyzing a creator's online footprint to discover their true identity, aliases, and platforms.

**Ground every field in the provided context.** Do not rely on prior knowledge of this handle. If a field cannot be determined from the context (bio, external URLs, link-in-bio destinations), return null / "unknown" / an empty list rather than guessing.

Do not hallucinate follower counts, niches, or accounts that aren't evidenced in the context.

## Context
```
{ctx_json}
```

## Task
1. Determine the creator's canonical name. If not clearly stated in display_name or bio, use the handle.
2. Infer primary_niche from bio and link-in-bio destination domains (e.g. onlyfans.com → adult creator; patreon.com → subscription creator).
3. Infer monetization_model from link-in-bio destinations (onlyfans/fanvue → subscription; patreon → subscription; shop/store → ecommerce; otherwise unknown).
4. List every account you can identify:
   - The input handle itself as a `proposed_account` with `is_primary=true`. Copy `display_name`, `bio`, and `follower_count` from the provided context into this primary account — do not leave them null when context has them.
   - Each link_in_bio_destination as a separate proposed_account. Infer platform from the domain; choose account_type per this mapping:
     - `monetization` for onlyfans.com, patreon.com, fanvue.com, fanplace.com, amazon.com/shop, *.tiktok.com/shop, any storefront / subscription-commerce URL
     - `link_in_bio` for linktr.ee, beacons.ai, beacons.page
     - `messaging` for t.me (Telegram) and Telegram cupidbot links
     - `social` for any other social-network domain (twitter/x.com, facebook.com, youtube.com, etc.)
5. Propose funnel edges from the input handle to each destination (edge_type=link_in_bio when routed via an aggregator; direct_link when listed directly in externalUrls).
6. Confidence 0.9+ only when the account appears literally in the context. 0.5–0.8 for strong inference (e.g. matching-handle OF account from a bio hint). Below 0.5 → don't emit.
""".strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_not_exception_type(ValidationError),
    reraise=True,
)
def run_gemini_discovery(ctx: InputContext) -> DiscoveryResult:
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = build_prompt(ctx)
    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_DISCOVERY_SCHEMA,
        ),
    )
    return DiscoveryResult.model_validate_json(resp.text)


def _write_dead_letter(run_id: UUID, error: str) -> None:
    """Append failed run to dead-letter file when mark_discovery_failed RPC itself fails."""
    try:
        DEAD_LETTER_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({"run_id": str(run_id), "error": error})
        with DEAD_LETTER_PATH.open("a") as f:
            f.write(entry + "\n")
    except Exception as e:
        console.log(f"[red]Dead-letter write failed: {e}[/red]")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
def _call_mark_discovery_failed(sb, run_id: UUID, error: str) -> None:
    sb.rpc("mark_discovery_failed", {
        "p_run_id": str(run_id),
        "p_error": error,
    }).execute()


def mark_discovery_failed_with_retry(sb, run_id: UUID, error: str) -> None:
    """Call mark_discovery_failed RPC with tenacity retry; dead-letter on final failure."""
    try:
        _call_mark_discovery_failed(sb, run_id, error)
    except Exception as nested:
        console.log(f"[red]mark_discovery_failed exhausted retries: {nested}[/red]")
        _write_dead_letter(run_id, error)


def _update_profile_from_context(sb, workspace_id: UUID, ctx: InputContext) -> None:
    """Write fresh Apify-sourced fields directly to the primary profile.

    `commit_discovery_result` upserts profiles from Gemini's `proposed_accounts`, but
    Gemini's output may omit bio / follower_count / avatar. We already fetched those
    authoritatively into ctx via the Apify details actor — write them here so the
    profile row reflects ground truth even when Gemini's proposed_account is sparse.

    Skips keys whose ctx value is None/empty, so we never clobber populated fields
    with nulls.
    """
    updates: dict = {}
    if ctx.display_name:
        updates["display_name"] = ctx.display_name
    if ctx.bio:
        updates["bio"] = ctx.bio
    if ctx.follower_count is not None:
        updates["follower_count"] = ctx.follower_count
    if ctx.following_count is not None:
        updates["following_count"] = ctx.following_count
    if ctx.post_count is not None:
        updates["post_count"] = ctx.post_count
    if ctx.avatar_url:
        updates["avatar_url"] = ctx.avatar_url

    if not updates:
        return

    updates["last_scraped_at"] = "now()"

    sb.table("profiles") \
        .update(updates) \
        .eq("workspace_id", str(workspace_id)) \
        .eq("platform", ctx.platform) \
        .eq("handle", ctx.handle) \
        .execute()


def commit(sb, run_id: UUID, result: DiscoveryResult):
    data = result.model_dump(mode="json")
    creator_data = {
        "canonical_name": data["canonical_name"],
        "known_usernames": data["known_usernames"],
        "display_name_variants": data["display_name_variants"],
        "primary_platform": data["primary_platform"],
        "primary_niche": data["primary_niche"],
        "monetization_model": data["monetization_model"],
    }
    sb.rpc("commit_discovery_result", {
        "p_run_id": str(run_id),
        "p_creator_data": creator_data,
        "p_accounts": data["proposed_accounts"],
        "p_funnel_edges": data["proposed_funnel_edges"],
    }).execute()
    console.log(f"[green]Committed discovery run {run_id}[/green]")


def run(inp: DiscoveryInput) -> None:
    sb = get_supabase()
    try:
        console.log(f"[blue]Starting discovery run {inp.run_id} (@{inp.input_handle}, {inp.input_platform_hint})[/blue]")
        ctx = fetch_input_context(inp)
        console.log(f"[cyan]Context: bio={bool(ctx.bio)} followers={ctx.follower_count} external_urls={len(ctx.external_urls)} destinations={len(ctx.link_in_bio_destinations)}[/cyan]")

        result = run_gemini_discovery(ctx)
        commit(sb, inp.run_id, result)

        # Write the Apify-sourced profile fields (bio / follower counts / avatar)
        # directly. Gemini's proposed_accounts may omit them; the upsert in
        # commit_discovery_result preserves existing values on conflict, so this
        # update fills in whatever's missing.
        _update_profile_from_context(sb, inp.workspace_id, ctx)

        # Kick off a small IG posts scrape for the primary account
        ig_accounts = [a for a in result.proposed_accounts if a.platform == "instagram"]
        if ig_accounts:
            ig_handle = ig_accounts[0].handle
            if not ig_handle and ig_accounts[0].url:
                path_parts = urlparse(ig_accounts[0].url).path.strip("/").split("/")
                ig_handle = path_parts[0] if path_parts and path_parts[0] else None
            if ig_handle:
                console.log(f"[cyan]Dispatching Apify posts scrape for @{ig_handle}[/cyan]")
                scrape_instagram_profile(str(inp.workspace_id), ig_handle, limit=5)

    except EmptyDatasetError as e:
        console.log(f"[yellow]Discovery aborted — empty context: {e}[/yellow]")
        mark_discovery_failed_with_retry(sb, inp.run_id, f"empty_context: {e}")
    except Exception as e:
        console.log(f"[red]Fatal discovery error: {e}[/red]")
        mark_discovery_failed_with_retry(sb, inp.run_id, str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=str)
    args = parser.parse_args()

    sb = get_supabase()
    resp = sb.table("discovery_runs").select("*").eq("id", args.run_id).single().execute()
    data = resp.data
    if not data:
        console.log(f"[red]Run {args.run_id} not found[/red]")
        exit(1)

    inp = DiscoveryInput(
        run_id=data["id"],
        creator_id=data["creator_id"],
        workspace_id=data["workspace_id"],
        input_handle=data["input_handle"],
        input_url=data["input_url"],
        input_platform_hint=data["input_platform_hint"],
    )
    run(inp)
