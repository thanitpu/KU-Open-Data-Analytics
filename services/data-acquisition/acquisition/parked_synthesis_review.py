"""Pure validation for the KU2D Parked Synthesis Review v1.

The review is a storage-neutral, non-authorizing projection of historical
parked synthesis.  This module performs no filesystem, git, GitHub, network,
database, acquisition, production, scheduling, ML, or branch operation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


REVIEW_SCHEMA = "ku2d.parked-synthesis-review.v1"
REVIEW_STATUSES = {
    "already_integrated_equivalent",
    "candidate_supported",
    "candidate_partially_supported",
    "contradicted_or_stale",
    "insufficient_evidence",
    "duplicate_of_current_knowledge",
}
DISPOSITIONS = {
    "use_current_equivalent",
    "retain_candidate_synthesis",
    "rewrite_before_reuse",
    "retire_historical_claim",
    "retain_historical_only",
    "no_new_knowledge",
}
EVIDENCE_AUTHORITIES = {
    "reviewed_current",
    "human_confirmed_policy",
    "candidate_only",
    "governance_only",
    "deterministic_contract_only",
}
EXPECTED_BOUNDARIES = {
    "storage_neutral": True,
    "historical_synthesis_is_authoritative": False,
    "review_equals_promotion": False,
    "candidate_promotion_count": 0,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "ground_truth_write": False,
    "branch_deletion_count": 0,
    "parked_branch_mutation_count": 0,
    "live_request_count": 0,
    "runtime_auto_write": False,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "embedding_or_vector_storage": False,
    "ml_dataset_export": False,
    "survey_doe_sem_work": False,
    "broader_recommendation_or_ranking": False,
}
EXPECTED_CLAIM_AUTHORITY = {
    "reviewed_corpus_authorized": False,
    "core_knowledge_authorized": False,
    "ground_truth_authorized": False,
    "production_authorized": False,
}
FORBIDDEN_ACTION_KEYS = {
    "promote_to_reviewed_corpus",
    "promote_to_core_knowledge",
    "promote_to_ground_truth",
    "delete_branch",
    "merge_branch",
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
            raise ValueError(f"executable promotion/mutation fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden_keys(child)


def validate_parked_synthesis_review(record: dict[str, Any]) -> dict[str, Any]:
    """Validate a complete claim-level review without granting authority."""
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

    surfaces = _list(record.get("historical_surfaces"), "historical_surfaces")
    if len(surfaces) != 2:
        raise ValueError("exactly two parked historical surfaces are required")
    surface_ids: set[str] = set()
    parked_prs: set[int] = set()
    for raw in surfaces:
        surface = _mapping(raw, "historical_surface")
        surface_id = _text(surface.get("surface_id"), "surface_id")
        if surface_id in surface_ids:
            raise ValueError("surface IDs must be unique")
        surface_ids.add(surface_id)
        branch = _text(surface.get("branch"), "historical_surface.branch")
        if not branch.startswith("codex/overnight-"):
            raise ValueError("historical surfaces must identify the parked overnight branches")
        pr_number = surface.get("pr_number")
        if pr_number not in {42, 43} or pr_number in parked_prs:
            raise ValueError("historical surfaces must map exactly to PRs #42 and #43")
        parked_prs.add(pr_number)
        _sha(surface.get("head_sha"), "historical_surface.head_sha")
        _sha(surface.get("historical_base_sha"), "historical_surface.historical_base_sha")
        _text(surface.get("file"), "historical_surface.file")
        if surface.get("open_draft_at_review") is not True:
            raise ValueError("parked historical surfaces must remain open Draft evidence")
        if surface.get("mutated_or_merged_by_review") is not False:
            raise ValueError("the review cannot mutate or merge parked surfaces")

    evidence_nodes = _list(record.get("evidence_nodes"), "evidence_nodes")
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for raw in evidence_nodes:
        node = _mapping(raw, "evidence_node")
        node_id = _text(node.get("evidence_id"), "evidence_id")
        if node_id in evidence_by_id:
            raise ValueError("evidence IDs must be unique")
        authority = node.get("authority")
        if authority not in EVIDENCE_AUTHORITIES:
            raise ValueError("evidence authority is invalid")
        references = _texts(node.get("references"), "evidence_node.references")
        if authority == "candidate_only":
            if not all("candidate_learning_evidence_registry.json#KU2D-CLE-" in item for item in references):
                raise ValueError("candidate-only nodes must reference Candidate Learning Evidence IDs")
            if node.get("promotion_authorized") is not False:
                raise ValueError("candidate-only evidence cannot authorize promotion")
        if node.get("ground_truth_asserted") is not False:
            raise ValueError("review evidence nodes cannot assert Ground Truth")
        evidence_by_id[node_id] = node

    observations = _list(record.get("historical_assertions"), "historical_assertions")
    observation_ids: set[str] = set()
    for raw in observations:
        observation = _mapping(raw, "historical_assertion")
        observation_id = _text(observation.get("assertion_id"), "assertion_id")
        if observation_id in observation_ids:
            raise ValueError("historical assertion IDs must be unique")
        observation_ids.add(observation_id)
        if observation.get("source_surface_id") not in surface_ids:
            raise ValueError("historical assertion must resolve to a parked source surface")
        _text(observation.get("location"), "historical_assertion.location")
        _text(observation.get("statement"), "historical_assertion.statement")
        if observation.get("authority") != "historical_unreviewed_ledger_only":
            raise ValueError("historical assertions must remain unreviewed ledger evidence")
        if observation.get("promotion_authorized") is not False:
            raise ValueError("historical assertions cannot authorize promotion")

    claims = _list(record.get("claims"), "claims")
    claim_by_id: dict[str, dict[str, Any]] = {}
    status_counts = {status: 0 for status in REVIEW_STATUSES}
    disposition_counts = {disposition: 0 for disposition in DISPOSITIONS}
    for raw in claims:
        claim = _mapping(raw, "claim")
        claim_id = _text(claim.get("claim_id"), "claim_id")
        if claim_id in claim_by_id:
            raise ValueError("claim IDs must be unique")
        claim_by_id[claim_id] = claim
        if claim.get("source_surface_id") not in surface_ids:
            raise ValueError("claim must resolve to a parked source surface")
        _text(claim.get("location"), "claim.location")
        _text(claim.get("statement"), "claim.statement")
        _text(claim.get("rationale"), "claim.rationale")
        status = claim.get("review_status")
        disposition = claim.get("disposition")
        if status not in REVIEW_STATUSES or disposition not in DISPOSITIONS:
            raise ValueError("claim review status or disposition is invalid")
        status_counts[status] += 1
        disposition_counts[disposition] += 1
        dependencies = _texts(claim.get("evidence_dependencies"), "claim.evidence_dependencies")
        if not set(dependencies) <= set(evidence_by_id):
            raise ValueError("claim references an unknown evidence node")
        authorities = {evidence_by_id[item]["authority"] for item in dependencies}
        if status in {"already_integrated_equivalent", "duplicate_of_current_knowledge"}:
            if not authorities & {"reviewed_current", "human_confirmed_policy", "governance_only"}:
                raise ValueError("current-equivalent claims require current durable authority")
        if status in {"candidate_supported", "candidate_partially_supported"}:
            if "candidate_only" not in authorities:
                raise ValueError("candidate-supported claims require candidate-only evidence")
            if disposition != "retain_candidate_synthesis":
                raise ValueError("candidate-supported claims must remain candidate synthesis")
        missing = _texts(
            claim.get("missing_evidence_requirements"),
            "claim.missing_evidence_requirements",
            nonempty=False,
        )
        if status in {"candidate_partially_supported", "insufficient_evidence"} and not missing:
            raise ValueError("partial or insufficient claims require explicit missing evidence")
        if status == "contradicted_or_stale" and disposition not in {
            "rewrite_before_reuse", "retire_historical_claim"
        }:
            raise ValueError("stale claims must be rewritten or retired")
        if status == "already_integrated_equivalent" and disposition != "use_current_equivalent":
            raise ValueError("integrated equivalents must defer to current durable knowledge")
        if status == "duplicate_of_current_knowledge" and disposition != "no_new_knowledge":
            raise ValueError("duplicate claims cannot create new knowledge")
        if _mapping(claim.get("authority"), "claim.authority") != EXPECTED_CLAIM_AUTHORITY:
            raise ValueError("claim authority must remain explicitly non-promoting")

    graph = _mapping(record.get("evidence_dependency_graph"), "evidence_dependency_graph")
    if set(graph) != set(claim_by_id):
        raise ValueError("dependency graph must include every claim exactly once")
    for claim_id, dependencies in graph.items():
        graph_dependencies = _texts(dependencies, f"evidence_dependency_graph.{claim_id}")
        if graph_dependencies != claim_by_id[claim_id]["evidence_dependencies"]:
            raise ValueError("dependency graph must exactly match claim evidence dependencies")

    summary = _mapping(record.get("summary"), "summary")
    if summary.get("historical_surface_count") != len(surfaces):
        raise ValueError("historical surface count is stale")
    if summary.get("historical_assertion_count") != len(observations):
        raise ValueError("historical assertion count is stale")
    if summary.get("claim_count") != len(claims):
        raise ValueError("claim count is stale")
    if summary.get("review_status_counts") != status_counts:
        raise ValueError("review-status summary is stale")
    if summary.get("disposition_counts") != disposition_counts:
        raise ValueError("disposition summary is stale")
    if summary.get("candidate_promotion_count") != 0:
        raise ValueError("synthesis review cannot promote candidate evidence")
    if summary.get("parked_branch_mutation_count") != 0:
        raise ValueError("synthesis review cannot mutate parked branches")
    if summary.get("parked_branch_merge_count") != 0:
        raise ValueError("synthesis review cannot merge parked branches")

    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_parked_synthesis_review(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached validated JSON object."""
    return validate_parked_synthesis_review(record)
