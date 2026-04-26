# scripts/pipeline/classifier.py — URL → (platform, account_type) classifier
import json
from dataclasses import dataclass
from typing import Optional
import google.generativeai as genai

from common import get_gemini_key
from data.gazetteer_loader import lookup as gazetteer_lookup

_LLM_MODEL = "gemini-2.5-flash"
_CONFIDENCE_THRESHOLD = 0.7

_PROMPT_TEMPLATE = """You are classifying a URL into a creator-platform taxonomy.

URL: {url}

Return a JSON object with these fields:
- platform: one of [instagram, tiktok, youtube, patreon, twitter, linkedin, facebook, onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, linktree, beacons, custom_domain, telegram_channel, telegram_cupidbot, link_me, tapforallmylinks, allmylinks, lnk_bio, snipfeed, launchyoursocials, fanfix, cashapp, venmo, kofi, buymeacoffee, snapchat, reddit, threads, bluesky, spotify, substack, discord, whatsapp, other]
- account_type: one of [social, monetization, link_in_bio, messaging, other]
- confidence: float 0.0-1.0 — how confident are you this is the right classification

Rules:
- monetization: anywhere a creator collects payment (subscription, tips, PPV, store, coaching landing page)
- social: content-posting social network profile
- link_in_bio: aggregator page listing multiple destinations
- messaging: direct communication channel (Telegram, Discord invite)
- other: affiliate links, news articles, blog posts, miscellaneous
- Below 0.7 confidence → prefer platform='other', account_type='other'.

Return ONLY the JSON object, no surrounding text.
"""


@dataclass(frozen=True)
class Classification:
    platform: str
    account_type: str
    confidence: float
    reason: str  # 'rule:X' | 'llm:high_confidence' | 'llm:low_confidence' | 'llm:cache_hit' | 'llm:timeout' | 'llm:no_cache_context'
    model_version: Optional[str] = None


def _classify_via_llm(url: str) -> tuple[str, str, float, str]:
    """Call Gemini to classify. Returns (platform, account_type, confidence, model_version)."""
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel(_LLM_MODEL)
    resp = model.generate_content(
        _PROMPT_TEMPLATE.format(url=url),
        generation_config=genai.GenerationConfig(response_mime_type="application/json"),
    )
    parsed = json.loads(resp.text)
    return (
        parsed.get("platform", "other"),
        parsed.get("account_type", "other"),
        float(parsed.get("confidence", 0.0)),
        _LLM_MODEL,
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
                  confidence: float, model_version: str) -> None:
    sb.table("classifier_llm_guesses").upsert({
        "canonical_url": canonical_url,
        "platform_guess": platform,
        "account_type_guess": account_type,
        "confidence": confidence,
        "model_version": model_version,
    }).execute()


def classify(canonical_url: str, supabase) -> Classification:
    """Classify a canonical URL into (platform, account_type).

    Rule-first via gazetteer. On miss, falls through to cached LLM guess. On
    cache miss, calls Gemini once and caches. On LLM timeout/error, returns
    ('other', 'other') with reason='llm:timeout' — non-fatal.

    `supabase` may be None (unit-test / offline context). In that case rule
    matches work but LLM fallback returns ('other','other','llm:no_cache_context').
    """
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
        platform, account_type, conf, model_v = _classify_via_llm(canonical_url)
    except TimeoutError:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:timeout")
    except Exception:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:timeout")

    try:
        _cache_insert(supabase, canonical_url, platform, account_type, conf, model_v)
    except Exception:
        pass  # non-fatal — we still return the guess

    if conf >= _CONFIDENCE_THRESHOLD:
        return Classification(platform=platform, account_type=account_type,
                              confidence=conf, reason="llm:high_confidence",
                              model_version=model_v)
    return Classification(platform="other", account_type="other",
                          confidence=conf, reason="llm:low_confidence",
                          model_version=model_v)
