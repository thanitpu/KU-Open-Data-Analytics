from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "acquisition", ROOT / "acquisition" / "providers", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import q_diving_acquisition
from LIVE_YOUTUBE_Q_DIVING_DISCOVERY import validate_options
from youtube_data_api import YouTubeDataAPI, YouTubeProviderError, YouTubeQuotaExceeded, api_status, load_policy
from youtube_source_foundation import (
    apply_retention_policy, discover, load_query_profiles, normalize_channels, normalize_playlists, normalize_videos,
    parse_search_items,
    quality_report, retention_action, select_query_profiles,
)

POLICY = load_policy()
NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
SECRET = "unit" + "-only-secret"


def video_item(index: int, *, privacy="public", caption="true") -> dict:
    return {
        "id": f"VID{index}", "etag": f"etag-v{index}",
        "snippet": {"channelId": f"CHAN{index}", "channelTitle": f"Dive channel {index}",
                    "title": f"Dive video {index}", "description": f"Metadata {index}",
                    "publishedAt": "2026-08-01T00:00:00Z", "categoryId": "17",
                    "defaultLanguage": "en", "defaultAudioLanguage": "th",
                    "thumbnails": {"default": {"url": f"https://img.youtube.com/{index}.jpg"}}},
        "contentDetails": {"duration": "PT10M", "caption": caption},
        "status": {"privacyStatus": privacy, "uploadStatus": "processed", "embeddable": True,
                   "madeForKids": False},
        "paidProductPlacementDetails": {"hasPaidProductPlacement": False},
    }


def channel_item(index: int) -> dict:
    return {
        "id": f"CHAN{index}", "etag": f"etag-c{index}",
        "snippet": {"title": f"Dive channel {index}", "description": "Public channel metadata", "country": "TH",
                    "publishedAt": "2020-01-01T00:00:00Z",
                    "thumbnails": {"default": {"url": f"https://img.youtube.com/channel/{index}.jpg"}}},
        "contentDetails": {"relatedPlaylists": {"uploads": f"UPLOADS{index}"}},
    }


class FixtureTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, endpoint, url, timeout):
        del timeout
        query = parse_qs(urlparse(url).query)
        assert query.get("key") == [SECRET]
        self.calls.append((endpoint, {k: v for k, v in query.items() if k != "key"}))
        if endpoint == "search.list":
            items = [{"id": {"kind": "youtube#video", "videoId": f"VID{i}"},
                      "snippet": {"channelId": f"CHAN{i}", "channelTitle": f"Dive channel {i}",
                                  "title": f"Search {i}", "description": f"Search metadata {i}",
                                  "publishedAt": "2026-08-01T00:00:00Z"}} for i in range(1, 6)]
            return {"items": items, "nextPageToken": "NEXT", "etag": "search-etag"}, {}, 200
        if endpoint == "videos.list":
            ids = query.get("id", [""])[0].split(",") if query.get("id") else []
            return {"items": [video_item(int(x.removeprefix("VID"))) for x in ids if x.startswith("VID")]}, {}, 200
        if endpoint == "channels.list":
            ids = query.get("id", [""])[0].split(",")
            return {"items": [channel_item(int(x.removeprefix("CHAN"))) for x in ids if x.startswith("CHAN")]}, {}, 200
        if endpoint == "playlistItems.list":
            return {"items": [{"contentDetails": {"videoId": "VID1"}}]}, {}, 200
        if endpoint == "playlists.list":
            return {"items": []}, {}, 200
        raise AssertionError(endpoint)


# A/B: missing-key behavior is explicit and status output is sanitized.
assert api_status(environ={}) == {"configured": False, "provider": "youtube-data-api-v3", "policy_version": "1.0"}
try:
    YouTubeDataAPI(api_key="", policy=POLICY)
    raise AssertionError("missing key accepted")
except YouTubeProviderError as exc:
    assert "KU2D_YOUTUBE_API_KEY" in str(exc)
status = api_status(environ={"KU2D_YOUTUBE_API_KEY": SECRET})
assert status["configured"] is True and SECRET not in json.dumps(status)

# C/D/E: search parsing, cross-profile deduplication, videos/channels hydration.
profiles = load_query_profiles()
assert all({"profile_id", "domain", "research_collection", "query_text", "region_code", "type",
            "max_results", "enabled", "cadence", "created_by", "review_status"} <= set(x) for x in profiles)
