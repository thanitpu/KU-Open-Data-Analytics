from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from source_explorer import explore_url
from monitoring_registry import normalized_sources
from operations_store import (
    quality_profile,
    replace_technique_assignments,
    set_quality_approval,
    technique_assignments,
)
import deep_audit as deep_audit_module
from retail_assigned_acquisition import assigned_acquisition as retail_assigned_acquisition
from control_plane.domain_playbooks import recommended_sequence
from control_plane.observation_bridge import persist_audit, persist_explore
from control_plane.scheduler import scheduler_plan

SOURCE_ID = "SRC-018"
EXIT_OK = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_APPROVAL_WITHHELD = 2


def now():
    return datetime.now(timezone.utc).isoformat()


def resolved_tracks(rows):
    tracks = set()
    for row in rows or []:
        evidence = row.get("evidence") or {}
        tracks.update(str(x) for x in (evidence.get("tracks") or []) if x)
        if row.get("track_name"):
            tracks.add(str(row["track_name"]))
    return tracks


def canonical_identity(record):
    if any(record.get(x) for x in ("sku", "model", "gtin", "product_id")):
        return True
    return bool(re.search(r"/(?:product|products|p|item|sku)/|/web/product/readProduct/\d+", str(record.get("source_url") or ""), re.I))


def domain_audit_gates(audit, playbook):
    quality = playbook.get("quality_gates") or {}
    records = [x for x in (audit.get("sample_records") or []) if x.get("record_type") == "ProductCandidate"]
    product_count = int((audit.get("yield") or {}).get("products") or len(records))
    price_pct = float((audit.get("field_quality") or {}).get("product_price_pct") or 0)
    semantic_pct = float((audit.get("field_quality") or {}).get("product_semantic_quality_pct") or 0)
    provenance_pct = float((audit.get("field_quality") or {}).get("provenance_pct") or 0)
    repeat_pct = float((audit.get("repeatability") or {}).get("product_repeatability_pct") or 0)
    execution_pct = float((audit.get("coverage") or {}).get("technique_execution_pct") or 0)
    identity_pct = round(100 * sum(canonical_identity(x) for x in records) / len(records), 1) if records else 0.0

    minimum_products = int(quality.get("minimum_product_records") or 5)
    minimum_price = float(quality.get("price_completeness_pct") or 85)
    minimum_semantic = float(quality.get("semantic_quality_pct") or 85)
    minimum_repeat = float(quality.get("repeatability_pct") or 70)
    minimum_provenance = float(quality.get("provenance_pct") or 95)
    minimum_identity = float(quality.get("model_or_sku_completeness_pct") or 90)

    return {
        "product_catalog_sample": {
            "passed": product_count >= minimum_products,
            "value": product_count,
            "required": f">={minimum_products} attributable products",
        },
        "product_price_completeness": {
            "passed": price_pct >= minimum_price,
            "value": price_pct,
            "required": f">={minimum_price}%",
        },
        "product_semantic_quality": {
            "passed": semantic_pct >= minimum_semantic,
            "value": semantic_pct,
            "required": f">={minimum_semantic}%",
        },
        "sellable_product_identity": {
            "passed": identity_pct >= minimum_identity,
            "value": identity_pct,
            "required": f">={minimum_identity}% SKU/model/GTIN/product ID or canonical product route",
        },
        "product_repeatability": {
            "passed": repeat_pct >= minimum_repeat,
            "value": repeat_pct,
            "required": f">={minimum_repeat}%",
        },
        "provenance": {
            "passed": provenance_pct >= minimum_provenance,
            "value": provenance_pct,
            "required": f">={minimum_provenance}% official source URL",
        },
        "assigned_technique_execution": {
            "passed": execution_pct >= 80,
            "value": execution_pct,
            "required": ">=80%",
        },
    }


def compact_technique(result):
    return {
        "technique": result.get("technique"),
        "label": result.get("label"),
        "status": result.get("status"),
        "record_count": result.get("record_count"),
        "record_types": result.get("record_types"),
        "pages_checked": result.get("pages_checked"),
        "potential": result.get("potential") or {},
        "sample_records": (result.get("sample_records") or [])[:8],
        "diagnostics": (result.get("diagnostics") or [])[:15],
    }


