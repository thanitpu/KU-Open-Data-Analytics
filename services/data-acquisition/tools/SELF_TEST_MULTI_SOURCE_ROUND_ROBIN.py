"""Deterministic P59 round-robin, safety-boundary, and resume tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))
sys.path.insert(0, str(ROOT / "tools"))

from round_robin_campaign import (  # noqa: E402
    CampaignValidationError, ProviderBoundary, RoundRobinCampaign, VisitContext,
    VisitResult, load_campaign_manifest, validate_campaign_manifest,
    verify_sealed_ledger,
)
from LIVE_MULTI_SOURCE_ROUND_ROBIN import (  # noqa: E402
    artifact_delivery_preflight, fixture_replay,
)


MANIFEST = load_campaign_manifest(ROOT / "config" / "multi_source_round_robin_manifest_v1.json")
ACTIVE = [row for row in MANIFEST["sources"] if row["preflight_status"] == "live_eligible"]
assert [row["source_id"] for row in ACTIVE] == ["SRC-001", "SRC-002", "SRC-004", "SRC-005"]
assert all("tiktok" not in json.dumps(row).lower() for row in MANIFEST["sources"])


# RR1-RR5: exact schema, deterministic domain/source order, limits, scope, and unknown-field rejection.
assert validate_campaign_manifest(MANIFEST) == MANIFEST
assert MANIFEST["source_order"] == [
    row["source_id"] for row in sorted(MANIFEST["sources"], key=lambda row: (row["domain"], row["source_id"]))
]
assert len(MANIFEST["phase_declarations"]) == 7
bad = deepcopy(MANIFEST)
bad["unknown"] = True
try:
    validate_campaign_manifest(bad)
    raise AssertionError("unknown manifest field validated")
except CampaignValidationError:
    pass
bad = deepcopy(MANIFEST)
bad["sources"][0]["source_name"] = "TikTok"
try:
    validate_campaign_manifest(bad)
    raise AssertionError("excluded provider validated")
except CampaignValidationError:
    pass


def record(source, suffix="1", name="Safe product"):
    return {
        "record_type": "ProductCandidate", "product_name": name,
        "sku": f"SKU-{suffix}", "price": 10.0, "currency": "THB",
        "source_url": f"https://official.example/product/{source['source_id']}/{suffix}",
        "provenance": "deterministic-fixture",
    }


def exhaust_adapter(calls):
    def adapter(source, context):
        calls.append(source["source_id"])
        response = context.provider_call(
            f"https://{source['source_id'].lower()}.example/public",
            lambda: {"ok": True, "status": 200, "bytes": 20},
        )
        assert response["ok"]
        return VisitResult("success", [record(source)], frontier_exhausted=True)
    return adapter


# RR6-RR11: serial fairness, preflight skips, stable dedup, separate observations, and seal.
with TemporaryDirectory() as tmp:
    calls = []
    adapters = {row["source_id"]: exhaust_adapter(calls) for row in ACTIVE}
    runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "ledger.json", adapters, run_id="RR-FAIR", sleeper=lambda _: None)
    runner.set_code_identity("1" * 40, "2" * 40)
    ledger = runner.run()
    assert calls == ["SRC-001", "SRC-002", "SRC-004", "SRC-005"]
    assert ledger["accepted_unique"] == 4 and ledger["observations"] == 4
    assert ledger["provider_operations"] == 4 and ledger["stop_reason"] == "empty_active_source_set"
    assert all(ledger["source_states"][row["source_id"]]["state"] == "to_be_skipped" for row in MANIFEST["sources"] if row["preflight_status"] == "preflight_skipped")
    verify_sealed_ledger(ledger)


# RR12-RR15: intent is durable before provider access and outcome is durable afterwards.
with TemporaryDirectory() as tmp:
    checkpoint = Path(tmp) / "ledger.json"
    runner = RoundRobinCampaign(MANIFEST, checkpoint, {}, run_id="RR-CHECKPOINT", sleeper=lambda _: None)
    source = ACTIVE[0]
    state = runner.ledger["source_states"][source["source_id"]]
    context = VisitContext(runner, source, state)
    def inspect_intent():
        durable = json.loads(checkpoint.read_text(encoding="utf-8"))
        assert durable["pending_operation"]["state"] == "intent_checkpointed"
        assert durable["provider_operations"] == 0
        return {"ok": True, "status": 200, "bytes": 1}
    context.provider_call("https://official.example/path?secret=never-persist", inspect_intent)
    durable = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert durable["pending_operation"] is None
    assert durable["provider_operations"] == 1
    assert durable["operation_log"][0]["sanitized_url"] == "https://official.example/path"
    assert "secret" not in json.dumps(durable)


# RR16-RR18: crash resume conservatively counts an uncertain operation exactly once.
with TemporaryDirectory() as tmp:
    checkpoint = Path(tmp) / "ledger.json"
    runner = RoundRobinCampaign(MANIFEST, checkpoint, {}, run_id="RR-RESUME", sleeper=lambda _: None)
    source = ACTIVE[0]
    context = VisitContext(runner, source, runner.ledger["source_states"][source["source_id"]])
    try:
        context.provider_call("https://official.example/crash", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        raise AssertionError("crash fixture returned")
    except KeyboardInterrupt:
        pass
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["pending_operation"] is not None
    resumed = RoundRobinCampaign.resume(MANIFEST, checkpoint, {}, run_id="RR-RESUME", sleeper=lambda _: None)
    assert resumed.ledger["provider_operations"] == 1
    assert resumed.ledger["pending_operation"] is None
    assert resumed.ledger["operation_log"][0]["state"] == "finalized_after_crash"


# RR19-RR22: same-host pacing and 403/429 access boundaries prevent a second call.
with TemporaryDirectory() as tmp:
    clock = [0.0]
    sleeps = []
    def monotonic(): return clock[0]
    def sleeper(value): sleeps.append(value); clock[0] += value
    runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "ledger.json", {}, run_id="RR-PACE", monotonic=monotonic, sleeper=sleeper)
    source = ACTIVE[0]
    context = VisitContext(runner, source, runner.ledger["source_states"][source["source_id"]])
    context.provider_call("https://official.example/a", lambda: {"ok": True, "status": 200})
    context.provider_call("https://official.example/b", lambda: {"ok": True, "status": 200})
    assert sleeps == [2.0]
    blocked = VisitContext(runner, source, runner.ledger["source_states"][source["source_id"]])
    blocked.provider_call("https://blocked.example/a", lambda: {"ok": False, "status": 403, "error": "HTTP 403"})
    try:
        blocked.provider_call("https://blocked.example/b", lambda: {"ok": True, "status": 200})
        raise AssertionError("access boundary allowed another request")
    except ProviderBoundary as exc:
        assert "403" in str(exc)


# RR23-RR27: two no-new visits and two transient rounds become terminal, without blocking later sources.
with TemporaryDirectory() as tmp:
    def empty(source, context): return VisitResult("success", [])
    runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "empty.json", {row["source_id"]: empty for row in ACTIVE}, run_id="RR-EMPTY", sleeper=lambda _: None)
    ledger = runner.run()
    assert all(ledger["source_states"][row["source_id"]]["reason"] == "two_visits_without_new_stable_identity" for row in ACTIVE)
    assert ledger["provider_operations"] == 0 and ledger["rounds_completed"] == 2
with TemporaryDirectory() as tmp:
    calls = []
    def transient(source, context):
        calls.append(source["source_id"])
        return VisitResult("transient_failure", [], warning="controlled")
    runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "transient.json", {row["source_id"]: transient for row in ACTIVE}, run_id="RR-TRANSIENT", sleeper=lambda _: None)
    ledger = runner.run()
    assert calls == [row["source_id"] for row in ACTIVE] * 2
    assert all(ledger["source_states"][row["source_id"]]["reason"] == "two_rounds_transient_technical_failure" for row in ACTIVE)


# RR28-RR32: source record cap, cross-round dedup, observation count, and no overclaim.
with TemporaryDirectory() as tmp:
    manifest = deepcopy(MANIFEST)
    focus = next(row for row in manifest["sources"] if row["source_id"] == "SRC-001")
    focus["budgets"]["max_records"] = 1
    for row in manifest["sources"]:
        if row["preflight_status"] == "live_eligible" and row["source_id"] != "SRC-001":
            row.update(preflight_status="preflight_skipped", skip_reason="deterministic_test_narrowing", method_lock_fingerprint=None)
            row["budgets"] = {key: None for key in row["budgets"]}
    validate_campaign_manifest(manifest)
    def many(source, context): return VisitResult("success", [record(source, str(i)) for i in range(150)])
    runner = RoundRobinCampaign(manifest, Path(tmp) / "cap.json", {"SRC-001": many}, run_id="RR-CAP", sleeper=lambda _: None)
    ledger = runner.run()
    assert ledger["accepted_unique"] == 1 and ledger["observations"] == 1
    assert ledger["source_states"]["SRC-001"]["state"] == "exhausted"


# RR33-RR37: global/source/visit ceilings stop before another provider call.
with TemporaryDirectory() as tmp:
    runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "limits.json", {}, run_id="RR-LIMIT", sleeper=lambda _: None)
    source = ACTIVE[0]
    state = runner.ledger["source_states"][source["source_id"]]
    context = VisitContext(runner, source, state)
    context.visit_provider_operations = 25
    reached = []
    try:
        context.provider_call("https://official.example/limit", lambda: reached.append(True) or {"ok": True})
        raise AssertionError("visit ceiling allowed a provider call")
    except ProviderBoundary:
        pass
    assert reached == [] and runner.ledger["provider_operations"] == 0
    context.visit_provider_operations = 0
    runner.ledger["provider_operations"] = 5000
    try:
        context.provider_call("https://official.example/global", lambda: reached.append(True) or {"ok": True})
        raise AssertionError("global ceiling allowed a provider call")
    except ProviderBoundary:
        pass
    assert reached == []


# RR38-RR42: artifact delivery must be outside Git and fixture replay is sealed and zero-provider.
try:
    artifact_delivery_preflight(ROOT / "data" / "p59")
    raise AssertionError("in-repository artifact directory validated")
except CampaignValidationError:
    pass
with TemporaryDirectory() as tmp:
    delivery = artifact_delivery_preflight(Path(tmp))
    assert delivery["outside_git"] is True and delivery["writable"] is True
    sealed = deepcopy(ledger)
    sealed["sealed_live"] = True
    sealed["provider_operations"] = 0
    report = fixture_replay(MANIFEST, sealed)
    assert report["provider_operations"] == 0
    assert report["provider_operations_before"] == report["provider_operations_after"] == 0
    by_source = {row["source_id"]: row for row in report["sources"]}
    assert by_source["roots_coffee"]["status"] == "passed"
    assert len(by_source["roots_coffee"]["fixtures"]) == 8
    assert by_source["SRC-001"]["status"] == "not_available"


# RR43-RR48: a sealed canary is imported exactly once; 403 is terminal and successful canaries remain active.
with TemporaryDirectory() as tmp:
    calls = []
    adapters = {row["source_id"]: exhaust_adapter(calls) for row in ACTIVE}
    canary = RoundRobinCampaign(MANIFEST, Path(tmp) / "canary.json", {}, run_id="RR-CANARY", sleeper=lambda _: None)
    canary.set_code_identity("3" * 40, "4" * 40)
    for source in ACTIVE:
        state = canary.ledger["source_states"][source["source_id"]]
        context = VisitContext(canary, source, state)
        status = 403 if source["source_id"] == "SRC-001" else 200
        context.provider_call(
            f"https://{source['source_id'].lower()}.example/canary",
            lambda status=status: {"ok": status == 200, "status": status},
        )
        if context.access_boundary:
            state.update(state="to_be_skipped", reason=context.access_boundary)
        else:
            state.update(state="exhausted", reason="canary_only_complete")
    canary.ledger.update(sealed_live=True, stop_reason="canary_complete", ended_at="2026-09-02T00:00:00+00:00")
    canary._checkpoint()
    runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "campaign.json", adapters, run_id="RR-AFTER-CANARY", sleeper=lambda _: None)
    runner.import_prelive_canary(canary.ledger)
    assert runner.ledger["provider_operations"] == 4
    assert runner.ledger["source_states"]["SRC-001"]["state"] == "to_be_skipped"
    assert runner.ledger["source_states"]["SRC-002"]["state"] == "active"
    ledger = runner.run()
    assert "SRC-001" not in calls and calls == ["SRC-002", "SRC-004", "SRC-005"]
    assert ledger["provider_operations"] == 7
    try:
        runner.import_prelive_canary(canary.ledger)
        raise AssertionError("canary was imported twice")
    except CampaignValidationError:
        pass
    legacy = deepcopy(canary.ledger)
    legacy.pop("manifest_fingerprint")
    import hashlib
    from round_robin_campaign import canonical_json
    attestation = {
        "schema": "ku2d.multi-source-prelive-canary-attestation.v1",
        "run_id": legacy["run_id"],
        "manifest_fingerprint": runner.ledger["manifest_fingerprint"],
        "canary_ledger_canonical_sha256": hashlib.sha256(canonical_json(legacy).encode("utf-8")).hexdigest(),
    }
    legacy_runner = RoundRobinCampaign(MANIFEST, Path(tmp) / "legacy.json", {}, run_id="RR-LEGACY", sleeper=lambda _: None)
    legacy_runner.import_prelive_canary(legacy, attestation)
    assert legacy_runner.ledger["provider_operations"] == 4


# RR51-RR58: sanitized live aggregate and post-live phase records are exact, non-authorizing, and contain no live payloads.
evidence = json.loads((ROOT / "knowledge" / "v1" / "multi-source" / "KU2D-P59-RR-20260902-001.json").read_text(encoding="utf-8"))
assert evidence["selected_sources"] == MANIFEST["source_order"]
assert evidence["provider_operations"] == 107 and evidence["documented_quota"] == 0
assert evidence["accepted_unique"] == 286 and evidence["observations"] == 305
assert evidence["quality"]["unique_identity_reconciliation"] == "286/286"
assert evidence["fixture_replay"]["provider_operations"] == 0
assert evidence["export"]["outside_git"] is True
assert evidence["safety"]["production_approved"] is False
assert evidence["safety"]["scheduler_action"] is None
serialized_evidence = json.dumps(evidence, ensure_ascii=False).lower()
assert not any(marker in serialized_evidence for marker in ('"api_key"', '"authorization"', '"cookie"', '"access_token"', '"raw_payload"'))
for phase_id in ("P59-04", "P59-05", "P59-06"):
    phase = json.loads((ROOT / "knowledge" / "v1" / "multi-source" / f"KU2D-SCOPE-000006-{phase_id}.json").read_text(encoding="utf-8"))
    assert phase["scope_declaration_id"] == "KU2D-SCOPE-000006"
    assert all(phase.get(field) for field in (
        "domain", "source", "capability", "acquisition_technique",
        "authorized_files_or_modules", "explicit_out_of_scope", "validation_profile",
    ))
    assert phase["boundaries"] == {"production_approved": False, "production_store": False, "scheduler_action": None}


print("P59 multi-source round-robin deterministic tests passed (RR1-RR58).")
