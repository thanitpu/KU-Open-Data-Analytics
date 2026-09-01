"""Fail-closed validators for immutable, versioned KU2D Run Manifests."""
from __future__ import annotations

import copy
import re
from datetime import datetime
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
RUN_ID = re.compile(r"^KU2D-RUN-[0-9]{6}$")
MANIFEST_ID = re.compile(r"^KU2D-RM-[0-9]{6}-V[0-9]{3}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?$")
TOP_FIELDS = {
    "schema", "manifest_id", "manifest_version", "run_id", "created_at",
    "execution_started_at", "source_manifest", "adapter",
    "domain_capability_profile", "requested_capabilities", "transport",
    "fixture_references", "evidence_references", "request_policy", "integrity",
    "authority_boundaries", "immutability",
}


def _exact(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        missing = sorted(fields - set(value)) if isinstance(value, dict) else sorted(fields)
        unknown = sorted(set(value) - fields) if isinstance(value, dict) else []
        raise ValueError(f"{name} fields are invalid; missing={missing}, unknown={unknown}")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be RFC 3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _version(value: Any, name: str) -> str:
    text = _text(value, name)
    if not VERSION.fullmatch(text):
        raise ValueError(f"{name} must be a semantic version")
    return text


def _unique_texts(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must contain unique values")
    return value


def validate_run_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = _exact(manifest, TOP_FIELDS, "run manifest")
    schema = manifest["schema"]
    if schema == "ku2d.immutable-run-manifest.v1":
        expected_version = "1.0.0"
    elif schema == "ku2d.immutable-run-manifest.v2":
        expected_version = "2.0.0"
    else:
        raise ValueError("invalid or unsupported immutable run manifest schema")
    if not isinstance(manifest["manifest_id"], str) or not MANIFEST_ID.fullmatch(manifest["manifest_id"]):
        raise ValueError("manifest_id is invalid")
    _version(manifest["manifest_version"], "manifest_version")
    if manifest["manifest_version"] != expected_version:
        raise ValueError("Run Manifest runtime version is unsupported")
    if not isinstance(manifest["run_id"], str) or not RUN_ID.fullmatch(manifest["run_id"]):
        raise ValueError("run_id is invalid")
    created_at = _timestamp(manifest["created_at"], "created_at")
    started_at = _timestamp(manifest["execution_started_at"], "execution_started_at")
    if started_at < created_at:
        raise ValueError("execution_started_at cannot precede created_at")

    source = _exact(manifest["source_manifest"], {"manifest_id", "path", "sha256"}, "source_manifest")
    _text(source["manifest_id"], "source_manifest.manifest_id")
    _text(source["path"], "source_manifest.path")
    _sha(source["sha256"], "source_manifest.sha256")

    adapter = _exact(
        manifest["adapter"],
        {
            "registry_id", "registry_version", "adapter_id", "adapter_version",
            "parser_id", "parser_version", "mapper_id", "mapper_version",
            "connector_contract_version",
        },
        "adapter",
    )
    for field in ("registry_id", "adapter_id", "parser_id", "mapper_id"):
        _text(adapter[field], f"adapter.{field}")
    for field in (
        "registry_version", "adapter_version", "parser_version", "mapper_version",
        "connector_contract_version",
    ):
        _version(adapter[field], f"adapter.{field}")

    profile = _exact(
        manifest["domain_capability_profile"], {"profile_id", "version", "path", "sha256"},
        "domain_capability_profile",
    )
    for field in ("profile_id", "path"):
        _text(profile[field], f"domain_capability_profile.{field}")
    _version(profile["version"], "domain_capability_profile.version")
    _sha(profile["sha256"], "domain_capability_profile.sha256")
    _unique_texts(manifest["requested_capabilities"], "requested_capabilities")

    transport = _exact(manifest["transport"], {"mode", "fixture_id"}, "transport")
    if transport["mode"] != "fixture_replay":
        raise ValueError("Run Manifest v1 permits deterministic fixture_replay only")
    _text(transport["fixture_id"], "transport.fixture_id")
    fixtures = manifest["fixture_references"]
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixture_references must be a non-empty array")
    fixture_ids: set[str] = set()
    for index, fixture in enumerate(fixtures):
        fixture = _exact(fixture, {"fixture_id", "path", "sha256"}, f"fixture_references[{index}]")
        fixture_id = _text(fixture["fixture_id"], "fixture_id")
        if fixture_id in fixture_ids:
            raise ValueError("fixture identifiers must be unique")
        fixture_ids.add(fixture_id)
        _text(fixture["path"], "fixture path")
        _sha(fixture["sha256"], "fixture sha256")
    if transport["fixture_id"] not in fixture_ids:
        raise ValueError("transport fixture is not pinned")
    _unique_texts(manifest["evidence_references"], "evidence_references")

    policy = _exact(
        manifest["request_policy"],
        {
            "maximum_attempts_per_capability", "maximum_provider_requests",
            "maximum_documented_quota_units", "credential_required", "allow_live_provider",
        },
        "request_policy",
    )
    if policy != {
        "maximum_attempts_per_capability": 1,
        "maximum_provider_requests": 0,
        "maximum_documented_quota_units": 0,
        "credential_required": False,
        "allow_live_provider": False,
    }:
        raise ValueError("request policy exceeds fixture-only authority")
    integrity_fields = {"adapter_registry_path", "adapter_registry_sha256"}
    if schema == "ku2d.immutable-run-manifest.v2":
        integrity_fields |= {
            "adapter_registry_catalog_path", "adapter_registry_catalog_sha256",
        }
    integrity = _exact(manifest["integrity"], integrity_fields, "integrity")
    _text(integrity["adapter_registry_path"], "adapter_registry_path")
    _sha(integrity["adapter_registry_sha256"], "adapter_registry_sha256")
    if schema == "ku2d.immutable-run-manifest.v2":
        _text(integrity["adapter_registry_catalog_path"], "adapter_registry_catalog_path")
        _sha(integrity["adapter_registry_catalog_sha256"], "adapter_registry_catalog_sha256")
    if manifest["authority_boundaries"] != {
        "semantic_quality_owner": "analysis",
        "production_store": False,
        "production_approved": False,
        "scheduler_action": None,
    }:
        raise ValueError("authority boundaries are not fail-closed")
    immutability = _exact(
        manifest["immutability"],
        {"executed_manifest_mutation_allowed", "correction_mode", "supersedes_manifest_id"},
        "immutability",
    )
    if (
        immutability["executed_manifest_mutation_allowed"] is not False
        or immutability["correction_mode"] != "new_manifest_version"
    ):
        raise ValueError("manifest immutability contract is invalid")
    supersedes = immutability["supersedes_manifest_id"]
    if supersedes is not None and (
        not isinstance(supersedes, str)
        or not MANIFEST_ID.fullmatch(supersedes)
        or supersedes == manifest["manifest_id"]
    ):
        raise ValueError("superseded manifest identity is invalid")
    if schema == "ku2d.immutable-run-manifest.v2" and supersedes is None:
        raise ValueError("Run Manifest v2 requires explicit supersession lineage")
    return copy.deepcopy(manifest)


def validate_manifest_lineage(manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate an explicit, closed manifest lineage and reject missing links or cycles."""
    if not isinstance(manifests, list) or not manifests:
        raise ValueError("manifest lineage must be a non-empty array")
    validated = [validate_run_manifest(manifest) for manifest in manifests]
    by_id: dict[str, dict[str, Any]] = {}
    for manifest in validated:
        manifest_id = manifest["manifest_id"]
        if manifest_id in by_id:
            raise ValueError("manifest lineage contains duplicate identities")
        by_id[manifest_id] = manifest
    for manifest in validated:
        supersedes = manifest["immutability"]["supersedes_manifest_id"]
        if supersedes is None:
            continue
        if supersedes not in by_id:
            raise ValueError("manifest supersession target is missing")
        current_series = manifest["manifest_id"].rsplit("-V", 1)[0]
        prior_series = supersedes.rsplit("-V", 1)[0]
        if current_series != prior_series:
            raise ValueError("manifest supersession crosses identity series")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(manifest_id: str) -> None:
        if manifest_id in visiting:
            raise ValueError("manifest supersession cycle detected")
        if manifest_id in visited:
            return
        visiting.add(manifest_id)
        supersedes = by_id[manifest_id]["immutability"]["supersedes_manifest_id"]
        if supersedes is not None:
            visit(supersedes)
        visiting.remove(manifest_id)
        visited.add(manifest_id)

    for manifest_id in by_id:
        visit(manifest_id)
    return copy.deepcopy(validated)
