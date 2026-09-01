"""Bounded Q-Diving identity discovery retention and review preparation."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

SCHEMA = "ku2d.youtube-qdiving-identity-discovery.v1"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
SEARCH_UNIT_COST = 100
VIDEOS_UNIT_COST = 1


def quota_plan(profile_count: int, *, metadata_request_count: int = 1) -> dict[str, Any]:
    if isinstance(profile_count, bool) or not isinstance(profile_count, int) or not 1 <= profile_count <= 8:
        raise ValueError("profile_count must be between 1 and 8")
    if metadata_request_count not in {0, 1}:
        raise ValueError("metadata_request_count must be zero or one")
    return {"search_request_cap": profile_count, "metadata_request_cap": metadata_request_count,
            "request_cap": profile_count + metadata_request_count,
            "quota_unit_cap": profile_count * SEARCH_UNIT_COST + metadata_request_count * VIDEOS_UNIT_COST,
            "unit_costs": {"search.list": SEARCH_UNIT_COST, "videos.list": VIDEOS_UNIT_COST},
            "value_origin": "official_documentation_accessed_2026-09-01"}


def retain_candidates(search_rows: list[dict[str, Any]], metadata_rows: list[dict[str, Any]], *, limit: int = 6) -> dict[str, Any]:
    if not 1 <= limit <= 10:
        raise ValueError("candidate limit must be between 1 and 10")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in search_rows:
        video_id = row.get("video_id")
        if not isinstance(video_id, str) or VIDEO_ID_RE.fullmatch(video_id) is None:
            raise ValueError("search evidence contains a malformed canonical video identity")
        grouped[video_id].append(row)
    metadata = {row.get("video_id"): row for row in metadata_rows}
    if len(metadata) != len(metadata_rows):
        raise ValueError("metadata contains duplicate video identities")
    retained, excluded = [], []
    for video_id, evidence in grouped.items():
        meta = metadata.get(video_id)
        channel_ids = {row.get("channel_id") for row in evidence if row.get("channel_id")}
        if len(channel_ids) != 1 or (meta and meta.get("channel_id") not in channel_ids):
            excluded.append({"video_id": video_id, "reason": "ambiguous_channel_linkage"}); continue
        if meta is None:
            excluded.append({"video_id": video_id, "reason": "unavailable_or_deleted"}); continue
        if meta.get("privacy_status") != "public" or meta.get("publicly_usable") is not True:
            excluded.append({"video_id": video_id, "reason": "private_or_unavailable"}); continue
        profiles = sorted({row.get("query_profile_id") for row in evidence if row.get("query_profile_id")})
        retained.append({"video_id": video_id, "canonical_watch_url": f"https://www.youtube.com/watch?v={video_id}",
                         "channel_id": meta["channel_id"], "channel_title": meta.get("channel_title"),
                         "title": meta.get("title"), "published_at": meta.get("published_at"),
                         "default_language": meta.get("default_language"),
                         "default_audio_language": meta.get("default_audio_language"),
                         "query_profile_ids": profiles, "profile_query_provenance": [
                             {"query_profile_id": row.get("query_profile_id"), "query_text": row.get("query_text")}
                             for row in evidence], "observed_at": meta.get("observed_at"),
                         "public_availability_state": "public", "suggested_match_reason": "returned by an existing Q-Diving query profile and resolved by public metadata",
                         "commercial_context_caveat": "not assessed by Acquisition",
                         "uncertainty": "semantic relevance and quality pending Analysis",
                         "acquisition_acceptance": "accepted_for_analysis",
                         "analysis_handoff_status": "pending_manifest",
                         "semantic_relevance": None, "quality": None, "analytical_rank": None,
                         "analytical_deduplication": None, "final_inclusion": None,
                         "production_ready": False})
    return {"retained": retained[:limit], "excluded": excluded,
            "duplicate_cross_profile_count": sum(len(rows) - 1 for rows in grouped.values()),
            "truncated": len(retained) > limit}


def build_review_package(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the historical v1 Human Review package for backward reading only."""
    if any(row.get("human_review_status") != "pending" or row.get("usable_for_live_acquisition") is not False
           for row in candidates):
        raise ValueError("candidate package attempted authority promotion")
    return {"schema": "ku2d.youtube-qdiving-human-review-package.v1", "selection_target": 2,
            "candidate_count": len(candidates), "candidates": candidates,
            "suggestions_are_non_authoritative": True, "human_adjudication_required": True,
            "production_approved": False, "scheduler_action": None}


