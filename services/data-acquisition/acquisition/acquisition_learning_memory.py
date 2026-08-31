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
GROUND_TRUTH_SCHEMA = "ku2d.ground-truth-decision-record.v1"
DECISION_TRACE_SCHEMA = "ku2d.decision-trace.v1"
REVIEW_ACTOR_TYPES = {
    "assistant_review", "human_review", "deterministic_validation", "policy_review",
}
REVIEW_RESULTS = {"accepted", "corrected", "rejected", "insufficient_evidence", "deferred"}
CONFIRMATION_STATUSES = {"confirmed", "rejected", "deferred"}
GROUND_TRUTH_STATUSES = {
    "candidate", "human_confirmed", "policy_confirmed", "deterministic_confirmed",
    "superseded", "withdrawn",
}
ML_ELIGIBILITY_STATES = {"ineligible", "candidate", "review_required", "human_confirmed", "excluded"}
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


def validate_ground_truth_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != GROUND_TRUTH_SCHEMA:
        raise ValueError(f"schema must be {GROUND_TRUTH_SCHEMA}")
    ground_id = _nonempty(record.get("ground_truth_record_id"), "ground_truth_record_id")
    learning_id = _nonempty(record.get("learning_record_id"), "learning_record_id")
    if ground_id == learning_id:
        raise ValueError("ground truth record cannot reference itself as learning evidence")
    if record.get("final_label") is None:
        raise ValueError("final_label is required; unknown is valid")
    status = record.get("status")
    if status not in GROUND_TRUTH_STATUSES:
        raise ValueError("ground truth status is invalid")
    _nonempty(record.get("authority_basis"), "authority_basis")
    _nonempty(record.get("effective_at"), "effective_at")
    for key in ("supporting_review_record_ids", "supporting_human_confirmation_record_ids"):
        if not isinstance(record.get(key), list):
            raise ValueError(f"{key} must be a list")
    if status == "human_confirmed" and not record["supporting_human_confirmation_record_ids"]:
        raise ValueError("human_confirmed ground truth requires Human Confirmation references")
    if record.get("supersedes_ground_truth_record_id") == ground_id:
        raise ValueError("ground truth record cannot supersede itself")
    provenance = _mapping(record, "provenance")
    if provenance.get("source_learning_record_schema") != LEARNING_RECORD_SCHEMA:
        raise ValueError("ground truth must reference Learning Record v1")
    return validate_safe_json_payload(record)


def build_ground_truth_record(
    *, ground_truth_record_id: str, learning_record_id: str, final_label: Any,
    status: str, confidence: str, authority_basis: str,
    supporting_review_record_ids: list[str],
    supporting_human_confirmation_record_ids: list[str], effective_at: str,
    supersedes_ground_truth_record_id: str | None = None,
    source_reference: str | None = None,
) -> dict[str, Any]:
    record = {
        "schema": GROUND_TRUTH_SCHEMA,
        "ground_truth_record_id": ground_truth_record_id,
        "learning_record_id": learning_record_id,
        "final_label": deepcopy(final_label),
        "status": status,
        "confidence": confidence,
        "authority_basis": authority_basis,
        "supporting_review_record_ids": list(supporting_review_record_ids),
        "supporting_human_confirmation_record_ids": list(supporting_human_confirmation_record_ids),
        "supersedes_ground_truth_record_id": supersedes_ground_truth_record_id,
        "effective_at": effective_at,
        "provenance": {
            "source_learning_record_schema": LEARNING_RECORD_SCHEMA,
            "source_review_record_schema": REVIEW_FEEDBACK_SCHEMA,
            "source_confirmation_record_schema": HUMAN_CONFIRMATION_SCHEMA,
            "source_reference": source_reference,
            "record_semantics": "current-authority-candidate-not-eternal-truth",
        },
    }
    return validate_ground_truth_record(record)


def serialize_ground_truth_record(record: dict[str, Any]) -> dict[str, Any]:
    return serialize_json_object(validate_ground_truth_record(record))


def _index(records: list[dict[str, Any]], id_key: str, validator) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        validator(record)
        record_id = str(record[id_key])
        if record_id in indexed:
            raise ValueError(f"duplicate {id_key}: {record_id}")
        indexed[record_id] = record
    return indexed


