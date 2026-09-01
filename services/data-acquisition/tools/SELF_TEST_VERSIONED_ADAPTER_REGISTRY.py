"""Deterministic P55 checks for versioned registry snapshots and manifest replay."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from adapter_registry import (
    AdapterComponents,
    AdapterRegistry,
    resolve_registry_snapshot,
    validate_adapter_registry,
    validate_adapter_registry_catalog,
)
from connector_kit import RequestPlan, ResponseEnvelope, fingerprint
from run_manifest import validate_manifest_lineage, validate_run_manifest
from source_runner import run_source, run_source_from_manifest
from technical_correction_journal import validate_technical_correction_journal
from youtube_qdiving_connector import (
    PublicVideoQDivingMapper,
    YouTubeQDivingAdapter,
    YouTubeQDivingCandidateParser,
)


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def reject(callable_, expected: str | None = None) -> None:
    try:
        callable_()
        raise AssertionError("invalid versioning input was accepted")
    except ValueError as exc:
        if expected is not None:
            assert expected in str(exc), str(exc)


v1_registry_path = ROOT / "config" / "adapter_registry_v1.json"
v2_registry_path = ROOT / "config" / "adapter_registry_v2.json"
catalog_path = ROOT / "config" / "adapter_registry_catalog_v1.json"
v1_manifest_path = ROOT / "config" / "run_manifests" / "youtube_qdiving_fixture_v1.json"
v2_manifest_path = ROOT / "config" / "run_manifests" / "youtube_qdiving_fixture_v2.json"

v1_registry = load(v1_registry_path)
v2_registry = load(v2_registry_path)
catalog = load(catalog_path)
v1_manifest = load(v1_manifest_path)
v2_manifest = load(v2_manifest_path)

implementations = {
    "youtube_qdiving_reference_v1": AdapterComponents(
        YouTubeQDivingAdapter,
        YouTubeQDivingCandidateParser,
        PublicVideoQDivingMapper,
    )
}

# VAR1: all four historical artifacts remain byte-identical to integration baseline ecd8614.
byte_invariants = {
    "config/adapter_registry_v1.json": (
        "398dd4daba89d5e6d3e80cb67d52984b114058d3",
        "be91ed647855424e068b0e747c60e71d15d143aeeaba806f27aa60d26c32cd7a",
    ),
    "config/run_manifests/youtube_qdiving_fixture_v1.json": (
        "80e2b6afc978542cb5a2fc75e137cd55bd656ef6",
        "6bec287d683b069fd0cbb6f65205095c4abfafca1b54d065a296c927152421f3",
    ),
    "knowledge/v1/adapter-registry.schema.json": (
        "53bda7d3f1c5d3b1765363c2c02e13a61c8f83d9",
        "469fc6f5789aaad6a69be11c9be9b03dc74fdd7790d29f7a629e5cde6fc51d42",
    ),
    "knowledge/v1/immutable-run-manifest.schema.json": (
        "e7b66d15df96cbf75fe87fa2d445d8e595ffa544",
        "1ee2a6a36dae2c87c6d2fc47e194436f28ce542dd5cbb15b06c5acb21a8665ac",
    ),
}
repository_root = ROOT.parents[1]
for relative_path, (expected_blob, expected_byte_sha256) in byte_invariants.items():
    repository_path = f"services/data-acquisition/{relative_path}"
    observed_blob = subprocess.check_output(
        ["git", "hash-object", f"--path={repository_path}", str(ROOT / relative_path)],
        cwd=repository_root,
        text=True,
    ).strip()
    assert observed_blob == expected_blob
    blob_bytes = subprocess.check_output(
        ["git", "cat-file", "blob", observed_blob], cwd=repository_root,
    )
    assert hashlib.sha256(blob_bytes).hexdigest() == expected_byte_sha256

# VAR2: v1 and v2 validators accept only their implemented versions.
assert validate_adapter_registry(v1_registry) == v1_registry
assert validate_adapter_registry(v2_registry) == v2_registry
assert validate_run_manifest(v1_manifest) == v1_manifest
assert validate_run_manifest(v2_manifest) == v2_manifest
for document, mutate, validator in (
    (v1_registry, lambda row: row.update({"registry_version": "2.0.0"}), validate_adapter_registry),
    (v2_registry, lambda row: row.update({"registry_version": "3.0.0"}), validate_adapter_registry),
    (v2_manifest, lambda row: row.update({"manifest_version": "3.0.0"}), validate_run_manifest),
):
    invalid = copy.deepcopy(document)
    mutate(invalid)
    reject(lambda invalid=invalid, validator=validator: validator(invalid), "unsupported")

# VAR3: catalog resolution is exact and has no latest/default fallback.
assert validate_adapter_registry_catalog(catalog) == catalog
v1_snapshot = resolve_registry_snapshot(catalog, "KU2D-ADAPTER-REGISTRY-V1", "1.0.0")
v2_snapshot = resolve_registry_snapshot(catalog, "KU2D-ADAPTER-REGISTRY-V2", "2.0.0")
assert v1_snapshot["sha256"] == fingerprint(v1_registry)
assert v2_snapshot["sha256"] == fingerprint(v2_registry)
for registry_id, version in (
    ("KU2D-ADAPTER-REGISTRY-V2", "1.0.0"),
    ("KU2D-ADAPTER-REGISTRY-UNKNOWN", "9.0.0"),
    ("", ""),
):
    reject(lambda registry_id=registry_id, version=version: resolve_registry_snapshot(
        catalog, registry_id, version,
    ), "not cataloged")

# VAR4: catalog shape, path containment, unique snapshots and lineage fail closed.
for mutate in (
    lambda row: row.update({"unknown": True}),
    lambda row: row["snapshots"][1].update({"path": "../adapter_registry_v2.json"}),
    lambda row: row["snapshots"][1].update({"sha256": "bad"}),
    lambda row: row["snapshots"].append(copy.deepcopy(row["snapshots"][0])),
    lambda row: row["snapshots"][1].update({"supersedes_registry_id": "missing"}),
    lambda row: row["snapshots"][0].update({"supersedes_registry_id": "KU2D-ADAPTER-REGISTRY-V2"}),
):
    invalid = copy.deepcopy(catalog)
    mutate(invalid)
    reject(lambda invalid=invalid: validate_adapter_registry_catalog(invalid))

# VAR5: V002 explicitly supersedes V001; missing links, cross-series links and cycles fail.
assert [row["manifest_id"] for row in validate_manifest_lineage([v1_manifest, v2_manifest])] == [
    "KU2D-RM-000001-V001", "KU2D-RM-000001-V002",
]
reject(lambda: validate_manifest_lineage([v2_manifest]), "missing")
cross_series = copy.deepcopy(v2_manifest)
cross_series["manifest_id"] = "KU2D-RM-000002-V002"
reject(lambda: validate_manifest_lineage([v1_manifest, cross_series]), "crosses")
cycle_v1 = copy.deepcopy(v1_manifest)
cycle_v1["immutability"]["supersedes_manifest_id"] = v2_manifest["manifest_id"]
reject(lambda: validate_manifest_lineage([cycle_v1, v2_manifest]), "cycle")

# VAR6: historical V1 and superseding V2 replay the same ten records with zero provider/quota.
v1_result = run_source_from_manifest(
    repository_root=ROOT, run_manifest=v1_manifest, implementations=implementations,
)
v2_result = run_source_from_manifest(
    repository_root=ROOT, run_manifest=v2_manifest, implementations=implementations,
)
assert len(v1_result["records"]) == len(v2_result["records"]) == 10
assert v1_result["records"] == v2_result["records"]
assert v1_result["quality_gate"] == v2_result["quality_gate"]
assert v1_result["request_accounting"]["provider_requests"] == 0
assert v2_result["request_accounting"]["provider_requests"] == 0
assert v1_result["request_accounting"]["documented_quota_units"] == 0
assert v2_result["request_accounting"]["documented_quota_units"] == 0

# VAR7: substituted, mutated, unlisted and path-drifted snapshots fail before execution.
for mutate, expected in (
    (lambda row: row["integrity"].update({"adapter_registry_sha256": "0" * 64}), "catalog snapshot"),
    (lambda row: row["integrity"].update({"adapter_registry_path": "config/adapter_registry_v1.json"}), "catalog snapshot"),
    (lambda row: row["adapter"].update({"registry_id": "KU2D-ADAPTER-REGISTRY-UNKNOWN"}), "not cataloged"),
    (lambda row: row["integrity"].update({"adapter_registry_catalog_sha256": "0" * 64}), "fingerprint"),
):
    invalid = copy.deepcopy(v2_manifest)
    mutate(invalid)
    reject(lambda invalid=invalid: run_source_from_manifest(
        repository_root=ROOT, run_manifest=invalid, implementations=implementations,
    ), expected)

with tempfile.TemporaryDirectory() as temporary_directory:
    temporary_root = Path(temporary_directory)
    copied_paths = (
        "config/adapter_registry_v2.json",
        "config/source_manifests/youtube_qdiving_v1.json",
        "config/domain_capability_profiles/public_video_q_diving_v1.json",
        "knowledge/v1/candidate-closure-packets/KU2D-YT-QDIVING-CANDIDATES-000001.json",
    )
    for relative_path in copied_paths:
        target = temporary_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative_path, target)
    mismatched_catalog = copy.deepcopy(catalog)
    mismatched_catalog["snapshots"][1]["supersedes_registry_id"] = None
    catalog_target = temporary_root / "config" / "adapter_registry_catalog_v1.json"
    catalog_target.write_text(json.dumps(mismatched_catalog), encoding="utf-8")
    mismatched_manifest = copy.deepcopy(v2_manifest)
    mismatched_manifest["integrity"]["adapter_registry_catalog_sha256"] = fingerprint(
        mismatched_catalog,
    )
    reject(lambda: run_source_from_manifest(
        repository_root=temporary_root,
        run_manifest=mismatched_manifest,
        implementations=implementations,
    ), "supersession")

# VAR8: implementation composition remains exact; no missing or surplus implementation is accepted.
reject(lambda: AdapterRegistry(v2_registry, {}), "exactly match")
reject(lambda: AdapterRegistry(v2_registry, {
    **implementations,
    "unregistered": AdapterComponents(
        YouTubeQDivingAdapter, YouTubeQDivingCandidateParser, PublicVideoQDivingMapper,
    ),
}), "exactly match")


class SyntheticAdapter:
    source_id = "synthetic-fixture-source"
    adapter_id = "synthetic-reference-adapter"
    adapter_version = "1.0.0"
    connector_contract_version = "1.0.0"
    parser_id = "synthetic-parser.v1"
    mapper_id = "synthetic-mapper.v1"

    def capability_declarations(self):
        return [{"capability_id": "public_identity", "state": "available"}]

    def build_request(self, capability_id):
        return RequestPlan(
            request_id="synthetic-fixture-request",
            capability_id=capability_id,
            operation="fixture.replay",
            parameters={"fixture_id": "synthetic-fixture"},
            max_attempts=1,
            quota_cost_per_attempt=0,
        )


class SyntheticParser:
    parser_id = "synthetic-parser.v1"
    parser_version = "1.0.0"

    def parse(self, envelope: ResponseEnvelope):
        return list(envelope.payload["records"])


class SyntheticMapper:
    mapper_id = "synthetic-mapper.v1"
    mapper_version = "1.0.0"

    def map_record(self, source_record):
        return {
            "schema": "ku2d.synthetic-public-record.v1",
            "record_id": source_record["id"],
            "provenance": {
                "observed_at": source_record["observed_at"],
                "surface": "fixture",
            },
        }


# VAR9: a synthetic second registration composes additively without source-runner edits.
synthetic_profile = {
    "schema": "ku2d.domain-capability-profile.v1",
    "profile_id": "synthetic-public.v1",
    "version": "1.0",
    "domain": "synthetic_public",
    "capabilities": [{
        "capability_id": "public_identity",
        "state": "available",
        "required_for_mtc": True,
        "reason": "fixture",
        "evidence_refs": ["fixture"],
    }],
    "semantic_quality_owner": "analysis",
    "boundaries": {"production_approved": False, "scheduler_action": None},
}
synthetic_source = {
    "schema": "ku2d.source-manifest.v1",
    "manifest_id": "KU2D-SM-SYNTHETIC-000001",
    "source_id": "synthetic-fixture-source",
    "provider": "fixture",
    "domain_profile_id": "synthetic-public.v1",
    "adapter": "test.SyntheticAdapter",
    "parser": "test.SyntheticParser",
    "mapper": "test.SyntheticMapper",
    "access_surface": "fixture",
    "capabilities": [{"capability_id": "public_identity", "state": "available"}],
    "known_limitations": ["fixture only"],
    "fixture_sets": ["synthetic-fixture"],
    "evidence_refs": ["fixture"],
    "integration_status": "source_lab",
    "boundaries": {
        "provider_requests_performed": 0,
        "documented_quota_units": 0,
        "production_store": False,
        "production_approved": False,
        "scheduler_action": None,
    },
}
synthetic_registry_document = copy.deepcopy(v2_registry)
synthetic_registry_document["registrations"].append({
    "source_id": "synthetic-fixture-source",
    "source_manifest_id": "KU2D-SM-SYNTHETIC-000001",
    "adapter_id": "synthetic-reference-adapter",
    "adapter_version": "1.0.0",
    "parser_id": "synthetic-parser.v1",
    "parser_version": "1.0.0",
    "mapper_id": "synthetic-mapper.v1",
    "mapper_version": "1.0.0",
    "connector_contract_version": "1.0.0",
    "implementation_key": "synthetic_reference_v1",
    "manifest_bindings": {
        "adapter": "test.SyntheticAdapter",
        "parser": "test.SyntheticParser",
        "mapper": "test.SyntheticMapper",
    },
    "supported_capabilities": ["public_identity"],
    "transport_modes": ["fixture_replay"],
})
synthetic_fixture = {
    "records": [{"id": "synthetic-1", "observed_at": "2026-09-01T12:45:00+00:00"}],
}
synthetic_manifest = copy.deepcopy(v2_manifest)
synthetic_manifest.update({
    "manifest_id": "KU2D-RM-000002-V002",
    "run_id": "KU2D-RUN-000003",
})
synthetic_manifest["source_manifest"] = {
    "manifest_id": synthetic_source["manifest_id"],
    "path": "fixture",
    "sha256": fingerprint(synthetic_source),
}
synthetic_manifest["adapter"].update({
    "adapter_id": "synthetic-reference-adapter",
    "parser_id": "synthetic-parser.v1",
    "mapper_id": "synthetic-mapper.v1",
})
synthetic_manifest["domain_capability_profile"] = {
    "profile_id": "synthetic-public.v1",
    "version": "1.0",
    "path": "fixture",
    "sha256": fingerprint(synthetic_profile),
}
synthetic_manifest["requested_capabilities"] = ["public_identity"]
synthetic_manifest["transport"]["fixture_id"] = "synthetic-fixture"
synthetic_manifest["fixture_references"] = [{
    "fixture_id": "synthetic-fixture",
    "path": "fixture",
    "sha256": fingerprint(synthetic_fixture),
}]
synthetic_manifest["integrity"]["adapter_registry_sha256"] = fingerprint(
    synthetic_registry_document,
)
synthetic_manifest["immutability"]["supersedes_manifest_id"] = "KU2D-RM-000002-V001"
synthetic_registry = AdapterRegistry(
    synthetic_registry_document,
    {
        **implementations,
        "synthetic_reference_v1": AdapterComponents(
            SyntheticAdapter, SyntheticParser, SyntheticMapper,
        ),
    },
)
synthetic_result = run_source(
    run_manifest=synthetic_manifest,
    source_manifest=synthetic_source,
    domain_capability_profile=synthetic_profile,
    adapter_registry_document=synthetic_registry_document,
    adapter_registry=synthetic_registry,
    fixture_payloads={"synthetic-fixture": synthetic_fixture},
)
assert [row["record_id"] for row in synthetic_result["records"]] == ["synthetic-1"]
assert synthetic_result["request_accounting"]["provider_requests"] == 0
assert synthetic_result["request_accounting"]["documented_quota_units"] == 0

# VAR10: additive schemas are closed; v1 schemas remain the historical contracts.
for filename in (
    "adapter-registry-v2.schema.json",
    "adapter-registry-catalog.schema.json",
    "immutable-run-manifest-v2.schema.json",
):
    schema = load(ROOT / "knowledge" / "v1" / filename)
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["additionalProperties"] is False
assert load(ROOT / "knowledge" / "v1" / "adapter-registry.schema.json")["properties"]["schema"] == {
    "const": "ku2d.adapter-registry.v1",
}
assert load(ROOT / "knowledge" / "v1" / "immutable-run-manifest.schema.json")["properties"]["schema"] == {
    "const": "ku2d.immutable-run-manifest.v1",
}

# VAR11: durable declaration, migration evidence and the active correction journal are exact.
scope = load(ROOT / "knowledge" / "v1" / "registry-migrations" / "KU2D-SCOPE-000002.json")
assert set(scope) == {
    "schema", "declaration_id", "package_id", "package_name", "package_declaration",
    "phase_declarations", "rules",
}
required_declaration_fields = {
    "domain", "source", "capability", "acquisition_technique",
    "authorized_files_or_modules", "explicit_out_of_scope", "validation_profile",
}
assert set(scope["package_declaration"]) == required_declaration_fields
assert [row["phase_id"] for row in scope["phase_declarations"]] == [
    "P55-01", "P55-02", "P55-03", "P55-04",
]
assert all(set(row) == {"phase_id", "phase", "declaration"} for row in scope["phase_declarations"])
assert all(set(row["declaration"]) == required_declaration_fields for row in scope["phase_declarations"])
assert scope["package_declaration"]["acquisition_technique"]["provider_requests"] == 0
assert all(row["declaration"]["acquisition_technique"]["provider_requests"] == 0 for row in scope["phase_declarations"])

migration = load(ROOT / "knowledge" / "v1" / "registry-migrations" / "KU2D-RMIG-000001.json")
assert set(migration) == {
    "schema", "migration_id", "prompt_id", "scope_declaration_id", "created_at",
    "integration_baseline", "historical_invariants", "registry_migration",
    "manifest_migration", "scope_audit", "validation", "boundaries",
}
assert migration["registry_migration"]["catalog_sha256"] == fingerprint(catalog)
assert migration["registry_migration"]["default_to_latest"] is False
assert migration["manifest_migration"]["historical_manifest_retargeted"] is False
assert migration["scope_audit"]["declared_scope_equals_actual_scope"] is True
assert migration["scope_audit"]["unauthorized_changed_paths"] == []
assert migration["scope_audit"]["read_only_invariant_changes"] == []
assert migration["validation"] == {
    "v1_record_count": 10,
    "v2_record_count": 10,
    "record_parity": True,
    "synthetic_additive_registration": True,
    "provider_requests": 0,
    "documented_quota_units": 0,
    "semantic_quality_scored": False,
}
journal = load(ROOT / "knowledge" / "v1" / "correction-journals" / "KU2D-CJ-000005.json")
validate_technical_correction_journal(journal, require_closed=True)
assert journal["summary"] == {
    "event_count": 4, "resolved_count": 4,
    "unresolved_count": 0, "correction_cycles_used": 4,
}
assert all(event["provider_impact"] == {
    "provider_reached": False, "request_delta": 0, "quota_delta": 0,
} for event in journal["events"])
assert all(
    event["related_commit_or_pending_commit"]
    == "a6c02b17424bc883f0424fca69b9344422f23fa1"
    for event in journal["events"][:3]
)
assert (
    journal["events"][3]["related_commit_or_pending_commit"]
    == "3cd96eb30499b9bae62c56990d0b6472c4f1dac7"
)

print("Versioned Adapter Registry deterministic checks passed: VAR1-VAR11")
