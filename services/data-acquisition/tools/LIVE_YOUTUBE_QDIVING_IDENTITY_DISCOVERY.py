"""Manual-only, exact-scope Q-Diving candidate discovery runner.

The API key is read only from the process environment by the provider. This
tool never serializes or prints it, request URLs, page tokens, or raw payloads.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from providers.youtube_data_api import YouTubeDataAPI, YouTubeProviderError, api_status, load_policy
from youtube_identity_discovery_review import (
    SEARCH_UNIT_COST, VIDEOS_UNIT_COST, build_review_package, retain_candidates,
    validate_discovery_evidence,
)
from youtube_source_foundation import load_query_profiles, select_query_profiles

PROFILES = ["QYT-BEGINNER-KOH-TAO-TH", "QYT-BEGINNER-EN"]
AUTH_SCOPE = {
    "operation": "youtube_qdiving_identity_discovery",
    "profiles": PROFILES,
    "max_results_per_profile": 5,
    "max_pages_per_profile": 1,
    "max_search_list_requests": 2,
    "max_videos_list_requests": 1,
    "max_documented_quota_units": 201,
    "comments_acquired": False,
    "captions_called": False,
    "transcript_text_acquired": False,
    "oauth_used": False,
    "production_store": False,
    "scheduler_action": None,
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def authorization(path: Path, decision_id: str, execution_revision: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("human_decision_id") != decision_id or record.get("decision") != "confirmed":
        raise ValueError("continuation authorization is absent or not confirmed")
    if record.get("authorized_scope") != AUTH_SCOPE:
        raise ValueError("continuation authorization does not match the exact H12 discovery scope")
    if SHA_RE.fullmatch(execution_revision or "") is None:
        raise ValueError("execution revision must be an immutable 40-character Git SHA")
    if record.get("authorized_execution_revision") != execution_revision:
        raise ValueError("continuation authorization does not bind the requested execution revision")
    if record.get("authorized_execution_branch") != "integration/data-acquisition-platform":
        raise ValueError("continuation authorization is not scoped to the integration implementation branch")
    return record


def classify_exit_code(exit_code: int) -> dict[str, object]:
    if exit_code == 0:
        return {"outcome": "candidate-evidence-obtained", "step_success": True}
    if exit_code == 2:
        return {"outcome": "evidence-withheld", "step_success": True}
    return {"outcome": "technical-failure", "step_success": False}


def sanitized_ledger(provider: YouTubeDataAPI) -> list[dict]:
    return [{key: item.get(key) for key in (
        "endpoint", "requested_at", "request_count", "quota_bucket", "estimated_cost",
        "query_profile_id", "result_count", "status", "error_code", "observed_at",
        "response_count", "next_page_available",
    )} for item in provider.quota_ledger]


def base_evidence(decision_id: str, *, classification: str, exit_code: int, reason: str) -> dict:
    return {
        "schema": "ku2d.youtube-qdiving-identity-discovery.v1", "discovery_id": "KU2D-YT-QDIVING-IDENTITY-DISCOVERY-RUNTIME-000001",
        "observed_at": now(), "classification": classification, "exit_classification": exit_code,
        "technical_completion": exit_code != 1, "withheld_reason": reason,
        "authority": {"human_decision_id": decision_id, "scope": "exact H12 continuation"},
        "planned_profiles": PROFILES, "candidate_count": 0, "retained_candidates": [], "excluded_candidates": [],
        "human_review_completed": False, "usable_reviewed_identity_count": 0,
        "boundaries": {"comments_acquired": False, "captions_called": False, "transcript_text_acquired": False,
                       "oauth_used": False, "browser_or_scraping_used": False, "production_store": False,
                       "production_approved": False, "authority_promoted": False, "scheduler_action": None},
    }


def write(path: Path, evidence: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


def run(output: Path, decision_path: Path, decision_id: str, execution_revision: str) -> int:
    authorization(decision_path, decision_id, execution_revision)
    status = api_status()
    if not status["configured"]:
        evidence = base_evidence(decision_id, classification="evidence_withheld", exit_code=2,
                                 reason="api_credential_not_configured")
        evidence["credential_preflight"] = {"configured": False, "secret_read_or_logged": False}
        evidence["request_quota_ledger"] = {"request_count": 0, "search_list_request_count": 0,
            "videos_list_request_count": 0, "page_count": 0, "documented_quota_units": 0, "events": []}
        write(output, evidence); return 2
    policy = copy.deepcopy(load_policy())
    policy["allowed_endpoints"] = ["search.list", "videos.list"]
    policy["quota_policy"]["endpoint_costs"].update({"search.list": SEARCH_UNIT_COST, "videos.list": VIDEOS_UNIT_COST})
    provider = YouTubeDataAPI(policy=policy, quota_budget=AUTH_SCOPE["max_documented_quota_units"], max_transient_retries=0)
    evidence = base_evidence(decision_id, classification="evidence_withheld", exit_code=2, reason="candidate_count_below_two")
    evidence["credential_preflight"] = {"configured": True, "secret_read_or_logged": False}
    search_rows: list[dict] = []
    try:
        profiles = select_query_profiles(PROFILES, profiles=load_query_profiles(), policy=policy)
        for profile in profiles:
            payload = provider.search_once(profile, max_results=AUTH_SCOPE["max_results_per_profile"])
            for item in payload.get("items") or []:
                snippet, identity = item.get("snippet") or {}, item.get("id") or {}
                if identity.get("videoId"):
                    search_rows.append({"video_id": identity["videoId"], "channel_id": snippet.get("channelId"),
                        "query_profile_id": profile["profile_id"], "query_text": profile["query_text"]})
            evidence["request_quota_ledger"] = {"request_count": provider.request_count,
                "search_list_request_count": sum(x["endpoint"] == "search.list" for x in provider.quota_ledger),
                "videos_list_request_count": 0, "page_count": 0, "documented_quota_units": provider.quota_used,
                "events": sanitized_ledger(provider)}
            write(output, evidence)  # durable evidence before the next request
        ids = list(dict.fromkeys(row["video_id"] for row in search_rows))
        metadata_rows = []
        for item in provider.videos(ids):
            snippet, status_row = item.get("snippet") or {}, item.get("status") or {}
            metadata_rows.append({"video_id": item.get("id"), "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"), "title": snippet.get("title"),
                "published_at": snippet.get("publishedAt"), "default_language": snippet.get("defaultLanguage"),
                "default_audio_language": snippet.get("defaultAudioLanguage"), "observed_at": now(),
                "privacy_status": status_row.get("privacyStatus"),
                "publicly_usable": status_row.get("privacyStatus") == "public"})
        retained = retain_candidates(search_rows, metadata_rows, limit=10)
        evidence.update({"candidate_count": len(retained["retained"]), "retained_candidates": retained["retained"],
                         "excluded_candidates": retained["excluded"],
                         "classification": "candidate_evidence_obtained" if len(retained["retained"]) >= 2 else "evidence_withheld",
                         "exit_classification": 0 if len(retained["retained"]) >= 2 else 2,
                         "withheld_reason": None if len(retained["retained"]) >= 2 else "candidate_count_below_two",
                         "human_review_package": build_review_package(retained["retained"])})
    except YouTubeProviderError as exc:
        evidence.update({"classification": "evidence_withheld", "exit_classification": 2,
                         "withheld_reason": "provider_or_quota_withheld", "provider_error_code": exc.error_code})
    evidence["request_quota_ledger"] = {"request_count": provider.request_count,
        "search_list_request_count": sum(x["endpoint"] == "search.list" for x in provider.quota_ledger),
        "videos_list_request_count": sum(x["endpoint"] == "videos.list" for x in provider.quota_ledger),
        "page_count": 0, "documented_quota_units": provider.quota_used, "events": sanitized_ledger(provider)}
    write(output, evidence)
    return int(evidence["exit_classification"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization-record", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--execution-revision", required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.output, args.authorization_record, args.authorization_id, args.execution_revision)
    except (OSError, ValueError, json.JSONDecodeError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