def result_paths(environ=None):
    env = environ or os.environ
    detail = Path(env.get("KU2D_JIB_RESULT", ROOT.parent.parent / "docs" / "validation" / "jib-live-latest.json"))
    summary = Path(env.get("KU2D_JIB_SUMMARY", detail.with_name("jib-live-summary.json")))
    return detail, summary


def isolated_database_paths(environ=None):
    """Require explicit, distinct staging databases before simulated approval."""
    env = environ or os.environ
    if str(env.get("KU2D_APPROVAL_SCOPE") or "").strip().lower() != "isolated-staging":
        raise RuntimeError("JIB lifecycle validation requires KU2D_APPROVAL_SCOPE=isolated-staging.")
    operations = str(env.get("KU2D_OPERATIONS_DB") or "").strip()
    observations = str(env.get("KU2D_OBSERVATION_DB") or "").strip()
    if not operations or not observations:
        raise RuntimeError("JIB lifecycle validation requires explicit isolated KU2D_OPERATIONS_DB and KU2D_OBSERVATION_DB paths.")
    op_path = Path(operations).expanduser().resolve()
    obs_path = Path(observations).expanduser().resolve()
    if op_path == obs_path:
        raise RuntimeError("JIB lifecycle validation operations and observation databases must be distinct.")
    default_data = (ROOT / "data").resolve()
    if op_path.is_relative_to(default_data) or obs_path.is_relative_to(default_data):
        raise RuntimeError("JIB lifecycle validation refuses the service default data tree; use isolated temporary database paths.")
    return op_path, obs_path


def selected_techniques_by_track(result):
    selected = {}
    for row in result.get("persisted_assignment") or []:
        for track in row.get("tracks") or []:
            selected[str(track)] = {
                "technique": row.get("technique"),
                "label": row.get("label"),
                "score": row.get("score"),
            }
    return selected


def approval_requirements_passed(result):
    audit = result.get("audit") or {}
    tracks = result.get("approval_track_policy") or {}
    return bool(
        result.get("approved")
        and audit.get("audit_passed")
        and not (audit.get("hard_failures") or [])
        and not (audit.get("domain_gate_failures") or [])
        and not (tracks.get("missing_required") or [])
    )


def validation_summary(result):
    audit = result.get("audit") or {}
    track_policy = result.get("approval_track_policy") or {}
    domain_gates = audit.get("domain_gate_checks") or {}
    technique_profile = audit.get("technique_profile") or {}
    yield_info = audit.get("yield") or {}
    field_quality = audit.get("field_quality") or {}
    repeatability = audit.get("repeatability") or {}

    def gate_value(name, fallback=None):
        return (domain_gates.get(name) or {}).get("value", fallback)

    return {
        "schema": "ku2d.retail-live-validation-summary.v1",
        "source_id": result.get("source_id"),
        "source_name": result.get("source_name"),
        "source_url": result.get("source_url"),
        "domain": result.get("domain"),
        "execution_environment": result.get("environment"),
        "validation_timestamp": result.get("finished_at") or result.get("started_at"),
        "technical_completion": not bool(result.get("technical_failure")),
        "approved": approval_requirements_passed(result),
        "continuous_enabled": bool(result.get("continuous_enabled")),
        "approval_scope": result.get("approval_scope"),
        "tracks": {
            "required": track_policy.get("required") or [],
            "optional": track_policy.get("optional") or [],
            "resolved": track_policy.get("resolved") or [],
            "missing_required": track_policy.get("missing_required") or [],
        },
        "base_deep_audit": {
            "passed": bool(audit.get("audit_passed")),
            "hard_failures": audit.get("hard_failures") or [],
            "quality_score": audit.get("quality_score"),
            "quality_label": audit.get("quality_label"),
        },
        "domain_gates": domain_gates,
        "domain_gate_failures": audit.get("domain_gate_failures") or [],
        "selected_techniques_by_track": selected_techniques_by_track(result),
        "technique_profile_fingerprint": technique_profile.get("fingerprint"),
        "metrics": {
            "product_sample_count": len([x for x in (audit.get("sample_records") or []) if x.get("record_type") == "ProductCandidate"]),
            "product_yield_count": int(yield_info.get("products") or 0),
            "price_completeness_pct": gate_value("product_price_completeness", field_quality.get("product_price_pct")),
            "identity_completeness_pct": gate_value("sellable_product_identity"),
            "semantic_quality_pct": gate_value("product_semantic_quality", field_quality.get("product_semantic_quality_pct")),
            "repeatability_pct": gate_value("product_repeatability", repeatability.get("product_repeatability_pct")),
            "provenance_pct": gate_value("provenance", field_quality.get("provenance_pct")),
            "assigned_technique_execution_pct": gate_value("assigned_technique_execution"),
        },
        "warnings": audit.get("warnings") or [],
        "approval_withheld_reason": result.get("approval_withheld_reason"),
        "scheduler_action": (((result.get("scheduler_plan_after_approval") or [{}])[0].get("decision") or {}).get("action") if approval_requirements_passed(result) else None),
        "technical_failure": result.get("technical_failure"),
    }


