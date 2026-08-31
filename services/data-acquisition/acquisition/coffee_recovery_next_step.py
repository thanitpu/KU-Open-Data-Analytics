"""Pure validation for the KU2D Coffee recovery next-step decision.

This module validates a planning artifact only. It cannot perform a request,
dispatch a rerun, mutate knowledge, authorize production, or schedule work.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


SCHEMA = "ku2d.coffee-recovery-next-step.v1"
OPTION_IDS = {"A", "B", "C"}
WEIGHTS = {
    "expected_evidence_gain": 25,
    "cross_source_reuse_value": 20,
    "incremental_request_risk_efficiency": 20,
    "coffee_gap_resolution": 25,
    "dependency_reduction": 10,
}
EXPECTED_BOUNDARIES = {
    "planning_only": True,
    "live_request_count": 0,
    "rerun_execution_authorized": False,
    "automatic_follow_on": False,
    "candidate_promotion_count": 0,
    "learning_memory_write": False,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "human_confirmation_write": False,
    "ground_truth_write": False,
    "parked_ref_mutation_count": 0,
    "cleanup_execution": False,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "survey_doe_sem_work": False,
}
FORBIDDEN_KEYS = {
    "execute_rerun", "dispatch_rerun", "request_command", "browser_command",
    "close_pr", "merge_pr", "delete_branch", "promote_candidate",
    "write_learning_memory", "scheduler_command",
}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str, *, length: int | None = None) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty JSON array")
    if length is not None and len(value) != length:
        raise ValueError(f"{field} must contain exactly {length} entries")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _timestamp(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return text


def _walk_forbidden(value: Any) -> None:
    if isinstance(value, dict):
        found = FORBIDDEN_KEYS & set(value)
        if found:
            raise ValueError(f"executable or mutating fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden(child)


def validate_coffee_recovery_next_step(record: dict[str, Any]) -> dict[str, Any]:
    """Validate exact evidence interpretation, scoring, envelope, and boundaries."""
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    _walk_forbidden(record)
    _timestamp(record.get("evaluated_at"), "evaluated_at")
    if record.get("authoritative_branch") != "codex/ku2d-coffee-recovery-next-step-v1":
        raise ValueError("authoritative branch drifted")

    basis = _mapping(record.get("evidence_basis"), "evidence_basis")
    required_refs = {
        "KU2D-R-000023", "KU2D-R-000024",
        "docs/validation/coffee-evidence-recovery-2026-08-31.json",
        "config/evidence_recovery_prioritization.json",
    }
    references = basis.get("references")
    if not isinstance(references, list) or not required_refs <= set(references):
        raise ValueError("evidence basis is incomplete")
    if basis.get("completed_observation_reinterpreted_as_success") is not False:
        raise ValueError("completed Coffee observation cannot be reinterpreted as success")

    observation = _mapping(record.get("completed_observation"), "completed_observation")
    expected_observation = {
        "classification": "evidence_withheld",
        "technical_completion": True,
        "http_200_source_count": 2,
        "acquisition_attempts": 2,
        "transport_requests": 2,
        "retained_product_records": 0,
        "repeatability_available": False,
        "deep_audit_passed": False,
        "confirmed_visible_challenge": False,
    }
    if any(observation.get(key) != value for key, value in expected_observation.items()):
        raise ValueError("completed Coffee observation facts drifted")

    risks = _mapping(record.get("risk_classification"), "risk_classification")
    expected_risks = {
        "detector_false_positive_risk": "material-unresolved",
        "environment_access_risk": "unresolved-not-confirmed",
        "live_technique_failure": "not-evaluated",
        "evidence_retention_failure": "mechanism-repaired-product-gap-open",
    }
    if {key: _mapping(risks.get(key), key).get("status") for key in expected_risks} != expected_risks:
        raise ValueError("Coffee risk classes must remain distinct and exact")
    for key in expected_risks:
        _text(risks[key].get("explanation"), f"{key}.explanation")

    model = _mapping(record.get("scoring_model"), "scoring_model")
    if model.get("scale") != {
        "minimum": 0, "maximum": 5, "direction": "higher-is-better",
        "integer_scores_only": True,
    }:
        raise ValueError("score scale drifted")
    criteria = _list(model.get("criteria"), "scoring_model.criteria", length=5)
    weights = {item.get("criterion"): item.get("weight_percent") for item in criteria if isinstance(item, dict)}
    if weights != WEIGHTS or sum(weights.values()) != 100:
        raise ValueError("score weights must remain exact and total 100")
    if any(not item.get("rationale") for item in criteria):
        raise ValueError("every score criterion requires a rationale")

    options = _list(record.get("options"), "options", length=3)
    by_id: dict[str, dict[str, Any]] = {}
    for option in options:
        option = _mapping(option, "option")
        option_id = option.get("option_id")
        if option_id not in OPTION_IDS or option_id in by_id:
            raise ValueError("options must be exactly A, B, and C")
        scores = _mapping(option.get("scores"), "option.scores")
        if set(scores) != set(WEIGHTS) or any(
            not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5
            for value in scores.values()
        ):
            raise ValueError("option scores must be complete integers from 0 to 5")
        rationales = _mapping(option.get("score_rationale"), "option.score_rationale")
        if set(rationales) != set(WEIGHTS) or any(not str(value).strip() for value in rationales.values()):
            raise ValueError("option score rationales must cover every criterion")
        points = sum(scores[name] * weight for name, weight in WEIGHTS.items())
        if option.get("weighted_points") != points or option.get("normalized_score") != points / 100:
            raise ValueError("option score arithmetic is inconsistent")
        if option.get("execution_authorized") is not False:
            raise ValueError("no option may authorize its own execution")
        _text(option.get("description"), "option.description")
        by_id[option_id] = option
    if set(by_id) != OPTION_IDS:
        raise ValueError("options must be exactly A, B, and C")
    ranked = sorted(by_id.values(), key=lambda item: (-item["weighted_points"], item["option_id"]))
    if [item.get("rank") for item in ranked] != [1, 2, 3]:
        raise ValueError("option ranks must follow deterministic scores")

    recommendation = _mapping(record.get("recommendation"), "recommendation")
    if recommendation.get("recommended_option_id") != ranked[0]["option_id"] or ranked[0]["option_id"] != "A":
        raise ValueError("exactly the highest-scoring option A must be recommended")
    if recommendation.get("recommendation_count") != 1:
        raise ValueError("exactly one next action must be recommended")
    if recommendation.get("execution_authorized") is not False or recommendation.get("separate_prompt_required") is not True:
        raise ValueError("recommendation must remain separately queued and unauthorized")
    _text(recommendation.get("reason"), "recommendation.reason")

    envelope = _mapping(record.get("option_a_safe_envelope"), "option_a_safe_envelope")
    expected_limits = {
        "target_count": 2, "observations_per_source": 2,
        "maximum_acquisition_attempts": 4, "maximum_transport_requests": 12,
        "maximum_redirects_per_attempt": 2, "retries": 0, "pagination": 0,
        "maximum_response_bytes": 1000000, "timeout_seconds": 15,
    }
    if any(envelope.get("limits", {}).get(key) != value for key, value in expected_limits.items()):
        raise ValueError("option A request envelope drifted")
    if envelope.get("same_reviewed_urls_only") is not True or envelope.get("hardened_detector_required") is not True:
        raise ValueError("option A must use the same URLs and hardened detector")
    if envelope.get("cloud_default") is not True or envelope.get("browser_or_edge_escalation") is not False:
        raise ValueError("option A execution environment boundary drifted")
    if envelope.get("stop_after_first_unusable_observation_per_source") is not True:
        raise ValueError("option A must avoid a valueless repeat after an unusable first observation")

    outcomes = _mapping(envelope.get("outcome_contract"), "outcome_contract")
    if set(outcomes) != {"success", "withheld_evidence", "new_access_boundary", "technical_failure"}:
        raise ValueError("option A outcome contract is incomplete")
    if outcomes["success"].get("deep_audit_passed") is not True or outcomes["success"].get("retained_product_records") != 4:
        raise ValueError("success requires four attributable records and Deep Audit")
    if outcomes["withheld_evidence"].get("exit_classification") != 2:
        raise ValueError("withheld evidence must remain exit 2")
    if outcomes["new_access_boundary"].get("confirmed_by_hardened_evidence") is not True:
        raise ValueError("new access boundary requires hardened evidence")
    if outcomes["technical_failure"].get("exit_classification") != 1:
        raise ValueError("technical failure must remain exit 1")

    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("planning and authority boundaries drifted")
    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_coffee_recovery_next_step(record: dict[str, Any]) -> dict[str, Any]:
    return validate_coffee_recovery_next_step(record)
