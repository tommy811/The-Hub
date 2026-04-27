"""Content scraper orchestrator.

Resolves the per-platform fetcher dispatch, calls commit_scrape_result,
runs flag_outliers per profile, and writes the daily profile metrics
snapshot. Error handling + dead-letter come in T9.
"""
from __future__ import annotations
import asyncio
import logging
import statistics
from dataclasses import dataclass
from datetime import datetime, date
from typing import Iterable
from uuid import UUID

from supabase import Client

from content_scraper.fetchers.base import BaseContentFetcher, ProfileTarget
from content_scraper.normalizer import NormalizedPost

_log = logging.getLogger(__name__)


@dataclass
class ProfileScope:
    profile_id: UUID
    handle: str
    platform: str  # "instagram" | "tiktok"
    creator_id: UUID


@dataclass
class ScrapeRunSummary:
    profiles_scraped: int = 0
    profiles_skipped: int = 0
    posts_upserted: int = 0
    outliers_flagged: int = 0
    failures: int = 0


class ScrapeOrchestrator:
    def __init__(
        self,
        *,
        supabase: Client,
        ig_fetcher: BaseContentFetcher,
        tt_fetcher: BaseContentFetcher,
        dead_letter_path: str | None,
    ):
        self._sb = supabase
        self._ig = ig_fetcher
        self._tt = tt_fetcher
        self._dead_letter_path = dead_letter_path

    async def run(
        self,
        scopes: Iterable[ProfileScope],
        *,
        since: datetime,
    ) -> ScrapeRunSummary:
        scope_list = list(scopes)
        ig_targets, tt_targets = [], []
        scope_by_pid: dict[UUID, ProfileScope] = {}
        for s in scope_list:
            scope_by_pid[s.profile_id] = s
            target = ProfileTarget(profile_id=s.profile_id, handle=s.handle)
            if s.platform == "instagram":
                ig_targets.append(target)
            elif s.platform == "tiktok":
                tt_targets.append(target)

        ig_result, tt_result = await asyncio.gather(
            self._ig.fetch(ig_targets, since=since),
            self._tt.fetch(tt_targets, since=since),
        )

        per_profile: dict[UUID, list[NormalizedPost]] = {}
        per_profile.update(ig_result)
        per_profile.update(tt_result)

        summary = ScrapeRunSummary()
        for s in scope_list:
            posts = per_profile.get(s.profile_id, [])
            if not posts:
                summary.profiles_skipped += 1
                _log.info("scrape_skip profile_id=%s handle=%s reason=no_posts",
                          s.profile_id, s.handle)
                continue
            await self._commit_one_profile(s, posts, summary)
        return summary

    async def _commit_one_profile(
        self,
        scope: ProfileScope,
        posts: list[NormalizedPost],
        summary: ScrapeRunSummary,
    ) -> None:
        payload = [p.model_dump(mode="json") for p in posts]
        commit_resp = await asyncio.to_thread(
            lambda: self._sb.rpc("commit_scrape_result", {
                "p_profile_id": str(scope.profile_id),
                "p_posts": payload,
            }).execute()
        )
        commit_data = commit_resp.data or {}
        summary.posts_upserted += int(commit_data.get("posts_upserted", 0))

        await asyncio.to_thread(
            lambda: self._sb.rpc("flag_outliers", {
                "p_profile_id": str(scope.profile_id),
            }).execute()
        )

        await self._write_profile_snapshot(scope, posts, summary)
        summary.profiles_scraped += 1

    async def _write_profile_snapshot(
        self,
        scope: ProfileScope,
        posts: list[NormalizedPost],
        summary: ScrapeRunSummary,
    ) -> None:
        rows_resp = await asyncio.to_thread(
            lambda: self._sb.table("scraped_content")
                .select("view_count,is_outlier")
                .eq("profile_id", str(scope.profile_id))
                .execute()
        )
        rows = rows_resp.data or []
        view_counts = [r.get("view_count") or 0 for r in rows]
        outlier_count = sum(1 for r in rows if r.get("is_outlier"))
        median_views = int(statistics.median(view_counts)) if view_counts else 0
        summary.outliers_flagged += outlier_count

        prof_resp = await asyncio.to_thread(
            lambda: self._sb.table("profiles")
                .select("follower_count")
                .eq("id", str(scope.profile_id))
                .single()
                .execute()
        )
        follower_count = (prof_resp.data or {}).get("follower_count")

        await asyncio.to_thread(
            lambda: self._sb.table("profile_metrics_snapshots").upsert({
                "profile_id": str(scope.profile_id),
                "snapshot_date": date.today().isoformat(),
                "follower_count": follower_count,
                "median_views": median_views,
                "outlier_count": outlier_count,
            }, on_conflict="profile_id,snapshot_date").execute()
        )
