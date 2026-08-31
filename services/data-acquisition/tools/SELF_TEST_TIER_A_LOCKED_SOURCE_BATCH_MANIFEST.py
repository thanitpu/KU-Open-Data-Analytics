"""Deterministic tests for Tier-A Locked-Source Batch Manifest v1."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from tier_a_locked_source_batch_manifest import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    EXPECTED_REQUEST_BUDGETS,
    EXPECTED_TECHNIQUES,
    SOURCE_NAMES,
    SOURCE_ORDER,
    method_lock_fingerprint,
    validate_tier_a_locked_source_batch_manifest,
)


manifest = json.loads((ROOT / "config" / "tier_a_locked_source_batch_manifest.json").read_text(encoding="utf-8"))
registry = json.loads((ROOT / "config" / "source_registry.json").read_text(encoding="utf-8"))
patterns = json.loads((ROOT / "config" / "supermarket_acquisition_patterns.json").read_text(encoding="utf-8"))
readiness = json.loads((ROOT / "config" / "acquisition_consolidation_readiness.json").read_text(encoding="utf-8"))


def rejects(mutator, message: str) -> None:
    changed = deepcopy(manifest)
    mutator(changed)
    try:
        validate_tier_a_locked_source_batch_manifest(changed)
        raise AssertionError(message)
    except ValueError:
        pass


def source(record: dict, source_id: str) -> dict:
    return next(row for row in record["source_manifests"] if row["source_id"] == source_id)


# TABM1-TABM8: artifact is deterministic, detached, non-executable, and Tier-A only.
validated = validate_tier_a_locked_source_batch_manifest(manifest)
assert validated == manifest and validated is not manifest
assert manifest["scope"]["exact_source_ids"] == SOURCE_ORDER
assert manifest["scope"]["exact_source_names"] == [SOURCE_NAMES[item] for item in SOURCE_ORDER]
assert manifest["scope"]["required_tracks"] == ["product_price", "discovery"]
assert manifest["scope"]["promotion_scheduled"] is False
assert manifest["scope"]["tier_b_or_c_inclusion"] is False
assert manifest["boundaries"] == EXPECTED_BOUNDARIES
assert manifest["boundaries"]["live_request_count"] == 0 and manifest["boundaries"]["executable"] is False

# TABM9-TABM16: merged readiness and registries reconcile the exact source inventory.
assert set(readiness["source_readiness"]["tiers"]["A"]) == set(SOURCE_NAMES.values())
assert set(readiness["source_readiness"]["tiers"]["B"]).isdisjoint(SOURCE_NAMES.values())
assert set(readiness["source_readiness"]["tiers"]["C"]).isdisjoint(SOURCE_NAMES.values())
registry_rows = {row["source_id"]: row for row in registry["sources"] if row["source_id"] in SOURCE_ORDER}
assert set(registry_rows) == set(SOURCE_ORDER)
assert all(registry_rows[item]["max_pages"] == 8 for item in SOURCE_ORDER)
assert all(registry_rows[item]["store_to_repository"] is False for item in SOURCE_ORDER)
pattern_rows = {row["source_id"]: row for row in patterns["validated_sources"] if row["source_id"] in SOURCE_ORDER}
assert list(pattern_rows) == SOURCE_ORDER and all(row["status"] == "approved" for row in pattern_rows.values())
assert all({"product_price", "discovery"} <= set(row["tracks"]) for row in pattern_rows.values())

# TABM17-TABM28: methods, profiles, environments, provenance, and tracks are locked.
sources = {row["source_id"]: row for row in manifest["source_manifests"]}
assert list(sources) == SOURCE_ORDER
assert all(row["readiness_tier"] == "A" for row in sources.values())
assert all(row["preflight_status"] == "ready_for_separately_authorized_live_batch" for row in sources.values())
assert all(row["method_lock"]["active_tracks"] == EXPECTED_TECHNIQUES[item] for item, row in sources.items())
assert all(row["method_lock_fingerprint"] == method_lock_fingerprint(row["method_lock"]) for row in sources.values())
assert all(row["method_lock"]["browser_mode"] == "disabled" for row in sources.values())
assert all(row["method_lock"]["auth_state"] == "public-no-auth" for row in sources.values())
assert all(row["method_lock"]["automatic_technique_switch"] is False for row in sources.values())
assert all(row["method_lock"]["automatic_environment_switch"] is False for row in sources.values())
assert all(row["method_lock"]["automatic_endpoint_rediscovery"] is False for row in sources.values())
assert all(row["execution_environment"]["value"] == "cloud-hosted-public-read-only" for row in sources.values())
assert all(any(surface["surface_role"] == "registry_root" for surface in row["surface_provenance"]) for row in sources.values())
assert {next(surface["value"] for surface in row["surface_provenance"] if surface["surface_role"] == "registry_root") for row in sources.values()} == {registry_rows[item]["url"] for item in SOURCE_ORDER}

# TABM29-TABM40: numeric values disclose origins and reconcile hard campaign ceilings.
envelope = manifest["campaign_envelope"]
assert envelope["source_order"]["value_origin"] == "proposal_not_observed"
assert envelope["global_primary_page_units"]["value_origin"] == "derived_from_merged_contract"
assert envelope["global_repeat_page_units"]["value_origin"] == "derived_from_merged_contract"
assert envelope["global_max_transport_requests"]["value"] == 264
assert envelope["global_primary_page_units"]["value"] == 32
assert envelope["global_repeat_page_units"]["value"] == 20
assert envelope["global_output_record_range"]["minimum"]["value"] == 20
assert envelope["global_output_record_range"]["target"]["value"] == 235
assert envelope["global_output_record_range"]["maximum"]["value"] == 968
assert envelope["total_wall_clock_target_minutes"]["value"] == 45
assert envelope["total_wall_clock_ceiling_minutes"]["value"] == 120
assert sum(row["budgets"]["max_transport_requests"]["value"] for row in sources.values()) == 264

# TABM41-TABM52: per-source work is bounded and quality/evidence gates fail closed.
assert {item: row["budgets"]["max_transport_requests"]["value"] for item, row in sources.items()} == EXPECTED_REQUEST_BUDGETS
assert all(row["budgets"]["primary_page_units"]["value"] == 8 for row in sources.values())
assert all(row["budgets"]["repeat_page_units"]["value"] == 5 for row in sources.values())
assert all(row["budgets"]["source_concurrency_cap"]["value"] == 1 for row in sources.values())
assert all(row["budgets"]["retry_count"]["value"] == 0 for row in sources.values())
assert all(row["expected_records"]["minimum"]["value"] == 5 for row in sources.values())
assert all(row["deep_audit"]["required"] is True for row in sources.values())
assert all(row["deep_audit"]["criteria"] and row["deep_audit"]["evidence"] for row in sources.values())
assert all(row["drift_checks"] and row["stop_conditions"] for row in sources.values())
assert all(set(row["exit_classification"]) == {"0", "1", "2"} for row in sources.values())
assert all(row["normalization_contract"]["required_identity_fields"] for row in sources.values())
assert all(row["normalization_contract"]["required_price_fields"] and row["normalization_contract"]["required_provenance_fields"] for row in sources.values())

# TABM53-TABM60: evidence-first, serial isolation, checkpointing, and authorization stay explicit.
assert envelope["evidence_write_before_next_request"] is True
assert envelope["scheduling_policy"] == "serial-fixed-order-no-work-stealing"
assert envelope["global_concurrency_cap"]["value"] == 1
assert envelope["checkpoint_resume"]["checkpoint_after_each_request"] is True
assert envelope["checkpoint_resume"]["resume_may_rediscover_or_switch"] is False
assert "source exit 1 or 2 stops that source only" in envelope["failure_isolation"]
assert manifest["preflight_summary"]["live_authorization_granted"] is False
assert manifest["preflight_summary"]["ready_source_ids"] == SOURCE_ORDER

# TABM61-TABM76: negative mutations cover every Prompt-mandated false-green path.
rejects(lambda row: row["source_manifests"].append({"source_id": "SRC-003"}), "Tier-B source leakage validated")
rejects(lambda row: row["scope"]["exact_source_ids"].append("SRC-018"), "Tier-C source leakage validated")
rejects(lambda row: source(row, "SRC-004")["method_lock"].update(active_tracks={"product_price": "rendered_browser"}), "method switch validated")
rejects(lambda row: source(row, "SRC-002")["method_lock"].update(automatic_technique_switch=True), "automatic technique switch validated")
rejects(lambda row: source(row, "SRC-005")["method_lock"].update(automatic_environment_switch=True), "automatic environment switch validated")
rejects(lambda row: source(row, "SRC-001")["method_lock"].update(automatic_endpoint_rediscovery=True), "endpoint rediscovery validated")
rejects(lambda row: source(row, "SRC-002")["budgets"]["max_transport_requests"].update(value=81), "source request overflow validated")
rejects(lambda row: row["campaign_envelope"]["global_max_transport_requests"].update(value=263), "global budget mismatch validated")
rejects(lambda row: source(row, "SRC-004").update(surface_provenance=[]), "missing provenance validated")
rejects(lambda row: source(row, "SRC-005").update(deep_audit={"required": False}), "missing audit validated")
rejects(lambda row: source(row, "SRC-001").update(drift_checks=[]), "missing drift rules validated")
rejects(lambda row: source(row, "SRC-002").update(stop_conditions=[]), "missing stop rules validated")
rejects(lambda row: source(row, "SRC-004")["surface_provenance"][0].update(value="https://unsupported.example/"), "unsupported exact URL validated")
rejects(lambda row: source(row, "SRC-005")["budgets"]["max_transport_requests"].update(value_origin="observed_merged_evidence", evidence=[]), "proposal represented as observed validated")
rejects(lambda row: row["campaign_envelope"].update(evidence_write_before_next_request=False), "evidence-after-request validated")
rejects(lambda row: row["boundaries"].update(executable=True), "executable manifest validated")

print("Tier-A Locked-Source Batch Manifest deterministic tests passed (TABM1-TABM76).")

