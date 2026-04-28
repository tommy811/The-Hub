"""Instagram content fetcher — apify/instagram-scraper, batched directUrls."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Iterable
from uuid import UUID

from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from content_scraper.fetchers.base import BaseContentFetcher, FetchBatchResult, ProfileTarget
from content_scraper.normalizer import NormalizedPost, instagram_to_normalized
from fetchers.base import is_transient_apify_error

_log = logging.getLogger(__name__)
_ACTOR_ID = "apify/instagram-scraper"


class InstagramContentFetcher(BaseContentFetcher):
    def __init__(self, *, apify_client: ApifyClient):
        self._apify = apify_client

    async def fetch(
        self,
        profiles: Iterable[ProfileTarget],
        *,
        since: datetime,
    ) -> FetchBatchResult:
        targets = list(profiles)
        if not targets:
            return FetchBatchResult(posts_by_profile={}, actor_id=_ACTOR_ID)

        handle_to_pid: dict[str, UUID] = {p.handle.lower(): p.profile_id for p in targets}
        run_id, dataset_id, items = await asyncio.to_thread(
            self._call_actor,
            direct_urls=[f"https://www.instagram.com/{p.handle}/" for p in targets],
            since=since,
        )

        out: dict[UUID, list[NormalizedPost]] = {}
        for item in items:
            owner = (item.get("ownerUsername") or "").lower()
            pid = handle_to_pid.get(owner)
            if pid is None:
                continue
            try:
                normalized = instagram_to_normalized(item, profile_id=pid)
            except Exception as exc:
                _log.warning("ig_normalize_failed id=%s err=%s", item.get("id"), exc)
                continue
            out.setdefault(pid, []).append(normalized)
        return FetchBatchResult(
            posts_by_profile=out,
            actor_id=_ACTOR_ID,
            apify_run_id=run_id,
            dataset_id=dataset_id,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception(is_transient_apify_error),
        reraise=True,
    )
    def _call_actor(self, *, direct_urls: list[str], since: datetime) -> tuple[str | None, str | None, list[dict]]:
        run_input = {
            "directUrls": direct_urls,
            "resultsType": "posts",
            "resultsLimit": 200,
            "onlyPostsNewerThan": since.date().isoformat(),
            "addParentData": True,
        }
        run = self._apify.actor(_ACTOR_ID).call(run_input=run_input)
        run_id = run.get("id")
        ds_id = run["defaultDatasetId"]
        items = list(self._apify.dataset(ds_id).iterate_items())
        return run_id, ds_id, items
