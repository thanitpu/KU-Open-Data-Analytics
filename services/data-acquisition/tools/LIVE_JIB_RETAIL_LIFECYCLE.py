from __future__ import annotations

import json
import os
import re
import sys
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


def finish(result):
    result["finished_at"] = now()
    out = Path(os.environ.get("KU2D_JIB_RESULT", ROOT.parent.parent / "docs" / "validation" / "jib-live-latest.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[JIB] RESULT_FILE={out}")
    print(f"[JIB] APPROVED={result.get('approved')}")
    if result.get("approval_withheld_reason"):
        print(f"[JIB] WITHHELD={result['approval_withheld_reason']}")


def main():
    sources = {x["source_id"]: x for x in normalized_sources()}
    source = sources.get(SOURCE_ID)
    if not source:
        raise SystemExit(f"{SOURCE_ID} not found in monitoring registry")
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
        result["approval_withheld_reason"] = "Explore did not close all required retail tracks."
        finish(result)
        return

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

    finish(result)


if __name__ == "__main__":
    main()
