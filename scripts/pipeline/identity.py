# scripts/pipeline/identity.py — Rule-cascade identity scorer
import re
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional


@dataclass
class ProfileFingerprint:
    """Everything identity.py needs to score a profile against peers."""
    profile_id: str
    handle: str
    platform: str
    bio: str = ""
    display_name: str = ""
    avatar_url: Optional[str] = None
    destination_urls: list[str] = field(default_factory=list)
    # {canonical_url: destination_class} — 'monetization' | 'aggregator' | 'social' | 'other'
    destination_classes: dict[str, str] = field(default_factory=dict)
    niche: Optional[str] = None


Action = Literal["auto_merge", "merge_candidate", "discard"]


@dataclass(frozen=True)
class IdentityVerdict:
    action: Action
    confidence: float
    reason: str
    evidence: dict


def _shared_classed_url(a: ProfileFingerprint, b: ProfileFingerprint,
                         target_class: str) -> Optional[str]:
    """Return the first URL that appears in both profiles with destination_class == target."""
    a_urls = {u for u in a.destination_urls if a.destination_classes.get(u) == target_class}
    b_urls = {u for u in b.destination_urls if b.destination_classes.get(u) == target_class}
    intersection = a_urls & b_urls
    return next(iter(intersection), None)


def _normalize_handle(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def _bio_mentions_other(a: ProfileFingerprint, b: ProfileFingerprint) -> bool:
    """True if a.bio contains b.handle (as @handle or full URL). Direction: a→b only."""
    if not a.bio:
        return False
    bio_lower = a.bio.lower()
    handle_norm = _normalize_handle(b.handle)
    if not handle_norm:
        return False
    # Match @handle, /handle/, or handle as whole word
    patterns = [
        rf"@{re.escape(b.handle.lower())}\b",
        rf"/{re.escape(b.handle.lower())}/",
        rf"\b{re.escape(b.handle.lower())}\b",
    ]
    return any(re.search(p, bio_lower) for p in patterns)


def score_pair(a: ProfileFingerprint, b: ProfileFingerprint,
               clip_fn: Optional[Callable[[str, str], float]]) -> IdentityVerdict:
    """Score a pair of profile fingerprints via rule cascade. First match wins.

    clip_fn(avatar_url_a, avatar_url_b) -> cosine similarity 0.0-1.0. May be None
    for unit tests — in that case Rule 4 is skipped.
    """
    # Rule 1: shared monetization destination → auto-merge
    url = _shared_classed_url(a, b, "monetization")
    if url:
        return IdentityVerdict(
            action="auto_merge", confidence=1.0,
            reason="shared_monetization_url",
            evidence={"shared_url": url, "class": "monetization"},
        )

    # Rule 2: shared aggregator URL → auto-merge
    url = _shared_classed_url(a, b, "aggregator")
    if url:
        return IdentityVerdict(
            action="auto_merge", confidence=1.0,
            reason="shared_aggregator_url",
            evidence={"shared_url": url, "class": "aggregator"},
        )

    # Rule 3: bio cross-mention (either direction)
    if _bio_mentions_other(a, b):
        return IdentityVerdict(
            action="merge_candidate", confidence=0.8,
            reason="bio_cross_mention",
            evidence={"direction": "a_mentions_b", "handle": b.handle},
        )
    if _bio_mentions_other(b, a):
        return IdentityVerdict(
            action="merge_candidate", confidence=0.8,
            reason="bio_cross_mention",
            evidence={"direction": "b_mentions_a", "handle": a.handle},
        )

    # Rule 4: handle exact match + CLIP similarity ≥ 0.85 (cross-platform only)
    if clip_fn and a.platform != b.platform:
        if _normalize_handle(a.handle) == _normalize_handle(b.handle) \
                and _normalize_handle(a.handle):
            if a.avatar_url and b.avatar_url:
                similarity = clip_fn(a.avatar_url, b.avatar_url)
                if similarity >= 0.85:
                    return IdentityVerdict(
                        action="merge_candidate", confidence=0.7,
                        reason="handle_match_clip",
                        evidence={
                            "handle": a.handle,
                            "clip_similarity": round(similarity, 3),
                        },
                    )

    # Rule 5: display name match + niche match — only with ≥2 prior signals
    # For SP1, cascade terminates at Rule 4 alone. Rule 5 is reserved for
    # future expansion when we have richer evidence accumulation.

    return IdentityVerdict(action="discard", confidence=0.0,
                           reason="no_signal", evidence={})


def find_candidates_for_profile(fp: ProfileFingerprint, workspace_id: str,
                                 supabase) -> list[str]:
    """Query profile_destination_links for peer profiles sharing monetization
    or aggregator URLs with this one. Returns list of peer profile_ids (excludes fp.profile_id).
    """
    # Only query on strong-signal URL classes
    target_urls = [
        u for u in fp.destination_urls
        if fp.destination_classes.get(u) in ("monetization", "aggregator")
    ]
    if not target_urls:
        return []

    resp = supabase.table("profile_destination_links").select(
        "profile_id, canonical_url"
    ).eq("workspace_id", workspace_id).in_(
        "canonical_url", target_urls
    ).neq("profile_id", fp.profile_id).execute()

    return list({row["profile_id"] for row in (resp.data or [])})


# CLIP loader and similarity helper — lazy so unit tests don't pay the cost
_CLIP_MODEL = None
_CLIP_PREPROCESS = None


def get_clip_similarity_fn() -> Callable[[str, str], float]:
    """Return a function that downloads two avatar URLs and returns CLIP cosine similarity.

    Lazy-loads the CLIP model on first call. Subsequent calls reuse the loaded model.
    Returns 0.0 on any fetch/encode error (safer than raising in the cascade hot path).
    """
    from io import BytesIO
    import httpx
    from PIL import Image
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim

    global _CLIP_MODEL
    if _CLIP_MODEL is None:
        _CLIP_MODEL = SentenceTransformer("clip-ViT-B-32")

    def similarity(url_a: str, url_b: str) -> float:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                img_a = Image.open(BytesIO(client.get(url_a).content)).convert("RGB")
                img_b = Image.open(BytesIO(client.get(url_b).content)).convert("RGB")
            emb = _CLIP_MODEL.encode([img_a, img_b], convert_to_tensor=True)
            return float(cos_sim(emb[0], emb[1]).item())
        except Exception:
            return 0.0

    return similarity
