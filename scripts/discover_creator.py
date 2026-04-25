# scripts/discover_creator.py — Discovery entry point, dispatches to v2 resolver
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import google.generativeai as genai
from pydantic import ValidationError
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from common import get_supabase, get_gemini_key, console
from schemas import DiscoveryInput, InputContext, DiscoveryResultV2
from apify_scraper import get_apify_client, scrape_instagram_profile
from fetchers.base import EmptyDatasetError

from pipeline.resolver import resolve_seed, ResolverResult
from pipeline.budget import BudgetTracker, BudgetExhaustedError


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


GEMINI_V2_SCHEMA = _clean_schema(_inline_refs(DiscoveryResultV2.model_json_schema()))


def build_prompt_v2(ctx: InputContext) -> str:
    ctx_json = ctx.model_dump_json(indent=2)
    return f"""
You are extracting identity metadata from a creator's profile — NOT classifying URLs.

**Ground every field in the provided context.** Do not rely on prior knowledge of this handle. If a field cannot be determined from the context, return null / "unknown" / an empty list.

## Context
```
{{ctx_json}}
```

## Task — return a JSON object matching the schema with ONLY these fields:

1. `canonical_name`: human-readable creator name. If not clearly stated in display_name or bio, use the handle.
2. `known_usernames`: list of handles this creator is known by (including the input handle).
3. `display_name_variants`: all variants of the creator's display name present in context.
4. `primary_niche`: free-text inference from bio (e.g. "adult", "fitness", "cooking", "asmr"). Null if unclear.
5. `monetization_model`: one of [subscription, tips, ppv, affiliate, brand_deals, ecommerce, coaching, saas, mixed, unknown]. Infer from link-in-bio destinations when present.
6. `text_mentions`: list of handles explicitly mentioned in prose (bio text). ONLY include mentions that name a handle + platform clearly (e.g. "follow my tiktok @alice2" → platform=tiktok, handle=alice2). Do NOT include anything from external_urls — URLs are classified separately by the resolver.
7. `raw_reasoning`: one-sentence summary of what you inferred.

DO NOT classify URLs. DO NOT propose accounts. DO NOT propose funnel edges. Those are handled by the deterministic classifier + resolver layers, not by you.
""".strip().format(ctx_json=ctx_json)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_not_exception_type(ValidationError),
    reraise=True,
)
def run_gemini_discovery_v2(ctx: InputContext) -> DiscoveryResultV2:
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = build_prompt_v2(ctx)
    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_V2_SCHEMA,
        ),
    )
    return DiscoveryResultV2.model_validate_json(resp.text)


def _write_dead_letter(run_id: UUID, error: str) -> None:
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
    try:
        _call_mark_discovery_failed(sb, run_id, error)
    except Exception as nested:
        console.log(f"[red]mark_discovery_failed exhausted retries: {nested}[/red]")
        _write_dead_letter(run_id, error)


def _classify_account_type_for(platform: str, discovered_urls: list, canonical_url: str) -> str:
    """Map from discovered_urls list entry to account_type for the profile row."""
    for du in discovered_urls:
        if du.canonical_url == canonical_url:
            return du.account_type
    return "other"


