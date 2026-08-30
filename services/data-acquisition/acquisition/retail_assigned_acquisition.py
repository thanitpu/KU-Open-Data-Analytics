from __future__ import annotations

from technique_strategy import (
    assigned_acquisition as base_assigned_acquisition,
    assigned_profile,
    dedup,
    materialize_for_run,
    technique_profile_fingerprint,
    technique_tracks_from_assignments,
)
from retail_detail_transport import generic_retail_detail_catalog

DETAIL_TECHNIQUE = "generic_retail_detail_catalog"


def assigned_acquisition(source, max_pages=8, progress=None, require_profile=True, stable_sample=False):
    """Operationally execute a persisted profile that includes canonical retail detail.

    The core technique engine predates the cross-domain retail-detail technique. This
    router preserves the established assigned-acquisition contract while executing the
    new detail track explicitly and delegating all remaining assigned techniques to the
    existing operational materializer. It never substitutes an unassigned technique.
    """
    rows, techniques = assigned_profile(source.get("source_id"))
    if DETAIL_TECHNIQUE not in set(techniques or []):
        return base_assigned_acquisition(
            source,
            max_pages=max_pages,
            progress=progress,
            require_profile=require_profile,
            stable_sample=stable_sample,
        )
    if require_profile and not techniques:
        raise RuntimeError("No Best Acquisition Technique is assigned. Run Find Best Data Acquisition Techniques first.")

    if progress:
        try:
            progress({
                "phase": "best-technique",
                "message": "Applying canonical retail detail and companion assigned techniques",
                "assigned_techniques": techniques,
            })
        except Exception:
            pass

    detail = generic_retail_detail_catalog(
        source.get("url"),
        max_pages=max_pages,
        candidate_urls=None,
    )
    detail.setdefault("status", "completed")
    detail.setdefault("technique", DETAIL_TECHNIQUE)
    detail.setdefault("label", "Canonical Retail Product Detail Catalog")
    detail.setdefault("operational_role", "acquisition")

    remaining = [x for x in techniques if x != DETAIL_TECHNIQUE]
    remaining_rows = [x for x in rows if x.get("technique") in set(remaining)]
    if remaining:
        delegated = materialize_for_run(
            source,
            remaining,
            max_pages=max_pages,
            assignment_rows=remaining_rows,
            stable_sample=stable_sample,
        )
    else:
        delegated = {
            "records": [],
            "benchmark": {
                "technique_results": [],
                "techniques_selected": [],
                "recommended_techniques": [],
                "track_recommendations": {},
                "operational_execution": True,
            },
            "techniques_used": [],
        }

    benchmark = delegated.get("benchmark") or {}
    technique_results = [detail] + list(benchmark.get("technique_results") or [])
    benchmark = {
        **benchmark,
        "technique_results": technique_results,
        "techniques_selected": list(techniques),
        "operational_execution": True,
    }

    records = dedup(list(detail.get("sample_records") or []) + list(delegated.get("records") or []))
    selected = set(techniques)
    applied_results = [x for x in technique_results if x.get("technique") in selected]

    urls = []
    diagnostics = []
    pages_checked = 0
    for result in applied_results:
        pages_checked += int(result.get("pages_checked") or 0)
        for url in result.get("urls_checked") or []:
            if url and url not in urls:
                urls.append(url)
        diagnostics.append({
            "technique": result.get("technique"),
            "label": result.get("label"),
            "status": result.get("status"),
            "record_count": int(result.get("record_count") or 0),
            "record_types": result.get("record_types") or [],
            "pages_checked": int(result.get("pages_checked") or 0),
            "elapsed_seconds": result.get("elapsed_seconds") or 0,
            "potential": result.get("potential") or {},
            "diagnostics": result.get("diagnostics") or [],
        })

    return {
        "records": records,
        "pages": [],
        "adapter": "best-technique:" + ",".join(techniques),
        "sector": source.get("sector") or source.get("domain"),
        "diagnostics": diagnostics,
        "benchmark": benchmark,
        "technique_results": applied_results,
        "technique_assignments": rows,
        "assigned_techniques": techniques,
        "technique_tracks": technique_tracks_from_assignments(rows),
        "technique_profile_fingerprint": technique_profile_fingerprint(techniques, rows),
        "pages_checked": pages_checked,
        "urls_checked": urls,
        "technique_profile_applied": True,
        "legacy_fallback_used": False,
    }
