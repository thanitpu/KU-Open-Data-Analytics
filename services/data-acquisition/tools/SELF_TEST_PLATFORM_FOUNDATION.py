from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from platform.observation_store import ObservationStore
from platform.lifecycle_policy import decide_next_action, drift_detected


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = ObservationStore(Path(td) / "obs.sqlite3")
        t1 = "2026-08-29T00:00:00+00:00"
        t2 = "2026-08-30T00:00:00+00:00"
        store.add_observation(
            source_id="SRC-X", source_url="https://example.com/p/1",
            lifecycle_stage="explore", record_type="ProductCandidate",
            entity_key="SKU-1", technique="html", validation_status="exploratory",
            payload={"sku":"SKU-1","price":42}, observed_at=t1,
        )
        store.add_observation(
            source_id="SRC-X", source_url="https://example.com/p/1",
            lifecycle_stage="acquire", record_type="ProductCandidate",
            entity_key="SKU-1", technique="api", profile_fingerprint="abc",
            validation_status="trusted", payload={"sku":"SKU-1","price":45}, observed_at=t2,
        )
        store.add_observation(
            source_id="SRC-X", source_url="https://example.com/",
            lifecycle_stage="explore", record_type="ProductCandidate",
            technique="basic_crawler", validation_status="rejected",
            rejection_reason="marketing_text", payload={"product_name":"สมัครสมาชิก","price":1}, observed_at=t1,
        )
        rows = store.observations("SRC-X")
        assert len(rows) == 3
        latest = store.latest_entity_observations("SRC-X")
        assert len(latest) == 1 and latest[0]["payload"]["price"] == 45
        assert any(r["validation_status"] == "rejected" and r["rejection_reason"] == "marketing_text" for r in rows)

    now = datetime(2026, 8, 29, tzinfo=timezone.utc)
    healthy = decide_next_action(
        quality_profile={"audit_passed":1,"approved_for_store":1,"last_audit_at":(now-timedelta(days=1)).isoformat()},
        run_state={"consecutive_failures":0}, current_profile_fingerprint="abc", audited_profile_fingerprint="abc", now=now,
    )
    assert healthy.action == "scheduled-acquire"

    changed = decide_next_action(
        quality_profile={"audit_passed":1,"approved_for_store":1,"last_audit_at":now.isoformat()},
        run_state={}, current_profile_fingerprint="def", audited_profile_fingerprint="abc", now=now,
    )
    assert changed.action == "deep-audit" and changed.requires_human_approval

    blocked = decide_next_action(
        quality_profile={"audit_passed":1,"approved_for_store":1,"last_audit_at":now.isoformat()},
        run_state={"consecutive_failures":3}, current_profile_fingerprint="abc", audited_profile_fingerprint="abc", now=now,
    )
    assert blocked.action == "re-explore"

    is_drift, reasons = drift_detected({"price_completeness_pct":70,"repeatability_pct":60})
    assert is_drift and "price-completeness-below-80" in reasons and "repeatability-below-70" in reasons
    print("[SELF_TEST_PLATFORM_FOUNDATION PASS]")


if __name__ == "__main__":
    main()
