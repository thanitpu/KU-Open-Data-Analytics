"""Fail-closed validation for P57 seven-field scope declarations."""
from __future__ import annotations

import copy
from pathlib import PurePosixPath
from typing import Any, Iterable


FIELDS = {
    "schema", "declaration_id", "declaration_type", "package_id", "package_name",
    "phase_id", "phase_name", "parent_declaration_id", "human_authority_id",
    "domain", "source", "capability", "acquisition_technique",
    "authorized_files_or_modules", "explicit_out_of_scope", "validation_profile",
}
SEVEN_FIELDS = {
    "domain", "source", "capability", "acquisition_technique",
    "authorized_files_or_modules", "explicit_out_of_scope", "validation_profile",
}
TECHNIQUE_FIELDS = {
    "status", "strategy_ladder", "preferred_path", "strategy_switch_rule",
    "freeze_rule", "selected_technique",
}


def _exact(value: Any, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{name} must contain exactly {sorted(fields)}")
    return value


def _texts(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{name} must be a non-empty string array")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must be unique")
    return value


def _contains(pattern: str, candidate: str) -> bool:
    pattern = pattern.split(" (", 1)[0].replace("\\", "/")
    candidate = candidate.split(" (", 1)[0].replace("\\", "/")
    if pattern.endswith("/**"):
        root = pattern[:-3].rstrip("/")
        return candidate == root or candidate.startswith(root + "/")
    return pattern == candidate


def validate_scope_declaration(
    declaration: dict[str, Any], *, parent: dict[str, Any] | None = None,
    allowed_root_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    _exact(declaration, FIELDS, "scope declaration")
    if declaration["schema"] != "ku2d.phase-package-scope-declaration.v1":
        raise ValueError("unsupported scope declaration schema")
    for field in ("declaration_id", "package_id", "package_name", "human_authority_id"):
        if not isinstance(declaration[field], str) or not declaration[field].strip():
            raise ValueError(f"{field} is required")
    _exact(declaration["domain"], {"id", "label"}, "domain")
    _exact(declaration["source"], {"id", "label", "topics"}, "source")
    if declaration["domain"]["id"] != "social.public_short_video" or declaration["source"]["id"] != "tiktok":
        raise ValueError("P57 domain/source authority drifted")
    _texts(declaration["source"]["topics"], "source.topics")
    _texts(declaration["capability"], "capability")
    technique = _exact(declaration["acquisition_technique"], TECHNIQUE_FIELDS, "acquisition technique")
    if technique["status"] not in {"strategy_ladder_authorized", "selected", "blocked"}:
        raise ValueError("invalid acquisition technique status")
    ladder = _texts(technique["strategy_ladder"], "strategy ladder")
    selected = technique["selected_technique"]
    if technique["status"] == "selected" and selected not in ladder:
        raise ValueError("selected technique is outside the authorized ladder")
    if technique["status"] != "selected" and selected is not None:
        raise ValueError("unselected technique must be null")
    allowed = _texts(declaration["authorized_files_or_modules"], "authorized files")
    excluded = _texts(declaration["explicit_out_of_scope"], "explicit out of scope")
    _texts(declaration["validation_profile"], "validation profile")
    for item in allowed + excluded:
        path = item.split(" (", 1)[0].replace("\\", "/")
        if path.startswith(("services/", ".github/")) and (PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
            raise ValueError("scope paths must be contained repository paths")
    if declaration["declaration_type"] == "package":
        if any(declaration[key] is not None for key in ("phase_id", "phase_name", "parent_declaration_id")):
            raise ValueError("package cannot identify a phase")
        if allowed_root_files is None:
            raise ValueError("root allowlist is required")
        roots = list(allowed_root_files)
        if any(not any(_contains(root, item) for root in roots) for item in allowed):
            raise ValueError("package contains an unauthorized file")
    else:
        if parent is None:
            raise ValueError("phase requires its package declaration")
        validate_scope_declaration(parent, allowed_root_files=parent["authorized_files_or_modules"])
        if declaration["parent_declaration_id"] != parent["declaration_id"]:
            raise ValueError("phase parent mismatch")
        if declaration["package_id"] != parent["package_id"] or declaration["human_authority_id"] != parent["human_authority_id"]:
            raise ValueError("phase authority mismatch")
        if declaration["domain"] != parent["domain"] or declaration["source"] != parent["source"]:
            raise ValueError("phase domain/source widened")
        if not set(declaration["capability"]).issubset(parent["capability"]):
            raise ValueError("phase capability widened")
        if any(not any(_contains(root, item) for root in parent["authorized_files_or_modules"]) for item in allowed):
            raise ValueError("phase file scope widened")
        if not set(parent["explicit_out_of_scope"]).issubset(excluded):
            raise ValueError("phase removed an exclusion")
        if not set(declaration["validation_profile"]).issubset(parent["validation_profile"]):
            raise ValueError("phase validation widened")
        if not set(technique["strategy_ladder"]).issubset(parent["acquisition_technique"]["strategy_ladder"]):
            raise ValueError("phase strategy widened")
    return copy.deepcopy(declaration)
