"""Q-Diving YouTube metadata normalization and Human Review staging."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "youtube_api_policy.json"
PROFILES_PATH = ROOT / "config" / "q_diving_youtube_query_profiles.json"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@dataclass
class YouTubeQueryProfile:
    profile_id: str
    domain: str
    research_collection: str
    query_text: str
    type: str = "video"
    region_code: str = "TH"
    relevance_language: str | None = None
    max_results: int = 10
    enabled: bool = True
    cadence: str = "manual-pilot"
    created_by: str = "KU2D"
    review_status: str = "foundation-candidate"
    legacy_source_ids: list[str] = field(default_factory=list)
    legacy_search_url: str | None = None


@dataclass
class YouTubeVideoCandidate:
    video_id: str
    channel_id: str | None
    channel_title: str | None
    title: str | None
    description: str | None
    published_at: str | None
    duration_iso8601: str | None
    default_language: str | None
    default_audio_language: str | None
    caption_available: bool | str
    transcript_access_status: str
    transcript_text: None
    privacy_status: str | None
    embeddable: bool | None
    made_for_kids: bool | None
    paid_product_placement: bool | None
    thumbnail_url: str | None
    video_url: str
    youtube_category_id: str | None
    query_profile_ids: list[str]
    research_collections: list[str]
    observed_at: str
    api_refreshed_at: str
    refresh_due_at: str
    source_endpoint: str
    source_query_profile_id: str | None
    etag: str | None
    data_status: str
    publicly_usable: bool
    provenance: dict
    human_review_status: str
    ku2d_manual_curation: dict = field(default_factory=dict)


@dataclass
class YouTubeChannelCandidate:
    channel_id: str
    channel_title: str | None
    channel_description: str | None
    country: str | None
    published_at: str | None
    uploads_playlist_id: str | None
    thumbnail_url: str | None
    channel_url: str
    query_profile_ids: list[str]
    observed_at: str
    api_refreshed_at: str
    refresh_due_at: str
    source_endpoint: str
    etag: str | None
    data_status: str
    provenance: dict
    human_review_status: str
    ku2d_manual_curation: dict = field(default_factory=dict)


@dataclass
class YouTubePlaylistCandidate:
    playlist_id: str
    channel_id: str | None
    title: str | None
    description: str | None
    published_at: str | None
    playlist_url: str
    item_count: int | None
    privacy_status: str | None
    observed_at: str
    api_refreshed_at: str
    refresh_due_at: str
    source_endpoint: str
    etag: str | None
    data_status: str
    publicly_usable: bool
    provenance: dict
    ku2d_manual_curation: dict = field(default_factory=dict)


@dataclass
class YouTubeQuotaObservation:
    endpoint: str
    quota_bucket: str
    estimated_cost: int
    request_count: int
    observed_at: str
    query_profile_id: str | None
    response_count: int
    next_page_available: bool
    status: str
    error_code: str | None


def load_policy(path: Path = POLICY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_query_profiles(path: Path = PROFILES_PATH) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    defaults = document.get("defaults") or {}
    return [{**defaults, **row} for row in document.get("profiles") or []]


def select_query_profiles(profile_ids: list[str] | None = None, *, profiles=None, policy=None) -> list[dict]:
    profiles = list(profiles if profiles is not None else load_query_profiles())
    if profile_ids:
        wanted = set(profile_ids)
        selected = [row for row in profiles if row.get("profile_id") in wanted]
        missing = sorted(wanted - {row.get("profile_id") for row in selected})
        if missing:
            raise ValueError(f"Unknown YouTube query profile(s): {', '.join(missing)}")
    else:
        selected = [row for row in profiles if row.get("enabled")]
    policy = policy or load_policy()
    maximum = int(policy["pilot_limits"]["max_query_profiles"])
    if not selected or len(selected) > maximum:
        raise ValueError(f"Select between 1 and {maximum} YouTube query profiles.")
    return selected


def _times(observed_at: datetime, policy: dict) -> tuple[str, str, str]:
    days = min(30, int(policy["retention"]["refresh_or_delete_days"]))
    return iso(observed_at), iso(observed_at), iso(observed_at + timedelta(days=days))


def retention_action(record: dict, *, now=None) -> str:
    """Return the deterministic minimum action for a normalized API record."""
    current = now or utcnow()
    due = datetime.fromisoformat(str(record["refresh_due_at"]).replace("Z", "+00:00"))
    if current < due:
        return "retain-until-refresh-due"
    if record.get("data_status") in {"deleted", "unavailable"}:
        return "delete-tombstone-audit-minimum"
    return "refresh-or-delete"


def apply_retention_policy(records: list[dict], *, now=None) -> dict:
    """Mark due current records and remove expired unavailable/deleted payloads.

    The returned audit entries retain only identity, timing, provenance, and the
    action needed to explain the removal; they are not historical API snapshots.
    """
    current = now or utcnow()
    retained, actions = [], []
    for source in records:
        row = dict(source)
        action = retention_action(row, now=current)
        identity = row.get("video_id") or row.get("channel_id") or row.get("playlist_id")
        audit = {"identity": identity, "action": action, "observed_at": row.get("observed_at"),
                 "refresh_due_at": row.get("refresh_due_at"), "provenance": row.get("provenance")}
        if action == "delete-tombstone-audit-minimum":
            actions.append(audit)
            continue
        if action == "refresh-or-delete":
            row["data_status"] = "refresh_due"
            actions.append(audit)
        retained.append(row)
    return {"records": retained, "actions": actions}


def _caption(value: Any):
    if value is True or str(value).lower() == "true":
        return True, "owner-authorization-required"
    if value is False or str(value).lower() == "false":
        return False, "unavailable"
    return "unknown", "metadata-only"


def _manual_curation() -> dict:
    return {
        "ku2d_manual_source_class": None,
        "ku2d_manual_review_note": None,
        "ku2d_manual_research_collection": None,
        "ku2d_manual_approved_by": None,
        "ku2d_manual_approved_at": None,
    }


def parse_search_items(items: list[dict], profile: dict) -> list[dict]:
    """Parse public search snippets while preserving KU2D profile provenance."""
    out = []
    for item in items:
        identity, snippet = item.get("id") or {}, item.get("snippet") or {}
        video_id = identity.get("videoId")
        if not video_id:
            continue
        out.append({
            "video_id": video_id,
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "published_at": snippet.get("publishedAt"),
            "query_profile_id": profile["profile_id"],
            "research_collection": profile["research_collection"],
            "provenance": {"provider":"youtube-data-api-v3", "endpoint":"search.list",
                           "query_profile_id":profile["profile_id"]},
        })
    return out


def normalize_videos(api_items: list[dict], search_evidence: dict[str, dict], *, requested_ids=None,
                     observed_at=None, policy=None) -> list[dict]:
    policy = policy or load_policy()
    observed = observed_at or utcnow()
    observed_s, refreshed_s, due_s = _times(observed, policy)
    out = []
    seen = set()
    for item in api_items:
        video_id = str(item.get("id") or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        snippet = item.get("snippet") or {}
        details = item.get("contentDetails") or {}
        status = item.get("status") or {}
        evidence = search_evidence.get(video_id) or {}
        privacy = status.get("privacyStatus")
        usable = privacy == "public" and status.get("uploadStatus", "processed") not in {"deleted", "failed", "rejected"}
        caption, transcript_status = _caption(details.get("caption"))
        profile_ids = sorted(set(evidence.get("query_profile_ids") or []))
        collections = sorted(set(evidence.get("research_collections") or []))
        thumbnails = snippet.get("thumbnails") or {}
        thumbnail = (thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}).get("url")
        row = YouTubeVideoCandidate(
            video_id=video_id, channel_id=snippet.get("channelId"), channel_title=snippet.get("channelTitle"),
            title=snippet.get("title"),
            description=snippet.get("description"), published_at=snippet.get("publishedAt"),
            duration_iso8601=details.get("duration"), default_language=snippet.get("defaultLanguage"),
            default_audio_language=snippet.get("defaultAudioLanguage"),
            caption_available=caption, transcript_access_status=transcript_status, transcript_text=None,
            privacy_status=privacy, embeddable=status.get("embeddable"), made_for_kids=status.get("madeForKids"),
            paid_product_placement=(item.get("paidProductPlacementDetails") or {}).get("hasPaidProductPlacement"),
            thumbnail_url=thumbnail, video_url=f"https://www.youtube.com/watch?v={video_id}",
            youtube_category_id=snippet.get("categoryId"), query_profile_ids=profile_ids,
            research_collections=collections, observed_at=observed_s, api_refreshed_at=refreshed_s,
            refresh_due_at=due_s, source_endpoint="videos.list",
            source_query_profile_id=profile_ids[0] if len(profile_ids) == 1 else None, etag=item.get("etag"),
            data_status="current" if usable else "unavailable", publicly_usable=usable,
            provenance={"provider":"youtube-data-api-v3", "endpoint":"videos.list",
                        "query_profile_ids":profile_ids, "search_result_observed":bool(evidence)},
            human_review_status="pending", ku2d_manual_curation=_manual_curation(),
        )
        out.append(asdict(row))
    for video_id in requested_ids or []:
        if video_id in seen:
            continue
        evidence = search_evidence.get(video_id) or {}
        profile_ids = sorted(set(evidence.get("query_profile_ids") or []))
        collections = sorted(set(evidence.get("research_collections") or []))
        out.append(asdict(YouTubeVideoCandidate(
            video_id=video_id, channel_id=evidence.get("channel_id"), channel_title=evidence.get("channel_title"),
            title=None, description=None, published_at=None, duration_iso8601=None,
            default_language=None, default_audio_language=None,
            caption_available="unknown", transcript_access_status="unavailable", transcript_text=None,
            privacy_status=None, embeddable=None, made_for_kids=None, paid_product_placement=None,
            thumbnail_url=None, video_url=f"https://www.youtube.com/watch?v={video_id}", youtube_category_id=None,
            query_profile_ids=profile_ids, research_collections=collections,
            observed_at=observed_s, api_refreshed_at=refreshed_s, refresh_due_at=due_s,
            source_endpoint="videos.list", source_query_profile_id=profile_ids[0] if len(profile_ids) == 1 else None,
            etag=None, data_status="deleted", publicly_usable=False,
            provenance={"provider":"youtube-data-api-v3", "endpoint":"videos.list",
                        "query_profile_ids":profile_ids, "missing_from_hydration":True, "tombstone":True},
            human_review_status="not-reviewable", ku2d_manual_curation=_manual_curation(),
        )))
    return out


def normalize_channels(api_items: list[dict], *, channel_evidence=None, observed_at=None, policy=None) -> list[dict]:
    policy = policy or load_policy(); observed = observed_at or utcnow()
    observed_s, refreshed_s, due_s = _times(observed, policy)
    out = []
    for item in api_items:
        channel_id = str(item.get("id") or "").strip()
        if not channel_id:
            continue
        snippet = item.get("snippet") or {}; evidence = (channel_evidence or {}).get(channel_id) or {}
        thumbnails = snippet.get("thumbnails") or {}
        thumbnail = (thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}).get("url")
        uploads = (((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"))
        out.append(asdict(YouTubeChannelCandidate(
            channel_id=channel_id, channel_title=snippet.get("title"), channel_description=snippet.get("description"),
            country=snippet.get("country"), published_at=snippet.get("publishedAt"), uploads_playlist_id=uploads,
            thumbnail_url=thumbnail, channel_url=f"https://www.youtube.com/channel/{channel_id}",
            query_profile_ids=sorted(set(evidence.get("query_profile_ids") or [])),
            observed_at=observed_s, api_refreshed_at=refreshed_s,
            refresh_due_at=due_s, source_endpoint="channels.list", etag=item.get("etag"), data_status="current",
            provenance={"provider":"youtube-data-api-v3", "endpoint":"channels.list"},
            human_review_status="pending", ku2d_manual_curation=_manual_curation(),
        )))
    return out


def normalize_playlists(api_items: list[dict], *, observed_at=None, policy=None) -> list[dict]:
    policy = policy or load_policy(); observed = observed_at or utcnow()
    observed_s, refreshed_s, due_s = _times(observed, policy)
    out = []
    for item in api_items:
        playlist_id = str(item.get("id") or "").strip()
        if not playlist_id:
            continue
        snippet, status = item.get("snippet") or {}, item.get("status") or {}
        privacy = status.get("privacyStatus")
        usable = privacy == "public"
        out.append(asdict(YouTubePlaylistCandidate(
            playlist_id=playlist_id, channel_id=snippet.get("channelId"), title=snippet.get("title"),
            description=snippet.get("description"), published_at=snippet.get("publishedAt"),
            playlist_url=f"https://www.youtube.com/playlist?list={playlist_id}",
            item_count=(item.get("contentDetails") or {}).get("itemCount"), privacy_status=privacy,
            observed_at=observed_s, api_refreshed_at=refreshed_s, refresh_due_at=due_s,
            source_endpoint="playlists.list", etag=item.get("etag"), data_status="current" if usable else "unavailable",
            publicly_usable=usable, provenance={"provider":"youtube-data-api-v3", "endpoint":"playlists.list"},
            ku2d_manual_curation=_manual_curation(),
        )))
    return out


def quality_report(videos: list[dict], *, raw_search_count=None) -> dict:
    public = [row for row in videos if row.get("publicly_usable")]
    count = len(public)
    pct = lambda n: round((100.0 * n / count), 2) if count else 0.0
    duplicates = max(0, int(raw_search_count or len(videos)) - len({x.get("video_id") for x in videos}))
    duplicate_pct = round(100.0 * duplicates / max(1, int(raw_search_count or len(videos))), 2)
    metrics = {
        "public_video_count": count,
        "video_id_completeness_pct": pct(sum(bool(x.get("video_id")) for x in public)),
        "channel_id_completeness_pct": pct(sum(bool(x.get("channel_id")) for x in public)),
        "title_completeness_pct": pct(sum(bool(x.get("title")) for x in public)),
        "published_at_completeness_pct": pct(sum(bool(x.get("published_at")) for x in public)),
        "source_url_completeness_pct": pct(sum(bool(x.get("video_url")) for x in public)),
        "provenance_completeness_pct": pct(sum(bool(x.get("provenance")) for x in public)),
        "refresh_due_at_completeness_pct": pct(sum(bool(x.get("refresh_due_at")) for x in public)),
        "duplicate_pct": duplicate_pct,
        "restricted_or_unavailable_count": len(videos) - count,
        "unauthorized_transcript_text_count": sum(x.get("transcript_text") is not None for x in videos),
    }
    gates = {
        "minimum_video_count": count >= 5,
        "video_id_complete": metrics["video_id_completeness_pct"] == 100.0,
        "channel_id_complete": metrics["channel_id_completeness_pct"] >= 95.0,
        "title_complete": metrics["title_completeness_pct"] >= 95.0,
        "published_at_complete": metrics["published_at_completeness_pct"] >= 90.0,
        "url_provenance_refresh_complete": all(metrics[key] == 100.0 for key in (
            "source_url_completeness_pct", "provenance_completeness_pct", "refresh_due_at_completeness_pct")),
        "duplicate_rate": duplicate_pct <= 5.0,
        "no_unauthorized_transcript_text": metrics["unauthorized_transcript_text_count"] == 0,
    }
    return {"passed": all(gates.values()), "gates": gates, "metrics": metrics,
            "note": "Views and likes are observations, not foundation approval gates."}


def discover(provider, profiles: list[dict], *, max_search_calls=8, max_pages_per_query=1, max_results=10, observed_at=None,
             policy=None) -> dict:
    policy = policy or load_policy()
    observed = observed_at or utcnow()
    if len(profiles) > int(policy["pilot_limits"]["max_query_profiles"]):
        raise ValueError("YouTube query-profile pilot limit exceeded.")
    search_call_limit = int(max_search_calls)
    if search_call_limit < len(profiles) or search_call_limit > int(policy["pilot_limits"]["max_query_profiles"]):
        raise ValueError("YouTube search-call budget must cover every selected profile and stay within the pilot maximum.")
    page_limit = int(max_pages_per_query)
    if page_limit < 1 or page_limit > int(policy["pilot_limits"]["max_pages_per_query"]):
        raise ValueError("YouTube page budget must be between 1 and the configured pilot maximum.")
    result_limit = int(max_results)
    if result_limit < 1 or result_limit > int(policy["pilot_limits"]["max_results_per_search"]):
        raise ValueError("YouTube result budget must be between 1 and the configured pilot maximum.")
    search_evidence: dict[str, dict] = {}
    raw_search_count = 0
    search_calls = 0
    for profile in profiles:
        token = None
        for _ in range(page_limit):
            if search_calls >= search_call_limit:
                break
            payload = provider.search(profile, page_token=token, max_results=result_limit)
            search_calls += 1
            items = payload.get("items") or []
            raw_search_count += len(items)
            for parsed in parse_search_items(items, profile):
                video_id = parsed["video_id"]
                evidence = search_evidence.setdefault(video_id, {"query_profile_ids": [], "research_collections": [],
                                                                  "channel_id": parsed.get("channel_id"),
                                                                  "channel_title": parsed.get("channel_title"),
                                                                  "search_title": parsed.get("title"),
                                                                  "search_description": parsed.get("description"),
                                                                  "search_published_at": parsed.get("published_at")})
                evidence["query_profile_ids"].append(profile["profile_id"])
                evidence["research_collections"].append(profile["research_collection"])
            token = payload.get("nextPageToken")
            if not token:
                break
    video_ids = list(search_evidence)
    video_items = provider.videos(video_ids)
    videos = normalize_videos(video_items, search_evidence, requested_ids=video_ids, observed_at=observed, policy=policy)
    channel_ids = sorted({x.get("channel_id") for x in videos if x.get("channel_id")})
    channel_evidence = {}
    for evidence in search_evidence.values():
        channel_id = evidence.get("channel_id")
        if channel_id:
            channel_evidence.setdefault(channel_id, {"query_profile_ids": []})["query_profile_ids"].extend(evidence.get("query_profile_ids") or [])
    channel_items = []
    for start in range(0, len(channel_ids), 50):
        channel_items.extend((provider.channels(channel_ids[start:start + 50]).get("items") or []))
    channels = normalize_channels(channel_items, channel_evidence=channel_evidence, observed_at=observed, policy=policy)
    report = quality_report(videos, raw_search_count=raw_search_count)
    return {
        "schema": "ku2d.youtube-source-foundation-result.v1",
        "provider": "youtube-data-api-v3",
        "observed_at": iso(observed),
        "query_profile_ids": [x["profile_id"] for x in profiles],
        "search_calls_used": search_calls,
        "videos": videos, "channels": channels, "playlists": [],
        "quality_report": report,
        "quota_observations": list(provider.quota_ledger),
        "review_stage": "human-review-required",
        "approved": False,
        "production_store": False,
        "scheduler_action": None,
    }
