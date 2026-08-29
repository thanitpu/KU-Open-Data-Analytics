from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

with TemporaryDirectory() as td:
    os.environ["KU2D_OPERATIONS_DB"] = str(Path(td) / "ops.sqlite3")
    os.environ["KU2D_OBSERVATION_DB"] = str(Path(td) / "obs.sqlite3")

    import operations_store as ops
    import technique_strategy as strategy
    import control_plane.scheduler as scheduler
    from control_plane.lifecycle_policy import evaluate_source
    from control_plane.observation_bridge import persist_explore, persist_audit, persist_acquire
    from control_plane.observation_store import ObservationStore

    source = {
        "source_id": "STAGE-001",
        "name": "Lifecycle Fixture Market",
        "url": "https://example.invalid/",
        "domain": "Supermarket",
        "source_type": "gourmet",
        "adapter": "gourmet",
        "registry": "commerce",
        "enabled": True,
        "cadence": "daily",
        "max_pages": 5,
        "purpose": "retail_market_intelligence",
        "raw": {"adapter": "gourmet"},
    }

    recs = [
        {
            "record_type": "ProductCandidate",
            "product_name": f"Fixture Product {i}",
            "sku": f"88500000000{i}",
            "price": 100 + i,
            "source_url": f"https://example.invalid/p/{i}",
            "provenance": "gourmet-rendered-product-card",
        }
        for i in range(1, 6)
    ]
    promo = {
        "record_type": "PromotionCandidate",
        "promotion_title": "Fixture Promotion",
        "offer": "Save 10",
        "source_url": "https://example.invalid/promo/1",
        "provenance": "gourmet-official-promotion",
    }

    recommendations = [
        {
            "technique": "gourmet_rendered_catalog",
            "label": "Gourmet Market Rendered Product Cards",
            "score": 100,
            "record_count": 5,
            "tracks": ["product_price"],
            "engine_version": "0.24",
            "potential": {"operational_config": {"identity_source": "fixture-gtin"}},
        },
        {
            "technique": "gourmet_promotion_surface",
            "label": "Gourmet Market Official Promotion Surface",
            "score": 90,
            "record_count": 1,
            "tracks": ["promotion"],
            "engine_version": "0.24",
        },
        {
            "technique": "generic_sitemap",
            "label": "Robots / Sitemap Discovery",
            "score": 60,
            "record_count": 1,
            "tracks": ["discovery"],
            "engine_version": "0.24",
        },
    ]
    rows = ops.replace_technique_assignments(source["source_id"], recommendations)
    assigned = [r["technique"] for r in rows]
    fp = strategy.technique_profile_fingerprint(assigned, rows)
    assert fp

    explore_result = {
        "technique_results": [
            {
                "technique": "gourmet_rendered_catalog",
                "sample_records": recs,
            },
            {
                "technique": "gourmet_promotion_surface",
                "sample_records": [promo],
            },
        ]
    }
    assert persist_explore(source["source_id"], source["url"], explore_result)["stored"] == 6

    audit = {
        "audit_passed": True,
        "quality_score": 99,
        "quality_label": "strong",
        "safe_cadence_recommendation": "daily",
        "accessibility": {"proposed_level": 1, "verified_method": "fixture"},
        "technique_profile": {"fingerprint": fp},
        "sample_records": recs + [promo],
    }
    ops.save_quality_audit(source["source_id"], audit)
    assert persist_audit(source["source_id"], source["url"], audit)["stored"] == 6

    q = ops.quality_profile(source["source_id"])
    decision = evaluate_source(
        source=source,
        quality=q,
        run_state={},
        assigned_fingerprint=fp,
        audited_fingerprint=fp,
    )
    assert decision["action"] == "await-human-approval"

    ops.set_quality_approval(source["source_id"], approved=True, continuous=True)
    q = ops.quality_profile(source["source_id"])
    decision = evaluate_source(
        source=source,
        quality=q,
        run_state={},
        assigned_fingerprint=fp,
        audited_fingerprint=fp,
    )
    assert decision["action"] == "scheduled-acquire"

    original_normalized_sources = scheduler.normalized_sources
    original_quality_profile = scheduler.quality_profile
    original_states = scheduler.states
    original_assignments = scheduler.technique_assignments
    original_fp = scheduler.technique_profile_fingerprint
    original_due = scheduler.cadence_due
    original_acquire = scheduler.acquire_and_store

    scheduler.normalized_sources = lambda: [source]
    scheduler.quality_profile = lambda sid: ops.quality_profile(sid)
    scheduler.states = lambda: ops.states()
    scheduler.technique_assignments = lambda sid: ops.technique_assignments(sid)
    scheduler.technique_profile_fingerprint = strategy.technique_profile_fingerprint
    scheduler.cadence_due = lambda last_success_at, cadence: True

    def fake_acquire(src, max_pages=20, require_approval=True):
        assert require_approval is True
        assert ops.quality_profile(src["source_id"])["approved_for_store"] == 1
        write = persist_acquire(src["source_id"], src["url"], recs + [promo], fp)
        return {
            "ok": True,
            "deep_run_id": "STAGING-ACQUIRE-1",
            "source_id": src["source_id"],
            "metrics": {"records_found": 6, "records_stored": 6, "observation_store": write},
        }

    scheduler.acquire_and_store = fake_acquire
    try:
        cycle = scheduler.run_scheduler_cycle([source["source_id"]])
    finally:
        scheduler.normalized_sources = original_normalized_sources
        scheduler.quality_profile = original_quality_profile
        scheduler.states = original_states
        scheduler.technique_assignments = original_assignments
        scheduler.technique_profile_fingerprint = original_fp
        scheduler.cadence_due = original_due
        scheduler.acquire_and_store = original_acquire

    result = cycle["results"][0]
    assert result["status"] == "success"
    assert ops.states()[source["source_id"]]["last_status"] == "success"

    summary = ObservationStore().summary(source["source_id"])
    groups = {(g["validation_status"], g["record_type"]): g["c"] for g in summary["groups"]}
    assert groups[("exploratory", "ProductCandidate")] == 5
    assert groups[("accepted", "ProductCandidate")] == 5
    assert groups[("trusted", "ProductCandidate")] == 5

    # Three consecutive acquisition failures must move the source back to Re-Explore.
    for i in range(3):
        rid = ops.start_run(source)
        ops.finish_run(rid, source["source_id"], "failed", error=f"fixture-failure-{i+1}")
    state = ops.states()[source["source_id"]]
    decision = evaluate_source(
        source=source,
        quality=ops.quality_profile(source["source_id"]),
        run_state=state,
        assigned_fingerprint=fp,
        audited_fingerprint=fp,
    )
    assert decision["action"] == "re-explore"

    # A material technique-profile change invalidates prior audit and approval.
    changed = [dict(recommendations[0], technique="gourmet_graphql_catalog", label="Gourmet Market GraphQL Product Catalog")]
    ops.replace_technique_assignments(source["source_id"], changed)
    q2 = ops.quality_profile(source["source_id"])
    assert q2["audit_passed"] == 0
    assert q2["approved_for_store"] == 0
    assert q2["continuous_enabled"] == 0

print("Full lifecycle staging acceptance: PASS")
