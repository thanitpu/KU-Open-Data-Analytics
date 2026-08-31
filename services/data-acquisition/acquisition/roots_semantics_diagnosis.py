"""Pure validation for the planning-only Roots semantics diagnosis."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from acquisition_learning_record import validate_safe_json_payload


SCHEMA = "ku2d.roots-semantics-diagnosis.v1"
CLASSIFICATIONS = {
    "missing_retained_evidence",
    "parser_normalizer_limitation",
    "overly_strict_contract",
    "genuinely_non_product_cafe_menu_ambiguity",
    "unresolved_from_retained_evidence",
}
EXPECTED_BOUNDARIES = {
    "planning_only": True,
    "live_request_count": 0,
    "parser_or_runtime_code_changed": False,
    "historical_result_reinterpreted": False,
    "candidate_promotion_count": 0,
    "learning_memory_write": False,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "human_confirmation_write": False,
    "ground_truth_write": False,
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


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
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


def validate_roots_semantics_diagnosis(record: dict[str, Any]) -> dict[str, Any]:
    """Validate exact retained facts, diagnosis, recommendation, and authority."""
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    _walk_forbidden(record)
    diagnosed_at = _text(record.get("diagnosed_at"), "diagnosed_at")
    parsed = datetime.fromisoformat(diagnosed_at)
    if parsed.tzinfo is None:
        raise ValueError("diagnosed_at must include a timezone")
    if record.get("authoritative_branch") != "codex/ku2d-roots-semantics-diagnosis-v1":
        raise ValueError("authoritative branch drifted")

    basis = _mapping(record.get("evidence_basis"), "evidence_basis")
    required_refs = {
        "KU2D-R-000027",
        "docs/validation/coffee-hardened-rerun-2026-08-31.json",
        "acquisition/coffee_evidence_recovery.py",
    }
    if not isinstance(basis.get("references"), list) or not required_refs <= set(basis["references"]):
        raise ValueError("evidence basis is incomplete")
    if basis.get("repository_evidence_only") is not True or basis.get("external_request_count") != 0:
        raise ValueError("diagnosis must use repository evidence only")
    if basis.get("historical_result_reinterpreted_as_success") is not False:
        raise ValueError("historical result cannot be reinterpreted")
    if basis.get("offline_fixture_treated_as_live_response") is not False:
        raise ValueError("offline fixtures cannot substitute for live evidence")

    roots = _mapping(record.get("roots_retained_evidence"), "roots_retained_evidence")
    exact_roots = {
        "http_status": 200,
        "transport_completed": True,
        "response_bytes": 90453,
        "response_sha256": "61690ed7c2e0f583d211d64531f0f07f9e866546b90e91df18390b0105243e47",
        "canonical_url_evidence": "https://shop.rootsbkk.com/products/house-blend-coffee",
        "retained_record": False,
        "retained_field_provenance_count": 0,
        "normalization_failure_reason": "normalized product withheld: coffee_product_semantics",
        "raw_html_retained": False,
        "headers_retained": False,
    }
    if any(roots.get(key) != expected for key, expected in exact_roots.items()):
        raise ValueError("retained Roots facts drifted")
    canonical = urlparse(roots["canonical_url_evidence"])
    if canonical.hostname != "shop.rootsbkk.com" or canonical.path != "/products/house-blend-coffee":
        raise ValueError("Roots canonical product-route evidence drifted")

    gates = _mapping(record.get("strict_contract_gate_results"), "strict_contract_gate_results")
    expected_gate_names = {
        "product_name", "attributable_displayed_price", "canonical_identity",
        "coffee_product_semantics", "retail_product_not_cafe_menu",
    }
    if gates.get("failed_gate_count") != 1 or expected_gate_names != (set(gates) - {"failed_gate_count"}):
        raise ValueError("strict gate inventory drifted")
    for name in expected_gate_names:
        gate = _mapping(gates[name], f"strict_contract_gate_results.{name}")
        if gate.get("classification") not in CLASSIFICATIONS:
            raise ValueError(f"{name} classification is invalid")
        _text(gate.get("basis"), f"{name}.basis")
    if gates["coffee_product_semantics"].get("result") != "failed":
        raise ValueError("coffee_product_semantics must remain the only failed gate")
    if gates["coffee_product_semantics"].get("classification") != "parser_normalizer_limitation":
        raise ValueError("the retained diagnosis must identify the matcher limitation")

    witnesses = record.get("semantic_witness_diagnosis")
    if not isinstance(witnesses, list) or len(witnesses) != 4:
        raise ValueError("semantic witness diagnosis must contain four entries")
    by_name = {item.get("witness"): item for item in witnesses if isinstance(item, dict)}
    expected_witnesses = {
        "jsonld_product_type", "explicit_coffee_bean_or_roasted_coffee_text",
        "coffee_name_plus_labeled_attributes", "official_product_route_plus_coffee_slug",
    }
    if set(by_name) != expected_witnesses:
        raise ValueError("semantic witness inventory drifted")
    if by_name["official_product_route_plus_coffee_slug"].get("current_result") != "available-but-not-evaluated":
        raise ValueError("retained canonical-route witness was lost")

    nana = _mapping(record.get("nana_comparator"), "nana_comparator")
    if nana.get("comparison_role") != "successful-contract-shape-not-source-equivalence":
        raise ValueError("Nana may not be treated as source equivalence")
    expected_nana = {
        "retained_record_count": 2,
        "coffee_product_id": "nanacoffeeroasters.com:house-blend",
        "price_values": [470.0, 470.0],
        "currency": "THB",
        "field_provenance_count_per_record": 13,
        "identity_repeatability_pct": 100.0,
        "canonical_repeatability_pct": 100.0,
        "source_audit_passed": True,
        "roots_required_to_use_nana_structure": False,
    }
    if any(nana.get(key) != expected for key, expected in expected_nana.items()):
        raise ValueError("Nana comparator facts drifted")

    decision = _mapping(record.get("correction_decision"), "correction_decision")
    if decision.get("deterministic_parser_correction_justified") is not True:
        raise ValueError("diagnosis must state whether an offline correction is justified")
    if decision.get("live_request_required_to_implement_or_test") is not False:
        raise ValueError("offline implementation and tests cannot require a live request")
    if decision.get("historical_roots_record_can_be_reconstructed") is not False:
        raise ValueError("missing retained values prevent historical reconstruction")
    if decision.get("historical_result_remains") != "evidence_withheld":
        raise ValueError("historical outcome drifted")
    correction = _mapping(decision.get("smallest_semantic_correction"), "smallest_semantic_correction")
    if correction.get("generic_product_route_alone_is_sufficient") is not False:
        raise ValueError("a generic product route cannot prove coffee semantics")
    if correction.get("target_configuration_alone_is_sufficient") is not False:
        raise ValueError("target configuration cannot prove product semantics")
    unchanged = correction.get("unchanged_required_gates")
    if not isinstance(unchanged, list) or not {
        "product_name", "attributable_displayed_price", "official_same_host_canonical",
        "non_menu_semantics", "field_level_provenance", "repeatability", "deep_audit",
    } <= set(unchanged):
        raise ValueError("the proposed correction weakens existing gates")

    fixtures = record.get("required_offline_tests_and_fixtures")
    if not isinstance(fixtures, list) or [item.get("id") for item in fixtures] != [
        "RSD-F01", "RSD-F02", "RSD-F03", "RSD-F04", "RSD-F05", "RSD-F06",
    ]:
        raise ValueError("offline fixture plan is incomplete")
    next_step = _mapping(record.get("next_step"), "next_step")
    if next_step.get("separate_prompt_required") is not True:
        raise ValueError("implementation must require a separate Prompt")
    if next_step.get("live_request_authorized") is not False or next_step.get("candidate_promotion_authorized") is not False:
        raise ValueError("diagnosis cannot authorize a request or promotion")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("planning boundaries drifted")
    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_roots_semantics_diagnosis(record: dict[str, Any]) -> dict[str, Any]:
    return validate_roots_semantics_diagnosis(record)
