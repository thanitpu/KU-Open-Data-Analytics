"""Pure validation for the non-authorizing Coffee evidence consolidation."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


SCHEMA = "ku2d.coffee-evidence-consolidation.v1"
EXPECTED_BOUNDARIES = {
    "consolidation_only": True,
    "live_request_count": 0,
    "historical_result_reinterpreted": False,
    "candidate_promotion_count": 0,
    "learning_memory_write": False,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "human_confirmation_write": False,
    "ground_truth_write": False,
    "parked_ref_action_count": 0,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "survey_doe_sem_work": False,
}
FORBIDDEN_KEYS = {
    "request_command", "dispatch_request", "execute_request", "merge_pr",
    "promote_candidate", "write_learning_memory", "scheduler_command",
}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


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


def _authority_is_non_promoting(authority: Any) -> bool:
    expected = {
        "candidate_only": True,
        "reviewed_corpus_authorized": False,
        "core_knowledge_authorized": False,
        "human_confirmed": False,
        "ground_truth_asserted": False,
        "production_authorized": False,
    }
    return isinstance(authority, dict) and authority == expected


def validate_coffee_evidence_consolidation(record: dict[str, Any]) -> dict[str, Any]:
    """Validate exact source facts, gap dispositions, and authority boundaries."""
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    _walk_forbidden(record)
    parsed = datetime.fromisoformat(str(record.get("consolidated_at") or ""))
    if parsed.tzinfo is None:
        raise ValueError("consolidated_at must include a timezone")
    if record.get("authoritative_branch") != "codex/ku2d-coffee-evidence-consolidation-v1":
        raise ValueError("authoritative branch drifted")

    basis = _mapping(record.get("evidence_basis"), "evidence_basis")
    expected_results = {
        "KU2D-R-000023", "KU2D-R-000024", "KU2D-R-000025", "KU2D-R-000026",
        "KU2D-R-000027", "KU2D-R-000028", "KU2D-R-000030",
    }
    if set(basis.get("result_ids") or []) != expected_results:
        raise ValueError("Coffee result chain is incomplete")
    if not {"KU2D-V-000027", "KU2D-V-000028", "KU2D-V-000030"} <= set(basis.get("accepted_review_ids") or []):
        raise ValueError("accepted review chain is incomplete")
    if basis.get("repository_evidence_only") is not True or basis.get("external_request_count") != 0:
        raise ValueError("consolidation must use repository evidence only")
    if basis.get("historical_result_reinterpreted_as_success") is not False:
        raise ValueError("historical result cannot be reinterpreted")
    if basis.get("parked_branch_read_or_mutated") is not False:
        raise ValueError("parked refs must remain untouched")

    sources = record.get("source_dispositions")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ValueError("exactly two Coffee source dispositions are required")
    by_id = {item.get("source_id"): item for item in sources if isinstance(item, dict)}
    if set(by_id) != {"nana_coffee_roasters", "roots_coffee"}:
        raise ValueError("Coffee source inventory drifted")

    nana = by_id["nana_coffee_roasters"]
    nana_evidence = _mapping(nana.get("observed_durable_evidence"), "Nana observed evidence")
    exact_nana = {
        "http_status": 200,
        "attempt_count": 2,
        "retained_record_count": 2,
        "coffee_product_id": "nanacoffeeroasters.com:house-blend",
        "displayed_price_values": [470.0, 470.0],
        "currency": "THB",
        "availability_values": ["InStock", "InStock"],
        "canonical_url": "https://nanacoffeeroasters.com/products/house-blend",
        "field_level_provenance_passed": True,
        "identity_repeatability_pct": 100.0,
        "canonical_repeatability_pct": 100.0,
        "source_deep_audit_passed": True,
        "access_boundary": None,
    }
    if any(nana_evidence.get(key) != value for key, value in exact_nana.items()):
        raise ValueError("durable Nana evidence drifted")
    if nana.get("unresolved_gaps") != []:
        raise ValueError("Nana phase gap must be closed")
    if nana.get("further_live_evidence_currently_necessary") is not False:
        raise ValueError("Nana must not require another request for this phase")
    if nana.get("evidence_recovery_complete_for_phase") is not True:
        raise ValueError("Nana phase completion drifted")
    if not _authority_is_non_promoting(nana.get("authority")):
        raise ValueError("Nana authority was promoted")

    roots = by_id["roots_coffee"]
    roots_evidence = _mapping(roots.get("observed_durable_evidence"), "Roots observed evidence")
    exact_roots = {
        "historical_classification": "evidence_withheld",
        "historical_exit_classification": 2,
        "http_status": 200,
        "attempt_count": 1,
        "retained_record_count": 0,
        "canonical_url_evidence": "https://shop.rootsbkk.com/products/house-blend-coffee",
        "normalization_failure_reason": "normalized product withheld: coffee_product_semantics",
        "retained_field_provenance_count": 0,
        "source_deep_audit_passed": False,
        "identity_repeatability_pct": 0.0,
        "canonical_repeatability_pct": 0.0,
        "access_boundary": None,
        "historical_record_reconstructable": False,
    }
    if any(roots_evidence.get(key) != value for key, value in exact_roots.items()):
        raise ValueError("durable Roots evidence drifted")
    gaps = roots.get("unresolved_gaps")
    if not isinstance(gaps, list) or len(gaps) != 3:
        raise ValueError("Roots unresolved evidence gaps must remain explicit")
    if roots.get("parser_tooling_readiness") != "offline-correction-merged-live-validation-pending":
        raise ValueError("Roots tooling/evidence readiness was conflated")
    if roots.get("further_live_evidence_currently_necessary") is not True:
        raise ValueError("Roots evidence completion still needs a separate validation")
    if roots.get("evidence_recovery_complete_for_phase") is not False:
        raise ValueError("Roots cannot be marked recovery-complete")
    future = _mapping(roots.get("minimum_future_evidence_objective"), "Roots future objective")
    if future.get("same_reviewed_url_only") is not True or future.get("staged_stop_after_first_failure") is not True:
        raise ValueError("Roots minimum future objective is not bounded")
    if any(future.get(key) is not False for key in (
        "new_live_validation_authorized", "automatic_rerun_authorized", "production_or_scheduling_authorized",
    )):
        raise ValueError("Roots future objective cannot authorize execution")
    if not _authority_is_non_promoting(roots.get("authority")):
        raise ValueError("Roots authority was promoted")

    phase = _mapping(record.get("coffee_domain_phase_disposition"), "Coffee phase disposition")
    if phase.get("value") != "complete-with-open-gap":
        raise ValueError("Coffee phase disposition drifted")
    if phase.get("complete_source_ids") != ["nana_coffee_roasters"] or phase.get("open_gap_source_ids") != ["roots_coffee"]:
        raise ValueError("Coffee source-level phase mapping drifted")
    if phase.get("new_live_validation_authorized") is not False or phase.get("automatic_follow_on") is not False:
        raise ValueError("phase disposition cannot authorize follow-on work")
    if not {"KU2D-R-000027", "KU2D-R-000028", "KU2D-R-000030"} <= set(phase.get("exact_evidence_dependencies") or []):
        raise ValueError("phase evidence dependencies are incomplete")

    gap_rows = record.get("parked_pr39_gap_map")
    if not isinstance(gap_rows, list) or len(gap_rows) != 3:
        raise ValueError("PR #39 gap map must contain exactly three gaps")
    gap_status = {row.get("gap_id"): row.get("status") for row in gap_rows if isinstance(row, dict)}
    if gap_status != {
        "KU2D-ERP-GAP-39-01": "partially-closed",
        "KU2D-ERP-GAP-39-02": "closed-for-evidence-recovery-phase",
        "KU2D-ERP-GAP-39-03": "partially-closed",
    }:
        raise ValueError("PR #39 gap dispositions drifted")

    parked = _mapping(record.get("parked_pr39_disposition"), "parked PR #39 disposition")
    for field in ("parked_ref_mutated", "parked_pr_merge_or_close_authorized", "candidate_registry_mutated", "unique_parked_code_claimed_losslessly_integrated"):
        if parked.get(field) is not False:
            raise ValueError(f"unsafe parked disposition: {field}")
    next_step = _mapping(record.get("next_step"), "next_step")
    if next_step.get("separate_prompt_required") is not True or next_step.get("separate_live_authorization_required") is not True:
        raise ValueError("future Roots validation must remain separately governed")
    if next_step.get("candidate_promotion_authorized") is not False or next_step.get("knowledge_authority_mutation_authorized") is not False:
        raise ValueError("consolidation cannot authorize promotion")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("consolidation boundaries drifted")
    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_coffee_evidence_consolidation(record: dict[str, Any]) -> dict[str, Any]:
    return validate_coffee_evidence_consolidation(record)
