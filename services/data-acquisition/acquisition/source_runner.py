"""Authoritative source-neutral execution path for immutable Run Manifest v1."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from acquisition_quality_gate import validate_early_acquisition_quality
from adapter_registry import AdapterComponents, AdapterRegistry
from connector_kit import (
    ConnectorKit,
    FixtureReplayTransport,
    fingerprint,
    validate_domain_capability_profile,
    validate_source_manifest,
)
from run_manifest import validate_run_manifest


EXECUTABLE_STATES = {"available", "partial", "unverified"}


def _load_pinned_json(root: Path, relative_path: str, name: str) -> dict[str, Any]:
    if not isinstance(relative_path, str) or not relative_path or Path(relative_path).is_absolute():
        raise ValueError(f"{name} path must be repository-relative")
    resolved_root = root.resolve()
    resolved_path = (resolved_root / relative_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"{name} path escapes the repository root")
    try:
        value = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is unavailable or invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _assert_fingerprint(value: Any, expected: str, name: str) -> None:
    if fingerprint(value) != expected:
        raise ValueError(f"{name} fingerprint does not match the immutable manifest")


def _merge_exact_records(capability_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse exact cross-capability replays; reject conflicting identities."""
    ordered: list[dict[str, Any]] = []
    by_identity: dict[str, str] = {}
    for result in capability_results:
        for record in result["domain_records"]:
            identity = record.get("record_id")
            if not isinstance(identity, str) or not identity:
                raise ValueError("mapped record identity is missing")
            record_hash = fingerprint(record)
            prior = by_identity.get(identity)
            if prior is None:
                by_identity[identity] = record_hash
                ordered.append(copy.deepcopy(record))
            elif prior != record_hash:
                raise ValueError("same technical identity produced conflicting records")
    return ordered


