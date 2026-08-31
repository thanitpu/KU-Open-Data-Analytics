"""Deterministic tests for the KU2D Coffee recovery next-step decision."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from coffee_recovery_next_step import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    OPTION_IDS,
    WEIGHTS,
    serialize_coffee_recovery_next_step,
    validate_coffee_recovery_next_step,
)


artifact = json.loads(
    (ROOT / "config" / "coffee_recovery_next_step.json").read_text(encoding="utf-8")
)
live_result = json.loads(
    (ROOT.parents[1] / "docs" / "validation" / "coffee-evidence-recovery-2026-08-31.json")
    .read_text(encoding="utf-8")
)


def rejects(mutator, message: str) -> None:
    changed = deepcopy(artifact)
    mutator(changed)
    try:
        validate_coffee_recovery_next_step(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# CRN1: the artifact validates as a detached deterministic value.
validated = validate_coffee_recovery_next_step(artifact)
assert validated == artifact and validated is not artifact
assert serialize_coffee_recovery_next_step(artifact) == artifact

# CRN2: this checkpoint is planning-only and made no live request.
assert artifact["boundaries"] == EXPECTED_BOUNDARIES
assert artifact["boundaries"]["live_request_count"] == 0

# CRN3: exactly options A, B, and C are compared.
options = {item["option_id"]: item for item in artifact["options"]}
assert set(options) == OPTION_IDS and len(options) == 3

# CRN4: the five requested criteria have transparent weights totaling 100.
weights = {item["criterion"]: item["weight_percent"] for item in artifact["scoring_model"]["criteria"]}
assert weights == WEIGHTS and sum(weights.values()) == 100

# CRN5: score arithmetic is exact.
for option in options.values():
    points = sum(option["scores"][name] * weight for name, weight in WEIGHTS.items())
    assert option["weighted_points"] == points
    assert option["normalized_score"] == points / 100
rejects(lambda item: item["options"][0].update(weighted_points=999), "bad score arithmetic validated")

# CRN6: deterministic ranking is A, B, C.
assert [(item["option_id"], item["rank"]) for item in sorted(options.values(), key=lambda value: value["rank"])] == [
    ("A", 1), ("B", 2), ("C", 3)
]

# CRN7: exactly one action is recommended and it is A.
assert artifact["recommendation"]["recommended_option_id"] == "A"
assert artifact["recommendation"]["recommendation_count"] == 1
rejects(lambda item: item["recommendation"].update(recommended_option_id="B"), "non-winner recommended")

# CRN8: recommendation and every option remain unauthorized.
assert artifact["recommendation"]["execution_authorized"] is False
assert artifact["recommendation"]["separate_prompt_required"] is True
assert all(item["execution_authorized"] is False for item in options.values())

# CRN9: the completed live result remains exit-2 withheld evidence, not success.
completed = artifact["completed_observation"]
assert completed["classification"] == live_result["classification"] == "evidence_withheld"
assert completed["technical_completion"] is live_result["technical_completion"] is True
assert completed["retained_product_records"] == sum(
    source["retained_record_count"] for source in live_result["deep_audit"]["source_audits"]
) == 0
assert artifact["evidence_basis"]["completed_observation_reinterpreted_as_success"] is False

# CRN10: detector, environment, technique, and retention are separate risk classes.
risks = artifact["risk_classification"]
assert set(risks) == {
    "detector_false_positive_risk", "environment_access_risk",
    "live_technique_failure", "evidence_retention_failure",
}

# CRN11: the historical detector false positive remains plausible but unresolved.
assert risks["detector_false_positive_risk"]["status"] == "material-unresolved"
assert live_result["observations"][0]["access_boundary_evidence"]["confidence"] == "screening-only"

# CRN12: environment/access is not upgraded to a confirmed challenge.
assert risks["environment_access_risk"]["status"] == "unresolved-not-confirmed"
assert completed["confirmed_visible_challenge"] is False

# CRN13: the live extraction technique is not falsely called failed.
assert risks["live_technique_failure"]["status"] == "not-evaluated"
assert all(row["record"] is None for row in live_result["observations"])

# CRN14: diagnostic retention worked while product evidence remains absent.
assert risks["evidence_retention_failure"]["status"] == "mechanism-repaired-product-gap-open"
assert live_result["run_state"] == "complete"

# CRN15: option A uses only the same two reviewed public official URLs.
envelope = artifact["option_a_safe_envelope"]
assert envelope["same_reviewed_urls_only"] is True
assert envelope["target_urls"] == [
    "https://shop.rootsbkk.com/collections/frontpage/products/house-blend-coffee",
    "https://nanacoffeeroasters.com/products/house-blend",
]

# CRN16: the maximum remains four attempts, with no retry or pagination.
limits = envelope["limits"]
assert limits["maximum_acquisition_attempts"] == 4
assert limits["observations_per_source"] == 2
assert limits["retries"] == limits["pagination"] == 0

# CRN17: a valueless repeat is skipped after an unusable first observation.
assert envelope["stop_after_first_unusable_observation_per_source"] is True
assert any("second observation only" in step for step in envelope["sequence"])

# CRN18: success requires four attributable records and passed Deep Audit.
success = envelope["outcome_contract"]["success"]
assert success["exit_classification"] == 0
assert success["retained_product_records"] == 4
assert success["deep_audit_passed"] is True

# CRN19: completed but incomplete evidence remains exit 2.
withheld = envelope["outcome_contract"]["withheld_evidence"]
assert withheld["exit_classification"] == 2 and withheld["technical_completion"] is True

# CRN20: a new access boundary needs hardened evidence and stops escalation.
boundary = envelope["outcome_contract"]["new_access_boundary"]
assert boundary["exit_classification"] == 2
assert boundary["confirmed_by_hardened_evidence"] is True
assert "without browser" in boundary["action"]

# CRN21: runtime, transport, budget, or evidence-writing failure remains exit 1.
technical = envelope["outcome_contract"]["technical_failure"]
assert technical["exit_classification"] == 1 and technical["technical_completion"] is False

# CRN22: Q-Diving retains broader three-role value but cannot resolve Coffee.
assert options["B"]["scores"]["cross_source_reuse_value"] == 5
assert options["B"]["scores"]["coffee_gap_resolution"] == 0

# CRN23: stopping Coffee has no request cost but leaves the gap open.
assert options["C"]["scores"]["incremental_request_risk_efficiency"] == 5
assert options["C"]["scores"]["coffee_gap_resolution"] == 1

# CRN24: cloud stays default and environment escalation stays disabled.
assert envelope["cloud_default"] is True
assert envelope["browser_or_edge_escalation"] is False

# CRN25: authority, knowledge, production, and scheduler boundaries fail closed.
rejects(lambda item: item["boundaries"].update(rerun_execution_authorized=True), "rerun authority validated")
rejects(lambda item: item["boundaries"].update(core_knowledge_write=True), "knowledge write validated")
rejects(lambda item: item["boundaries"].update(production_authorized=True), "production authority validated")
rejects(lambda item: item["boundaries"].update(scheduler_action="scheduled"), "scheduler action validated")

# CRN26: executable or mutating fields are rejected anywhere.
rejects(lambda item: item.update(execute_rerun=True), "executable rerun field validated")
rejects(lambda item: item["recommendation"].update(promote_candidate=True), "promotion field validated")

# CRN27: score completeness, integer range, and option identity fail closed.
rejects(lambda item: item["options"][0]["scores"].pop("coffee_gap_resolution"), "incomplete scores validated")
rejects(lambda item: item["options"][0]["scores"].update(expected_evidence_gain=5.5), "fractional score validated")
rejects(lambda item: item["options"][0].update(option_id="B"), "duplicate option validated")

# CRN28: the completed observation cannot be rewritten as access success.
rejects(
    lambda item: item["completed_observation"].update(confirmed_visible_challenge=True),
    "unconfirmed challenge validated",
)

print("Coffee recovery next-step deterministic tests passed (CRN1-CRN28).")
