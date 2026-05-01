# scripts/tests/harvester/test_cache.py
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from harvester.cache import lookup_cache, write_cache, DEFAULT_TTL_SECONDS
from harvester.types import HarvestedUrl


def _mock_supabase_with_row(row):
    sb = MagicMock()
    chain = sb.table.return_value.select.return_value.eq.return_value.gt.return_value.maybe_single.return_value
    chain.execute.return_value.data = row
    return sb


def test_lookup_miss_returns_none():
    sb = _mock_supabase_with_row(None)
    assert lookup_cache(sb, "https://nope.example.com") is None


def test_lookup_hit_returns_harvested_urls():
    sb = _mock_supabase_with_row({
        "canonical_url": "https://linktr.ee/x",
        "harvest_method": "httpx",
        "destinations": [
            {
                "canonical_url": "https://onlyfans.com/x",
                "raw_url": "https://onlyfans.com/x",
                "raw_text": "OnlyFans",
                "destination_class": "monetization",
                "harvest_method": "httpx",
            }
        ],
    })
    result = lookup_cache(sb, "https://linktr.ee/x")
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], HarvestedUrl)
    assert result[0].canonical_url == "https://onlyfans.com/x"


def test_lookup_returns_none_when_supabase_returns_none_response():
    # supabase-py 2.x quirk: maybe_single().execute() can return None
    sb = MagicMock()
    chain = sb.table.return_value.select.return_value.eq.return_value.gt.return_value.maybe_single.return_value
    chain.execute.return_value = None
    assert lookup_cache(sb, "https://anything") is None


def test_write_cache_upserts_with_ttl():
    sb = MagicMock()
    destinations = [HarvestedUrl(
        canonical_url="https://onlyfans.com/x",
        raw_url="https://onlyfans.com/x?l_=abc",
        raw_text="OnlyFans",
        destination_class="monetization",
        harvest_method="headless",
    )]
    write_cache(sb, "https://tapforallmylinks.com/esmaecursed", "headless", destinations)

    call = sb.table.return_value.upsert.call_args
    payload = call.args[0]
    assert payload["canonical_url"] == "https://tapforallmylinks.com/esmaecursed"
    assert payload["harvest_method"] == "headless"
    assert isinstance(payload["destinations"], list)
    assert payload["destinations"][0]["destination_class"] == "monetization"
    # expires_at should be ~24h from now
    expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    delta = expires - datetime.now(timezone.utc)
    assert timedelta(hours=23) < delta < timedelta(hours=25)


def test_default_ttl_is_24h():
    assert DEFAULT_TTL_SECONDS == 24 * 3600


def test_lookup_returns_none_when_supabase_is_none():
    # Offline mode — no DB context
    assert lookup_cache(None, "https://anything") is None


def test_write_cache_noop_when_supabase_is_none():
    # No exception, just returns
    destinations = [HarvestedUrl(
        canonical_url="https://x.com/y",
        raw_url="https://x.com/y",
        raw_text="",
        destination_class="social",
        harvest_method="httpx",
    )]
    write_cache(None, "https://x.com/y", "httpx", destinations)  # no raise
