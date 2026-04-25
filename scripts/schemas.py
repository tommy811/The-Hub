# scripts/schemas.py — Pydantic models for discovery pipeline
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field

PLATFORM_VALUES = (
    "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
    "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
    "tiktok_shop", "linktree", "beacons", "custom_domain",
    "telegram_channel", "telegram_cupidbot", "other",
)

Platform = Literal[
    "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
    "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
    "tiktok_shop", "linktree", "beacons", "custom_domain",
    "telegram_channel", "telegram_cupidbot", "other",
]

EdgeType = Literal["link_in_bio", "direct_link", "cta_mention", "qr_code", "inferred"]

AccountType = Literal["social", "monetization", "link_in_bio", "messaging", "other"]

MonetizationModel = Literal[
    "subscription", "tips", "ppv", "affiliate", "brand_deals",
    "ecommerce", "coaching", "saas", "mixed", "unknown",
]


class DiscoveryInput(BaseModel):
    run_id: UUID
    creator_id: UUID
    workspace_id: UUID
    input_handle: Optional[str] = None
    input_url: Optional[str] = None
    input_platform_hint: Optional[str] = None


class InputContext(BaseModel):
    """Structured context passed to Gemini. Replaces the old free-form HTML dump."""
    handle: str
    platform: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    external_urls: list[str] = Field(default_factory=list)
    link_in_bio_destinations: list[str] = Field(default_factory=list)
    source_note: Optional[str] = None  # e.g. "apify/instagram-scraper details mode"

    def is_empty(self) -> bool:
        """True when the Apify fetch produced nothing useful (login wall / gone / private)."""
        return (
            not self.bio
            and self.follower_count is None
            and not self.external_urls
        )


class ProposedAccount(BaseModel):
    account_type: AccountType
    platform: Platform
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
    from_platform: Platform
    to_handle: str
    to_platform: Platform
    edge_type: EdgeType
    confidence: float = Field(ge=0.0, le=1.0)


class DiscoveryResult(BaseModel):
    canonical_name: str
    known_usernames: list[str]
    display_name_variants: list[str]
    primary_platform: Platform
    primary_niche: Optional[str] = None
    monetization_model: MonetizationModel = "unknown"
    proposed_accounts: list[ProposedAccount]
    proposed_funnel_edges: list[ProposedFunnelEdge]
    raw_reasoning: str


# --- v2 additions ---

DestinationClass = Literal["monetization", "aggregator", "social", "other"]
DiscoverySource = Literal["seed", "manual_add", "retry", "auto_expand"]


class DiscoveredUrl(BaseModel):
    """A URL the resolver discovered + classified. One row per URL in the creator's network."""
    canonical_url: str
    platform: Platform
    account_type: AccountType
    destination_class: DestinationClass
    reason: str  # 'rule:X' | 'llm:high_confidence' | 'llm:cache_hit' | 'llm:low_confidence' | 'llm:timeout' | 'manual_add'
    depth: int = 0  # 0 = seed, 1 = surfaced from seed bio, 2 = surfaced from depth-1's bio, ...


class TextMention(BaseModel):
    """A handle Gemini extracted from bio prose (no URL present). Fed back into Stage B."""
    platform: Platform
    handle: str
    source: Literal["seed_bio", "enriched_bio"] = "seed_bio"


HighlightSource = Literal["highlight_link_sticker", "highlight_caption_mention"]


class HighlightLink(BaseModel):
    """A URL or handle surfaced from an IG highlight item.

    Two flavors:
    - `highlight_link_sticker`: an absolute URL clicked through the link sticker.
      `url` is populated; `platform`/`handle` may be None.
    - `highlight_caption_mention`: a @handle mention in the caption/text overlay,
      extracted by Gemini. `platform` + `handle` are populated; `url` is "" (the
      resolver synthesizes it via _synthesize_url).
    """
    url: str = ""
    source: HighlightSource
    platform: Optional[Platform] = None
    handle: Optional[str] = None
    source_text: Optional[str] = None  # raw caption / sticker title for debugging


class DiscoveryResultV2(BaseModel):
    """Narrower Gemini output shape — no URL classification, no account proposals.

    Resolver output populates accounts/funnel_edges directly from the classifier
    and fetchers; Gemini's remaining job is canonicalization + niche + text hints.
    """
    canonical_name: str
    known_usernames: list[str]
    display_name_variants: list[str]
    primary_niche: Optional[str] = None
    monetization_model: MonetizationModel = "unknown"
    text_mentions: list[TextMention] = Field(default_factory=list)
    raw_reasoning: str
