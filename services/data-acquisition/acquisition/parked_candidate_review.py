"""Pure validation for the KU2D Parked Candidate Review v1.

The artifact is a storage-neutral review of exact historical Git evidence.  It
does not read files, call Git/GitHub/network services, write a database, mutate
candidate authority, or participate in acquisition/runtime scheduling.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


REVIEW_SCHEMA = "ku2d.parked-candidate-review.v1"
REVIEW_STATUSES = {
    "already_integrated_equivalent",
    "candidate_supported",
    "candidate_partially_supported",
    "contradicted_or_stale",
    "insufficient_evidence",
    "duplicate_of_current_knowledge",
    "source_specific_historical_only",
}
DISPOSITIONS = {
    "use_current_equivalent",
    "retain_candidate_only",
    "retain_candidate_with_gaps",
    "rewrite_before_reuse",
    "retire_historical_claim",
    "retain_historical_only",
    "no_new_knowledge",
}
EXPECTED_SURFACES = {
    36: (
        "codex/overnight-tiktok-shop-commerce-pulse-explore",
        "9f62c33f933989bb12581fdb3b2a6fb21a1ca6b5",
        8,
    ),
    37: (
        "codex/overnight-marketplace-source-inventory",
        "0e99926c72cec7e83e259408c153fd6c99fd1492",
        2,
    ),
    38: (
        "codex/overnight-ota-source-expansion",
        "8c8ac59c5ef852bf2bbd33be6c8ff44e55e00c73",
        2,
    ),
    39: (
        "codex/overnight-coffee-source-expansion",
        "441c71d678a30cc62b742ea58f23f629a9d1e2d6",
        7,
    ),
    40: (
        "codex/overnight-qdiving-source-expansion",
        "5f972d456415dbd0d8ae695f02c056e4a7c76e56",
        9,
    ),
    41: (
        "codex/overnight-cross-domain-source-gap-scan",
        "408e4a3889a70b89b71cbd076b0b980d1aaae2d3",
        2,
    ),
}
EXPECTED_BOUNDARIES = {
    "storage_neutral": True,
    "review_equals_promotion": False,
    "candidate_promotion_count": 0,
    "learning_memory_write": False,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "human_confirmation_write": False,
    "ground_truth_write": False,
    "parked_branch_mutation_count": 0,
    "parked_pr_merge_count": 0,
    "branch_deletion_count": 0,
    "live_request_count": 0,
    "runtime_auto_write": False,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "ml_dataset_export": False,
    "survey_doe_sem_work": False,
    "broader_recommendation_or_ranking": False,
}
EXPECTED_AUTHORITY = {
    "candidate_only": True,
    "reviewed_corpus_authorized": False,
    "core_knowledge_authorized": False,
    "human_confirmed": False,
    "ground_truth_asserted": False,
    "production_authorized": False,
}
FORBIDDEN_ACTION_KEYS = {
    "promote_to_reviewed_corpus",
    "promote_to_core_knowledge",
    "promote_to_ground_truth",
    "merge_branch",
    "delete_branch",
    "mutation_command",
    "scheduler_command",
}


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{field} must be a {qualifier}list")
    return value


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _texts(value: Any, field: str, *, nonempty: bool = True) -> list[str]:
    values = _list(value, field, nonempty=nonempty)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicates")
    return values


def _sha(value: Any, field: str) -> str:
    text = _text(value, field)
    if len(text) != 40 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be a lowercase 40-character git SHA")
    return text


def _timestamp(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return text


def _walk_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        found = FORBIDDEN_ACTION_KEYS & set(value)
        if found:
            raise ValueError(f"executable mutation/promotion fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden_keys(child)


def validate_parked_candidate_review(record: dict[str, Any]) -> dict[str, Any]:
    """Validate exact parked-candidate provenance and non-promoting review."""
    if not isinstance(record, dict) or record.get("schema") != REVIEW_SCHEMA:
        raise ValueError(f"schema must be {REVIEW_SCHEMA}")
    if record.get("version") != "1.0":
        raise ValueError("review version must be 1.0")
    _walk_forbidden_keys(record)
    _timestamp(record.get("reviewed_at"), "reviewed_at")
    _text(record.get("repository"), "repository")
    _text(record.get("authoritative_branch"), "authoritative_branch")
    _text(record.get("base_branch"), "base_branch")
    _sha(record.get("base_sha"), "base_sha")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("review boundaries must remain exact and non-authorizing")

    surfaces = _list(record.get("parked_surfaces"), "parked_surfaces")
    if len(surfaces) != len(EXPECTED_SURFACES):
        raise ValueError("exactly six parked candidate surfaces are required")
    surface_ids: set[str] = set()
    surface_by_pr: dict[int, dict[str, Any]] = {}
    all_unique_files: set[str] = set()
    for raw in surfaces:
        surface = _mapping(raw, "parked_surface")
        surface_id = _text(surface.get("surface_id"), "surface_id")
        if surface_id in surface_ids:
            raise ValueError("surface IDs must be unique")
        surface_ids.add(surface_id)
        pr_number = surface.get("pr_number")
        if pr_number not in EXPECTED_SURFACES or pr_number in surface_by_pr:
            raise ValueError("parked surfaces must map exactly to PRs #36-#41")
        expected_branch, expected_head, expected_files = EXPECTED_SURFACES[pr_number]
        if surface.get("branch") != expected_branch or surface.get("head_sha") != expected_head:
            raise ValueError("parked branch/head provenance drifted")
        _sha(surface.get("historical_base_sha"), "historical_base_sha")
        if surface.get("base_branch") != "integration/data-acquisition-platform":
            raise ValueError("parked PR base is invalid")
        if not all(surface.get(key) is expected for key, expected in {
            "open_at_review": True,
            "draft_at_review": True,
            "merged_at_review": False,
            "mutated_by_review": False,
        }.items()):
            raise ValueError("parked PR state or mutation boundary is invalid")
        unique_files = _texts(surface.get("unique_files"), "parked_surface.unique_files")
        if len(unique_files) != expected_files:
            raise ValueError("parked unique-file inventory is incomplete")
        all_unique_files.update(unique_files)
        surface_by_pr[pr_number] = surface

    evidence_nodes = _list(record.get("evidence_nodes"), "evidence_nodes")
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for raw in evidence_nodes:
        node = _mapping(raw, "evidence_node")
        node_id = _text(node.get("evidence_id"), "evidence_id")
        if node_id in evidence_by_id:
            raise ValueError("evidence IDs must be unique")
        _text(node.get("authority"), "evidence_node.authority")
        _texts(node.get("references"), "evidence_node.references")
        if node.get("promotion_authorized") is not False:
            raise ValueError("review evidence cannot authorize promotion")
        evidence_by_id[node_id] = node

    coverage = _list(record.get("candidate_coverage"), "candidate_coverage")
    if len(coverage) != 11:
        raise ValueError("all eleven Candidate Learning Evidence records are required")
    coverage_by_id: dict[str, dict[str, Any]] = {}
    for raw in coverage:
        item = _mapping(raw, "candidate_coverage_item")
        candidate_id = _text(item.get("candidate_id"), "candidate_id")
        if candidate_id in coverage_by_id:
            raise ValueError("candidate coverage IDs must be unique")
        coverage_by_id[candidate_id] = item
        expected_number = int(candidate_id.rsplit("-", 1)[-1])
        if expected_number not in range(1, 12):
            raise ValueError("candidate coverage ID is outside CLE-000001..000011")
        if item.get("pr_number") not in EXPECTED_SURFACES:
            raise ValueError("candidate coverage must resolve to a parked PR")
        if item.get("lossless_projection") is not False:
            raise ValueError("current CLE summaries are not lossless branch projections")
        _texts(item.get("unrepresented_unique_knowledge"), "unrepresented_unique_knowledge")
        _texts(item.get("future_promotion_evidence"), "future_promotion_evidence")
        if _mapping(item.get("authority"), "candidate_coverage.authority") != EXPECTED_AUTHORITY:
            raise ValueError("candidate coverage authority must remain candidate-only")
    if set(coverage_by_id) != {f"KU2D-CLE-{number:06d}" for number in range(1, 12)}:
        raise ValueError("candidate coverage must include CLE-000001 through CLE-000011 exactly")

    claims = _list(record.get("claims"), "claims")
    claim_by_id: dict[str, dict[str, Any]] = {}
    status_counts = {status: 0 for status in REVIEW_STATUSES}
    disposition_counts = {disposition: 0 for disposition in DISPOSITIONS}
    surface_claim_counts = {surface_id: 0 for surface_id in surface_ids}
    for raw in claims:
        claim = _mapping(raw, "claim")
        claim_id = _text(claim.get("claim_id"), "claim_id")
        if claim_id in claim_by_id:
            raise ValueError("claim IDs must be unique")
        claim_by_id[claim_id] = claim
        surface_id = claim.get("source_surface_id")
        if surface_id not in surface_ids:
            raise ValueError("claim must resolve to an exact parked surface")
        surface_claim_counts[surface_id] += 1
        if _text(claim.get("file"), "claim.file") not in all_unique_files:
            raise ValueError("claim file is absent from the exact unique delta")
        _text(claim.get("location"), "claim.location")
        _text(claim.get("statement"), "claim.statement")
        _text(claim.get("rationale"), "claim.rationale")
        status = claim.get("review_status")
        disposition = claim.get("disposition")
        if status not in REVIEW_STATUSES or disposition not in DISPOSITIONS:
            raise ValueError("claim status or disposition is invalid")
        status_counts[status] += 1
        disposition_counts[disposition] += 1
        dependencies = _texts(claim.get("evidence_dependencies"), "claim.evidence_dependencies")
        if not set(dependencies) <= set(evidence_by_id):
            raise ValueError("claim references an unknown evidence node")
        candidate_ids = _texts(claim.get("candidate_evidence_ids"), "candidate_evidence_ids", nonempty=False)
        if not set(candidate_ids) <= set(coverage_by_id):
            raise ValueError("claim references unknown Candidate Learning Evidence")
        missing = _texts(claim.get("missing_promotion_evidence"), "missing_promotion_evidence", nonempty=False)
        if status in {"candidate_supported", "candidate_partially_supported", "insufficient_evidence"} and not missing:
            raise ValueError("candidate/insufficient claims need explicit promotion evidence gaps")
        if status == "candidate_supported" and disposition != "retain_candidate_only":
            raise ValueError("supported candidates must remain candidate-only")
        if status == "candidate_partially_supported" and disposition != "retain_candidate_with_gaps":
            raise ValueError("partially supported candidates must retain gaps")
        if status == "already_integrated_equivalent" and disposition != "use_current_equivalent":
            raise ValueError("integrated equivalents must defer to current knowledge")
        if status == "duplicate_of_current_knowledge" and disposition != "no_new_knowledge":
            raise ValueError("duplicates cannot create new knowledge")
        if status == "source_specific_historical_only" and disposition != "retain_historical_only":
            raise ValueError("historical-only claims must remain historical-only")
        if status == "contradicted_or_stale" and disposition not in {"rewrite_before_reuse", "retire_historical_claim"}:
            raise ValueError("stale claims must be rewritten or retired")
        if _mapping(claim.get("authority"), "claim.authority") != EXPECTED_AUTHORITY:
            raise ValueError("claim authority must remain candidate-only and non-authorizing")
    if any(count == 0 for count in surface_claim_counts.values()):
        raise ValueError("every parked surface needs claim-level review")

    graph = _mapping(record.get("evidence_dependency_graph"), "evidence_dependency_graph")
    if set(graph) != set(claim_by_id):
        raise ValueError("dependency graph must include every claim exactly once")
    for claim_id, dependencies in graph.items():
        if _texts(dependencies, f"evidence_dependency_graph.{claim_id}") != claim_by_id[claim_id]["evidence_dependencies"]:
            raise ValueError("dependency graph must exactly match claim dependencies")

    summary = _mapping(record.get("summary"), "summary")
    expected_summary = {
        "parked_surface_count": len(surfaces),
        "unique_file_count": sum(len(item["unique_files"]) for item in surfaces),
        "candidate_coverage_count": len(coverage),
        "claim_count": len(claims),
        "review_status_counts": status_counts,
        "disposition_counts": disposition_counts,
        "surface_claim_counts": surface_claim_counts,
        "lossless_candidate_projection_count": 0,
        "candidate_promotion_count": 0,
        "parked_branch_mutation_count": 0,
        "parked_pr_merge_count": 0,
    }
    if summary != expected_summary:
        raise ValueError("review summary is stale or non-authorizing counts drifted")

    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_parked_candidate_review(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached validated JSON object."""
    return validate_parked_candidate_review(record)