def validate_learning_memory_bundle(
    learning_records: list[dict[str, Any]], review_records: list[dict[str, Any]],
    confirmation_records: list[dict[str, Any]], ground_truth_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate references and active authority without requiring a database."""
    from acquisition_learning_record import validate_learning_record

    learning = _index(learning_records, "learning_record_id", validate_learning_record)
    reviews = _index(review_records, "review_record_id", validate_review_feedback_record)
    confirmations = _index(
        confirmation_records, "confirmation_record_id", validate_human_confirmation_record,
    )
    ground = _index(ground_truth_records, "ground_truth_record_id", validate_ground_truth_record)

    all_ids = list(learning) + list(reviews) + list(confirmations) + list(ground)
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("record identifiers must be globally unique within a bundle")
    for record in reviews.values():
        if record["target"]["learning_record_id"] not in learning:
            raise ValueError("orphan Review Feedback learning_record_id")
    for record in confirmations.values():
        learning_id = record["learning_record_id"]
        if learning_id not in learning:
            raise ValueError("orphan Human Confirmation learning_record_id")
        review_id = record.get("review_record_id")
        if review_id:
            if review_id not in reviews:
                raise ValueError("orphan Human Confirmation review_record_id")
            if reviews[review_id]["target"]["learning_record_id"] != learning_id:
                raise ValueError("Human Confirmation review target is inconsistent")

    for record in ground.values():
        learning_id = record["learning_record_id"]
        if learning_id not in learning:
            raise ValueError("orphan Ground Truth learning_record_id")
        for review_id in record["supporting_review_record_ids"]:
            if review_id not in reviews or reviews[review_id]["target"]["learning_record_id"] != learning_id:
                raise ValueError("Ground Truth has an invalid supporting review")
        for confirmation_id in record["supporting_human_confirmation_record_ids"]:
            if confirmation_id not in confirmations or confirmations[confirmation_id]["learning_record_id"] != learning_id:
                raise ValueError("Ground Truth has an invalid Human Confirmation")
        if record["status"] == "human_confirmed":
            matching = [
                confirmations[confirmation_id]
                for confirmation_id in record["supporting_human_confirmation_record_ids"]
                if confirmations[confirmation_id]["confirmation_status"] == "confirmed"
                and confirmations[confirmation_id]["confirmed_decision"] == record["final_label"]
            ]
            if not matching:
                raise ValueError("human_confirmed Ground Truth lacks matching explicit confirmation")
        supersedes = record.get("supersedes_ground_truth_record_id")
        if supersedes:
            if supersedes not in ground:
                raise ValueError("Ground Truth supersedes an unknown record")
            if ground[supersedes]["learning_record_id"] != learning_id:
                raise ValueError("Ground Truth cannot supersede another learning target")

    # A chain may revise history but may never cycle.
    for record_id in ground:
        seen: set[str] = set()
        cursor: str | None = record_id
        while cursor:
            if cursor in seen:
                raise ValueError("Ground Truth supersession cycle detected")
            seen.add(cursor)
            cursor = ground[cursor].get("supersedes_ground_truth_record_id")

    superseded_ids = {
        record["supersedes_ground_truth_record_id"]
        for record in ground.values() if record.get("supersedes_ground_truth_record_id")
    }
    active_statuses = {"candidate", "human_confirmed", "policy_confirmed", "deterministic_confirmed"}
    active_by_learning: dict[str, list[dict[str, Any]]] = {}
    for record_id, record in ground.items():
        if record["status"] in active_statuses and record_id not in superseded_ids:
            active_by_learning.setdefault(record["learning_record_id"], []).append(record)
    for records in active_by_learning.values():
        labels = {json.dumps(record["final_label"], sort_keys=True, ensure_ascii=False) for record in records}
        if len(labels) > 1:
            raise ValueError("contradictory active Ground Truth labels")

    return {
        "learning_records": learning,
        "review_records": reviews,
        "confirmation_records": confirmations,
        "ground_truth_records": ground,
        "active_ground_truth_by_learning_record_id": active_by_learning,
        "superseded_ground_truth_record_ids": sorted(superseded_ids),
    }


def build_decision_trace(
    learning_record_id: str, *, learning_records: list[dict[str, Any]],
    review_records: list[dict[str, Any]], confirmation_records: list[dict[str, Any]],
    ground_truth_records: list[dict[str, Any]],
) -> dict[str, Any]:
    bundle = validate_learning_memory_bundle(
        learning_records, review_records, confirmation_records, ground_truth_records,
    )
    if learning_record_id not in bundle["learning_records"]:
        raise ValueError("Decision Trace learning_record_id is unknown")
    learning = bundle["learning_records"][learning_record_id]
    reviews = sorted(
        (record for record in bundle["review_records"].values()
         if record["target"]["learning_record_id"] == learning_record_id),
        key=lambda record: (record["reviewed_at"], record["review_record_id"]),
    )
    confirmations = sorted(
        (record for record in bundle["confirmation_records"].values()
         if record["learning_record_id"] == learning_record_id),
        key=lambda record: (record["confirmed_at"], record["confirmation_record_id"]),
    )
    ground = sorted(
        (record for record in bundle["ground_truth_records"].values()
         if record["learning_record_id"] == learning_record_id),
        key=lambda record: (record["effective_at"], record["ground_truth_record_id"]),
    )
    active = bundle["active_ground_truth_by_learning_record_id"].get(learning_record_id, [])
    initial_suggestion = learning["decision"].get("system_suggestion")
    if initial_suggestion is None:
        initial_suggestion = next((
            record["proposal"].get("system_suggestion") for record in reviews
            if record["proposal"].get("system_suggestion") is not None
        ), None)
    return serialize_json_object({
        "schema": DECISION_TRACE_SCHEMA,
        "learning_record_id": learning_record_id,
        "initial_system_suggestion": initial_suggestion,
        "learning_record_decision": deepcopy(learning["decision"]),
        "review_history": deepcopy(reviews),
        "human_confirmation_history": deepcopy(confirmations),
        "ground_truth_history": deepcopy(ground),
        "current_authoritative_label": active[-1]["final_label"] if active else None,
        "current_authority_status": active[-1]["status"] if active else "unresolved",
        "human_involved": bool(confirmations or any(
            record["review_actor"]["actor_type"] == "human_review" for record in reviews
        )),
        "has_been_superseded": bool(bundle["superseded_ground_truth_record_ids"]),
    })


def assess_ml_dataset_eligibility(
    learning_record_id: str, *, learning_records: list[dict[str, Any]],
    review_records: list[dict[str, Any]], confirmation_records: list[dict[str, Any]],
    ground_truth_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assess future export readiness; this does not create a dataset or train ML."""
    try:
        bundle = validate_learning_memory_bundle(
            learning_records, review_records, confirmation_records, ground_truth_records,
        )
    except ValueError as exc:
        message = str(exc)
        state = "excluded" if any(term in message.casefold() for term in (
            "sensitive", "credential", "session", "cookie", "token",
        )) else "ineligible"
        return {"state": state, "reason": message, "learning_record_id": learning_record_id}
    if learning_record_id not in bundle["learning_records"]:
        return {"state": "ineligible", "reason": "learning record is absent", "learning_record_id": learning_record_id}
    active = bundle["active_ground_truth_by_learning_record_id"].get(learning_record_id, [])
    if active:
        statuses = {record["status"] for record in active}
        if "human_confirmed" in statuses:
            state, reason = "human_confirmed", "active label has explicit Human Confirmation"
        else:
            state, reason = "candidate", "active deterministic or policy Ground Truth candidate"
    else:
        reviews = [
            record for record in bundle["review_records"].values()
            if record["target"]["learning_record_id"] == learning_record_id
        ]
        if any(record["review_actor"]["actor_type"] == "assistant_review" for record in reviews):
            state, reason = "review_required", "assistant review is not Human Confirmation"
        else:
            state, reason = "candidate", "validated evidence and deterministic label are available"
    if state not in ML_ELIGIBILITY_STATES:
        raise AssertionError("invalid eligibility state")
    return {"state": state, "reason": reason, "learning_record_id": learning_record_id}


def serialize_record_json(record: dict[str, Any], validator) -> str:
    return json.dumps(
        serialize_json_object(validator(record)), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )
