"""Closed Adapter Registry v1 with explicit, allowlisted implementations."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping


VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
REGISTRY_FIELDS = {
    "schema", "registry_id", "registry_version", "connector_contract_version",
    "registrations", "boundaries",
}
REGISTRATION_FIELDS = {
    "source_id", "source_manifest_id", "adapter_id", "adapter_version",
    "parser_id", "parser_version", "mapper_id", "mapper_version",
    "connector_contract_version", "implementation_key", "manifest_bindings",
    "supported_capabilities", "transport_modes",
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


@dataclass(frozen=True)
class AdapterComponents:
    adapter_factory: Callable[[], Any]
    parser_factory: Callable[[], Any]
    mapper_factory: Callable[[], Any]


@dataclass(frozen=True)
class ResolvedAdapter:
    metadata: dict[str, Any]
    adapter: Any
    parser: Any
    mapper: Any


def validate_adapter_registry(document: dict[str, Any]) -> dict[str, Any]:
    document = _exact(document, REGISTRY_FIELDS, "adapter registry")
    if document["schema"] != "ku2d.adapter-registry.v1":
        raise ValueError("invalid Adapter Registry v1 schema")
    _text(document["registry_id"], "registry_id")
    _version(document["registry_version"], "registry_version")
    _version(document["connector_contract_version"], "connector_contract_version")
    if document["registry_version"] != "1.0.0" or document["connector_contract_version"] != "1.0.0":
        raise ValueError("Adapter Registry v1 runtime version is unsupported")
    if document["boundaries"] != {
        "dynamic_imports": False,
        "production_approved": False,
        "scheduler_action": None,
    }:
        raise ValueError("adapter registry boundaries are not fail-closed")
    rows = document["registrations"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("registrations must be a non-empty array")
    identities: set[tuple[str, str, str]] = set()
    source_manifests: set[str] = set()
    implementation_keys: set[str] = set()
    for index, row in enumerate(rows):
        row = _exact(row, REGISTRATION_FIELDS, f"registrations[{index}]")
        for field in (
            "source_id", "source_manifest_id", "adapter_id", "parser_id",
            "mapper_id", "implementation_key",
        ):
            _text(row[field], f"registrations[{index}].{field}")
        for field in (
            "adapter_version", "parser_version", "mapper_version",
            "connector_contract_version",
        ):
            _version(row[field], f"registrations[{index}].{field}")
        if row["connector_contract_version"] != document["connector_contract_version"]:
            raise ValueError("registration contract version is incompatible")
        bindings = _exact(
            row["manifest_bindings"], {"adapter", "parser", "mapper"},
            f"registrations[{index}].manifest_bindings",
        )
        for field in bindings:
            _text(bindings[field], f"registrations[{index}].manifest_bindings.{field}")
        _unique_texts(row["supported_capabilities"], "supported_capabilities")
        modes = _unique_texts(row["transport_modes"], "transport_modes")
        if any(mode not in {"fixture_replay", "live_official_api"} for mode in modes):
            raise ValueError("registration transport mode is unsupported")
        identity = (row["source_id"], row["adapter_id"], row["adapter_version"])
        if identity in identities or row["source_manifest_id"] in source_manifests:
            raise ValueError("duplicate adapter registration")
        if row["implementation_key"] in implementation_keys:
            raise ValueError("duplicate implementation key")
        identities.add(identity)
        source_manifests.add(row["source_manifest_id"])
        implementation_keys.add(row["implementation_key"])
    return copy.deepcopy(document)


class AdapterRegistry:
    """Resolve only metadata registered against an explicit implementation catalog."""

    def __init__(
        self,
        document: dict[str, Any],
        implementations: Mapping[str, AdapterComponents],
    ) -> None:
        self.document = validate_adapter_registry(document)
        self._implementations = dict(implementations)
        registered = {row["implementation_key"] for row in self.document["registrations"]}
        if set(self._implementations) != registered:
            raise ValueError("implementation catalog must exactly match registered keys")
        self._rows = {
            (row["source_id"], row["adapter_id"], row["adapter_version"]): row
            for row in self.document["registrations"]
        }

    def resolve(self, source_id: str, adapter_id: str, adapter_version: str) -> ResolvedAdapter:
        row = self._rows.get((source_id, adapter_id, adapter_version))
        if row is None:
            raise ValueError("adapter identity is not registered")
        components = self._implementations[row["implementation_key"]]
        adapter = components.adapter_factory()
        parser = components.parser_factory()
        mapper = components.mapper_factory()
        observed = {
            "source_id": getattr(adapter, "source_id", None),
            "adapter_id": getattr(adapter, "adapter_id", None),
            "adapter_version": getattr(adapter, "adapter_version", None),
            "connector_contract_version": getattr(adapter, "connector_contract_version", None),
            "parser_id": getattr(parser, "parser_id", None),
            "parser_version": getattr(parser, "parser_version", None),
            "mapper_id": getattr(mapper, "mapper_id", None),
            "mapper_version": getattr(mapper, "mapper_version", None),
        }
        expected = {key: row[key] for key in observed}
        if observed != expected:
            raise ValueError("registered implementation identity drifted from metadata")
        return ResolvedAdapter(copy.deepcopy(row), adapter, parser, mapper)