def run_source(
    *,
    run_manifest: dict[str, Any],
    source_manifest: dict[str, Any],
    domain_capability_profile: dict[str, Any],
    adapter_registry_document: dict[str, Any],
    adapter_registry: AdapterRegistry,
    fixture_payloads: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute one fixture-pinned manifest without source-specific runner logic."""
    run_manifest = validate_run_manifest(run_manifest)
    profile = validate_domain_capability_profile(domain_capability_profile)
    source_manifest = validate_source_manifest(source_manifest, profile)
    if adapter_registry.document != adapter_registry_document:
        raise ValueError("adapter registry instance does not match supplied metadata")
    _assert_fingerprint(source_manifest, run_manifest["source_manifest"]["sha256"], "source manifest")
    _assert_fingerprint(
        profile, run_manifest["domain_capability_profile"]["sha256"], "domain capability profile",
    )
    _assert_fingerprint(
        adapter_registry_document,
        run_manifest["integrity"]["adapter_registry_sha256"],
        "adapter registry",
    )
    if source_manifest["manifest_id"] != run_manifest["source_manifest"]["manifest_id"]:
        raise ValueError("source manifest identity mismatch")
    profile_ref = run_manifest["domain_capability_profile"]
    if profile["profile_id"] != profile_ref["profile_id"] or profile["version"] != profile_ref["version"]:
        raise ValueError("domain capability profile identity mismatch")
    adapter_ref = run_manifest["adapter"]
    if (
        adapter_ref["registry_id"] != adapter_registry_document["registry_id"]
        or adapter_ref["registry_version"] != adapter_registry_document["registry_version"]
    ):
        raise ValueError("adapter registry version drift")
    resolved = adapter_registry.resolve(
        source_manifest["source_id"], adapter_ref["adapter_id"], adapter_ref["adapter_version"],
    )
    metadata = resolved.metadata
    expected_adapter_ref = {
        "registry_id": adapter_registry_document["registry_id"],
        "registry_version": adapter_registry_document["registry_version"],
        "adapter_id": metadata["adapter_id"],
        "adapter_version": metadata["adapter_version"],
        "parser_id": metadata["parser_id"],
        "parser_version": metadata["parser_version"],
        "mapper_id": metadata["mapper_id"],
        "mapper_version": metadata["mapper_version"],
        "connector_contract_version": metadata["connector_contract_version"],
    }
    if adapter_ref != expected_adapter_ref:
        raise ValueError("run manifest adapter contract drift")
    if metadata["source_manifest_id"] != source_manifest["manifest_id"]:
        raise ValueError("registered source manifest identity mismatch")
    if metadata["manifest_bindings"] != {
        "adapter": source_manifest["adapter"],
        "parser": source_manifest["parser"],
        "mapper": source_manifest["mapper"],
    }:
        raise ValueError("source manifest implementation binding drift")
    if run_manifest["transport"]["mode"] not in metadata["transport_modes"]:
        raise ValueError("transport mode is not registered")
    requested = run_manifest["requested_capabilities"]
    supported = set(metadata["supported_capabilities"])
    profile_states = {row["capability_id"]: row["state"] for row in profile["capabilities"]}
    source_states = {row["capability_id"]: row["state"] for row in source_manifest["capabilities"]}
    for capability_id in requested:
        if (
            capability_id not in supported
            or profile_states.get(capability_id) not in EXECUTABLE_STATES
            or source_states.get(capability_id) not in EXECUTABLE_STATES
        ):
            raise ValueError("requested capability is unsupported or outside authority")

    fixture_id = run_manifest["transport"]["fixture_id"]
    fixture_ref = next(
        row for row in run_manifest["fixture_references"] if row["fixture_id"] == fixture_id
    )
    if set(fixture_payloads) != {fixture_id}:
        raise ValueError("fixture payload catalog must exactly match the run manifest")
    fixture_payload = fixture_payloads[fixture_id]
    _assert_fingerprint(fixture_payload, fixture_ref["sha256"], "fixture")
    transport = FixtureReplayTransport(
        {fixture_id: fixture_payload}, observed_at=run_manifest["execution_started_at"],
    )
    kit = ConnectorKit(credentials={})
    capability_results: list[dict[str, Any]] = []
    for capability_id in requested:
        result = kit.execute(
            resolved.adapter, resolved.parser, resolved.mapper, capability_id, transport,
        )
        request_plan = result["evidence"]["request_plan"]
        if (
            request_plan["max_attempts"] > run_manifest["request_policy"]["maximum_attempts_per_capability"]
            or request_plan["credential_required"]
            or request_plan["operation"] != "fixture.replay"
        ):
            raise ValueError("adapter request plan exceeds immutable run policy")
        capability_results.append(result)
    records = _merge_exact_records(capability_results)
    evidence = {
        capability_id: result["evidence"]
        for capability_id, result in zip(requested, capability_results)
    }
    quality_gate = validate_early_acquisition_quality(records, evidence, run_manifest)
    connector_attempts = sum(len(result["request_ledger"]) for result in capability_results)
    quota_units = sum(result["evidence"]["documented_quota_units"] for result in capability_results)
    if quota_units != 0:
        raise ValueError("fixture replay unexpectedly consumed quota")
    output = {
        "schema": "ku2d.source-run-result.v1",
        "run_id": run_manifest["run_id"],
        "run_manifest_id": run_manifest["manifest_id"],
        "run_manifest_sha256": fingerprint(run_manifest),
        "adapter_registry_sha256": fingerprint(adapter_registry_document),
        "source_manifest_id": source_manifest["manifest_id"],
        "domain_capability_profile_id": profile["profile_id"],
        "adapter_identity": {
            "adapter_id": metadata["adapter_id"],
            "adapter_version": metadata["adapter_version"],
            "parser_id": metadata["parser_id"],
            "parser_version": metadata["parser_version"],
            "mapper_id": metadata["mapper_id"],
            "mapper_version": metadata["mapper_version"],
        },
        "transport_mode": "fixture_replay",
        "requested_capabilities": list(requested),
        "records": records,
        "capability_evidence": evidence,
        "quality_gate": quality_gate,
        "lifecycle": [
            "manifest_validated",
            "adapter_resolved",
            "connector_executed",
            "quality_gate_passed",
            "analysis_handoff_ready",
        ],
        "request_accounting": {
            "connector_attempts": connector_attempts,
            "provider_requests": 0,
            "documented_quota_units": 0,
        },
        "boundaries": {
            "semantic_quality_owner": "analysis",
            "production_store": False,
            "production_approved": False,
            "scheduler_action": None,
        },
    }
    return copy.deepcopy(output)


def run_source_from_manifest(
    *,
    repository_root: Path,
    run_manifest: dict[str, Any],
    implementations: Mapping[str, AdapterComponents],
) -> dict[str, Any]:
    """Load every pinned repository reference before executing the generic path."""
    validated = validate_run_manifest(run_manifest)
    source_manifest = _load_pinned_json(
        repository_root, validated["source_manifest"]["path"], "source manifest",
    )
    profile = _load_pinned_json(
        repository_root, validated["domain_capability_profile"]["path"],
        "domain capability profile",
    )
    registry_document = _load_pinned_json(
        repository_root, validated["integrity"]["adapter_registry_path"], "adapter registry",
    )
    fixtures = {
        row["fixture_id"]: _load_pinned_json(
            repository_root, row["path"], f"fixture {row['fixture_id']}",
        )
        for row in validated["fixture_references"]
    }
    registry = AdapterRegistry(registry_document, implementations)
    return run_source(
        run_manifest=validated,
        source_manifest=source_manifest,
        domain_capability_profile=profile,
        adapter_registry_document=registry_document,
        adapter_registry=registry,
        fixture_payloads=fixtures,
    )
