# Gemini Schema

## Discovery Response Schema
Used as `response_schema` in the Gemini API call.
Defined in `scripts/discover_creator.py` as `GEMINI_DISCOVERY_SCHEMA`.
This is the single source of truth — prompt and model both reference this dict.

```python
GEMINI_DISCOVERY_SCHEMA = {
  "type": "object",
  "properties": {
    "canonical_name": {"type": "string"},
    "known_usernames": {"type": "array", "items": {"type": "string"}},
    "display_name_variants": {"type": "array", "items": {"type": "string"}},
    "primary_platform": {
      "type": "string",
      "enum": [
        "instagram","tiktok","youtube","facebook","twitter","linkedin","patreon",
        "onlyfans","fanvue","fanplace","amazon_storefront","tiktok_shop",
        "linktree","beacons","custom_domain",
        "telegram_channel","telegram_cupidbot","other"
      ]
    },
    "primary_niche": {"type": "string"},
    "monetization_model": {
      "type": "string",
      "enum": ["subscription","tips","ppv","affiliate","brand_deals","ecommerce","coaching","saas","mixed","unknown"]
    },
    "raw_reasoning": {"type": "string"},
    "proposed_accounts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "account_type": {
            "type": "string",
            "enum": ["social","monetization","link_in_bio","messaging","other"]
          },
          "platform": {"type": "string", "enum": ["instagram","tiktok","youtube","facebook","twitter","linkedin","patreon","onlyfans","fanvue","fanplace","amazon_storefront","tiktok_shop","linktree","beacons","custom_domain","telegram_channel","telegram_cupidbot","other"]},
          "handle": {"type": ["string","null"]},
          "url": {"type": ["string","null"]},
          "display_name": {"type": ["string","null"]},
          "bio": {"type": ["string","null"]},
          "follower_count": {"type": ["integer","null"]},
          "is_primary": {"type": "boolean"},
          "discovery_confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "reasoning": {"type": "string"}
        },
        "required": ["account_type","platform","is_primary","discovery_confidence","reasoning"]
      }
    },
    "proposed_funnel_edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "from_handle": {"type": "string"},
          "from_platform": {"type": "string"},
          "to_handle": {"type": "string"},
          "to_platform": {"type": "string"},
          "edge_type": {
            "type": "string",
            "enum": ["link_in_bio","direct_link","cta_mention","qr_code","inferred"]
          },
          "confidence": {"type": "number"}
        }
      }
    }
  },
  "required": [
    "canonical_name","known_usernames","primary_platform",
    "monetization_model","proposed_accounts","proposed_funnel_edges","raw_reasoning"
  ]
}
```

## Confidence Score Guide (instruct Gemini in prompt)
- 1.0 — Found via direct link (IG bio → Linktree → this account)
- 0.8–0.99 — Found in link-in-bio destinations
- 0.5–0.79 — Inferred from display name / handle similarity
- 0.3–0.49 — Speculative (same niche, similar name)
- < 0.3 — Do not include

## Content Analysis Schema (Phase 3)

> **Note:** `archetype` and `vibe` appear here because they exist in `content_analysis` in the live schema (initial migration). The Phase 2 migration will DROP these columns from `content_analysis` and move them to `creators`. When that migration runs, remove `archetype` and `vibe` from this schema and from `required`. See [[PROJECT_STATE#4.2 Pending migration]] and [[03-Database/Migration Log]].

```python
GEMINI_ANALYSIS_SCHEMA = {
  "type": "object",
  "properties": {
    "quality_score": {"type": "number", "minimum": 0, "maximum": 100},
    "archetype": {"type": "string", "enum": ["the_jester","the_caregiver","the_lover","the_everyman","the_creator","the_hero","the_sage","the_innocent","the_explorer","the_rebel","the_magician","the_ruler"]},
    "vibe": {"type": "string", "enum": ["playful","girl_next_door","body_worship","wifey","luxury","edgy","wholesome","mysterious","confident","aspirational"]},
    "category": {"type": "string", "enum": ["comedy_entertainment","fashion_style","fitness","lifestyle","beauty","travel","food","music","gaming","education","other"]},
    "visual_tags": {"type": "array", "items": {"type": "string"}},
    "hook_analysis": {"type": "string"},
    "is_clean": {"type": "boolean"},
    "transcription": {"type": ["string","null"]}
  },
  "required": ["quality_score","archetype","vibe","category","is_clean"]
}
```
