"""Early technical acquisition gate; semantic quality remains Analysis-owned."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from connector_kit import fingerprint, validate_sanitized


def _timestamp(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be RFC 3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


def validate_early_acquisition_quality(
    records: list[dict[str, Any]],
    evidence_by_capability: Mapping[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Validate technical handoff fitness without judging relevance or inclusion."""
    if not isinstance(records, list) or not records:
        raise ValueError("quality gate requires at least one mapped record")
    validate_sanitized(records, path="analysis_handoff_records")
    identities: set[str] = set()
    record_hashes: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError("mapped records must be JSON objects")
        if not isinstance(record.get("schema"), str) or not record["schema"].strip():
            raise ValueError(f"records[{index}].schema is required")
        identity = record.get("record_id")
        if not isinstance(identity, str) or not identity.strip() or identity in identities:
            raise ValueError("record identities must be unique non-empty strings")
        identities.add(identity)
        record_hash = fingerprint(record)
        if record_hash in record_hashes:
            raise ValueError("exact duplicate mapped records are forbidden after merge")
        record_hashes.add(record_hash)
        provenance = record.get("provenance")
        if not isinstance(provenance, dict) or not provenance:
            raise ValueError(f"records[{index}].provenance is required")
        _timestamp(provenance.get("observed_at"), f"records[{index}].provenance.observed_at")

    requested = manifest["requested_capabilities"]
    if set(evidence_by_capability) != set(requested):
        raise ValueError("evidence must exactly cover requested capabilities")
    for capability_id in requested:
        evidence = evidence_by_capability[capability_id]
        if not isinstance(evidence, dict) or evidence.get("capability_id") != capability_id:
            raise ValueError("capability evidence identity mismatch")
        if evidence.get("domain_record_count", 0) < 1:
            raise ValueError("capability evidence is incomplete")
        response = evidence.get("response")
        if not isinstance(response, dict) or not isinstance(response.get("provenance"), dict):
            raise ValueError("response provenance is required")
        _timestamp(response.get("observed_at"), "evidence.response.observed_at")
        if not isinstance(response.get("payload_sha256"), str) or len(response["payload_sha256"]) != 64:
            raise ValueError("response payload fingerprint is required")
        if evidence.get("documented_quota_units") != 0:
            raise ValueError("fixture quality evidence must have zero quota")
    if manifest["authority_boundaries"]["semantic_quality_owner"] != "analysis":
        raise ValueError("semantic quality authority drifted from Analysis")
    return {
        "status": "passed",
        "checks": {
            "authority": True,
            "schema": True,
            "provenance": True,
            "timestamps": True,
            "sanitization": True,
            "exact_technical_duplication": True,
            "evidence_completeness": True,
        },
        "hard_failures": [],
        "metrics": {
            "record_count": len(records),
            "unique_identity_count": len(identities),
            "requested_capability_count": len(requested),
            "evidenced_capability_count": len(evidence_by_capability),
        },
        "semantic_quality_scored": False,
        "final_inclusion_decided": False,
    }