selected = select_query_profiles(["QYT-BEGINNER-EN", "QYT-KOH-TAO-EN"], profiles=profiles, policy=POLICY)
transport = FixtureTransport()
provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=transport, max_transient_retries=0)
search = provider.search(selected[0], max_results=5)
assert len(search["items"]) == 5 and provider.quota_ledger[-1]["query_profile_id"] == "QYT-BEGINNER-EN"
parsed_search = parse_search_items(search["items"], selected[0])
assert parsed_search[0]["video_id"] == "VID1" and parsed_search[0]["channel_id"] == "CHAN1"
assert parsed_search[0]["title"] == "Search 1" and parsed_search[0]["description"] == "Search metadata 1"
assert parsed_search[0]["published_at"] == "2026-08-01T00:00:00Z"
assert parsed_search[0]["provenance"]["query_profile_id"] == "QYT-BEGINNER-EN"
result = discover(provider, selected, max_pages_per_query=1, max_results=5, observed_at=NOW, policy=POLICY)
assert len(result["videos"]) == 5 and len(result["channels"]) == 5
assert all(len(row["query_profile_ids"]) == 2 for row in result["videos"])
assert result["videos"][0]["duration_iso8601"] == "PT10M"
assert result["videos"][0]["default_language"] == "en" and result["videos"][0]["default_audio_language"] == "th"
assert result["videos"][0]["caption_available"] is True and result["videos"][0]["embeddable"] is True
assert result["channels"][0]["country"] == "TH" and result["channels"][0]["uploads_playlist_id"] == "UPLOADS1"
assert result["channels"][0]["query_profile_ids"] == ["QYT-BEGINNER-EN", "QYT-KOH-TAO-EN"]
assert result["approved"] is False and result["production_store"] is False
assert result["review_stage"] == "human-review-required" and result["scheduler_action"] is None
assert "raw_api_response" not in json.dumps(result)

# F/G: approved-channel monitoring uses uploads playlist, then batches videos; never search.
monitor_transport = FixtureTransport()
monitor_provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=monitor_transport, max_transient_retries=0)
monitored = monitor_provider.monitor_approved_channel("CHAN1")
assert monitored["uploads_playlist_id"] == "UPLOADS1" and len(monitored["videos"]) == 1
assert [x[0] for x in monitor_transport.calls] == ["channels.list", "playlistItems.list", "videos.list"]
batch_transport = FixtureTransport()
batch_provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=batch_transport, max_transient_retries=0)
batch_provider.videos([f"VID{i}" for i in range(1, 52)])
video_calls = [x for x in batch_transport.calls if x[0] == "videos.list"]
assert [len(x[1]["id"][0].split(",")) for x in video_calls] == [50, 1]

# H/I: paging obeys the two-page bound and quota exhaustion stops before another request.
paging_transport = FixtureTransport()
paging_provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=paging_transport, max_transient_retries=0)
discover(paging_provider, selected[:1], max_pages_per_query=2, max_results=5, observed_at=NOW, policy=POLICY)
assert len([x for x in paging_transport.calls if x[0] == "search.list"]) == 2
bounded_transport = FixtureTransport()
bounded_provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=bounded_transport, max_transient_retries=0)
bounded = discover(bounded_provider, selected[:1], max_search_calls=1, max_pages_per_query=2,
                   max_results=5, observed_at=NOW, policy=POLICY)
assert bounded["search_calls_used"] == 1
try:
    discover(paging_provider, selected[:1], max_pages_per_query=3, max_results=5, observed_at=NOW, policy=POLICY)
    raise AssertionError("page budget accepted")
except ValueError:
    pass
quota_transport = FixtureTransport()
quota_provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=quota_transport,
                                max_transient_retries=0, quota_budget=1)
quota_provider.search(selected[0], max_results=5)
try:
    quota_provider.channels(["CHAN1"])
    raise AssertionError("quota exhaustion ignored")
except YouTubeQuotaExceeded:
    pass
assert len(quota_transport.calls) == 1
quota_response_calls = []
def quota_response(endpoint, url, timeout):
    del endpoint, timeout
    quota_response_calls.append(1)
    body = io.BytesIO(json.dumps({"error":{"errors":[{"reason":"quotaExceeded"}]}}).encode())
    raise HTTPError(url, 403, "quota", {}, body)
quota_response_provider = YouTubeDataAPI(api_key=SECRET, policy=POLICY, transport=quota_response,
                                         max_transient_retries=2)
try:
    quota_response_provider.search(selected[0], max_results=5)
    raise AssertionError("quota response accepted")
except YouTubeQuotaExceeded:
    pass
assert len(quota_response_calls) == 1 and quota_response_provider.quota_ledger[-1]["status"] == "quota-exceeded"

# J: secrets never appear in results, ledger, status, or errors.
serialized = json.dumps({"result": result, "ledger": provider.quota_ledger, "status": status})
assert SECRET not in serialized
captured = io.StringIO()
with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
    try:
        provider._request("commentThreads.list", {})
        raise AssertionError("unsupported endpoint accepted")
    except YouTubeProviderError as exc:
        assert SECRET not in str(exc)
assert SECRET not in captured.getvalue()

# K/L: refresh is at most 30 days and missing hydrated IDs become non-usable tombstones.
evidence = {"VID1": {"query_profile_ids": ["QYT-BEGINNER-EN"],
                     "research_collections": ["learn_to_dive"], "channel_id": "CHAN1"},
            "MISSING": {"query_profile_ids": ["QYT-BEGINNER-EN"],
                        "research_collections": ["learn_to_dive"], "channel_id": "CHANX"}}
