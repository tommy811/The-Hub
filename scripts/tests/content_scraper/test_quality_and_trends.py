from validate_scraped_content import _reason_for
from extract_audio_trends import _audio, _eligible_signatures
from judge_suspicious_content import _parse_decision


def test_quality_validator_rejects_auth_wall_payload():
    flag, reason = _reason_for({
        "post_url": "https://example.com/post",
        "posted_at": "2026-04-27T00:00:00Z",
        "platform": "instagram",
        "raw_apify_payload": {"html": "please log in to continue"},
    })
    assert flag == "rejected"
    assert reason == "auth_wall_marker"


def test_quality_validator_marks_tiktok_zero_views_suspicious():
    flag, reason = _reason_for({
        "post_url": "https://tiktok.com/@x/video/1",
        "posted_at": "2026-04-27T00:00:00Z",
        "platform": "tiktok",
        "view_count": 0,
        "caption": "x",
        "raw_apify_payload": {},
    })
    assert flag == "suspicious"
    assert reason == "tiktok_zero_views"


def test_audio_extractor_reads_closed_shape_signature():
    audio = _audio({
        "platform_metrics": {
            "audio": {
                "signature": "7100000000000000000",
                "artist": "creator",
                "title": "original sound",
            }
        }
    })
    assert audio == {
        "signature": "7100000000000000000",
        "artist": "creator",
        "title": "original sound",
    }


def test_audio_extractor_filters_single_use_signatures():
    eligible = _eligible_signatures({
        "repeat": [{"id": "1"}, {"id": "2"}],
        "single": [{"id": "3"}],
    }, min_usage=2)

    assert list(eligible) == ["repeat"]


def test_judge_decision_parser_accepts_json():
    decision = _parse_decision('{"quality_flag":"clean","quality_reason":"usable_post"}')
    assert decision.quality_flag == "clean"
    assert decision.quality_reason == "usable_post"
