# scripts/discover_creator.py — Discovery and Network Analysis Logic
import json
import argparse
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field
import httpx
from bs4 import BeautifulSoup
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
from common import get_supabase, get_gemini_key, console
from apify_scraper import scrape_instagram_profile

# --- Models ---
class DiscoveryInput(BaseModel):
    run_id: UUID
    creator_id: UUID
    workspace_id: UUID
    input_handle: Optional[str] = None
    input_url: Optional[str] = None
    input_platform_hint: Optional[str] = None

class ProposedAccount(BaseModel):
    account_type: Literal['social','monetization','link_in_bio','messaging','other']
    platform: str
    handle: Optional[str] = None
    url: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    is_primary: bool = False
    discovery_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

class ProposedFunnelEdge(BaseModel):
    from_handle: str
    from_platform: str
    to_handle: str
    to_platform: str
    edge_type: Literal['link_in_bio','direct_link','cta_mention','qr_code','inferred']
    confidence: float

class DiscoveryResult(BaseModel):
    canonical_name: str
    known_usernames: list[str]
    display_name_variants: list[str]
    primary_platform: str
    primary_niche: Optional[str] = None
    monetization_model: str
    proposed_accounts: list[ProposedAccount]
    proposed_funnel_edges: list[ProposedFunnelEdge]
    raw_reasoning: str

# Use the Pydantic type schema explicitly for Gemini
GEMINI_DISCOVERY_SCHEMA = DiscoveryResult.model_json_schema()

# Provide rigid enums to explicitly limit hallucination
GEMINI_DISCOVERY_SCHEMA["properties"]["proposed_accounts"]["items"]["properties"]["platform"]["enum"] = [
    "instagram", "tiktok", "youtube", "facebook", "twitter", "linkedin",
    "onlyfans", "fanvue", "fanplace", "amazon_storefront", "tiktok_shop",
    "linktree", "beacons", "telegram_channel", "telegram_cupidbot", "custom_domain", "other"
]

def fetch_input_context(inp: DiscoveryInput) -> dict:
    url = inp.input_url
    if not url and inp.input_handle and inp.input_platform_hint:
         # Basic heuristic URL builder
         domain_map = {
             "instagram": f"https://instagram.com/{inp.input_handle}",
             "tiktok": f"https://tiktok.com/@{inp.input_handle}",
             "twitter": f"https://x.com/{inp.input_handle}",
         }
         url = domain_map.get(inp.input_platform_hint)

    context = {"raw_input": inp.model_dump(mode='json'), "scraped_data": None}
    if url:
        try:
            r = httpx.get(url, timeout=10.0, follow_redirects=True)
            soup = BeautifulSoup(r.text, 'html.parser')
            # Extract basic text content and links
            text_content = soup.get_text(separator=' ', strip=True)[:5000] # Cap 5k chars
            links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith('http')][:50]
            context["scraped_data"] = {
                "page_title": soup.title.string if soup.title else None,
                "text_sample": text_content,
                "outbound_links": links
            }
        except Exception as e:
             console.log(f"[yellow]Failed to fetch URL context {url}: {e}[/yellow]")
             
    return context

def resolve_link_in_bio(url: str) -> list[str]:
    # Placeholder for actual Linktree/Beacons resolution logic.
    # A complete implementation would fetch the page and extract URLs linking out.
    return []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def run_gemini_discovery(context: dict, link_destinations: list[str]) -> DiscoveryResult:
    genai.configure(api_key=get_gemini_key())
    # Use gemini-1.5-pro for high complexity reasoning
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = f"""
    Analyze the following creator footprint data and discover their true identity, aliases, and platforms.
    Context Data:
    {json.dumps(context, indent=2)}
    
    Link in Bio Destinations (if any found):
    {json.dumps(link_destinations, indent=2)}
    """
    
    # Passing structured model for strict JSON extraction
    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=DiscoveryResult
        )
    )
    
    return DiscoveryResult.model_validate_json(resp.text)

def commit(run_id: UUID, result: DiscoveryResult):
    sb = get_supabase()
    # Call the RPC to transact the results
    data = result.model_dump(mode='json')
    # Partition the data for the RPC
    creator_data = {
       "canonical_name": data["canonical_name"],
       "known_usernames": data["known_usernames"],
       "display_name_variants": data["display_name_variants"],
       "primary_platform": data["primary_platform"],
       "primary_niche": data["primary_niche"],
       "monetization_model": data["monetization_model"]
    }
    accounts_data = data["proposed_accounts"]
    funnel_edges = data["proposed_funnel_edges"]
    
    try:
        res = sb.rpc("commit_discovery_result", {
            "p_run_id": str(run_id),
            "p_creator_data": creator_data,
            "p_accounts": accounts_data,
            "p_funnel_edges": funnel_edges
        }).execute()
        console.log(f"[green]Successfully committed discovery run {run_id}.[/green]")
    except Exception as e:
        console.log(f"[red]Commit failed: {e}[/red]")
        raise e

def run(inp: DiscoveryInput) -> None:
    sb = get_supabase()
    try:
        console.log(f"[blue]Starting discovery run {inp.run_id}[/blue]")
        ctx = fetch_input_context(inp)
        
        links = []
        if ctx.get("scraped_data"):
             links = ctx["scraped_data"].get("outbound_links", [])
             
        # Optional: actively resolve linktree
        resolved = []
        for l in links:
             if "linktr.ee" in l or "beacons.ai" in l:
                 resolved.extend(resolve_link_in_bio(l))
                 
        res = run_gemini_discovery(ctx, resolved)
        commit(inp.run_id, res)
        
        # Trigger follow-up Apify Scrape if we found an IG account
        console.log("[cyan]Checking if Apify scrape is needed...[/cyan]")
        ig_accounts = [acc for acc in res.proposed_accounts if acc.platform == "instagram"]
        
        if ig_accounts:
            ig_handle = ig_accounts[0].handle
            if not ig_handle and ig_accounts[0].url:
                 ig_handle = ig_accounts[0].url.strip('/').split('/')[-1]
                 
            if ig_handle:
                console.log(f"[cyan]Dispatching Apify scrape for detected IG handle: {ig_handle}[/cyan]")
                # We do a small scrape (5 posts) on initial discovery to populate recent content
                scrape_instagram_profile(str(inp.workspace_id), ig_handle, limit=5)
            
    except Exception as e:
        console.log(f"[red]Fatal discovery error: {str(e)}[/red]")
        try:
            sb.rpc("mark_discovery_failed", {
                "p_run_id": str(inp.run_id),
                "p_error": str(e)
            }).execute()
        except Exception as nested_e:
            console.log(f"[red]Failed to run error RPC: {nested_e}[/red]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=str)
    args = parser.parse_args()
    
    sb = get_supabase()
    # Fetch run details to construct input
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
        input_platform_hint=data["input_platform_hint"]
    )
    run(inp)
