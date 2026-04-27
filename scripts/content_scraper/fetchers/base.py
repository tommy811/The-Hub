"""Base contract for platform content fetchers.

Each subclass implements `fetch(profiles, since)` and returns a dict
mapping profile_id → list of NormalizedPost. The orchestrator calls one
fetcher per platform per CLI run, batching all profiles for that platform
into one Apify call (cost optimization — see spec Appendix C).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable
from uuid import UUID

from content_scraper.normalizer import NormalizedPost


class ProfileTarget:
    """A single profile to scrape, plus the inputs the fetcher needs."""
    def __init__(self, *, profile_id: UUID, handle: str, profile_url: str | None = None):
        self.profile_id = profile_id
        self.handle = handle
        self.profile_url = profile_url

    def __repr__(self) -> str:
        return f"ProfileTarget({self.handle!r}, {self.profile_id})"


class BaseContentFetcher(ABC):
    """Platform-agnostic content fetcher contract.

    Subclasses are responsible for:
      - Translating ProfileTargets into the Apify actor's input shape
      - Issuing ONE actor call covering all targets
      - Disaggregating results back to per-profile lists
      - Calling the right normalizer (instagram_to_normalized / tiktok_to_normalized)
      - Wrapping transient errors with tenacity (use is_transient_apify_error)
    """

    @abstractmethod
    async def fetch(
        self,
        profiles: Iterable[ProfileTarget],
        *,
        since: datetime,
    ) -> dict[UUID, list[NormalizedPost]]:
        """Fetch posts for the given profiles since the given datetime.

        Returns a dict keyed by profile_id. Profiles that returned no posts
        (private, login wall, captcha, no posts in window) are absent from
        the dict — the orchestrator treats absence as "skip with warning."
        """
