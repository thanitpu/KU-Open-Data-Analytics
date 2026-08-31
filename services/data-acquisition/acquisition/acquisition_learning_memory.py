"""Storage-neutral review contracts for KU2D Learning Memory v1.

All builders are explicit pure functions. They do not persist records, grant
authority, or alter acquisition, approval, scheduler, or production state.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from acquisition_learning_record import (
    SCHEMA as LEARNING_RECORD_SCHEMA,
    serialize_json_object,
    validate_safe_json_payload,
)


REVIEW_FEEDBACK_SCHEMA = "ku2d.review-feedback-record.v1"
HUMAN_CONFIRMATION_SCHEMA = "ku2d.human-confirmation-record.v1"
REVIEW_ACTOR_TYPES = {
    "assistant_review", "human_review", "deterministic_validation", "policy_review",
}
REVIEW_RESULTS = {"accepted", "corrected", "rejected", "insufficient_evidence", "deferred"}
CONFIRMATION_STATUSES = {"confirmed", "rejected", "deferred"}
_ACTOR_AUTHORITY = {
    "assistant_review": "assistant_reviewed",
    "human_review": "human_reviewed",
    "deterministic_validation": "deterministic_verified",
    "policy_review": "policy_reviewed",
}


def _nonempty(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _mapping(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def validate_review_feedback_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != REVIEW_FEEDBACK_SCHEMA:
        raise ValueError(f"schema must be {REVIEW_FEEDBACK_SCHEMA}")
    review_id = _nonempty(record.get("review_record_id"), "review_record_id")
    _nonempty(record.get("reviewed_at"), "reviewed_at")
    target = _mapping(record, "target")
    learning_id = _nonempty(target.get("learning_record_id"), "target.learning_record_id")
    if review_id == learning_id:
        raise ValueError("review record cannot reference itself")
    actor = _mapping(record, "review_actor")
    actor_type = actor.get("actor_type")
    if actor_type not in REVIEW_ACTOR_TYPES:
        raise ValueError("review_actor.actor_type is invalid")
    if actor.get("authority_level") != _ACTOR_AUTHORITY[actor_type]:
        raise ValueError("review actor authority does not match actor_type")
    if actor_type == "human_review" and not str(actor.get("actor_id") or "").strip():
        raise ValueError("human_review requires an explicit actor_id")
    result = record.get("review_result")
    if result not in REVIEW_RESULTS:
        raise ValueError("review_result is invalid")
    proposal = _mapping(record, "proposal")
    if "system_suggestion" not in proposal or "reviewed_suggestion" not in proposal:
        raise ValueError("proposal must preserve system and reviewed suggestions")
    if result == "corrected" and proposal.get("system_suggestion") == proposal.get("reviewed_suggestion"):
        raise ValueError("a corrected review must preserve a changed suggestion")
    decision = _mapping(record, "decision")
    for key in ("proposed_final_decision", "reason_code", "explanation", "evidence_references"):
        if key not in decision:
            raise ValueError(f"decision.{key} must be preserved")
    if decision.get("proposed_final_decision") is None:
        raise ValueError("proposed_final_decision is required; unknown is valid")
    _nonempty(decision.get("reason_code"), "decision.reason_code")
    references = decision.get("evidence_references")
    if not isinstance(references, list) or not references:
        raise ValueError("decision.evidence_references must be non-empty")
    provenance = _mapping(record, "provenance")
    if provenance.get("source_learning_record_schema") != LEARNING_RECORD_SCHEMA:
        raise ValueError("review provenance must reference Learning Record v1")
    _nonempty(provenance.get("evidence_origin"), "provenance.evidence_origin")
    return validate_safe_json_payload(record)


def build_review_feedback_record(
    *, review_record_id: str, reviewed_at: str, learning_record_id: str,
    actor_type: str, actor_id: str | None, review_result: str,
    system_suggestion: Any, reviewed_suggestion: Any,
    proposed_final_decision: Any, reason_code: str, explanation: str,
    evidence_references: list[str], source_domain: str | None = None,
    source_reference: str | None = None,
) -> dict[str, Any]:
    authority = _ACTOR_AUTHORITY.get(actor_type)
    record = {
        "schema": REVIEW_FEEDBACK_SCHEMA,
        "review_record_id": review_record_id,
        "reviewed_at": reviewed_at,
        "target": {"learning_record_id": learning_record_id, "source_domain": source_domain},
        "review_actor": {
            "actor_type": actor_type, "actor_id": actor_id, "authority_level": authority,
        },
        "review_result": review_result,
        "proposal": {
            "system_suggestion": deepcopy(system_suggestion),
            "reviewed_suggestion": deepcopy(reviewed_suggestion),
        },
        "decision": {
            "proposed_final_decision": deepcopy(proposed_final_decision),
            "reason_code": reason_code,
            "explanation": explanation,
            "evidence_references": list(evidence_references),
        },
        "provenance": {
            "source_learning_record_schema": LEARNING_RECORD_SCHEMA,
            "source_reference": source_reference,
            "evidence_origin": "explicit-review-feedback",
        },
    }
    return validate_review_feedback_record(record)


def validate_human_confirmation_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != HUMAN_CONFIRMATION_SCHEMA:
        raise ValueError(f"schema must be {HUMAN_CONFIRMATION_SCHEMA}")
    confirmation_id = _nonempty(record.get("confirmation_record_id"), "confirmation_record_id")
    learning_id = _nonempty(record.get("learning_record_id"), "learning_record_id")
    if confirmation_id == learning_id or confirmation_id == record.get("review_record_id"):
        raise ValueError("confirmation record cannot reference itself")
    status = record.get("confirmation_status")
    if status not in CONFIRMATION_STATUSES:
        raise ValueError("confirmation_status is invalid")
    if status == "confirmed" and record.get("confirmed_decision") is None:
        raise ValueError("confirmed status requires confirmed_decision")
    _nonempty(record.get("confirmed_by"), "confirmed_by")
    _nonempty(record.get("confirmed_at"), "confirmed_at")
    provenance = _mapping(record, "provenance")
    if provenance.get("confirmation_source") != "explicit_human_input":
        raise ValueError("Human Confirmation requires explicit_human_input provenance")
    if provenance.get("source_learning_record_schema") != LEARNING_RECORD_SCHEMA:
        raise ValueError("confirmation must reference Learning Record v1")
    return validate_safe_json_payload(record)


def build_human_confirmation_record(
    *, confirmation_record_id: str, learning_record_id: str,
    confirmation_status: str, confirmed_decision: Any, reason_note: str,
    confirmed_by: str, confirmed_at: str, review_record_id: str | None = None,
    source_reference: str | None = None,
) -> dict[str, Any]:
    """Build only from explicit human input; never derive this automatically."""
    record = {
        "schema": HUMAN_CONFIRMATION_SCHEMA,
        "confirmation_record_id": confirmation_record_id,
        "learning_record_id": learning_record_id,
        "review_record_id": review_record_id,
        "confirmation_status": confirmation_status,
        "confirmed_decision": deepcopy(confirmed_decision),
        "reason_note": reason_note,
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at,
        "provenance": {
            "source_learning_record_schema": LEARNING_RECORD_SCHEMA,
            "source_review_record_schema": REVIEW_FEEDBACK_SCHEMA if review_record_id else None,
            "source_reference": source_reference,
            "confirmation_source": "explicit_human_input",
        },
    }
    return validate_human_confirmation_record(record)


def serialize_review_feedback_record(record: dict[str, Any]) -> dict[str, Any]:
    return serialize_json_object(validate_review_feedback_record(record))


def serialize_human_confirmation_record(record: dict[str, Any]) -> dict[str, Any]:
    return serialize_json_object(validate_human_confirmation_record(record))


def serialize_record_json(record: dict[str, Any], validator) -> str:
    return json.dumps(
        serialize_json_object(validator(record)), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )
