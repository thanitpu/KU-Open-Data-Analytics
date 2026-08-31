"""Fail-closed validation for KU2D acquisition consolidation readiness artifacts."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


READINESS_SCHEMA = "ku2d.acquisition-consolidation-readiness.v1"
BATCH_TEMPLATE_SCHEMA = "ku2d.locked-source-batch-campaign-template.v1"
AUTHORITATIVE_BRANCH = "codex/ku2d-acquisition-consolidation-readiness-v1"
EXPECTED_EVIDENCE_IDS = {f"ACR-E{index:03d}" for index in range(1, 19)}
EXPECTED_PATTERN_IDS = {f"APL-{index:03d}" for index in range(1, 11)}
EXPECTED_FAILURE_IDS = {f"FBP-{index:03d}" for index in range(1, 16)}
EXPECTED_GAP_IDS = {f"KU2D-KG-{index:03d}" for index in range(1, 9)}
EXPECTED_TIER_NAMES = {
    "A": {"Lotus's", "Big C", "Makro", "Tops"},
    "B": {"Gourmet Market", "JIB"},
    "C": {
        "Watsons", "Lazada Thailand", "Shopee Thailand", "YouTube Q-Diving",
        "Nana Coffee Roasters", "Roots Coffee", "LINE SHOPPING", "Agoda",
        "Traveloka", "SSI Blog", "Scubadoo Koh Tao", "Aquamaster Thailand",
    },
}
EXPECTED_DISPOSITIONS = {
    "close_now_offline", "next_bounded_live_candidate", "defer",
    "human_adjudication", "obsolete/superseded", "monitor",
}
EXPECTED_BOUNDARIES = {
    "repository_only": True,
    "live_request_count": 0,
    "browser_or_edge_request_count": 0,
    "candidate_promotion_count": 0,
    "knowledge_authority_mutation_count": 0,
    "parked_ref_mutation_count": 0,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "survey_doe_sem_work": False,
    "main_or_integration_mutation": False,
}
REQUIRED_PATTERN_FIELDS = {
    "pattern_id", "name", "classification", "prerequisites", "evidence_threshold",
    "applicable_to", "not_applicable_to", "failure_modes", "provenance_requirements",
    "repeatability_expectation", "deep_audit_expectation", "known_examples",
    "transferability_confidence",
}
REQUIRED_FAILURE_FIELDS = {
    "pattern_id", "name", "minimum_evidence", "safe_stop", "forbidden_inference",
    "recovery_class", "examples",
}
FORBIDDEN_MUTATING_KEYS = {
    "dispatch_request", "execute_request", "request_command", "merge_pr",
    "promote_candidate", "write_core_knowledge", "scheduler_command",
}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{field} must be a JSON array" + (" with entries" if nonempty else ""))
    return value


def _unique_index(rows: Any, field: str, expected: set[str]) -> dict[str, dict[str, Any]]:
    values = _list(rows, field)
    if any(not isinstance(row, dict) for row in values):
        raise ValueError(f"{field} entries must be objects")
    indexed = {str(row.get(field)): row for row in values}
    if len(indexed) != len(values) or set(indexed) != expected:
        raise ValueError(f"{field} inventory drifted")
    return indexed


def _walk_forbidden(value: Any) -> None:
    if isinstance(value, dict):
        found = FORBIDDEN_MUTATING_KEYS & set(value)
        if found:
            raise ValueError(f"mutating/executable fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden(child)


def validate_acquisition_consolidation_readiness(record: dict[str, Any]) -> dict[str, Any]:
    """Validate evidence coverage, authority limits, patterns, backlog, and tiers."""
    if not isinstance(record, dict) or record.get("schema") != READINESS_SCHEMA:
        raise ValueError(f"schema must be {READINESS_SCHEMA}")
    _walk_forbidden(record)
    parsed = datetime.fromisoformat(str(record.get("generated_at") or ""))
    if parsed.tzinfo is None:
        raise ValueError("generated_at must include timezone")
    if record.get("authoritative_branch") != AUTHORITATIVE_BRANCH:
        raise ValueError("authoritative branch drifted")

    rule = _mapping(record.get("evidence_rule"), "evidence_rule")
    for flag in (
        "repository_evidence_only", "observation_is_not_interpretation",
        "code_theme_descriptor_interpretation_are_distinct", "technique_is_not_environment",
    ):
        if rule.get(flag) is not True:
            raise ValueError(f"evidence rule {flag} must be true")
    required_unknowns = {
        "candidate", "unresolved", "insufficient_evidence", "no_existing_code_fits",
        "novel_pattern_candidate",
    }
    if set(rule.get("insufficient_evidence_labels") or []) != required_unknowns:
        raise ValueError("insufficient-evidence taxonomy drifted")

    coffee = _mapping(record.get("coffee_baseline"), "coffee_baseline")
    if coffee.get("phase_disposition") != "complete-with-open-gap":
        raise ValueError("Coffee phase baseline drifted")
    if coffee.get("complete_sources") != ["Nana Coffee Roasters"]:
        raise ValueError("Nana completion baseline drifted")
    if coffee.get("open_gap_sources") != ["Roots Coffee"]:
        raise ValueError("Roots open gap was lost")
    if "candidate-only" not in str(coffee.get("nana_authority")):
        raise ValueError("Nana authority was promoted")

    evidence = _unique_index(record.get("cross_domain_evidence_map"), "evidence_id", EXPECTED_EVIDENCE_IDS)
    required_evidence_fields = {
        "source", "domain", "surface", "technique", "environment", "observed_evidence",
        "outcome", "limitations", "transferability", "confidence", "provenance",
    }
    for evidence_id, row in evidence.items():
        if not required_evidence_fields <= set(row):
            raise ValueError(f"{evidence_id} is missing common evidence fields")
        if not _list(row.get("provenance"), f"{evidence_id}.provenance"):
            raise ValueError(f"{evidence_id} lacks durable provenance")
    by_source = {row["source"]: row for row in evidence.values()}
    if by_source["JIB"]["outcome"] != "live-profile-validated-isolated-staging":
        raise ValueError("JIB isolated-staging scope drifted")
    if "Production approval is false" not in by_source["JIB"]["limitations"]:
        raise ValueError("JIB production boundary was lost")
    if by_source["Shopee Thailand"]["outcome"] != "paused-access-boundary":
        raise ValueError("Shopee pause drifted")
    if by_source["Roots Coffee"]["outcome"] != "evidence-withheld-open-gap":
        raise ValueError("Roots withheld result drifted")
    for source in ("LINE SHOPPING", "SSI Blog", "Scubadoo Koh Tao", "Aquamaster Thailand"):
        if "candidate-only" not in by_source[source]["outcome"]:
            raise ValueError(f"{source} candidate authority was promoted")

    library = _mapping(record.get("acquisition_pattern_library"), "acquisition_pattern_library")
    if library.get("schema") != "ku2d.acquisition-pattern-library.v1":
        raise ValueError("acquisition pattern schema drifted")
    patterns = _unique_index(library.get("patterns"), "pattern_id", EXPECTED_PATTERN_IDS)
    for pattern_id, row in patterns.items():
        if not REQUIRED_PATTERN_FIELDS <= set(row):
            raise ValueError(f"{pattern_id} is incomplete")
        for field in (
            "prerequisites", "applicable_to", "not_applicable_to", "failure_modes",
            "provenance_requirements", "known_examples",
        ):
            _list(row.get(field), f"{pattern_id}.{field}")
    if patterns["APL-010"]["classification"] != "environment-policy-not-technique":
        raise ValueError("environment was conflated with technique")

    failures = _mapping(record.get("failure_boundary_pattern_library"), "failure library")
    if failures.get("schema") != "ku2d.failure-boundary-pattern-library.v1":
        raise ValueError("failure pattern schema drifted")
    failure_rows = _unique_index(failures.get("patterns"), "pattern_id", EXPECTED_FAILURE_IDS)
    allowed_recovery = {"offline", "bounded-live", "environment-specific", "human-adjudicated"}
    for pattern_id, row in failure_rows.items():
        if not REQUIRED_FAILURE_FIELDS <= set(row):
            raise ValueError(f"{pattern_id} is incomplete")
        if row.get("recovery_class") not in allowed_recovery:
            raise ValueError(f"{pattern_id} recovery class is invalid")
        _list(row.get("examples"), f"{pattern_id}.examples")

    backlog = _mapping(record.get("recovery_backlog"), "recovery_backlog")
    items = _list(backlog.get("items"), "recovery_backlog.items")
    ids = [row.get("backlog_id") for row in items if isinstance(row, dict)]
    if len(ids) != len(items) or len(ids) != len(set(ids)) or not EXPECTED_GAP_IDS <= set(ids):
        raise ValueError("backlog does not reconcile KG001-KG008 exactly once")
    for row in items:
        if row.get("disposition") not in EXPECTED_DISPOSITIONS:
            raise ValueError("backlog disposition is invalid")
        if not isinstance(row.get("score"), int) or not 6 <= row["score"] <= 30:
            raise ValueError("backlog score must use six 1-5 dimensions")
        _list(row.get("evidence"), f"{row.get('backlog_id')}.evidence")

    readiness = _mapping(record.get("source_readiness"), "source_readiness")
    tiers = _mapping(readiness.get("tiers"), "source_readiness.tiers")
    if set(tiers) != {"A", "B", "C"}:
        raise ValueError("source tiers must be A/B/C")
    seen: set[str] = set()
    for tier, expected in EXPECTED_TIER_NAMES.items():
        actual = set(tiers.get(tier) or [])
        if actual != expected or seen & actual:
            raise ValueError(f"Tier {tier} membership drifted")
        seen |= actual
    if readiness.get("batch_planning_readiness") != "ready-for-separate-controlled-plan-not-execution":
        raise ValueError("batch planning readiness drifted")
    intake = _mapping(readiness.get("ku2a_one_way_intake"), "ku2a_one_way_intake")
    if intake.get("candidate_or_diagnostic_auto_intake") is not False:
        raise ValueError("candidate/diagnostic evidence cannot auto-enter KU2A")

    hardening = _mapping(record.get("hardening_sweep"), "hardening_sweep")
    if hardening.get("runtime_behavior_changes") != [] or hardening.get("semantic_broadening") is not False:
        raise ValueError("this campaign cannot broaden runtime semantics")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("readiness boundaries drifted")
    validate_safe_json_payload(record)
    return deepcopy(record)


def validate_locked_source_batch_template(record: dict[str, Any]) -> dict[str, Any]:
    """Validate the non-executable locked-source campaign manifest template."""
    if not isinstance(record, dict) or record.get("schema") != BATCH_TEMPLATE_SCHEMA:
        raise ValueError(f"schema must be {BATCH_TEMPLATE_SCHEMA}")
    _walk_forbidden(record)
    if record.get("template_only") is not True:
        raise ValueError("batch artifact must remain template-only")
    if record.get("campaign_status") != "not-configured-not-authorized-not-executable":
        raise ValueError("batch template was made executable")
    if record.get("campaign_id") is not None or record.get("reviewed_manifest_id") is not None:
        raise ValueError("batch template cannot claim a configured campaign")
    if record.get("sources") != []:
        raise ValueError("batch template cannot contain executable source entries")
    source = _mapping(record.get("source_template"), "source_template")
    technique = _mapping(source.get("technique_lock"), "technique_lock")
    environment = _mapping(source.get("environment_lock"), "environment_lock")
    if technique.get("automatic_switch_allowed") is not False:
        raise ValueError("automatic technique switching is forbidden")
    if environment.get("automatic_switch_allowed") is not False:
        raise ValueError("automatic environment switching is forbidden")
    if source.get("failure_behavior") != "Stop this source, write boundary/drift evidence, and continue only sources whose independent locks remain valid.":
        raise ValueError("locked-source stop behavior drifted")
    required_escalation_blocks = {
        "different extraction technique", "different execution environment", "browser or Edge fallback",
        "login or authentication", "CAPTCHA or challenge handling", "private API",
        "proxy or session reuse", "budget expansion", "production approval or scheduling",
    }
    if set(source.get("forbidden_automatic_escalation") or []) != required_escalation_blocks:
        raise ValueError("automatic escalation blocks are incomplete")
    recommendations = _mapping(record.get("readiness_recommendations"), "readiness_recommendations")
    if set(recommendations.get("eligible_for_first_manifest_after_separate_review") or []) != EXPECTED_TIER_NAMES["A"]:
        raise ValueError("Tier-A batch recommendation drifted")
    conditional = {row.get("source") for row in recommendations.get("conditional_only") or []}
    if conditional != EXPECTED_TIER_NAMES["B"]:
        raise ValueError("Tier-B conditional recommendation drifted")
    if set(recommendations.get("excluded_until_new_evidence_or_authority") or []) != EXPECTED_TIER_NAMES["C"]:
        raise ValueError("Tier-C exclusion drifted")
    expected_boundaries = {
        "manifest_template_only": True, "execution_enabled": False, "live_request_count": 0,
        "automatic_technique_switch": False, "automatic_environment_switch": False,
        "production_authorized": False, "production_store": False, "scheduler_action": None,
    }
    if _mapping(record.get("boundaries"), "boundaries") != expected_boundaries:
        raise ValueError("batch template boundaries drifted")
    validate_safe_json_payload(record)
    return deepcopy(record)