def build_analysis_handoff_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Stage every technically accepted candidate for a durable Analysis manifest."""
    if not candidates:
        return {
            "acquisition_acceptance": {
                "status": "no_records_to_handoff", "accepted_record_count": 0,
                "semantic_quality_claimed": False,
            },
            "analysis_handoff": {
                "status": "not_ready", "record_count": 0,
                "pending_decisions": ["semantic_relevance", "quality", "analytical_rank",
                                      "analytical_deduplication", "final_inclusion"],
            },
        }
    required_nulls = ("semantic_relevance", "quality", "analytical_rank",
                      "analytical_deduplication", "final_inclusion")
    for row in candidates:
        if row.get("acquisition_acceptance") != "accepted_for_analysis":
            raise ValueError("candidate is not technically accepted for Analysis")
        if row.get("analysis_handoff_status") != "pending_manifest":
            raise ValueError("candidate Analysis handoff status is invalid")
        if row.get("production_ready") is not False or any(row.get(field, object()) is not None for field in required_nulls):
            raise ValueError("candidate attempted semantic or production promotion")
    return {
        "acquisition_acceptance": {
            "status": "accepted_for_analysis", "accepted_record_count": len(candidates),
            "semantic_quality_claimed": False,
        },
        "analysis_handoff": {
            "status": "ready_for_analysis", "record_count": len(candidates),
            "pending_decisions": ["semantic_relevance", "quality", "analytical_rank",
                                  "analytical_deduplication", "final_inclusion"],
        },
    }


def validate_discovery_evidence(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("schema") != SCHEMA:
        raise ValueError("identity discovery evidence schema is invalid")
    ledger = record.get("request_quota_ledger") or {}
    requests = ledger.get("request_count")
    quota = ledger.get("documented_quota_units")
    if isinstance(requests, bool) or not isinstance(requests, int) or requests < 0:
        raise ValueError("request count is invalid")
    if isinstance(quota, bool) or not isinstance(quota, int) or quota < 0:
        raise ValueError("quota count is invalid")
    if record.get("classification") == "evidence_withheld":
        if record.get("exit_classification") != 2 or record.get("technical_completion") is not True:
            raise ValueError("withheld discovery must be exit 2 technical completion")
        if record.get("withheld_reason") == "api_credential_not_configured" and (requests or quota):
            raise ValueError("credential preflight must precede every request")
    elif record.get("classification") == "candidate_evidence_obtained":
        if record.get("exit_classification") != 0 or record.get("candidate_count", 0) < 1:
            raise ValueError("successful discovery requires at least one technically accepted candidate")
        retained = record.get("retained_candidates")
        if not isinstance(retained, list) or len(retained) != record["candidate_count"]:
            raise ValueError("successful discovery candidate count is inconsistent")
    else:
        raise ValueError("discovery classification is invalid")
    # Historical evidence remains readable, but its Human Review fields do not
    # act as the current Acquisition completion gate or grant current authority.
    if "usable_reviewed_identity_count" in record and record.get("usable_reviewed_identity_count") != 0:
        raise ValueError("historical discovery evidence promoted Human Review authority")
    if "human_review_completed" in record and record.get("human_review_completed") is not False:
        raise ValueError("historical discovery evidence promoted Human Review authority")
    acceptance = record.get("acquisition_acceptance")
    handoff = record.get("analysis_handoff")
    if acceptance is not None or handoff is not None:
        if not isinstance(acceptance, dict) or not isinstance(handoff, dict):
            raise ValueError("active Acquisition-to-Analysis status is invalid")
        count = record.get("candidate_count", 0)
        if record.get("classification") == "candidate_evidence_obtained":
            if acceptance != {"status": "accepted_for_analysis", "accepted_record_count": count,
                              "semantic_quality_claimed": False}:
                raise ValueError("active Acquisition acceptance is invalid")
            if handoff.get("status") != "ready_for_analysis" or handoff.get("record_count") != count:
                raise ValueError("active Analysis handoff is invalid")
            pending = {"semantic_relevance", "quality", "analytical_rank",
                       "analytical_deduplication", "final_inclusion"}
            if set(handoff.get("pending_decisions") or []) != pending:
                raise ValueError("active Analysis ownership is incomplete")
            for candidate in record["retained_candidates"]:
                if candidate.get("acquisition_acceptance") != "accepted_for_analysis":
                    raise ValueError("active candidate was not accepted for Analysis")
                if candidate.get("production_ready") is not False:
                    raise ValueError("active candidate attempted production promotion")
        else:
            if acceptance.get("status") != "no_records_to_handoff" or acceptance.get("accepted_record_count") != 0:
                raise ValueError("withheld evidence cannot accept records for Analysis")
            if handoff.get("status") != "not_ready" or handoff.get("record_count") != 0:
                raise ValueError("withheld evidence cannot be ready for Analysis")
    boundaries = record.get("boundaries") or {}
    for field in ("comments_acquired", "captions_called", "transcript_text_acquired", "oauth_used",
                  "production_store", "production_approved", "authority_promoted"):
        if boundaries.get(field) is not False:
            raise ValueError(f"prohibited boundary changed: {field}")
    if boundaries.get("scheduler_action") is not None:
        raise ValueError("discovery evidence cannot schedule work")
    return record
