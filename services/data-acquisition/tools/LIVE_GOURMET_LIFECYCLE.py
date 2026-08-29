from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from source_explorer import explore_url
from monitoring_registry import normalized_sources
from operations_store import replace_technique_assignments, set_quality_approval, quality_profile, technique_assignments
from deep_audit import audit_source
from control_plane.observation_bridge import persist_explore, persist_audit
from control_plane.scheduler import scheduler_plan

SOURCE_ID = "SRC-003"
TECHNIQUES = [
    "gourmet_graphql_catalog",
    "gourmet_rendered_catalog",
    "gourmet_promotion_surface",
    "gourmet_catalog_network",
    "generic_sitemap",
    "generic_app_bundle",
    "generic_browser_network",
    "generic_api_probe",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def compact_technique(x):
    p = x.get("potential") or {}
    return {
        "technique": x.get("technique"),
        "label": x.get("label"),
        "status": x.get("status"),
        "record_count": x.get("record_count"),
        "record_types": x.get("record_types"),
        "pages_checked": x.get("pages_checked"),
        "elapsed_seconds": x.get("elapsed_seconds"),
        "potential": p,
        "sample_records": (x.get("sample_records") or [])[:8],
        "diagnostics": (x.get("diagnostics") or [])[:12],
    }


def main():
    sources = {s["source_id"]: s for s in normalized_sources()}
    source = sources.get(SOURCE_ID)
    if not source:
        raise SystemExit(f"{SOURCE_ID} not found in monitoring registry")

    source = {**source, **(source.get("raw") or {})}
    result = {
        "kind": "ku2d-live-source-validation",
        "source_id": SOURCE_ID,
        "source_name": source.get("name"),
        "source_url": source.get("url"),
        "started_at": now(),
        "environment": "github-hosted-public-staging",
        "safety": "public official-site access only; no authentication/challenge bypass",
    }

    print("[Gourmet] Explore started", flush=True)
    explore = explore_url(
        source["url"],
        domain=source.get("domain") or "Supermarket",
        purpose=source.get("purpose") or "retail_market_intelligence",
        max_pages=min(8, int(source.get("max_pages") or 8)),
        techniques=TECHNIQUES,
    )
    persist_explore(SOURCE_ID, source["url"], explore)
    recs = explore.get("recommended_techniques") or []
    result["explore"] = {
        "quality": explore.get("quality"),
        "record_count": explore.get("record_count"),
        "record_types": explore.get("record_types"),
        "assigned_techniques": explore.get("assigned_techniques"),
        "track_recommendations": explore.get("track_recommendations"),
        "recommended_techniques": recs,
        "technique_results": [compact_technique(x) for x in (explore.get("technique_results") or [])],
    }

    if not recs:
        result["approved"] = False
        result["approval_withheld_reason"] = "Explore produced no credible Best Technique profile."
        finish(result)
        return

    rows = replace_technique_assignments(SOURCE_ID, recs)
    result["persisted_assignment"] = [
        {k: r.get(k) for k in ("track_name", "technique", "label", "score", "record_count", "engine_version")}
        for r in rows
    ]

    print("[Gourmet] Deep Audit started", flush=True)
    audit = audit_source(source, max_pages=min(8, int(source.get("max_pages") or 8)), repeat_check=True)
    persist_audit(SOURCE_ID, source["url"], audit)
    result["audit"] = {
        "audit_passed": audit.get("audit_passed"),
        "quality_score": audit.get("quality_score"),
        "quality_label": audit.get("quality_label"),
        "hard_failures": audit.get("hard_failures"),
        "gate_checks": audit.get("gate_checks"),
        "warnings": audit.get("warnings"),
        "field_stats": audit.get("field_stats"),
        "repeatability": audit.get("repeatability"),
        "technique_profile": audit.get("technique_profile"),
        "technique_tracks": audit.get("technique_tracks"),
        "sample_records": (audit.get("sample_records") or [])[:15],
    }

    assigned_rows = technique_assignments(SOURCE_ID)
    tracks = {r.get("track_name") for r in assigned_rows if r.get("track_name")}
    required_tracks = {"product_price", "promotion", "discovery"}
    missing_tracks = sorted(required_tracks - tracks)

    if audit.get("audit_passed") and not missing_tracks:
        # This approval is intentionally in the isolated staging operations DB.
        # The validated profile/evidence is committed separately; production state is not mutated.
        set_quality_approval(SOURCE_ID, approved=True, continuous=True)
        qp = quality_profile(SOURCE_ID) or {}
        result["approved"] = bool(qp.get("approved_for_store"))
        result["continuous_enabled"] = bool(qp.get("continuous_enabled"))
        result["approval_scope"] = "isolated-staging-db"
        result["scheduler_plan_after_approval"] = scheduler_plan([SOURCE_ID])
    else:
        result["approved"] = False
        if not audit.get("audit_passed"):
            result["approval_withheld_reason"] = "Deep Audit did not pass all hard gates."
        else:
            result["approval_withheld_reason"] = f"Missing required supermarket track(s): {', '.join(missing_tracks)}"

    finish(result)


def finish(result):
    result["finished_at"] = now()
    out = Path(os.environ.get("KU2D_GOURMET_RESULT", ROOT.parent.parent / "docs" / "validation" / "gourmet-live-latest.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[Gourmet] RESULT_FILE={out}")
    print(f"[Gourmet] APPROVED={result.get('approved')}")
    if result.get("approval_withheld_reason"):
        print(f"[Gourmet] WITHHELD={result['approval_withheld_reason']}")


if __name__ == "__main__":
    main()
