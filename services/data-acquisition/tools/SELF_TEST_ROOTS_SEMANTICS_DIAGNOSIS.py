"""Deterministic tests for the planning-only Roots semantics diagnosis."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from roots_semantics_diagnosis import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    serialize_roots_semantics_diagnosis,
    validate_roots_semantics_diagnosis,
)


artifact = json.loads((ROOT / "config" / "roots_semantics_diagnosis.json").read_text(encoding="utf-8"))
live = json.loads(
    (ROOT.parents[1] / "docs" / "validation" / "coffee-hardened-rerun-2026-08-31.json")
    .read_text(encoding="utf-8")
)
roots_live = next(row for row in live["observations"] if row["source_id"] == "roots_coffee")
nana_live = [row for row in live["observations"] if row["source_id"] == "nana_coffee_roasters"]


def rejects(mutator, message: str) -> None:
    changed = deepcopy(artifact)
    mutator(changed)
    try:
        validate_roots_semantics_diagnosis(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# RSD1-RSD2: detached validation and planning boundaries are exact.
validated = validate_roots_semantics_diagnosis(artifact)
assert validated == artifact and validated is not artifact
assert serialize_roots_semantics_diagnosis(artifact) == artifact
assert artifact["boundaries"] == EXPECTED_BOUNDARIES
assert artifact["boundaries"]["live_request_count"] == 0

# RSD3-RSD7: Roots retained facts are copied exactly, without raw material.
retained = artifact["roots_retained_evidence"]
assert retained["http_status"] == roots_live["http_status"] == 200
assert retained["response_bytes"] == roots_live["sanitized_response"]["response_bytes"] == 90453
assert retained["response_sha256"] == roots_live["sanitized_response"]["response_sha256"]
assert retained["canonical_url_evidence"] == roots_live["sanitized_response"]["canonical_url_evidence"]
assert retained["normalization_failure_reason"] == roots_live["normalization_failure_reason"]
assert roots_live["record"] is None and roots_live["field_provenance"] == {}
assert retained["raw_html_retained"] is retained["headers_retained"] is False

# RSD8-RSD10: the exact strict failure is semantics; other missing-list gates
# can only be inferred as passed, and their values were not retained.
gates = artifact["strict_contract_gate_results"]
assert gates["failed_gate_count"] == 1
assert gates["coffee_product_semantics"]["result"] == "failed"
assert gates["coffee_product_semantics"]["classification"] == "parser_normalizer_limitation"
assert gates["product_name"]["result"] == gates["attributable_displayed_price"]["result"] == "inferred-pass-value-not-retained"
assert gates["retail_product_not_cafe_menu"]["result"] == "inferred-pass"

# RSD11-RSD14: current semantic witnesses and the ignored canonical-route
# witness remain distinct.
witnesses = {row["witness"]: row for row in artifact["semantic_witness_diagnosis"]}
assert witnesses["jsonld_product_type"]["current_result"] is False
assert witnesses["explicit_coffee_bean_or_roasted_coffee_text"]["current_result"] is False
assert witnesses["coffee_name_plus_labeled_attributes"]["current_result"] is False
assert witnesses["official_product_route_plus_coffee_slug"]["current_result"] == "available-but-not-evaluated"
assert retained["canonical_url_evidence"].endswith("/products/house-blend-coffee")

# RSD15-RSD19: Nana is a successful contract-shape comparator, not forced
# source equivalence.
comparator = artifact["nana_comparator"]
assert len(nana_live) == comparator["retained_record_count"] == 2
assert all(row["record"]["coffee_product_id"] == comparator["coffee_product_id"] for row in nana_live)
assert [row["record"]["price"] for row in nana_live] == comparator["price_values"]
assert all(len(row["field_provenance"]) == comparator["field_provenance_count_per_record"] for row in nana_live)
assert comparator["identity_repeatability_pct"] == comparator["canonical_repeatability_pct"] == 100.0
assert comparator["roots_required_to_use_nana_structure"] is False

# RSD20-RSD22: the offline Roots fixture is useful for future tests but is not
# the retained live response and cannot reconstruct the historical record.
fixture_bytes = (ROOT / "fixtures" / "coffee_evidence_recovery" / "roots_product.html").read_bytes()
assert hashlib.sha256(fixture_bytes).hexdigest() != retained["response_sha256"]
assert artifact["evidence_basis"]["offline_fixture_treated_as_live_response"] is False
decision = artifact["correction_decision"]
assert decision["historical_roots_record_can_be_reconstructed"] is False
assert decision["historical_result_remains"] == live["classification"] == "evidence_withheld"

# RSD23-RSD25: the proposed matcher addition is narrow and keeps every strict
# downstream gate.
assert decision["deterministic_parser_correction_justified"] is True
assert decision["live_request_required_to_implement_or_test"] is False
correction = decision["smallest_semantic_correction"]
assert correction["generic_product_route_alone_is_sufficient"] is False
assert correction["target_configuration_alone_is_sufficient"] is False
assert {"field_level_provenance", "repeatability", "deep_audit"} <= set(correction["unchanged_required_gates"])

# RSD26-RSD27: future withheld diagnostics stay sanitized and replayable.
retention = decision["independent_retention_hardening"]
assert {"product_name", "displayed_price", "canonical_url", "semantic_witnesses"} <= set(retention["required_fields"])
assert retention["raw_html_required"] is retention["headers_or_session_material_required"] is False

# RSD28: all six offline fixtures/tests are specified in deterministic order.
assert [row["id"] for row in artifact["required_offline_tests_and_fixtures"]] == [
    "RSD-F01", "RSD-F02", "RSD-F03", "RSD-F04", "RSD-F05", "RSD-F06",
]

# RSD29: no request, promotion, or automatic follow-on is authorized.
next_step = artifact["next_step"]
assert next_step["separate_prompt_required"] is True
assert next_step["live_request_authorized"] is next_step["candidate_promotion_authorized"] is False

# RSD30: retained facts, authority, historical outcome, and safe matcher bounds
# all fail closed under drift.
rejects(lambda row: row["roots_retained_evidence"].update(http_status=201), "Roots status drift validated")
rejects(lambda row: row["strict_contract_gate_results"].update(failed_gate_count=0), "failure count drift validated")
rejects(lambda row: row["correction_decision"].update(historical_roots_record_can_be_reconstructed=True), "historical reconstruction validated")
rejects(lambda row: row["correction_decision"]["smallest_semantic_correction"].update(generic_product_route_alone_is_sufficient=True), "generic route proof validated")
rejects(lambda row: row["next_step"].update(live_request_authorized=True), "live request authority validated")
rejects(lambda row: row["boundaries"].update(core_knowledge_write=True), "knowledge write validated")
rejects(lambda row: row.update(execute_request=True), "executable request field validated")

print("Roots semantics diagnosis deterministic tests passed (RSD1-RSD30).")
