# scripts/fetchers/youtube.py — YouTube channel fetcher via yt-dlp
import re
import yt_dlp

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",
    "skip_download": True,
    "playlist_items": "0",  # don't fetch videos, just channel info
}

_URL_RE = re.compile(r"https?://[^\s]+")


def _best_thumbnail(thumbnails: list[dict]) -> str | None:
    if not thumbnails:
        return None
    # yt-dlp orders by preference; pick highest-preference with url
    ranked = sorted(thumbnails, key=lambda t: t.get("preference", 0), reverse=True)
    for t in ranked:
        if t.get("url"):
            return t["url"]
    return None


def fetch(handle: str) -> InputContext:
    """Fetch YouTube channel profile context via yt-dlp.

    `handle` is expected as `@handle`. Strips `@` for URL building. Raises
    EmptyDatasetError on any extraction failure (channel not found, private,
    terms-of-service block).
    """
    clean = handle.lstrip("@")
    url = f"https://www.youtube.com/@{clean}"
    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise EmptyDatasetError(
            f"yt-dlp could not extract channel info for @{clean}: {e}"
        )

    if not info:
        raise EmptyDatasetError(f"yt-dlp returned empty info for @{clean}")

    description = info.get("description") or ""
    external_urls = _URL_RE.findall(description)

    return InputContext(
        handle=handle,
        platform="youtube",
        display_name=info.get("channel") or info.get("uploader"),
        bio=description,
        follower_count=info.get("channel_follower_count"),
        avatar_url=_best_thumbnail(info.get("thumbnails") or []),
        external_urls=external_urls,
        source_note="yt-dlp channel info",
    )