def _synthesize_handle_from_url(url: str) -> str:
    """Best-effort handle when no fetcher provided one.

    Used for novel platforms (Wattpad, Substack, etc.) where no platform
    fetcher exists. Persisting the row keeps the destination on the creator
    HQ page instead of leaving it stranded in profile_destination_links.
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if parts:
        return parts[-1].lstrip("@").split("?")[0]
    return parsed.netloc or url


def _commit_v2(sb, run_id: UUID, workspace_id: UUID, result: ResolverResult,
                bulk_import_id: str | None) -> None:
    """Build the v2 commit_discovery_result payload from the resolver output."""
    seed = result.seed_context
    gem = result.gemini_result

    accounts = [{
        "platform": seed.platform,
        "handle": seed.handle,
        "url": None,
        "display_name": seed.display_name,
        "bio": seed.bio,
        "follower_count": seed.follower_count,
        "account_type": "social",
        "is_primary": True,
        "discovery_confidence": 1.0,
        "reasoning": "seed",
    }]

    for canon, ctx in result.enriched_contexts.items():
        accounts.append({
            "platform": ctx.platform,
            "handle": ctx.handle,
            "url": canon,
            "display_name": ctx.display_name,
            "bio": ctx.bio,
            "follower_count": ctx.follower_count,
            "account_type": _classify_account_type_for(ctx.platform, result.discovered_urls, canon),
            "is_primary": False,
            "discovery_confidence": 0.9,
            "reasoning": ctx.source_note,
        })

    # Persist discovered URLs that no fetcher enriched (novel platforms,
    # link-in-bio aggregators, budget-skipped profiles). Without this they'd
    # only land in profile_destination_links and never render on the HQ page.
    for du in result.discovered_urls:
        if du.canonical_url in result.enriched_contexts:
            continue
        accounts.append({
            "platform": du.platform,
            "handle": _synthesize_handle_from_url(du.canonical_url),
            "url": du.canonical_url,
            "display_name": None,
            "bio": None,
            "follower_count": None,
            "account_type": du.account_type,
            "is_primary": False,
            "discovery_confidence": 0.6,
            "reasoning": f"discovered_only_no_fetcher: {du.reason}",
        })

    funnel_edges = []
    for canon, ctx in result.enriched_contexts.items():
        funnel_edges.append({
            "from_platform": seed.platform,
            "from_handle": seed.handle,
            "to_platform": ctx.platform,
            "to_handle": ctx.handle,
            "edge_type": "link_in_bio",
            "confidence": 0.9,
        })

    creator_data = {
        "canonical_name": gem.canonical_name,
        "known_usernames": gem.known_usernames,
        "display_name_variants": gem.display_name_variants,
        "primary_platform": seed.platform,
        "primary_niche": gem.primary_niche,
        "monetization_model": gem.monetization_model,
    }

    discovered_urls_payload = [du.model_dump() for du in result.discovered_urls]

    sb.rpc("commit_discovery_result", {
        "p_run_id": str(run_id),
        "p_creator_data": creator_data,
        "p_accounts": accounts,
        "p_funnel_edges": funnel_edges,
        "p_discovered_urls": discovered_urls_payload,
        "p_bulk_import_id": bulk_import_id,
    }).execute()
    console.log(f"[green]Committed v2 discovery run {run_id}[/green]")


def run(inp: DiscoveryInput, bulk_import_id: str | None = None,
        cap_cents: int | None = None) -> None:
    """Run discovery for one seed. v2 pipeline.

    bulk_import_id: if set, passed to commit for counter updates.
    cap_cents: per-seed Apify budget. Defaults to env BULK_IMPORT_APIFY_USD_CAP (×100).
    """
    sb = get_supabase()
    if cap_cents is None:
        cap_cents = int(float(os.environ.get("BULK_IMPORT_APIFY_USD_CAP", "5")) * 100)

    budget = BudgetTracker(
        cap_cents=cap_cents,
        on_warning=lambda msg: console.log(f"[yellow]{msg}[/yellow]"),
    )
    try:
        console.log(f"[blue]Starting v2 discovery run {inp.run_id} "
                    f"(@{inp.input_handle}, {inp.input_platform_hint})[/blue]")
        result = resolve_seed(
            handle=inp.input_handle,
            platform_hint=inp.input_platform_hint,
            supabase=sb,
            apify_client=get_apify_client(),
            budget=budget,
        )

        _commit_v2(sb, inp.run_id, inp.workspace_id, result, bulk_import_id)

        sb.table("discovery_runs").update({
            "apify_cost_cents": budget.spent_cents,
        }).eq("id", str(inp.run_id)).execute()

        if result.seed_context.platform == "instagram":
            console.log(f"[cyan]Dispatching Apify posts scrape for @{inp.input_handle}[/cyan]")
            scrape_instagram_profile(str(inp.workspace_id), inp.input_handle, limit=5)

    except EmptyDatasetError as e:
        console.log(f"[yellow]Discovery aborted — empty context: {e}[/yellow]")
        mark_discovery_failed_with_retry(sb, inp.run_id, f"empty_context: {e}")
    except BudgetExhaustedError as e:
        console.log(f"[yellow]Discovery blocked by budget: {e}[/yellow]")
        mark_discovery_failed_with_retry(sb, inp.run_id, f"budget_exceeded: {e}")
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
    run(inp, bulk_import_id=data.get("bulk_import_id"))
