# scripts/harvester/types.py
from typing import Literal
from pydantic import BaseModel, Field

from schemas import DestinationClass

HarvestMethod = Literal["cache", "httpx", "headless"]

# Destination classes whose pages are routing surfaces — recurse into them.
# Excludes terminal classes (social profiles handled by fetchers; monetization
# and messaging are leaf nodes).
HARVEST_CLASSES: frozenset[str] = frozenset({
    "aggregator", "content", "commerce", "affiliate", "professional", "unknown",
})

# Substrings (lowercase) we look for in HTML to detect 2-step interstitials.
SIGNAL_KEYWORDS: frozenset[str] = frozenset({
    "sensitive content",
    "open link",
    "continue to",
    "i am over 18",
    "may contain content",
    "external website",
})

# DOM hydration markers — page is SPA-rendered, anchors materialize after JS runs.
SPA_MARKERS: frozenset[str] = frozenset({
    "data-reactroot",
    "__next_data__",
    "data-vue-meta",
    "data-svelte",
    "astro-island",  # Astro 4+ uses <astro-island> custom elements for hydration
})

# Floor below which an aggregator-shaped page looks suspicious.
LOW_ANCHOR_FLOOR = 2


class HarvestedUrl(BaseModel):
    canonical_url: str
    raw_url: str
    raw_text: str = ""
    destination_class: DestinationClass
    harvest_method: HarvestMethod


class Tier1Result(BaseModel):
    html: str = ""
    anchors: list[str] = Field(default_factory=list)
    anchor_texts: dict[str, str] = Field(default_factory=dict)  # url → label
    signals_tripped: set[str] = Field(default_factory=set)

    def needs_tier2(self) -> bool:
        return bool(self.signals_tripped)
