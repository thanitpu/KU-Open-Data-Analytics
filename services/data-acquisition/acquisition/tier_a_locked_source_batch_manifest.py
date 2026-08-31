"""Fail-closed validation for the planning-only Tier-A locked-source manifest."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


SCHEMA = "ku2d.tier-a-locked-source-batch-manifest.v1"
AUTHORITATIVE_BRANCH = "codex/ku2d-tier-a-locked-source-batch-manifest-v1"
SOURCE_ORDER = ["SRC-002", "SRC-004", "SRC-005", "SRC-001"]
SOURCE_NAMES = {
    "SRC-002": "Lotus's", "SRC-004": "Big C", "SRC-005": "Makro", "SRC-001": "Tops",
}
EXPECTED_TECHNIQUES = {
    "SRC-002": {"product_price": "lotus_catalog_api", "discovery": "lotus_catalog_api"},
    "SRC-004": {"product_price": "bigc_product_catalog", "discovery": "generic_sitemap"},
    "SRC-005": {"product_price": "makro_pro_catalog", "discovery": "makro_pro_catalog"},
    "SRC-001": {"product_price": "tops_product_catalog", "discovery": "generic_sitemap"},
}
EXPECTED_REQUEST_BUDGETS = {"SRC-002": 80, "SRC-004": 80, "SRC-005": 24, "SRC-001": 80}
EXACT_URL_ALLOWLIST = {
    "https://www.lotuss.com/th", "https://www.bigc.co.th/",
    "https://www.makro.co.th/th/index", "https://www.makro.pro/th/c/search",
    "https://www.tops.co.th/th",
}
VALUE_ORIGINS = {
    "observed_merged_evidence", "derived_from_merged_contract", "proposal_not_observed",
}
EXPECTED_BOUNDARIES = {
    "manifest_only": True, "executable": False, "live_request_count": 0,
    "browser_or_edge_request_count": 0, "tier_b_or_c_source_count": 0,
    "automatic_technique_switch": False, "automatic_environment_switch": False,
    "automatic_endpoint_rediscovery": False, "candidate_promotion_count": 0,
    "knowledge_authority_mutation_count": 0, "parked_ref_mutation_count": 0,
    "production_authorized": False, "production_store": False, "scheduler_action": None,
    "ml_training_or_inference": False, "survey_doe_sem_work": False,
}
FORBIDDEN_EXECUTABLE_KEYS = {
    "command", "request_command", "execute", "dispatch", "workflow_dispatch",
    "write_production", "merge_pr", "promote_candidate", "scheduler_command",
}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        suffix = " with entries" if nonempty else ""
        raise ValueError(f"{field} must be a JSON array{suffix}")
    return value


def _walk_forbidden(value: Any) -> None:
    if isinstance(value, dict):
        found = FORBIDDEN_EXECUTABLE_KEYS & set(value)
        if found:
            raise ValueError(f"executable fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden(child)


def _validate_value(value: Any, field: str) -> None:
    """Require every numeric/planning wrapper to disclose its evidence origin."""
    row = _mapping(value, field)
    origin = row.get("value_origin")
    if origin not in VALUE_ORIGINS:
        raise ValueError(f"{field} has unsupported or missing value_origin")
    if "value" not in row:
        raise ValueError(f"{field} lacks value")
    if origin == "observed_merged_evidence" and not _list(row.get("evidence"), f"{field}.evidence"):
        raise ValueError(f"{field} observed value lacks merged evidence")
    if origin == "derived_from_merged_contract":
        if not str(row.get("derivation") or "").strip():
            raise ValueError(f"{field} derived value lacks derivation")
        _list(row.get("evidence"), f"{field}.evidence")
    if origin == "proposal_not_observed" and not str(row.get("rationale") or "").strip():
        raise ValueError(f"{field} proposal lacks rationale")


def method_lock_fingerprint(method_lock: dict[str, Any]) -> str:
    payload = json.dumps(method_lock, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_tier_a_locked_source_batch_manifest(record: dict[str, Any]) -> dict[str, Any]:
    """Validate the manifest without executing, authorizing, or discovering anything."""
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    _walk_forbidden(record)
    if record.get("status") != "preflight-only-not-authorized-not-executable":
        raise ValueError("manifest status must remain non-authorized and non-executable")
    if record.get("authoritative_branch") != AUTHORITATIVE_BRANCH:
        raise ValueError("authoritative branch drifted")
    prepared = datetime.fromisoformat(str(record.get("prepared_at") or ""))
    if prepared.tzinfo is None:
        raise ValueError("prepared_at must include timezone")

    scope = _mapping(record.get("scope"), "scope")
    if scope.get("readiness_tier") != "A":
        raise ValueError("only readiness Tier A is allowed")
    if scope.get("exact_source_ids") != SOURCE_ORDER:
        raise ValueError("Tier-A source order or membership drifted")
    if scope.get("exact_source_names") != [SOURCE_NAMES[source] for source in SOURCE_ORDER]:
        raise ValueError("Tier-A source names drifted")
    if scope.get("required_tracks") != ["product_price", "discovery"]:
        raise ValueError("required tracks drifted")
    if scope.get("promotion_scheduled") is not False or scope.get("tier_b_or_c_inclusion") is not False:
        raise ValueError("promotion scheduling or Tier B/C inclusion is forbidden")
    _list(scope.get("evidence_basis"), "scope.evidence_basis")

    origin_contract = _mapping(record.get("value_origin_contract"), "value_origin_contract")
    if set(origin_contract.get("allowed") or []) != VALUE_ORIGINS:
        raise ValueError("value-origin taxonomy drifted")
    for origin in VALUE_ORIGINS:
        if not str(origin_contract.get(origin) or "").strip():
            raise ValueError(f"value-origin definition missing: {origin}")

    envelope = _mapping(record.get("campaign_envelope"), "campaign_envelope")
    _validate_value(envelope.get("source_order"), "campaign_envelope.source_order")
    if envelope["source_order"]["value"] != SOURCE_ORDER:
        raise ValueError("campaign source order drifted")
    if envelope.get("scheduling_policy") != "serial-fixed-order-no-work-stealing":
        raise ValueError("scheduling policy must remain deterministic and serial")
    for key in (
        "global_max_transport_requests", "global_primary_page_units",
        "global_repeat_page_units", "total_wall_clock_target_minutes",
        "total_wall_clock_ceiling_minutes", "global_concurrency_cap",
    ):
        _validate_value(envelope.get(key), f"campaign_envelope.{key}")
        value = envelope[key]["value"]
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"campaign_envelope.{key} must be a finite positive integer")
    output_range = _mapping(envelope.get("global_output_record_range"), "global_output_record_range")
    for label in ("minimum", "target", "maximum"):
        _validate_value(output_range.get(label), f"global_output_record_range.{label}")
    if not 0 < output_range["minimum"]["value"] <= output_range["target"]["value"] <= output_range["maximum"]["value"]:
        raise ValueError("global output range is inconsistent")
    if envelope["global_primary_page_units"]["value"] != 32 or envelope["global_repeat_page_units"]["value"] != 20:
        raise ValueError("campaign page-unit derivation drifted")
    if envelope["global_concurrency_cap"]["value"] != 1:
        raise ValueError("campaign concurrency must remain one")
    if envelope["total_wall_clock_target_minutes"]["value"] > envelope["total_wall_clock_ceiling_minutes"]["value"]:
        raise ValueError("wall-clock target exceeds ceiling")
    if envelope.get("evidence_write_before_next_request") is not True:
        raise ValueError("evidence must be written before every next request")
    for field in ("evidence_write_rule", "failure_isolation"):
        if not str(envelope.get(field) or "").strip():
            raise ValueError(f"campaign {field} is required")
    checkpoint = _mapping(envelope.get("checkpoint_resume"), "checkpoint_resume")
    if checkpoint.get("checkpoint_after_each_request") is not True or checkpoint.get("resume_may_rediscover_or_switch") is not False:
        raise ValueError("checkpoint/resume safety drifted")
    _list(checkpoint.get("resume_requirements"), "checkpoint_resume.resume_requirements")
    _list(envelope.get("global_stop_conditions"), "global_stop_conditions")

    sources = _list(record.get("source_manifests"), "source_manifests")
    indexed = {row.get("source_id"): row for row in sources if isinstance(row, dict)}
    if len(indexed) != len(sources) or list(indexed) != SOURCE_ORDER:
        raise ValueError("source manifests must contain exactly the ordered Tier-A set")
    request_sum = 0
    primary_sum = 0
    repeat_sum = 0
    for source_id in SOURCE_ORDER:
        source = indexed[source_id]
        prefix = f"source_manifests.{source_id}"
        if source.get("source_name") != SOURCE_NAMES[source_id] or source.get("readiness_tier") != "A":
            raise ValueError(f"{source_id} identity or tier drifted")
        if source.get("preflight_status") != "ready_for_separately_authorized_live_batch":
            raise ValueError(f"{source_id} cannot claim this manifest's ready status")
        if not str(source.get("confidence") or "").strip():
            raise ValueError(f"{source_id} lacks confidence statement")
        lock = _mapping(source.get("method_lock"), f"{prefix}.method_lock")
        if lock.get("active_tracks") != EXPECTED_TECHNIQUES[source_id]:
            raise ValueError(f"{source_id} approved technique lock drifted")
        if source.get("method_lock_fingerprint") != method_lock_fingerprint(lock):
            raise ValueError(f"{source_id} method-lock fingerprint drifted")
        for key in (
            "profile_id", "technique_ids", "technique_families", "discovery_surface_type",
            "detail_surface_type", "endpoint_family", "extraction_strategy", "browser_mode", "auth_state",
        ):
            if not lock.get(key):
                raise ValueError(f"{source_id} incomplete method lock: {key}")
        if lock.get("browser_mode") != "disabled" or lock.get("auth_state") != "public-no-auth":
            raise ValueError(f"{source_id} browser/auth lock is unsafe")
        for key in (
            "automatic_technique_switch", "automatic_environment_switch",
            "automatic_endpoint_rediscovery", "automatic_extraction_strategy_switch",
        ):
            if lock.get(key) is not False:
                raise ValueError(f"{source_id} automatic lock switching is forbidden")

        surfaces = _list(source.get("surface_provenance"), f"{prefix}.surface_provenance")
        if not any(row.get("surface_role") == "registry_root" for row in surfaces):
            raise ValueError(f"{source_id} lacks registry-root provenance")
        for surface in surfaces:
            if not isinstance(surface, dict) or not all(surface.get(key) for key in ("surface_role", "claim_type", "value")):
                raise ValueError(f"{source_id} has incomplete surface provenance")
            if surface.get("claim_type") not in {"exact_url", "url_pattern"}:
                raise ValueError(f"{source_id} has unsupported surface claim type")
            if surface.get("claim_type") == "exact_url" and surface.get("value") not in EXACT_URL_ALLOWLIST:
                raise ValueError(f"{source_id} makes an unsupported exact URL claim")
            _validate_value({"value": surface["value"], "value_origin": surface.get("value_origin"), "evidence": surface.get("evidence")}, f"{prefix}.surface")

        environment = source.get("execution_environment")
        _validate_value(environment, f"{prefix}.execution_environment")
        if environment["value"] != "cloud-hosted-public-read-only":
            raise ValueError(f"{source_id} execution environment drifted")
        transport = _mapping(source.get("transport"), f"{prefix}.transport")
        _list(transport.get("allowed_modes"), f"{prefix}.transport.allowed_modes")
        forbidden_modes = set(_list(transport.get("forbidden_modes"), f"{prefix}.transport.forbidden_modes"))
        if not {"Edge", "login", "cookies", "session", "private-api", "proxy"} <= forbidden_modes:
            raise ValueError(f"{source_id} transport boundaries are incomplete")
        if not str(transport.get("allowed_pagination") or "").strip():
            raise ValueError(f"{source_id} pagination is unbounded")

        budgets = _mapping(source.get("budgets"), f"{prefix}.budgets")
        for key in ("primary_page_units", "repeat_page_units", "max_output_items", "max_transport_requests", "source_concurrency_cap", "timeout_seconds", "retry_count"):
            _validate_value(budgets.get(key), f"{prefix}.budgets.{key}")
            value = budgets[key]["value"]
            if not isinstance(value, int) or value < 0 or (key != "retry_count" and value == 0):
                raise ValueError(f"{source_id} budget {key} is unbounded or invalid")
        if budgets["max_transport_requests"]["value"] != EXPECTED_REQUEST_BUDGETS[source_id]:
            raise ValueError(f"{source_id} request ceiling drifted")
        if budgets["source_concurrency_cap"]["value"] != 1:
            raise ValueError(f"{source_id} concurrency exceeds campaign lock")
        request_sum += budgets["max_transport_requests"]["value"]
        primary_sum += budgets["primary_page_units"]["value"]
        repeat_sum += budgets["repeat_page_units"]["value"]

        expected = _mapping(source.get("expected_records"), f"{prefix}.expected_records")
        for label in ("minimum", "target", "maximum"):
            _validate_value(expected.get(label), f"{prefix}.expected_records.{label}")
        if not 0 < expected["minimum"]["value"] <= expected["target"]["value"] <= expected["maximum"]["value"]:
            raise ValueError(f"{source_id} expected range is inconsistent")
        normalization = _mapping(source.get("normalization_contract"), f"{prefix}.normalization_contract")
        for field in ("required_identity_fields", "required_price_fields", "required_provenance_fields"):
            _list(normalization.get(field), f"{prefix}.{field}")
        if normalization.get("record_type") != "ProductCandidate" or not normalization.get("price_role_handling"):
            raise ValueError(f"{source_id} normalization/price role contract is incomplete")
        if not str(source.get("repeatability_policy") or "").strip():
            raise ValueError(f"{source_id} lacks repeatability policy")
        audit = _mapping(source.get("deep_audit"), f"{prefix}.deep_audit")
        if audit.get("required") is not True:
            raise ValueError(f"{source_id} Deep Audit is required")
        _list(audit.get("criteria"), f"{prefix}.deep_audit.criteria")
        _list(audit.get("evidence"), f"{prefix}.deep_audit.evidence")
        _list(source.get("drift_checks"), f"{prefix}.drift_checks")
        _list(source.get("stop_conditions"), f"{prefix}.stop_conditions")
        exits = _mapping(source.get("exit_classification"), f"{prefix}.exit_classification")
        if set(exits) != {"0", "1", "2"} or any(not str(value).strip() for value in exits.values()):
            raise ValueError(f"{source_id} exit classification must define 0/1/2")
        _list(source.get("evidence_references"), f"{prefix}.evidence_references")

    if request_sum != envelope["global_max_transport_requests"]["value"]:
        raise ValueError("global request ceiling does not reconcile per-source ceilings")
    if primary_sum != envelope["global_primary_page_units"]["value"] or repeat_sum != envelope["global_repeat_page_units"]["value"]:
        raise ValueError("global page-unit budgets do not reconcile")

    exits = _mapping(record.get("campaign_exit_classification"), "campaign_exit_classification")
    if set(exits) != {"0", "1", "2"} or any(not str(value).strip() for value in exits.values()):
        raise ValueError("campaign exit classification must define 0/1/2")
    summary = _mapping(record.get("preflight_summary"), "preflight_summary")
    if summary.get("ready_source_ids") != SOURCE_ORDER or summary.get("blocked_source_ids") != []:
        raise ValueError("preflight source status drifted")
    if summary.get("ready_for_separate_live_authorization") is not True or summary.get("live_authorization_granted") is not False:
        raise ValueError("preflight authorization boundary drifted")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("manifest boundaries drifted")
    validate_safe_json_payload(record)
    return deepcopy(record)

