"""Fail-closed preflight and evidence validation for the bounded Q-Diving pilot.

This module deliberately has no transport, credential, OAuth, browser, storage,
or scheduler integration.  A live executor may proceed only after exactly two
canonical, non-sanitized, Human-Reviewed video identities are supplied by
durable merged evidence.
"""
from __future__ import annotations

import re
from typing import Any


SCHEMA = "ku2d.youtube-qdiving-live-pilot.v1"
REQUIRED_VIDEO_COUNT = 2
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
INCLUDED_KNOWLEDGE_USES = {"include", "include_with_context"}


class IdentityEvidenceWithheld(ValueError):
    """The reviewed evidence cannot resolve the exact authorized identities."""


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def resolve_exact_reviewed_video_ids(
    reviewed_records: list[dict[str, Any]], *, required_count: int = REQUIRED_VIDEO_COUNT,
) -> list[str]:
    """Resolve only explicit, real, current Human-Reviewed video identities."""
    if required_count != REQUIRED_VIDEO_COUNT:
        raise ValueError("The authorized Q-Diving pilot requires exactly two videos")
    if not isinstance(reviewed_records, list):
        raise ValueError("reviewed_records must be a list")

    resolved: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(reviewed_records):
        row = _mapping(record, f"reviewed_records[{index}]")
        if row.get("review_status") != "reviewed":
            continue
        if row.get("knowledge_use") not in INCLUDED_KNOWLEDGE_USES:
            continue
        provenance = _mapping(row.get("provenance"), f"reviewed_records[{index}].provenance")
        if provenance.get("provider") != "youtube-data-api-v3":
            raise IdentityEvidenceWithheld("Reviewed identity lacks official YouTube provider provenance")
        if provenance.get("sanitized") is not False:
            raise IdentityEvidenceWithheld("Reviewed identity is sanitized or has no explicit non-sanitized provenance")
        if provenance.get("human_reviewed") is not True:
            raise IdentityEvidenceWithheld("Reviewed identity lacks explicit Human Review provenance")
        video_id = row.get("video_id")
        if not isinstance(video_id, str) or VIDEO_ID_RE.fullmatch(video_id) is None:
            raise IdentityEvidenceWithheld("Reviewed identity is not a canonical 11-character YouTube video ID")
        if video_id in seen:
            raise IdentityEvidenceWithheld("Reviewed identity evidence contains a duplicate video ID")
        seen.add(video_id)
        resolved.append(video_id)

    if len(resolved) != required_count:
        raise IdentityEvidenceWithheld(
            f"Expected exactly {required_count} reviewed video identities; resolved {len(resolved)}"
        )
    return resolved


def validate_pilot_evidence(record: dict[str, Any]) -> dict[str, Any]:
    """Validate durable evidence without interpreting counts or optional absence."""
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"pilot evidence schema must be {SCHEMA}")
    if record.get("pilot_id") != "KU2D-YT-QDIVING-PILOT-000001":
        raise ValueError("pilot_id is invalid")
    authority = _mapping(record.get("authority"), "authority")
    if authority.get("human_decision_id") != "KU2D-H-000011" or authority.get("decision") != "confirmed":
        raise ValueError("pilot evidence lacks the exact confirmed Human Decision")
    limits = _mapping(authority.get("authorized_limits"), "authority.authorized_limits")
    if limits.get("video_count") != REQUIRED_VIDEO_COUNT or limits.get("comment_threads_max_pages_per_video") != 2:
        raise ValueError("pilot authority limits were broadened")
    if limits.get("transcript_languages") != ["th", "en"]:
        raise ValueError("pilot transcript-language boundary changed")

    identity = _mapping(record.get("identity_preflight"), "identity_preflight")
    if identity.get("required_video_count") != REQUIRED_VIDEO_COUNT:
        raise ValueError("identity preflight requires exactly two videos")
    resolved = identity.get("resolved_video_ids")
    if not isinstance(resolved, list) or len(resolved) != len(set(resolved)):
        raise ValueError("resolved_video_ids must be a unique list")
    if identity.get("resolved_video_count") != len(resolved):
        raise ValueError("resolved_video_count is inconsistent")
    if any(not isinstance(video_id, str) or VIDEO_ID_RE.fullmatch(video_id) is None for video_id in resolved):
        raise ValueError("resolved_video_ids contains a non-canonical identity")

    ledger = _mapping(record.get("request_quota_ledger"), "request_quota_ledger")
    request_count = _nonnegative_int(ledger.get("request_count"), "request_quota_ledger.request_count")
    quota_units = _nonnegative_int(ledger.get("estimated_quota_units"), "request_quota_ledger.estimated_quota_units")
    pages = _nonnegative_int(ledger.get("comment_threads_page_count"), "request_quota_ledger.comment_threads_page_count")
    transcripts = _mapping(record.get("transcript_caption_boundary"), "transcript_caption_boundary")
    if any(_nonnegative_int(transcripts.get(field), f"transcript_caption_boundary.{field}") != 0 for field in (
        "captions_list_request_count", "captions_download_request_count", "transcript_content_record_count",
        "oauth_flow_count", "audio_video_download_count",
    )):
        raise ValueError("pilot evidence records prohibited transcript/caption activity")

    classification = record.get("classification")
    if classification == "evidence_withheld":
        if record.get("exit_classification") != 2 or record.get("technical_completion") is not True:
            raise ValueError("evidence_withheld must be technical completion with exit 2")
        if resolved or request_count or quota_units or pages:
            raise ValueError("identity-preflight withholding must occur before every live request")
        if identity.get("status") != "insufficient_reviewed_identity_evidence":
            raise ValueError("identity-preflight withholding status is invalid")
    elif classification == "evidence_obtained":
        if record.get("exit_classification") != 0 or record.get("technical_completion") is not True:
            raise ValueError("evidence_obtained must be technical completion with exit 0")
        if len(resolved) != REQUIRED_VIDEO_COUNT:
            raise ValueError("evidence_obtained requires exactly two identities")
    elif classification == "technical_failure":
        if record.get("exit_classification") != 1 or record.get("technical_completion") is not False:
            raise ValueError("technical_failure must be incomplete with exit 1")
    else:
        raise ValueError("classification is invalid")

    boundaries = _mapping(record.get("boundaries"), "boundaries")
    required_false = (
        "production_authorized", "production_store", "production_approved", "comments_globally_enabled",
        "authority_promoted", "parked_refs_mutated",
    )
    if any(boundaries.get(field) is not False for field in required_false):
        raise ValueError("pilot boundary changed")
    if boundaries.get("scheduler_action") is not None:
        raise ValueError("pilot must not schedule acquisition")
    return record