normalized = normalize_videos([video_item(1)], evidence, requested_ids=["VID1", "MISSING"], observed_at=NOW, policy=POLICY)
assert normalized[0]["refresh_due_at"].startswith("2026-09-29")
tombstone = next(x for x in normalized if x["video_id"] == "MISSING")
assert tombstone["data_status"] == "deleted" and tombstone["publicly_usable"] is False
assert tombstone["provenance"]["tombstone"] is True
assert retention_action(normalized[0], now=datetime(2026, 9, 29, tzinfo=timezone.utc)) == "refresh-or-delete"
retained = apply_retention_policy(normalized, now=datetime(2026, 9, 29, tzinfo=timezone.utc))
assert [x["video_id"] for x in retained["records"]] == ["VID1"]
assert retained["records"][0]["data_status"] == "refresh_due"
assert any(x["action"] == "delete-tombstone-audit-minimum" for x in retained["actions"])

# M/N/O: no caption/comment scraping methods, transcript stays null, and restricted content is unusable.
for forbidden in ("captions", "comment_threads", "comments", "download_video", "download_audio"):
    assert not hasattr(provider, forbidden)
assert POLICY["comments_enabled"] is False and POLICY["comment_threads_enabled"] is False
assert POLICY["arbitrary_transcript_acquisition_enabled"] is False
assert POLICY["comment_acquisition_enabled"] is False and POLICY["scraping_prohibited"] is True
assert POLICY["audiovisual_download_prohibited"] is True
private = normalize_videos([video_item(2, privacy="private", caption="false")], {}, observed_at=NOW, policy=POLICY)[0]
assert private["publicly_usable"] is False and private["data_status"] == "unavailable"
assert private["transcript_text"] is None and private["transcript_access_status"] == "unavailable"
assert all(row["transcript_text"] is None for row in result["videos"])

# P: KU2D research labels remain separate from the YouTube category id.
video = result["videos"][0]
assert video["youtube_category_id"] == "17"
assert video["research_collections"] == ["learn_to_dive"]
assert video["youtube_category_id"] not in video["research_collections"]
assert set(video["ku2d_manual_curation"].values()) == {None}

# Quality gates are deterministic and do not use views/likes.
quality = quality_report([normalize_videos([video_item(i)], {
    f"VID{i}": {"query_profile_ids": ["QYT-BEGINNER-EN"], "research_collections": ["learn_to_dive"]}
}, observed_at=NOW, policy=POLICY)[0] for i in range(1, 6)], raw_search_count=5)
assert quality["passed"] is True
assert "views" not in json.dumps({"gates":quality["gates"], "metrics":quality["metrics"]}).lower()
assert "likes" not in json.dumps({"gates":quality["gates"], "metrics":quality["metrics"]}).lower()

# Optional playlist normalization is public-only and provenance-bearing.
playlist = normalize_playlists([{"id":"PL1", "etag":"p1", "snippet":{"channelId":"CHAN1", "title":"Dives",
    "publishedAt":"2025-01-01T00:00:00Z"}, "contentDetails":{"itemCount":5}, "status":{"privacyStatus":"public"}}],
    observed_at=NOW, policy=POLICY)[0]
assert playlist["publicly_usable"] is True and playlist["source_endpoint"] == "playlists.list"
assert normalize_channels([channel_item(1)], observed_at=NOW, policy=POLICY)[0]["uploads_playlist_id"] == "UPLOADS1"

# The legacy Q-Diving HTML acquisition path refuses YouTube before fetch.
try:
    q_diving_acquisition.acquire_url("https://www.youtube.com/watch?v=VID1")
    raise AssertionError("YouTube HTML acquisition accepted")
except RuntimeError as exc:
    assert "Data API v3" in str(exc)

# Q: live pilot refuses missing key, production/approval omission, bad budgets, and unsupported endpoints.
base = argparse.Namespace(endpoint="discovery", no_approve=True, no_production_store=True,
                          profiles=["QYT-BEGINNER-EN", "QYT-KOH-TAO-EN"],
                          max_results=10, max_pages=2, max_search_calls=2, quota_budget=10)
try:
    validate_options(base, policy=POLICY, environ={})
    raise AssertionError("live command accepted missing key")
except ValueError:
    pass
for changes in ({"no_approve":False}, {"no_production_store":False}, {"max_results":11},
                {"max_pages":3}, {"max_search_calls":1}, {"max_search_calls":9},
                {"quota_budget":0}, {"endpoint":"comments"}):
    args = argparse.Namespace(**{**vars(base), **changes})
    try:
        validate_options(args, policy=POLICY, environ={"KU2D_YOUTUBE_API_KEY": SECRET})
        raise AssertionError(f"unsafe live options accepted: {changes}")
    except ValueError:
        pass

# Registry traceability replaces enabled raw search URLs with reviewed profile references.
registry = json.loads((ROOT / "config" / "q_diving_source_registry.json").read_text(encoding="utf-8"))
for source_id in ("Q-004", "Q-005"):
    row = next(x for x in registry["sources"] if x["source_id"] == source_id)
    assert row["enabled"] is False and row["query_profile_ids"] and "url" not in row
    assert row["legacy_search_url"].startswith("https://www.youtube.com/results?")

print("YouTube source foundation deterministic contracts: PASS")
