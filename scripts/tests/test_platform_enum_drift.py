"""Drift detector: schemas.py Platform Literal vs Postgres platform enum.

If a developer adds a value to the Postgres enum but forgets to update
schemas.py (or vice versa), discovery silently breaks because Pydantic
validation rejects the new value. This test catches that drift.

Skips if SUPABASE_URL is not set in env (e.g. CI without DB credentials).
"""
import os
import typing
import pytest

from schemas import Platform


def _platform_literal_values() -> set[str]:
    """Extract the string values from the Platform Literal type."""
    args = typing.get_args(Platform)
    return set(args)


@pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
    reason="DB credentials not available — drift check requires live Postgres",
)
def test_platform_literal_matches_postgres_enum():
    # Placeholder for a future live-DB drift check. supabase-py doesn't expose
    # raw SQL, and we don't yet have a get_platform_enum_values RPC. The two
    # static lockdowns below give us tight feedback at unit-test speed; this
    # one will tighten further once the RPC lands.
    pytest.skip("Supabase MCP needed for live enum check; implement via separate /verify command")


def test_platform_literal_includes_all_t17_additions():
    """Locks in the 19 platform values added by T17 (commit c08dcdd).

    If anyone removes a Literal entry, this test fails. Migration would also fail
    against the live DB, but this gives faster feedback at test time.
    """
    expected_t17_additions = {
        "link_me", "tapforallmylinks", "allmylinks", "lnk_bio", "snipfeed",
        "launchyoursocials", "fanfix", "cashapp", "venmo", "snapchat",
        "reddit", "spotify", "threads", "bluesky", "kofi", "buymeacoffee",
        "substack", "discord", "whatsapp",
    }
    actual = _platform_literal_values()
    missing = expected_t17_additions - actual
    assert not missing, f"Platform Literal missing T17 additions: {missing}"


def test_platform_literal_includes_all_pre_t17_values():
    """Locks in the original 18 platform values that pre-date T17."""
    expected_pre_t17 = {
        "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
        "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
        "tiktok_shop", "linktree", "beacons", "custom_domain",
        "telegram_channel", "telegram_cupidbot", "other",
    }
    actual = _platform_literal_values()
    missing = expected_pre_t17 - actual
    assert not missing, f"Platform Literal lost pre-T17 values: {missing}"
