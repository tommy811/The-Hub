# scripts/pipeline/classifier.py — URL → (platform, account_type) classifier
import json
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs
import google.generativeai as genai

from common import get_gemini_key
from data.gazetteer_loader import lookup as gazetteer_lookup

_LLM_MODEL = "gemini-2.5-flash"
_CONFIDENCE_THRESHOLD = 0.7

# link.me redirector → destination platform via sensitiveLinkLabel param.
# Hand-maintained map; extend as new labels appear.
_LINKME_LABEL_TO_PLATFORM = {
    "of": ("onlyfans", "monetization"),
    "onlyfans": ("onlyfans", "monetization"),
    "fanvue": ("fanvue", "monetization"),
    "fanfix": ("fanfix", "monetization"),
    "fanplace": ("fanplace", "monetization"),
    "patreon": ("patreon", "monetization"),
}


def _classify_linkme_redirector(canonical_url: str) -> tuple[str, str, str] | None:
    """Classify visit.link.me redirector URLs by their sensitiveLinkLabel param.

    link.me's 'sensitive content' wrapper exposes the destination platform
    in the query string (e.g. ?sensitiveLinkLabel=OF). Treat this as authoritative
    — it's link.me's own metadata, not inference.
    """
    try:
        parsed = urlparse(canonical_url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host != "visit.link.me":
        return None
    params = parse_qs(parsed.query)
    label_raw = (params.get("sensitiveLinkLabel") or [""])[0].lower().strip()
    if not label_raw:
        return None
    mapping = _LINKME_LABEL_TO_PLATFORM.get(label_raw)
    if not mapping:
        return None
    platform, account_type = mapping
    return (platform, account_type, f"rule:linkme_redirector_{label_raw}")

_PROMPT_TEMPLATE = """You are classifying a URL into a creator-platform taxonomy AND describing the platform.

URL: {url}

Return a JSON object with these fields:

REQUIRED — for the taxonomy:
- platform: one of [instagram, tiktok, youtube, patreon, twitter, linkedin, facebook, onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, linktree, beacons, custom_domain, telegram_channel, telegram_cupidbot, link_me, tapforallmylinks, allmylinks, lnk_bio, snipfeed, launchyoursocials, fanfix, cashapp, venmo, snapchat, reddit, spotify, threads, bluesky, kofi, buymeacoffee, substack, discord, whatsapp, other]
- account_type: one of [social, monetization, link_in_bio, messaging, other]
- confidence: float 0.0-1.0 — how confident are you this is the right classification

ALSO REQUIRED — for VA-actionable platform suggestions (used when platform='other'):
- suggested_label: human-readable platform name (e.g. "Stan Store", "Bunny App", "ManyVids"). If platform isn't 'other', use the canonical platform name.
- suggested_slug: proposed snake_case slug for our enum (e.g. "stan_store", "bunny_app"). If platform isn't 'other', use the platform value itself.
- description: one short sentence describing what this platform/site is (e.g. "Creator e-commerce platform for digital products and tips"). Always provide.
- icon_category: visual class hint, one of [monetization, social, aggregator, messaging, content, ecommerce, other]

Rules:
- monetization: anywhere a creator collects payment (subscription, tips, PPV, store, coaching landing page)
- social: content-posting social network profile
- link_in_bio: aggregator page listing multiple destinations
- messaging: direct communication channel (Telegram, Discord invite, WhatsApp)
- ecommerce: a Stan-store-like product page or storefront (treat as monetization for account_type, but use icon_category=ecommerce)
- content: blog/podcast/newsletter (Substack, Medium, Spotify show)
- other: affiliate links, news articles, miscellaneous
- Below 0.7 confidence → prefer platform='other', account_type='other', but STILL provide best-guess suggested_label / suggested_slug / description / icon_category from URL host inspection.

Return ONLY the JSON object, no surrounding text.
"""


@dataclass(frozen=True)
class Classification:
    platform: str
    account_type: str
    confidence: float
    reason: str  # 'rule:X' | 'llm:high_confidence' | 'llm:low_confidence' | 'llm:cache_hit' | 'llm:timeout' | 'llm:no_cache_context'
    model_version: Optional[str] = None


def _classify_via_llm(url: str) -> tuple[str, str, float, str, dict]:
    """Call Gemini to classify. Returns (platform, account_type, confidence, model_version, enriched_metadata)."""
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel(_LLM_MODEL)
    resp = model.generate_content(
        _PROMPT_TEMPLATE.format(url=url),
        generation_config=genai.GenerationConfig(response_mime_type="application/json"),
    )
    parsed = json.loads(resp.text)
    enriched = {
        "suggested_label": parsed.get("suggested_label") or "",
        "suggested_slug": parsed.get("suggested_slug") or "",
        "description": parsed.get("description") or "",
        "icon_category": parsed.get("icon_category") or "",
    }
    return (
        parsed.get("platform", "other"),
        parsed.get("account_type", "other"),
        float(parsed.get("confidence", 0.0)),
        _LLM_MODEL,
        enriched,
    )


def _cache_lookup(sb, canonical_url: str) -> Optional[dict]:
    # supabase-py 2.x: .maybe_single().execute() returns None (not APIResponse)
    # when no row matches. Guard against that before accessing .data.
    resp = sb.table("classifier_llm_guesses").select("*").eq(
        "canonical_url", canonical_url
    ).maybe_single().execute()
    if resp is None:
        return None
    return resp.data


def _cache_insert(sb, canonical_url: str, platform: str, account_type: str,
                  confidence: float, model_version: str,
                  enriched: dict | None = None) -> None:
    payload = {
        "canonical_url": canonical_url,
        "platform_guess": platform,
        "account_type_guess": account_type,
        "confidence": confidence,
        "model_version": model_version,
    }
    if enriched:
        payload["suggested_label"] = enriched.get("suggested_label") or None
        payload["suggested_slug"] = enriched.get("suggested_slug") or None
        payload["description"] = enriched.get("description") or None
        payload["icon_category"] = enriched.get("icon_category") or None
    sb.table("classifier_llm_guesses").upsert(payload).execute()


def classify(canonical_url: str, supabase) -> Classification:
    """Classify a canonical URL into (platform, account_type).

    Rule-first via gazetteer. On miss, falls through to cached LLM guess. On
    cache miss, calls Gemini once and caches. On LLM timeout/error, returns
    ('other', 'other') with reason='llm:timeout' — non-fatal.

    `supabase` may be None (unit-test / offline context). In that case rule
    matches work but LLM fallback returns ('other','other','llm:no_cache_context').
    """
    # Special: link.me redirector with explicit destination metadata
    # e.g. https://visit.link.me/kirapregiato?sensitiveLinkLabel=OF
    # The query param tells us the actual destination platform.
    redirector_hit = _classify_linkme_redirector(canonical_url)
    if redirector_hit is not None:
        platform, account_type, reason = redirector_hit
        return Classification(
            platform=platform, account_type=account_type,
            confidence=1.0, reason=reason,
        )

    # 1. Rule match
    rule_hit = gazetteer_lookup(canonical_url)
    if rule_hit is not None:
        platform, account_type, reason = rule_hit
        return Classification(platform=platform, account_type=account_type,
                              confidence=1.0, reason=reason)

    # 2. No DB → can't cache, skip LLM
    if supabase is None:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:no_cache_context")

    # 3. Cache hit
    cached = _cache_lookup(supabase, canonical_url)
    if cached:
        return Classification(
            platform=cached["platform_guess"] or "other",
            account_type=cached["account_type_guess"] or "other",
            confidence=float(cached["confidence"]),
            reason="llm:cache_hit",
            model_version=cached["model_version"],
        )

    # 4. LLM fallback
    try:
        platform, account_type, conf, model_v, enriched = _classify_via_llm(canonical_url)
    except TimeoutError:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:timeout")
    except Exception:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:timeout")

    try:
        _cache_insert(supabase, canonical_url, platform, account_type, conf, model_v, enriched)
    except Exception:
        pass  # non-fatal — we still return the guess

    if conf >= _CONFIDENCE_THRESHOLD:
        return Classification(platform=platform, account_type=account_type,
                              confidence=conf, reason="llm:high_confidence",
                              model_version=model_v)
    return Classification(platform="other", account_type="other",
                          confidence=conf, reason="llm:low_confidence",
                          model_version=model_v)
