from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from acquisition_quality_gate import validate_early_acquisition_quality
from adapter_registry import AdapterComponents, AdapterRegistry, validate_adapter_registry
from connector_kit import RequestPlan, ResponseEnvelope, fingerprint
from run_manifest import validate_run_manifest
from source_runner import run_source, run_source_from_manifest
from youtube_qdiving_connector import (
    PublicVideoQDivingMapper,
    YouTubeQDivingAdapter,
    YouTubeQDivingCandidateParser,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


registry_document = load(ROOT / "config" / "adapter_registry_v1.json")
run_manifest = load(ROOT / "config" / "run_manifests" / "youtube_qdiving_fixture_v1.json")
source_manifest = load(ROOT / "config" / "source_manifests" / "youtube_qdiving_v1.json")
profile = load(ROOT / "config" / "domain_capability_profiles" / "public_video_q_diving_v1.json")
packet = load(
    ROOT / "knowledge" / "v1" / "candidate-closure-packets" /
    "KU2D-YT-QDIVING-CANDIDATES-000001.json"
)
implementations = {
    "youtube_qdiving_reference_v1": AdapterComponents(
        YouTubeQDivingAdapter, YouTubeQDivingCandidateParser, PublicVideoQDivingMapper,
    )
}

# SR1: closed metadata and immutable manifest validate, then resolve explicitly.
registry = AdapterRegistry(registry_document, implementations)
validate_run_manifest(run_manifest)
resolved = registry.resolve(
    source_manifest["source_id"], run_manifest["adapter"]["adapter_id"],
    run_manifest["adapter"]["adapter_version"],
)
assert resolved.metadata["implementation_key"] == "youtube_qdiving_reference_v1"

# SR2: missing and unknown manifest/registry fields fail closed.
for invalid in (
    {key: value for key, value in run_manifest.items() if key != "run_id"},
    {**run_manifest, "unknown": True},
):
    try:
        validate_run_manifest(invalid)
        raise AssertionError("invalid run manifest shape was accepted")
    except ValueError:
        pass
version_drift = copy.deepcopy(run_manifest)
version_drift["manifest_version"] = "2.0.0"
try:
    validate_run_manifest(version_drift)
    raise AssertionError("unsupported Run Manifest version was accepted")
except ValueError as exc:
    assert "unsupported" in str(exc)
registry_version_drift = copy.deepcopy(registry_document)
registry_version_drift["registry_version"] = "2.0.0"
try:
    validate_adapter_registry(registry_version_drift)
    raise AssertionError("unsupported Adapter Registry version was accepted")
except ValueError as exc:
    assert "unsupported" in str(exc)
bad_registry = copy.deepcopy(registry_document)
bad_registry["registrations"][0]["unknown"] = True
try:
    validate_adapter_registry(bad_registry)
    raise AssertionError("unknown registry field was accepted")
except ValueError:
    pass

# SR3: immutable versions, timestamps and correction lineage fail closed on drift.
for mutate in (
    lambda row: row.update({"manifest_version": "v1"}),
    lambda row: row.update({"execution_started_at": "2026-09-01T10:59:59+00:00"}),
    lambda row: row["immutability"].update({"executed_manifest_mutation_allowed": True}),
    lambda row: row["immutability"].update({"supersedes_manifest_id": row["manifest_id"]}),
):
    invalid = copy.deepcopy(run_manifest)
    mutate(invalid)
    try:
        validate_run_manifest(invalid)
        raise AssertionError("manifest lifecycle drift was accepted")
    except ValueError:
        pass
corrected = copy.deepcopy(run_manifest)
corrected["manifest_id"] = "KU2D-RM-000001-V002"
corrected["immutability"]["supersedes_manifest_id"] = run_manifest["manifest_id"]
validate_run_manifest(corrected)

# SR4: duplicate, unknown and incompatible registry identities fail closed.
duplicate = copy.deepcopy(registry_document)
duplicate["registrations"].append(copy.deepcopy(duplicate["registrations"][0]))
try:
    validate_adapter_registry(duplicate)
    raise AssertionError("duplicate adapter registration was accepted")
except ValueError:
    pass
try:
    registry.resolve(source_manifest["source_id"], "unknown-adapter", "1.0.0")
    raise AssertionError("unknown adapter identity was accepted")
except ValueError:
    pass
incompatible = copy.deepcopy(registry_document)
incompatible["registrations"][0]["connector_contract_version"] = "2.0.0"
try:
    validate_adapter_registry(incompatible)
    raise AssertionError("incompatible connector contract was accepted")
except ValueError:
    pass

# SR5: the complete immutable fixture run is deterministic and zero-provider.
result = run_source(
    run_manifest=run_manifest,
    source_manifest=source_manifest,
    domain_capability_profile=profile,
    adapter_registry_document=registry_document,
    adapter_registry=registry,
    fixture_payloads={"KU2D-YT-QDIVING-CANDIDATES-000001": packet},
)
repeat = run_source(
    run_manifest=run_manifest,
    source_manifest=source_manifest,
    domain_capability_profile=profile,
    adapter_registry_document=registry_document,
    adapter_registry=registry,
    fixture_payloads={"KU2D-YT-QDIVING-CANDIDATES-000001": packet},
)
assert result == repeat
assert result["request_accounting"] == {
    "connector_attempts": 2,
    "provider_requests": 0,
    "documented_quota_units": 0,
}
assert result["quality_gate"]["status"] == "passed"
assert result["quality_gate"]["semantic_quality_scored"] is False
assert result["quality_gate"]["final_inclusion_decided"] is False
assert result["lifecycle"] == [
    "manifest_validated", "adapter_resolved", "connector_executed",
    "quality_gate_passed", "analysis_handoff_ready",
]
loaded_result = run_source_from_manifest(
    repository_root=ROOT,
    run_manifest=run_manifest,
    implementations=implementations,
)
assert loaded_result == result

# SR6: hash drift and fixture catalog expansion are rejected before execution.
for manifest_change, payloads in (
    (("source_manifest", "sha256"), {"KU2D-YT-QDIVING-CANDIDATES-000001": packet}),
    (("integrity", "adapter_registry_sha256"), {"KU2D-YT-QDIVING-CANDIDATES-000001": packet}),
):
    invalid = copy.deepcopy(run_manifest)
    invalid[manifest_change[0]][manifest_change[1]] = "0" * 64
    try:
        run_source(
            run_manifest=invalid, source_manifest=source_manifest,
            domain_capability_profile=profile, adapter_registry_document=registry_document,
            adapter_registry=registry, fixture_payloads=payloads,
        )
        raise AssertionError("integrity drift was accepted")
    except ValueError as exc:
        assert "fingerprint" in str(exc)
try:
    run_source(
        run_manifest=run_manifest, source_manifest=source_manifest,
        domain_capability_profile=profile, adapter_registry_document=registry_document,
        adapter_registry=registry,
        fixture_payloads={"KU2D-YT-QDIVING-CANDIDATES-000001": packet, "extra": {}},
    )
    raise AssertionError("unmanifested fixture was accepted")
except ValueError as exc:
    assert "exactly match" in str(exc)
path_escape = copy.deepcopy(run_manifest)
path_escape["source_manifest"]["path"] = "../outside.json"
try:
    run_source_from_manifest(
        repository_root=ROOT, run_manifest=path_escape, implementations=implementations,
    )
    raise AssertionError("repository path escape was accepted")
except ValueError as exc:
    assert "escapes" in str(exc)

# SR7: unsupported capabilities and authority expansion fail before transport.
invalid_capability = copy.deepcopy(run_manifest)
invalid_capability["requested_capabilities"] = ["comments"]
try:
    run_source(
        run_manifest=invalid_capability, source_manifest=source_manifest,
        domain_capability_profile=profile, adapter_registry_document=registry_document,
        adapter_registry=registry,
        fixture_payloads={"KU2D-YT-QDIVING-CANDIDATES-000001": packet},
    )
    raise AssertionError("blocked capability was executed")
except ValueError as exc:
    assert "unsupported" in str(exc)
authority_drift = copy.deepcopy(run_manifest)
authority_drift["request_policy"]["maximum_provider_requests"] = 1
try:
    validate_run_manifest(authority_drift)
    raise AssertionError("provider authority expansion was accepted")
except ValueError:
    pass

# SR8: the quality gate rejects sensitive material and exact technical duplicates.
bad_record = copy.deepcopy(result["records"][0])
bad_record["session_token"] = "forbidden"
try:
    validate_early_acquisition_quality(
        [bad_record], result["capability_evidence"], run_manifest,
    )
    raise AssertionError("sensitive mapped record was accepted")
except ValueError as exc:
    assert "sensitive field" in str(exc)
try:
    validate_early_acquisition_quality(
        [result["records"][0], copy.deepcopy(result["records"][0])],
        result["capability_evidence"], run_manifest,
    )
    raise AssertionError("exact duplicate was accepted")
except ValueError:
    pass

# SR9: a future adapter is added through metadata/composition, not runner edits.
class FutureAdapter:
    source_id = "fixture-future-source"
    adapter_id = "future-reference-adapter"
    adapter_version = "1.0.0"
    connector_contract_version = "1.0.0"
    parser_id = "future-parser.v1"
    mapper_id = "future-mapper.v1"

    def capability_declarations(self):
        return [{"capability_id": "public_identity", "state": "available"}]

    def build_request(self, capability_id):
        return RequestPlan(
            request_id="future-fixture-request", capability_id=capability_id,
            operation="fixture.replay", parameters={"fixture_id": "future-fixture"},
            max_attempts=1, quota_cost_per_attempt=0,
        )


class FutureParser:
    parser_id = "future-parser.v1"
    parser_version = "1.0.0"

    def parse(self, envelope: ResponseEnvelope):
        return list(envelope.payload["records"])


class FutureMapper:
    mapper_id = "future-mapper.v1"
    mapper_version = "1.0.0"

    def map_record(self, source_record):
        return {
            "schema": "ku2d.future-public-record.v1",
            "record_id": source_record["id"],
            "provenance": {"observed_at": source_record["observed_at"], "surface": "fixture"},
        }


future_profile = {
    "schema": "ku2d.domain-capability-profile.v1", "profile_id": "future-public.v1",
    "version": "1.0", "domain": "future_public",
    "capabilities": [{
        "capability_id": "public_identity", "state": "available", "required_for_mtc": True,
        "reason": "fixture", "evidence_refs": ["fixture"],
    }],
    "semantic_quality_owner": "analysis",
    "boundaries": {"production_approved": False, "scheduler_action": None},
}
future_source_manifest = {
    "schema": "ku2d.source-manifest.v1", "manifest_id": "KU2D-SM-FUTURE-000001",
    "source_id": "fixture-future-source", "provider": "fixture",
    "domain_profile_id": "future-public.v1", "adapter": "test.FutureAdapter",
    "parser": "test.FutureParser", "mapper": "test.FutureMapper", "access_surface": "fixture",
    "capabilities": [{"capability_id": "public_identity", "state": "available"}],
    "known_limitations": ["fixture only"], "fixture_sets": ["future-fixture"],
    "evidence_refs": ["fixture"], "integration_status": "source_lab",
    "boundaries": {"provider_requests_performed": 0, "documented_quota_units": 0, "production_store": False, "production_approved": False, "scheduler_action": None},
}
future_registry_document = copy.deepcopy(registry_document)
future_registry_document["registrations"].append({
    "source_id": "fixture-future-source", "source_manifest_id": "KU2D-SM-FUTURE-000001",
    "adapter_id": "future-reference-adapter", "adapter_version": "1.0.0",
    "parser_id": "future-parser.v1", "parser_version": "1.0.0",
    "mapper_id": "future-mapper.v1", "mapper_version": "1.0.0",
    "connector_contract_version": "1.0.0", "implementation_key": "future_reference_v1",
    "manifest_bindings": {"adapter": "test.FutureAdapter", "parser": "test.FutureParser", "mapper": "test.FutureMapper"},
    "supported_capabilities": ["public_identity"], "transport_modes": ["fixture_replay"],
})
future_fixture = {"records": [{"id": "future-1", "observed_at": "2026-09-01T11:00:00+00:00"}]}
future_run = copy.deepcopy(run_manifest)
future_run.update({"manifest_id": "KU2D-RM-000002-V001", "run_id": "KU2D-RUN-000002"})
future_run["source_manifest"] = {"manifest_id": "KU2D-SM-FUTURE-000001", "path": "fixture", "sha256": fingerprint(future_source_manifest)}
future_run["adapter"].update({
    "adapter_id": "future-reference-adapter", "parser_id": "future-parser.v1",
    "mapper_id": "future-mapper.v1",
})
future_run["domain_capability_profile"] = {"profile_id": "future-public.v1", "version": "1.0", "path": "fixture", "sha256": fingerprint(future_profile)}
future_run["requested_capabilities"] = ["public_identity"]
future_run["transport"]["fixture_id"] = "future-fixture"
future_run["fixture_references"] = [{"fixture_id": "future-fixture", "path": "fixture", "sha256": fingerprint(future_fixture)}]
future_run["integrity"]["adapter_registry_sha256"] = fingerprint(future_registry_document)
future_registry = AdapterRegistry(
    future_registry_document,
    {**implementations, "future_reference_v1": AdapterComponents(FutureAdapter, FutureParser, FutureMapper)},
)
future_result = run_source(
    run_manifest=future_run, source_manifest=future_source_manifest,
    domain_capability_profile=future_profile, adapter_registry_document=future_registry_document,
    adapter_registry=future_registry, fixture_payloads={"future-fixture": future_fixture},
)
assert [row["record_id"] for row in future_result["records"]] == ["future-1"]
assert future_result["request_accounting"]["provider_requests"] == 0

# SR10: generic modules remain source-neutral and schemas remain closed.
runner_source = (ACQUISITION / "source_runner.py").read_text(encoding="utf-8").lower()
gate_source = (ACQUISITION / "acquisition_quality_gate.py").read_text(encoding="utf-8").lower()
for forbidden in ("youtube", "tiktok", "shopee", "lazada", "watch?v=", "selector"):
    assert forbidden not in runner_source
    assert forbidden not in gate_source
for filename in ("adapter-registry.schema.json", "immutable-run-manifest.schema.json"):
    schema = load(ROOT / "knowledge" / "v1" / filename)
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["additionalProperties"] is False

print("Source Runner v1 deterministic checks passed: SR1-SR10")
