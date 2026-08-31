"""Deterministic tests for Coffee evidence consolidation v1."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from coffee_evidence_consolidation import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    serialize_coffee_evidence_consolidation,
    validate_coffee_evidence_consolidation,
)


artifact = json.loads((ROOT / "config" / "coffee_evidence_consolidation.json").read_text(encoding="utf-8"))
live = json.loads(
    (ROOT.parents[1] / "docs" / "validation" / "coffee-hardened-rerun-2026-08-31.json")
    .read_text(encoding="utf-8")
)
registry = json.loads((ROOT / "config" / "candidate_learning_evidence_registry.json").read_text(encoding="utf-8"))
parked = json.loads((ROOT / "config" / "parked_candidate_review.json").read_text(encoding="utf-8"))


def rejects(mutator, message: str) -> None:
    changed = deepcopy(artifact)
    mutator(changed)
    try:
        validate_coffee_evidence_consolidation(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# CEC1-CEC4: detached validation, exact evidence chain, and zero-request
# consolidation boundaries are stable.
validated = validate_coffee_evidence_consolidation(artifact)
assert validated == artifact and validated is not artifact
assert serialize_coffee_evidence_consolidation(artifact) == artifact
assert artifact["boundaries"] == EXPECTED_BOUNDARIES
assert artifact["evidence_basis"]["external_request_count"] == 0
assert artifact["evidence_basis"]["historical_result_reinterpreted_as_success"] is False

# CEC5-CEC12: Nana is copied exactly from durable retained records and is
# recovery-complete for this phase without authority promotion.
sources = {row["source_id"]: row for row in artifact["source_dispositions"]}
nana = sources["nana_coffee_roasters"]
nana_live = [row for row in live["observations"] if row["source_id"] == "nana_coffee_roasters"]
assert len(nana_live) == nana["observed_durable_evidence"]["retained_record_count"] == 2
assert [row["record"]["price"] for row in nana_live] == nana["observed_durable_evidence"]["displayed_price_values"] == [470.0, 470.0]
assert all(row["record"]["coffee_product_id"] == "nanacoffeeroasters.com:house-blend" for row in nana_live)
assert all(row["record"]["availability"] == "InStock" for row in nana_live)
assert all(len(row["field_provenance"]) == 13 for row in nana_live)
assert nana["observed_durable_evidence"]["identity_repeatability_pct"] == 100.0
assert nana["observed_durable_evidence"]["canonical_repeatability_pct"] == 100.0
assert nana["observed_durable_evidence"]["source_deep_audit_passed"] is True
assert nana["further_live_evidence_currently_necessary"] is False
assert nana["evidence_recovery_complete_for_phase"] is True
assert nana["authority"]["candidate_only"] is True
assert not any(value for key, value in nana["authority"].items() if key != "candidate_only")

# CEC13-CEC20: Roots remains the exact historical exit-2 result; merged
# offline tooling is readiness, not live evidence or retrospective success.
roots = sources["roots_coffee"]
roots_live = next(row for row in live["observations"] if row["source_id"] == "roots_coffee")
roots_evidence = roots["observed_durable_evidence"]
assert live["classification"] == roots_evidence["historical_classification"] == "evidence_withheld"
assert roots_evidence["historical_exit_classification"] == 2
assert roots_live["http_status"] == roots_evidence["http_status"] == 200
assert roots_live["record"] is None and roots_evidence["retained_record_count"] == 0
assert roots_live["field_provenance"] == {} and roots_evidence["retained_field_provenance_count"] == 0
assert roots_live["normalization_failure_reason"] == roots_evidence["normalization_failure_reason"]
assert roots_evidence["historical_record_reconstructable"] is False
assert roots["candidate_evidence_quality"]["offline_fixture_or_tooling_treated_as_live_evidence"] is False
assert roots["parser_tooling_readiness"] == "offline-correction-merged-live-validation-pending"
assert roots["further_live_evidence_currently_necessary"] is True
assert roots["evidence_recovery_complete_for_phase"] is False

# CEC21-CEC25: the minimum future objective is staged and descriptive only.
future = roots["minimum_future_evidence_objective"]
assert future["same_reviewed_url_only"] is True
assert future["staged_stop_after_first_failure"] is True
assert future["new_live_validation_authorized"] is False
assert future["automatic_rerun_authorized"] is False
assert future["production_or_scheduling_authorized"] is False

# CEC26-CEC29: Coffee is complete-with-open-gap and the exact source split is
# explicit rather than inferred from aggregate record count.
phase = artifact["coffee_domain_phase_disposition"]
assert phase["value"] == "complete-with-open-gap"
assert phase["complete_source_ids"] == ["nana_coffee_roasters"]
assert phase["open_gap_source_ids"] == ["roots_coffee"]
assert phase["new_live_validation_authorized"] is phase["automatic_follow_on"] is False

# CEC30-CEC34: the three parked PR #39 gaps are reconciled without changing
# the parked branch or stale candidate-only authority records.
gaps = {row["gap_id"]: row for row in artifact["parked_pr39_gap_map"]}
assert gaps["KU2D-ERP-GAP-39-01"]["status"] == "partially-closed"
assert gaps["KU2D-ERP-GAP-39-02"]["status"] == "closed-for-evidence-recovery-phase"
assert gaps["KU2D-ERP-GAP-39-03"]["status"] == "partially-closed"
assert gaps["KU2D-ERP-GAP-39-02"]["open_evidence"] == []
parked_disposition = artifact["parked_pr39_disposition"]
assert parked_disposition["parked_ref_mutated"] is False
assert parked_disposition["candidate_registry_mutated"] is False
assert parked_disposition["unique_parked_code_claimed_losslessly_integrated"] is False
candidate_ids = {row["candidate_id"] for row in registry["candidates"]}
assert {"KU2D-CLE-000006", "KU2D-CLE-000007"} <= candidate_ids
surface = next(row for row in parked["parked_surfaces"] if row["surface_id"] == "KU2D-PC-PR39")
assert surface["head_sha"] == "441c71d678a30cc62b742ea58f23f629a9d1e2d6"

# CEC35-CEC40: authority and fail-closed disposition rules reject drift.
rejects(lambda row: row["source_dispositions"][0].update(further_live_evidence_currently_necessary=True), "Nana rerun requirement validated")
rejects(lambda row: row["source_dispositions"][1]["observed_durable_evidence"].update(retained_record_count=1), "historical Roots record validated")
rejects(lambda row: row["coffee_domain_phase_disposition"].update(value="complete"), "false complete phase validated")
rejects(lambda row: row["parked_pr39_gap_map"][0].update(status="closed-for-evidence-recovery-phase"), "Roots gap closure validated")
rejects(lambda row: row["next_step"].update(candidate_promotion_authorized=True), "candidate promotion validated")
rejects(lambda row: row["boundaries"].update(live_request_count=1), "live request validated")
rejects(lambda row: row.update(execute_request=True), "executable request field validated")

print("Coffee evidence consolidation deterministic tests passed (CEC1-CEC40).")
