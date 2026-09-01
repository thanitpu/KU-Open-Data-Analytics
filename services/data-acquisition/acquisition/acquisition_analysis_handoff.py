"""Versioned, non-authorizing Acquisition-to-Analysis handoff contract."""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "ku2d.acquisition-analysis-handoff.v1"
MANIFEST_ID_RE = re.compile(r"^KU2D-AI-[0-9]{6}$")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ANALYSIS_PENDING_FIELDS = {
    "semantic_relevance",
    "quality",
    "analytical_rank",
    "analytical_deduplication",
    "final_inclusion",
}
ACQUISITION_CRITERIA = {
    "technically_valid",
    "authorized",
    "policy_compliant",
    "provenance_bearing",
    "sanitized",
}
RETAINED_HUMAN_GATES = {
    "legal_or_policy_ambiguity",
    "restricted_or_personal_data",
    "material_provider_scope_or_quota_expansion",
    "new_spending",
    "production_write",
    "elevated_authority",
}


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _string_list(value: Any, name: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{name} must be a JSON string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain only non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must not contain duplicates")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields do not match the v1 contract")


def validate_analysis_intake(record: dict[str, Any], *, packet: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate that every accepted technical record remains retrievable for Analysis.

    Historical candidate packets may still contain Human Review fields. They are
    treated only as source evidence; this active manifest cannot promote them.
    """
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"analysis intake schema must be {SCHEMA}")
    _exact_keys(record, {"schema", "manifest_id", "created_at", "source_batch", "acquisition_acceptance",
                         "records", "analysis_handoff", "retrieval", "governance", "boundaries"}, "manifest")
    manifest_id = _string(record.get("manifest_id"), "manifest_id")
    if MANIFEST_ID_RE.fullmatch(manifest_id) is None:
        raise ValueError("manifest_id is invalid")
    _string(record.get("created_at"), "created_at")

    source = _mapping(record.get("source_batch"), "source_batch")
    _exact_keys(source, {"domain", "provider", "batch_id", "result_id", "artifact_id", "artifact_name",
                         "immutable_packet"}, "source_batch")
    for field in ("domain", "provider", "batch_id", "result_id", "artifact_id", "artifact_name"):
        _string(source.get(field), f"source_batch.{field}")
    packet_ref = _mapping(source.get("immutable_packet"), "source_batch.immutable_packet")
    _exact_keys(packet_ref, {"packet_id", "path", "commit_sha", "git_blob_sha", "sha256"},
                "source_batch.immutable_packet")
    for field in ("packet_id", "path", "commit_sha", "git_blob_sha", "sha256"):
        _string(packet_ref.get(field), f"source_batch.immutable_packet.{field}")
    if SHA1_RE.fullmatch(packet_ref["commit_sha"]) is None or SHA1_RE.fullmatch(packet_ref["git_blob_sha"]) is None:
        raise ValueError("immutable packet Git provenance is invalid")
    if SHA256_RE.fullmatch(packet_ref["sha256"]) is None:
        raise ValueError("immutable packet SHA-256 is invalid")

    acceptance = _mapping(record.get("acquisition_acceptance"), "acquisition_acceptance")
    _exact_keys(acceptance, {"status", "accepted_record_count", "criteria", "semantic_quality_claimed"},
                "acquisition_acceptance")
    if acceptance.get("status") != "accepted_for_analysis":
        raise ValueError("acquisition acceptance must be accepted_for_analysis")
    criteria = _mapping(acceptance.get("criteria"), "acquisition_acceptance.criteria")
    if set(criteria) != ACQUISITION_CRITERIA or any(criteria[name] is not True for name in ACQUISITION_CRITERIA):
        raise ValueError("every Acquisition acceptance criterion must be explicitly true")
    if acceptance.get("semantic_quality_claimed") is not False:
        raise ValueError("Acquisition cannot claim semantic quality")

    rows = record.get("records")
    if not isinstance(rows, list) or not rows:
        raise ValueError("records must be a non-empty JSON array")
    if acceptance.get("accepted_record_count") != len(rows):
        raise ValueError("accepted record count does not match records")
    identities: list[str] = []
    for expected_index, row in enumerate(rows):
        row = _mapping(row, "records item")
        _exact_keys(row, {"candidate_id", "record_type", "source_packet_id", "source_packet_index",
                          "provenance", "acceptance_status", "semantic_relevance", "quality",
                          "analytical_rank", "analytical_deduplication", "final_inclusion",
                          "production_ready"}, "records item")
        candidate_id = _string(row.get("candidate_id"), "candidate_id")
        if VIDEO_ID_RE.fullmatch(candidate_id) is None:
            raise ValueError("candidate_id is not a canonical video identity")
        identities.append(candidate_id)
        if row.get("record_type") != "public_video_identity_candidate":
            raise ValueError("record_type is invalid")
        if row.get("source_packet_index") != expected_index:
            raise ValueError("source_packet_index must preserve packet order")
        if row.get("source_packet_id") != packet_ref["packet_id"]:
            raise ValueError("record packet identity is inconsistent")
        if row.get("acceptance_status") != "accepted_for_analysis":
            raise ValueError("record was not accepted for Analysis")
        if row.get("production_ready") is not False:
            raise ValueError("Analysis intake cannot assert production readiness")
        for field in ANALYSIS_PENDING_FIELDS:
            if row.get(field, object()) is not None:
                raise ValueError(f"{field} must remain null pending Analysis")
        provenance = _mapping(row.get("provenance"), "record.provenance")
        _exact_keys(provenance, {"channel_id", "query_profile_ids", "observed_at"}, "record.provenance")
        _string(provenance.get("channel_id"), "record.provenance.channel_id")
        _string_list(provenance.get("query_profile_ids"), "record.provenance.query_profile_ids")
        _string(provenance.get("observed_at"), "record.provenance.observed_at")
    if len(identities) != len(set(identities)):
        raise ValueError("Analysis intake contains duplicate candidate identities")

    handoff = _mapping(record.get("analysis_handoff"), "analysis_handoff")
    _exact_keys(handoff, {"status", "owner", "record_count", "pending_decisions"}, "analysis_handoff")
    if handoff.get("status") != "ready_for_analysis":
        raise ValueError("Analysis handoff is not ready")
    if handoff.get("owner") != "KU2A":
        raise ValueError("Analysis handoff owner is invalid")
    if set(_string_list(handoff.get("pending_decisions"), "analysis_handoff.pending_decisions")) != ANALYSIS_PENDING_FIELDS:
        raise ValueError("Analysis ownership is incomplete")
    if handoff.get("record_count") != len(rows):
        raise ValueError("Analysis handoff record count is inconsistent")

    retrieval = _mapping(record.get("retrieval"), "retrieval")
    _exact_keys(retrieval, {"record_count", "all_records_indexed", "immutable_packet_required",
                            "provenance_preserved", "hidden_record_count_zero"}, "retrieval")
    if retrieval.get("record_count") != len(rows):
        raise ValueError("retrieval record count is inconsistent")
    for flag in ("all_records_indexed", "immutable_packet_required", "provenance_preserved", "hidden_record_count_zero"):
        if retrieval.get(flag) is not True:
            raise ValueError(f"retrieval.{flag} must be true")

    governance = _mapping(record.get("governance"), "governance")
    _exact_keys(governance, {"acquisition_human_gate_retained_only_for",
                             "analysis_selection_is_acquisition_authority"}, "governance")
    if set(_string_list(governance.get("acquisition_human_gate_retained_only_for"),
                        "governance.acquisition_human_gate_retained_only_for")) != RETAINED_HUMAN_GATES:
        raise ValueError("Acquisition Human-gate boundary is invalid")
    if governance.get("analysis_selection_is_acquisition_authority") is not False:
        raise ValueError("Analysis selection cannot become Acquisition authority")

    boundaries = _mapping(record.get("boundaries"), "boundaries")
    _exact_keys(boundaries, {"provider_request_performed", "documented_quota_units",
                             "semantic_quality_claimed", "production_store", "production_approved",
                             "authority_promoted", "scheduler_action"}, "boundaries")
    for field in ("provider_request_performed", "semantic_quality_claimed", "production_store",
                  "production_approved", "authority_promoted"):
        if boundaries.get(field) is not False:
            raise ValueError(f"prohibited boundary changed: {field}")
    if boundaries.get("documented_quota_units") != 0 or boundaries.get("scheduler_action") is not None:
        raise ValueError("Analysis handoff cannot consume quota or schedule work")

    if packet is not None:
        packet_rows = packet.get("candidates")
        if not isinstance(packet_rows, list) or packet.get("candidate_count") != len(packet_rows):
            raise ValueError("historical candidate packet is invalid")
        if len(packet_rows) != len(rows):
            raise ValueError("Analysis intake did not preserve every packet candidate")
        for index, (source_row, intake_row) in enumerate(zip(packet_rows, rows)):
            if source_row.get("video_id") != intake_row["candidate_id"]:
                raise ValueError(f"candidate identity mismatch at packet index {index}")
            provenance = intake_row["provenance"]
            if source_row.get("channel_id") != provenance["channel_id"]:
                raise ValueError(f"channel provenance mismatch at packet index {index}")
            if source_row.get("query_profile_ids") != provenance["query_profile_ids"]:
                raise ValueError(f"profile provenance mismatch at packet index {index}")
            if source_row.get("observed_at") != provenance["observed_at"]:
                raise ValueError(f"observation provenance mismatch at packet index {index}")
    return record


def legacy_candidate_is_readable(candidate: dict[str, Any]) -> bool:
    """Recognize old pending candidates without granting them active authority."""
    return (
        isinstance(candidate, dict)
        and candidate.get("human_review_status") == "pending"
        and candidate.get("usable_for_live_acquisition") is False
        and VIDEO_ID_RE.fullmatch(str(candidate.get("video_id", ""))) is not None
    )