def write_evidence(result, environ=None):
    result["finished_at"] = now()
    detail_path, summary_path = result_paths(environ)
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary_path.write_text(json.dumps(validation_summary(result), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[JIB] RESULT_FILE={detail_path}")
    print(f"[JIB] SUMMARY_FILE={summary_path}")
    print(f"[JIB] APPROVED={result.get('approved')}")
    if result.get("approval_withheld_reason"):
        print(f"[JIB] WITHHELD={result['approval_withheld_reason']}")
    return detail_path, summary_path


def resolve_exit_code(result, require_approved=False):
    if result.get("technical_failure"):
        return EXIT_TECHNICAL_FAILURE
    if require_approved and not approval_requirements_passed(result):
        return EXIT_APPROVAL_WITHHELD
    return EXIT_OK


def run_lifecycle():
    isolated_database_paths()
    sources = {x["source_id"]: x for x in normalized_sources()}
    source = sources.get(SOURCE_ID)
    if not source:
        raise RuntimeError(f"{SOURCE_ID} not found in monitoring registry")
    source = {**source, **(source.get("raw") or {})}
    domain = source.get("domain") or source.get("sector") or "IT Retail"
    playbook = recommended_sequence(domain, clues=[])
    required_tracks = set(playbook.get("required_tracks") or ["product_price", "discovery"])

    result = {
        "schema": "ku2d.retail-live-lifecycle.v1",
        "source_id": SOURCE_ID,
        "source_name": source.get("name") or source.get("business"),
        "source_url": source.get("url"),
        "domain": domain,
        "started_at": now(),
        "environment": "cloud-hosted-public-read-only",
        "safety": "official public-site access only; no login, CAPTCHA solving, proxy rotation or access-control bypass",
    }

    print("[JIB] Pattern-guided Explore started", flush=True)
    explore = explore_url(
        source.get("url"),
        domain=domain,
        purpose=source.get("purpose") or "retail_market_intelligence",
        max_pages=min(6, int(source.get("max_pages") or 6)),
        techniques=None,
    )
    persist_explore(SOURCE_ID, source.get("url"), explore)
    recs = explore.get("recommended_techniques") or []
    result["explore"] = {
        "quality": explore.get("quality"),
        "record_count": explore.get("record_count"),
        "record_types": explore.get("record_types"),
        "recommendation": explore.get("recommendation"),
        "assigned_techniques": explore.get("assigned_techniques") or [],
        "track_recommendations": explore.get("track_recommendations") or {},
        "required_track_gaps": (explore.get("track_selection") or {}).get("required_track_gaps") or {},
        "recommended_techniques": recs,
        "technique_results": [compact_technique(x) for x in (explore.get("technique_results") or [])],
    }

    explore_gaps = (explore.get("track_selection") or {}).get("required_track_gaps") or {}
    if not recs or explore_gaps:
        result["approved"] = False
        result["continuous_enabled"] = False
        result["approval_scope"] = "isolated-staging-db"
        result["approval_track_policy"] = {
            "required": sorted(required_tracks),
            "optional": playbook.get("optional_tracks") or ["promotion"],
            "resolved": sorted((explore.get("track_recommendations") or {}).keys()),
            "missing_required": sorted(explore_gaps.keys()),
        }
        result["approval_withheld_reason"] = "Explore did not close all required retail tracks."
        return result

    persisted = replace_technique_assignments(SOURCE_ID, recs)
    result["persisted_assignment"] = [
        {
            "technique": row.get("technique"),
            "label": row.get("label"),
            "score": row.get("score"),
            "tracks": (row.get("evidence") or {}).get("tracks") or [],
            "track_scores": (row.get("evidence") or {}).get("track_scores") or {},
        }
        for row in persisted
    ]

    print("[JIB] Deep Audit started", flush=True)
    original_assigned = deep_audit_module.assigned_acquisition
    deep_audit_module.assigned_acquisition = retail_assigned_acquisition
    try:
        audit = deep_audit_module.audit_source(
            source,
            max_pages=min(8, int(source.get("max_pages") or 8)),
            repeat_check=True,
        )
    finally:
        deep_audit_module.assigned_acquisition = original_assigned
    persist_audit(SOURCE_ID, source.get("url"), audit)

    assigned_rows = technique_assignments(SOURCE_ID)
    tracks = resolved_tracks(assigned_rows)
    missing_tracks = sorted(required_tracks - tracks)
    domain_gates = domain_audit_gates(audit, playbook)
    domain_failures = [name for name, gate in domain_gates.items() if not gate.get("passed")]

    result["audit"] = {
        "audit_passed": audit.get("audit_passed"),
        "quality_score": audit.get("quality_score"),
        "quality_label": audit.get("quality_label"),
        "audit_status": audit.get("audit_status"),
        "hard_failures": audit.get("hard_failures") or [],
        "gate_checks": audit.get("gate_checks") or {},
        "domain_gate_checks": domain_gates,
        "domain_gate_failures": domain_failures,
        "warnings": audit.get("warnings") or [],
        "yield": audit.get("yield") or {},
        "field_quality": audit.get("field_quality") or {},
        "repeatability": audit.get("repeatability") or {},
        "technique_profile": audit.get("technique_profile") or {},
        "sample_records": (audit.get("sample_records") or [])[:15],
    }
    result["approval_track_policy"] = {
        "required": sorted(required_tracks),
        "optional": playbook.get("optional_tracks") or ["promotion"],
        "resolved": sorted(tracks),
        "missing_required": missing_tracks,
    }

    passed = bool(audit.get("audit_passed")) and not missing_tracks and not domain_failures
    if passed:
        set_quality_approval(SOURCE_ID, approved=True, continuous=True)
        profile = quality_profile(SOURCE_ID) or {}
        result["approved"] = bool(profile.get("approved_for_store"))
        result["continuous_enabled"] = bool(profile.get("continuous_enabled"))
        result["approval_scope"] = "isolated-staging-db"
        result["scheduler_plan_after_approval"] = scheduler_plan([SOURCE_ID])
    else:
        result["approved"] = False
        reasons = []
        if not audit.get("audit_passed"):
            reasons.append("base Deep Audit hard gates failed")
        if missing_tracks:
            reasons.append("missing required tracks: " + ", ".join(missing_tracks))
        if domain_failures:
            reasons.append("IT Retail domain gates failed: " + ", ".join(domain_failures))
        result["approval_withheld_reason"] = "; ".join(reasons)

    return result


def technical_failure_result(exc):
    return {
        "schema": "ku2d.retail-live-lifecycle.v1",
        "source_id": SOURCE_ID,
        "source_name": "JIB",
        "source_url": "https://www.jib.co.th/web/index.php",
        "domain": "IT Retail",
        "started_at": now(),
        "environment": "cloud-hosted-public-read-only",
        "approved": False,
        "continuous_enabled": False,
        "approval_scope": "isolated-staging-db",
        "technical_failure": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
        "approval_withheld_reason": "Lifecycle did not complete because of a technical/runtime failure.",
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the isolated JIB retail lifecycle validation.")
    parser.add_argument(
        "--require-approved",
        action="store_true",
        help="Return exit code 2 when lifecycle evidence is written but isolated staging approval is withheld.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = run_lifecycle()
    except Exception as exc:
        result = technical_failure_result(exc)
        traceback.print_exc()
    try:
        write_evidence(result)
    except Exception:
        traceback.print_exc()
        return EXIT_TECHNICAL_FAILURE
    return resolve_exit_code(result, require_approved=args.require_approved)


if __name__ == "__main__":
    raise SystemExit(main())
