"""Pure fail-closed validation for KU2D Phase/Package Scope Declaration v1."""
from __future__ import annotations

import copy
import re
from pathlib import PurePosixPath
from typing import Any, Iterable


SCHEMA = "ku2d.phase-package-scope-declaration.v1"
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
REQUIRED_VALIDATION_GATES = {
    "definition and seven-field scope declaration",
    "contract/schema validation",
    "isolated feature branch",
    "diff and invariant-byte check",
    "source integration and evidence validation",
    "bounded public live smoke only when necessary",
    "exact-head full deterministic corpus",
    "PR approval and CI",
    "squash merge to integration",
    "post-merge verification",
}
DECLARATION_ID = re.compile(r"^KU2D-SCOPE-[0-9]{6}(?:-P[0-9]{2})?$")
PACKAGE_ID = re.compile(r"^KU2D-P-[0-9]{6}$")
PHASE_ID = re.compile(r"^P[0-9]{2}-[0-9]{2}$")
HUMAN_ID = re.compile(r"^KU2D-H-[0-9]{6}$")


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


def _unique_texts(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must contain unique values")
    return value


def _path_part(value: str) -> str:
    return value.split(" (", 1)[0].replace("\\", "/")


def _contains(pattern: str, candidate: str) -> bool:
    pattern, candidate = _path_part(pattern), _path_part(candidate)
    if pattern.endswith("/**"):
        root = pattern[:-3].rstrip("/")
        return candidate == root or candidate.startswith(root + "/")
    return pattern == candidate


def _validate_paths(paths: list[str], name: str) -> None:
    for raw in paths:
        path = _path_part(raw)
        if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
            raise ValueError(f"{name} paths must be repository-relative")
        if ".." in PurePosixPath(path).parts:
            raise ValueError(f"{name} paths may not traverse parents")


def _validate_shape(declaration: dict[str, Any]) -> None:
    _exact(declaration, FIELDS, "scope declaration")
    if declaration["schema"] != SCHEMA:
        raise ValueError("invalid Phase/Package Scope Declaration v1 schema")
    if not DECLARATION_ID.fullmatch(_text(declaration["declaration_id"], "declaration_id")):
        raise ValueError("declaration_id is invalid")
    if declaration["declaration_type"] not in {"package", "phase"}:
        raise ValueError("declaration_type is invalid")
    if not PACKAGE_ID.fullmatch(_text(declaration["package_id"], "package_id")):
        raise ValueError("package_id is invalid")
    _text(declaration["package_name"], "package_name")
    if not HUMAN_ID.fullmatch(_text(declaration["human_authority_id"], "human_authority_id")):
        raise ValueError("human_authority_id is invalid")
    _exact(declaration["domain"], {"id", "label"}, "domain")
    _text(declaration["domain"]["id"], "domain.id")
    _text(declaration["domain"]["label"], "domain.label")
    _exact(declaration["source"], {"id", "label", "topics"}, "source")
    _text(declaration["source"]["id"], "source.id")
    _text(declaration["source"]["label"], "source.label")
    _unique_texts(declaration["source"]["topics"], "source.topics")
    _unique_texts(declaration["capability"], "capability")
    technique = _exact(
        declaration["acquisition_technique"],
        {"status", "strategy_ladder", "selected_technique", "freeze_rule"},
        "acquisition_technique",
    )
    if technique["status"] not in {
        "to_be_selected_by_bounded_source_lab", "selected", "externally_blocked",
    }:
        raise ValueError("acquisition_technique.status is invalid")
    _unique_texts(technique["strategy_ladder"], "acquisition_technique.strategy_ladder")
    _text(technique["freeze_rule"], "acquisition_technique.freeze_rule")
    selected = technique["selected_technique"]
    if technique["status"] == "selected":
        _text(selected, "acquisition_technique.selected_technique")
    elif selected is not None:
        raise ValueError("selected_technique must be null until the technique is selected")
    authorized = _unique_texts(
        declaration["authorized_files_or_modules"], "authorized_files_or_modules",
    )
    out_of_scope = _unique_texts(declaration["explicit_out_of_scope"], "explicit_out_of_scope")
    _validate_paths([item for item in authorized if item.startswith(("services/", ".github/"))], "authorized")
    _validate_paths([item for item in out_of_scope if item.startswith(("services/", ".github/"))], "out-of-scope")
    for allowed in authorized:
        if any(_contains(blocked, allowed) or _contains(allowed, blocked) for blocked in out_of_scope):
            raise ValueError(f"authorized scope overlaps explicit out-of-scope: {allowed}")
    validation = set(_unique_texts(declaration["validation_profile"], "validation_profile"))
    missing_gates = sorted(REQUIRED_VALIDATION_GATES - validation)
    if missing_gates:
        raise ValueError(f"validation profile is missing required gates: {missing_gates}")
    if not any(item.startswith("unit and ") and item.endswith(" fixture tests") for item in validation):
        raise ValueError("validation profile is missing the source-specific fixture-test gate")
    if declaration["declaration_type"] == "package":
        if any(declaration[field] is not None for field in ("phase_id", "phase_name", "parent_declaration_id")):
            raise ValueError("package declaration cannot identify a phase or parent")
    else:
        if not PHASE_ID.fullmatch(_text(declaration["phase_id"], "phase_id")):
            raise ValueError("phase_id is invalid")
        _text(declaration["phase_name"], "phase_name")
        parent_id = _text(declaration["parent_declaration_id"], "parent_declaration_id")
        if not re.fullmatch(r"KU2D-SCOPE-[0-9]{6}", parent_id):
            raise ValueError("parent_declaration_id is invalid")


def validate_scope_declaration(
    declaration: dict[str, Any], *, parent: dict[str, Any] | None = None,
    allowed_root_files: Iterable[str] | None = None,
    allowed_human_authority_ids: Iterable[str],
) -> dict[str, Any]:
    """Validate shape, Human authority and non-expanding inheritance."""
    _validate_shape(declaration)
    authorities = set(allowed_human_authority_ids)
    if declaration["human_authority_id"] not in authorities:
        raise ValueError("scope declaration lacks current Human authority")
    if parent is None:
        if declaration["declaration_type"] != "package":
            raise ValueError("a root declaration must be a package")
        if allowed_root_files is None:
            raise ValueError("root authorization allowlist is required")
        allowlist = list(allowed_root_files)
        for candidate in declaration["authorized_files_or_modules"]:
            if not any(_contains(allowed, candidate) for allowed in allowlist):
                raise ValueError(f"unauthorized file or module: {candidate}")
        return copy.deepcopy(declaration)

    _validate_shape(parent)
    if parent["declaration_type"] != "package":
        raise ValueError("phase parent must be a package declaration")
    if declaration["declaration_type"] != "phase":
        raise ValueError("child declaration must be a phase")
    if declaration["parent_declaration_id"] != parent["declaration_id"]:
        raise ValueError("phase parent declaration does not match")
    if declaration["package_id"] != parent["package_id"] or declaration["package_name"] != parent["package_name"]:
        raise ValueError("phase package identity is broader than its parent")
    if declaration["human_authority_id"] != parent["human_authority_id"]:
        raise ValueError("phase scope changed without matching Human authority")
    if declaration["domain"] != parent["domain"]:
        raise ValueError("phase domain may not differ from package authority")
    if declaration["source"]["id"] != parent["source"]["id"] or declaration["source"]["label"] != parent["source"]["label"]:
        raise ValueError("phase source may not differ from package authority")
    if not set(declaration["source"]["topics"]).issubset(parent["source"]["topics"]):
        raise ValueError("phase topics are broader than package authority")
    if not set(declaration["capability"]).issubset(parent["capability"]):
        raise ValueError("phase capabilities are broader than package authority")
    for candidate in declaration["authorized_files_or_modules"]:
        if not any(_contains(allowed, candidate) for allowed in parent["authorized_files_or_modules"]):
            raise ValueError(f"phase file/module is broader than package authority: {candidate}")
    if not set(parent["explicit_out_of_scope"]).issubset(declaration["explicit_out_of_scope"]):
        raise ValueError("phase removed an explicit package exclusion")
    if not set(declaration["validation_profile"]).issubset(parent["validation_profile"]):
        raise ValueError("phase validation profile is broader than package authority")
    parent_ladder = parent["acquisition_technique"]["strategy_ladder"]
    child_ladder = declaration["acquisition_technique"]["strategy_ladder"]
    if not set(child_ladder).issubset(parent_ladder):
        raise ValueError("phase technique ladder is broader than package authority")
    selected = declaration["acquisition_technique"]["selected_technique"]
    if selected is not None and selected not in parent_ladder:
        raise ValueError("selected technique is outside the package strategy ladder")
    return copy.deepcopy(declaration)
