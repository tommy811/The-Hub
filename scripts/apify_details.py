# scripts/apify_details.py — DEPRECATED shim. Use fetchers.{instagram,tiktok} directly.
# Kept temporarily so PR #2's tests keep importing from the old path until
# Task 17 rewires discover_creator.py onto the resolver.
from fetchers.base import EmptyDatasetError  # noqa: F401
from fetchers.instagram import fetch as fetch_instagram_details  # noqa: F401
from fetchers.tiktok import fetch as fetch_tiktok_details  # noqa: F401
