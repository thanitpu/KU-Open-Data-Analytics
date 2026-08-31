"""Deterministic tests for Acquisition Consolidation & Readiness v1."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from acquisition_consolidation_readiness import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    EXPECTED_EVIDENCE_IDS,
    EXPECTED_FAILURE_IDS,
    EXPECTED_GAP_IDS,
    EXPECTED_PATTERN_IDS,
    EXPECTED_TIER_NAMES,
    validate_acquisition_consolidation_readiness,
    validate_locked_source_batch_template,
)


artifact = json.loads((ROOT / "config" / "acquisition_consolidation_readiness.json").read_text(encoding="utf-8"))
template = json.loads((ROOT / "config" / "locked_source_batch_campaign_template.json").read_text(encoding="utf-8"))
supermarkets = json.loads((ROOT / "config" / "supermarket_acquisition_patterns.json").read_text(encoding="utf-8"))
retail_validations = json.loads((ROOT / "config" / "retail_domain_validations.json").read_text(encoding="utf-8"))
coffee = json.loads((ROOT / "config" / "coffee_evidence_consolidation.json").read_text(encoding="utf-8"))
gaps = json.loads((ROOT / "config" / "knowledge_gap_register.json").read_text(encoding="utf-8"))


def rejects_artifact(mutator, message: str) -> None:
    changed = deepcopy(artifact)
    mutator(changed)
    try:
        validate_acquisition_consolidation_readiness(changed)
        raise AssertionError(message)
    except ValueError:
        pass


def rejects_template(mutator, message: str) -> None:
    changed = deepcopy(template)
    mutator(changed)
    try:
        validate_locked_source_batch_template(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# ACR1-ACR5: both artifacts are detached, storage-neutral, and zero-request.
validated = validate_acquisition_consolidation_readiness(artifact)
assert validated == artifact and validated is not artifact
validated_template = validate_locked_source_batch_template(template)
assert validated_template == template and validated_template is not template
assert artifact["boundaries"] == EXPECTED_BOUNDARIES
assert artifact["boundaries"]["live_request_count"] == 0
assert template["boundaries"]["execution_enabled"] is False
assert template["sources"] == []

# ACR6-ACR10: Coffee phase closure is copied exactly without authority promotion.
assert artifact["coffee_baseline"]["phase_disposition"] == coffee["coffee_domain_phase_disposition"]["value"]
assert artifact["coffee_baseline"]["complete_sources"] == ["Nana Coffee Roasters"]
assert artifact["coffee_baseline"]["open_gap_sources"] == ["Roots Coffee"]
assert "candidate-only" in artifact["coffee_baseline"]["nana_authority"]
assert coffee["boundaries"]["candidate_promotion_count"] == 0

# ACR11-ACR17: common evidence map is complete, cited, and preserves exact high-risk outcomes.
evidence = {row["evidence_id"]: row for row in artifact["cross_domain_evidence_map"]}
assert set(evidence) == EXPECTED_EVIDENCE_IDS and len(evidence) == 18
by_source = {row["source"]: row for row in evidence.values()}
assert {row["business"] for row in supermarkets["validated_sources"]} <= set(by_source)
assert by_source["JIB"]["outcome"] == "live-profile-validated-isolated-staging"
assert "Production approval is false" in by_source["JIB"]["limitations"]
assert by_source["Shopee Thailand"]["outcome"] == "paused-access-boundary"
assert by_source["Roots Coffee"]["outcome"] == "evidence-withheld-open-gap"
assert all(row["provenance"] for row in evidence.values())
for row in evidence.values():
    for reference in row["provenance"]:
        path = reference.split("#", 1)[0]
        assert (ROOT / path).resolve().is_file(), f"missing evidence file: {path}"

# ACR18-ACR24: all required reusable techniques are explicit and environment remains separate.
patterns = {row["pattern_id"]: row for row in artifact["acquisition_pattern_library"]["patterns"]}
assert set(patterns) == EXPECTED_PATTERN_IDS and len(patterns) == 10
names = {row["name"] for row in patterns.values()}
for required in (
    "Sitemap to Canonical Detail Discovery", "Structured or SSR Product Detail Catalog",
    "Rendered Product Detail or Listing", "First-party App-Bundle Discovery",
    "Official API Metadata Acquisition", "Source-detail Normalization",
    "Search-versus-detail Price Comparison", "Official Campaign Surface",
):
    assert required in names
assert patterns["APL-010"]["classification"] == "environment-policy-not-technique"
assert patterns["APL-005"]["transferability_confidence"] == "medium-single-source"
assert "Lazada unresolved comparison" in patterns["APL-008"]["known_examples"]
assert all(row["provenance_requirements"] and row["deep_audit_expectation"] for row in patterns.values())

# ACR25-ACR31: failure taxonomy has safe stops and never conflates access, extraction, or demand.
failures = {row["pattern_id"]: row for row in artifact["failure_boundary_pattern_library"]["patterns"]}
assert set(failures) == EXPECTED_FAILURE_IDS and len(failures) == 15
failure_names = {row["name"] for row in failures.values()}
assert "Blocked access is not extraction failure" in failure_names
assert "Displayed order is not demand" in failure_names
assert "Product versus variant ambiguity" in failure_names
assert "Price-role ambiguity" in failure_names
assert "Request retention or diagnostic gap" in failure_names
assert "Wrong host or canonical ambiguity" in failure_names
assert all(row["minimum_evidence"] and row["safe_stop"] and row["forbidden_inference"] for row in failures.values())

# ACR32-ACR38: backlog reconciles KG001-KG008, later gaps, and transparent dispositions.
backlog = artifact["recovery_backlog"]["items"]
backlog_ids = [row["backlog_id"] for row in backlog]
assert EXPECTED_GAP_IDS <= set(backlog_ids)
assert set(row["gap_id"] for row in gaps["gaps"]) == EXPECTED_GAP_IDS
assert len(backlog_ids) == len(set(backlog_ids)) == 11
dispositions = Counter(row["disposition"] for row in backlog)
assert dispositions == Counter({"close_now_offline": 4, "next_bounded_live_candidate": 4, "human_adjudication": 2, "monitor": 1})
assert next(row for row in backlog if row["backlog_id"] == "ACR-GAP-ROOTS")["disposition"] == "next_bounded_live_candidate"
assert next(row for row in backlog if row["backlog_id"] == "KU2D-KG-007")["disposition"] == "human_adjudication"
assert all(6 <= row["score"] <= 30 for row in backlog)

# ACR39-ACR45: source tiers are conservative and cross-checked against durable registries.
tiers = artifact["source_readiness"]["tiers"]
assert {tier: set(names) for tier, names in tiers.items()} == EXPECTED_TIER_NAMES
assert [len(tiers[key]) for key in ("A", "B", "C")] == [4, 2, 12]
assert {"Lotus's", "Big C", "Makro", "Tops"} <= {row["business"] for row in supermarkets["validated_sources"]}
assert "Gourmet Market" in tiers["B"]
jib = retail_validations["domains"]["it_retail"]["live_validated_sources"][0]
assert jib["production_approved"] is False and "JIB" in tiers["B"]
assert {"Watsons", "Shopee Thailand", "Roots Coffee", "Nana Coffee Roasters"} <= set(tiers["C"])
assert artifact["source_readiness"]["batch_planning_readiness"] == "ready-for-separate-controlled-plan-not-execution"
assert artifact["source_readiness"]["ku2a_one_way_intake"]["candidate_or_diagnostic_auto_intake"] is False

# ACR46-ACR52: batch template locks technique/environment, budgets, stops, and exits.
source_template = template["source_template"]
assert source_template["technique_lock"]["automatic_switch_allowed"] is False
assert source_template["environment_lock"]["automatic_switch_allowed"] is False
assert set(source_template["exit_classification"]) == {"0", "1", "2"}
assert "locked technique fails" in source_template["stop_conditions"]
assert "browser or Edge fallback" in source_template["forbidden_automatic_escalation"]
assert "production approval or scheduling" in source_template["forbidden_automatic_escalation"]
assert set(template["readiness_recommendations"]["eligible_for_first_manifest_after_separate_review"]) == EXPECTED_TIER_NAMES["A"]

# ACR53-ACR64: fail-closed mutations prevent false readiness and unsafe execution.
rejects_artifact(lambda row: row["coffee_baseline"].update(phase_disposition="complete"), "false Coffee closure validated")
rejects_artifact(lambda row: row["cross_domain_evidence_map"].pop(), "missing evidence row validated")
rejects_artifact(lambda row: row["cross_domain_evidence_map"][5].update(outcome="production-approved"), "JIB promotion validated")
rejects_artifact(lambda row: row["acquisition_pattern_library"]["patterns"].pop(), "missing pattern validated")
rejects_artifact(lambda row: row["acquisition_pattern_library"]["patterns"][9].update(classification="technique"), "environment/technique conflation validated")
rejects_artifact(lambda row: row["failure_boundary_pattern_library"]["patterns"].pop(), "missing failure pattern validated")
rejects_artifact(lambda row: row["recovery_backlog"]["items"][0].update(disposition="execute_now"), "executable backlog disposition validated")
rejects_artifact(lambda row: row["source_readiness"]["tiers"]["A"].append("Nana Coffee Roasters"), "candidate Tier A validated")
rejects_artifact(lambda row: row["boundaries"].update(live_request_count=1), "live request validated")
rejects_artifact(lambda row: row.update(execute_request=True), "executable request field validated")
rejects_template(lambda row: row["source_template"]["technique_lock"].update(automatic_switch_allowed=True), "automatic technique switch validated")
rejects_template(lambda row: row["boundaries"].update(execution_enabled=True), "executable template validated")

print("Acquisition Consolidation & Readiness deterministic tests passed (ACR1-ACR64).")

