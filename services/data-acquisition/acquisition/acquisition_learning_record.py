"""Small, storage-neutral contract for future acquisition learning evidence.

This module validates and serializes deterministic knowledge artifacts. It does
not train a model, authorize acquisition, or write records automatically.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit


SCHEMA = "ku2d.acquisition-learning-record.v1"
DECISION_SOURCES = {
    "deterministic_rule", "human_review", "reviewed_policy", "source_explicit_label",
}
_FORBIDDEN_KEYS = {
    "authorization", "authorization_header", "cookie", "cookies", "access_token",
    "refresh_token", "session", "session_data", "session_id", "browser_profile",
    "storage_state", "device_id", "raw_netlog", "netlog", "password", "secret",
}
_SENSITIVE_VALUE_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._~+/=-]{8,}|(?:sessionid|access_token|refresh_token|"
    r"api[_-]?key|password)\s*[=:]\s*[^\s&]+|https?://[^/\s:@]+:[^@\s/]+@)",
    re.IGNORECASE,
)


def _walk(value: Any, path: str = "record"):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            yield path, normalized, child
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield path, f"[{index}]", child
            yield from _walk(child, f"{path}[{index}]")


def _required_mapping(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def validate_safe_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the shared sensitive-material and JSON-safety boundary."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    for path, key, value in _walk(payload):
        if key in _FORBIDDEN_KEYS:
            raise ValueError(f"sensitive field is prohibited at {path}.{key}")
        if isinstance(value, str) and _SENSITIVE_VALUE_RE.search(value):
            raise ValueError(f"credential/session material is prohibited at {path}.{key}")
        if key == "source_surface" and isinstance(value, str):
            parsed = urlsplit(value)
            if parsed.username or parsed.password:
                raise ValueError("credential-bearing source_surface is prohibited")
    try:
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"payload is not JSON safe: {exc}") from exc
    return payload


def serialize_json_object(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a detached object in deterministic key order."""
    validate_safe_json_payload(payload)
    return json.loads(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ))


def validate_learning_record(record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on malformed, unsafe, or provenance-poor records."""
    if not isinstance(record, dict):
        raise ValueError("learning record must be a JSON object")
    if record.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if not str(record.get("learning_record_id") or "").strip():
        raise ValueError("learning_record_id is required")
    if not str(record.get("generated_at") or "").strip():
        raise ValueError("generated_at is required")

    identity = _required_mapping(record, "identity")
    if not str(identity.get("domain") or "").strip():
        raise ValueError("identity.domain is required")
    if not str(identity.get("source_id") or identity.get("platform") or "").strip():
        raise ValueError("identity source_id or platform is required")
    if not str(identity.get("source_type") or "").strip():
        raise ValueError("identity.source_type is required")

    context = _required_mapping(record, "observation_context")
    technique = _required_mapping(record, "technique")
    evidence = _required_mapping(record, "observed_evidence")
    labels = _required_mapping(record, "semantic_labels")
    outcome = _required_mapping(record, "acquisition_outcome")
    decision = _required_mapping(record, "decision")
    provenance = _required_mapping(record, "provenance")
    if not context:
        raise ValueError("observation_context must preserve context")
    if not technique:
        raise ValueError("technique must preserve acquisition technique")
    if not str(technique.get("technique_id") or "").strip() or not str(technique.get("acquisition_mode") or "").strip():
        raise ValueError("technique_id and acquisition_mode are required")
    if not evidence:
        raise ValueError("observed_evidence must preserve evidence, including negative evidence")
    if not str(evidence.get("evidence_type") or "").strip():
        raise ValueError("observed_evidence.evidence_type is required")
    if not labels:
        raise ValueError("semantic_labels is required; unknown is a valid label")
    if not str(provenance.get("evidence_origin") or "").strip():
        raise ValueError("provenance.evidence_origin is required")
    if not str(provenance.get("source_schema") or provenance.get("extractor_schema") or "").strip():
        raise ValueError("source or extractor schema provenance is required")

    for key in ("technical_completion", "usable_evidence", "production_approved", "production_store"):
        if not isinstance(outcome.get(key), bool):
            raise ValueError(f"acquisition_outcome.{key} must be boolean")
    if "scheduler_action" not in outcome:
        raise ValueError("acquisition_outcome.scheduler_action must be preserved")
    if labels.get("canonical_price_asserted") is False and labels.get("canonical_price") is not None:
        raise ValueError("canonical_price must be null when canonical_price_asserted is false")

    decision_source = decision.get("decision_source")
    if decision_source not in DECISION_SOURCES:
        raise ValueError("decision.decision_source is invalid")
    for key in ("decision_type", "system_suggestion", "final_decision", "reason_code", "evidence_references"):
        if key not in decision:
            raise ValueError(f"decision.{key} must be preserved")
    if not str(decision.get("decision_type") or "").strip() or not str(decision.get("reason_code") or "").strip():
        raise ValueError("decision_type and reason_code are required")
    if decision.get("final_decision") is None:
        raise ValueError("decision.final_decision is required; unknown is valid")
    reviewed_status = provenance.get("reviewed_status")
    reviewer = provenance.get("reviewer_provenance")
    if decision_source == "human_review" and (reviewed_status != "human-reviewed" or not reviewer):
        raise ValueError("human_review requires genuine reviewed status and reviewer provenance")
    if reviewer and decision_source != "human_review":
        raise ValueError("reviewer provenance cannot be attached to a non-human decision")

    return validate_safe_json_payload(record)


def build_learning_record(
    *, learning_record_id: str, generated_at: str, identity: dict[str, Any],
    observation_context: dict[str, Any], technique: dict[str, Any],
    observed_evidence: dict[str, Any], semantic_labels: dict[str, Any],
    acquisition_outcome: dict[str, Any], decision: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "schema": SCHEMA,
        "learning_record_id": learning_record_id,
        "generated_at": generated_at,
        "identity": deepcopy(identity),
        "observation_context": deepcopy(observation_context),
        "technique": deepcopy(technique),
        "observed_evidence": deepcopy(observed_evidence),
        "semantic_labels": deepcopy(semantic_labels),
        "acquisition_outcome": deepcopy(acquisition_outcome),
        "decision": deepcopy(decision),
        "provenance": deepcopy(provenance),
    }
    return validate_learning_record(record)


def serialize_learning_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached, deterministic-key-order, JSON-safe object."""
    validate_learning_record(record)
    return serialize_json_object(record)


def serialize_learning_record_json(record: dict[str, Any]) -> str:
    """Return one canonical JSON object suitable for a future JSONL line."""
    return json.dumps(
        serialize_learning_record(record), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )
