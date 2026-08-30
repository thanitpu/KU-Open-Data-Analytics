"""Bounded, metadata-only YouTube Data API v3 provider.

The provider deliberately exposes only the documented list methods approved by
``config/youtube_api_policy.json``.  It never logs request URLs or API keys.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "youtube_api_policy.json"
PROVIDER = "youtube-data-api-v3"


class YouTubeProviderError(RuntimeError):
    pass


class YouTubeQuotaExceeded(YouTubeProviderError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def api_status(environ=None, policy=None) -> dict:
    env = os.environ if environ is None else environ
    policy = policy or load_policy()
    return {
        "configured": bool(str(env.get("KU2D_YOUTUBE_API_KEY") or "").strip()),
        "provider": policy["provider"],
        "policy_version": policy["version"],
    }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_transport(endpoint: str, url: str, timeout: int):
    del endpoint
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KU2D-YouTube-Foundation/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8")), dict(response.headers), getattr(response, "status", 200)


def _error_reason(exc: HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        errors = ((body.get("error") or {}).get("errors") or [])
        return str((errors[0] if errors else {}).get("reason") or "http-error")
    except Exception:
        return "http-error"


class YouTubeDataAPI:
    def __init__(self, api_key=None, *, policy=None, transport=None, sleeper=None, timeout=20,
                 max_transient_retries=2, quota_budget=None):
        self.policy = policy or load_policy()
        self.api_key = str(api_key if api_key is not None else os.environ.get("KU2D_YOUTUBE_API_KEY") or "").strip()
        if not self.api_key:
            raise YouTubeProviderError("KU2D_YOUTUBE_API_KEY is not configured.")
        self.transport = transport or _default_transport
        self.sleeper = sleeper or time.sleep
        self.timeout = int(timeout)
        self.max_transient_retries = max(0, int(max_transient_retries))
        self.quota_budget = None if quota_budget is None else max(0, int(quota_budget))
        self.quota_used = 0
        self.quota_ledger: list[dict] = []
        self.request_count = 0

    def _endpoint_cost(self, endpoint: str) -> int:
        return int((((self.policy.get("quota_policy") or {}).get("endpoint_costs") or {}).get(endpoint)) or 1)

    def _request(self, endpoint: str, params: dict, *, query_profile_id=None) -> dict:
        if endpoint not in set(self.policy.get("allowed_endpoints") or []):
            raise YouTubeProviderError(f"Unsupported YouTube endpoint: {endpoint}")
        cost = self._endpoint_cost(endpoint)
        resource = endpoint.split(".", 1)[0]
        safe_params = {k: v for k, v in params.items() if v is not None and v != ""}
        request_params = {**safe_params, "key": self.api_key}
        url = f"{self.policy['api_root'].rstrip('/')}/{resource}?{urlencode(request_params, doseq=True)}"
        attempt = 0
        while True:
            if self.quota_budget is not None and self.quota_used + cost > self.quota_budget:
                raise YouTubeQuotaExceeded("Configured YouTube quota budget would be exceeded.")
            requested_at = _utcnow()
            self.request_count += 1
            self.quota_used += cost
            observation = {
                "endpoint": endpoint,
                "requested_at": requested_at,
                "request_count": self.request_count,
                "quota_bucket": (((self.policy.get("quota_policy") or {}).get("endpoint_quota_buckets") or {}).get(endpoint) or "metadata-read"),
                "estimated_quota_bucket": (((self.policy.get("quota_policy") or {}).get("endpoint_quota_buckets") or {}).get(endpoint) or "metadata-read"),
                "estimated_cost": cost,
                "query_profile_id": query_profile_id,
                "result_count": 0,
                "next_page_token": None,
                "status": "requested",
                "error": None,
                "observed_at": requested_at,
                "response_count": 0,
                "next_page_available": False,
                "error_code": None,
            }
            try:
                payload, headers, status = self.transport(endpoint, url, self.timeout)
                if not isinstance(payload, dict):
                    raise YouTubeProviderError("YouTube API response must be a JSON object.")
                observation.update({
                    "result_count": len(payload.get("items") or []),
                    "next_page_token": payload.get("nextPageToken"),
                    "response_count": len(payload.get("items") or []),
                    "next_page_available": bool(payload.get("nextPageToken")),
                    "status": "ok" if int(status) < 400 else "http-error",
                })
                self.quota_ledger.append(observation)
                return payload
            except HTTPError as exc:
                reason = _error_reason(exc)
                quota_error = exc.code == 403 and reason in {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}
                observation.update({"status": "quota-exceeded" if quota_error else "http-error", "error": f"HTTP {exc.code}: {reason}",
                                    "error_code": reason})
                self.quota_ledger.append(observation)
                if quota_error:
                    raise YouTubeQuotaExceeded(observation["error"]) from None
                transient = exc.code in {429, 500, 502, 503, 504}
                if transient and attempt < self.max_transient_retries:
                    retry_after = (exc.headers or {}).get("Retry-After")
                    self.sleeper(float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 8))
                    attempt += 1
                    continue
                raise YouTubeProviderError(observation["error"]) from None
            except (URLError, TimeoutError) as exc:
                observation.update({"status": "transport-error", "error": type(exc).__name__, "error_code": type(exc).__name__})
                self.quota_ledger.append(observation)
                if attempt < self.max_transient_retries:
                    self.sleeper(min(2 ** attempt, 8)); attempt += 1; continue
                raise YouTubeProviderError(f"YouTube API transport failure: {type(exc).__name__}") from None
            except YouTubeProviderError as exc:
                observation.update({"status": "invalid-response", "error": str(exc), "error_code": type(exc).__name__})
                self.quota_ledger.append(observation)
                raise
            except Exception as exc:
                observation.update({"status": "provider-error", "error": type(exc).__name__, "error_code": type(exc).__name__})
                self.quota_ledger.append(observation)
                raise YouTubeProviderError(f"YouTube API provider failure: {type(exc).__name__}") from None

    def search(self, query_profile: dict, *, page_token=None, max_results=None) -> dict:
        limit = min(int(max_results or query_profile.get("max_results") or 10),
                    int(self.policy["pilot_limits"]["max_results_per_search"]))
        return self._request("search.list", {
            "part": "snippet", "q": query_profile["query_text"], "type": query_profile.get("type", "video"),
            "regionCode": query_profile.get("region_code"), "relevanceLanguage": query_profile.get("relevance_language"),
            "maxResults": limit, "pageToken": page_token,
        }, query_profile_id=query_profile.get("profile_id"))

    def channels(self, channel_ids: list[str]) -> dict:
        return self._request("channels.list", {"part": "snippet,contentDetails", "id": ",".join(dict.fromkeys(channel_ids[:50]))})

    def playlists(self, playlist_ids: list[str]) -> dict:
        return self._request("playlists.list", {"part": "snippet,contentDetails,status", "id": ",".join(dict.fromkeys(playlist_ids[:50]))})

    def playlist_items(self, playlist_id: str, *, page_token=None, max_results=50) -> dict:
        return self._request("playlistItems.list", {"part": "snippet,contentDetails,status", "playlistId": playlist_id,
                                                       "maxResults": min(50, int(max_results)), "pageToken": page_token})

    def videos(self, video_ids: list[str]) -> list[dict]:
        out = []
        batch_size = int(self.policy["pilot_limits"]["max_video_ids_per_request"])
        for start in range(0, len(video_ids), batch_size):
            batch = list(dict.fromkeys(video_ids[start:start + batch_size]))
            if batch:
                out.extend((self._request("videos.list", {
                    "part": "snippet,contentDetails,status,paidProductPlacementDetails", "id": ",".join(batch)
                }).get("items") or []))
        return out

    def monitor_approved_channel(self, channel_id: str, *, max_results=50) -> dict:
        channel_payload = self.channels([channel_id])
        channels = channel_payload.get("items") or []
        if not channels:
            return {"channel": None, "uploads_playlist_id": None, "videos": []}
        uploads = ((((channels[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")))
        if not uploads:
            return {"channel": channels[0], "uploads_playlist_id": None, "videos": []}
        items = self.playlist_items(uploads, max_results=max_results).get("items") or []
        ids = [((x.get("contentDetails") or {}).get("videoId")) for x in items]
        ids = [x for x in ids if x]
        return {"channel": channels[0], "uploads_playlist_id": uploads, "videos": self.videos(ids)}
