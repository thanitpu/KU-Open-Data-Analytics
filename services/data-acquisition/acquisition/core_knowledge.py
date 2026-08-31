"""Pure validation contracts for KU2D Core Knowledge v1.

Core Knowledge is a storage-neutral, reviewed projection of repository evidence.
This module performs no I/O, acquisition, authorization, scheduling, export,
training, embedding, or inference.
"""
from __future__ import annotations

import re
from typing import Any

from acquisition_learning_record import serialize_json_object, validate_safe_json_payload


TAXONOMY_SCHEMA = "ku2d.core-knowledge-taxonomy.v1"
CORPUS_SCHEMA = "ku2d.reviewed-learning-corpus.v1"
EPISODE_SCHEMA = "ku2d.reviewed-learning-episode.v1"
COVERAGE_SCHEMA = "ku2d.core-coverage-matrix.v1"
ML_MAP_SCHEMA = "ku2d.ml-knowledge-map.v1"
GAP_REGISTER_SCHEMA = "ku2d.knowledge-gap-register.v1"

REQUIRED_DIMENSIONS = {
    "source_characteristic", "acquisition_technique", "execution_environment",
    "evidence_type", "semantic_interpretation", "acquisition_outcome",
    "failure_boundary_type", "transferability", "evidence_strength",
    "review_authority", "change_drift", "data_quality_yield",
    "request_cost_latency", "privacy_authorization", "provenance_class",
}
CORPUS_ELIGIBILITY = {
    "eligible_reviewed_corpus", "excluded_insufficient_evidence",
    "excluded_candidate_only", "excluded_sensitive_material",
}
COVERAGE_STATES = {
    "validated_multi_source", "validated_single_source", "partial",
    "boundary_validated", "contract_only", "gap",
}
ML_READINESS_STATES = {
    "insufficient_evidence", "candidate_small_reviewed_corpus",
    "review_required", "blocked_by_label_authority",
}
POLARITIES = {"positive", "negative", "mixed"}
_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")


def _mapping(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _nonempty_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return value


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def validate_taxonomy(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != TAXONOMY_SCHEMA:
        raise ValueError(f"schema must be {TAXONOMY_SCHEMA}")
    if record.get("storage_neutral") is not True or record.get("production_authorized") is not False:
        raise ValueError("taxonomy must be storage-neutral and non-authorizing")
    dimensions = _nonempty_list(record.get("dimensions"), "dimensions")
    names: set[str] = set()
    ids: set[str] = set()
    index: dict[str, set[str]] = {}
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            raise ValueError("each taxonomy dimension must be an object")
        name = _nonempty(dimension.get("dimension"), "dimension.dimension")
        if name in names:
            raise ValueError(f"duplicate taxonomy dimension: {name}")
        names.add(name)
        index[name] = set()
        for value in _nonempty_list(dimension.get("values"), f"{name}.values"):
            if not isinstance(value, dict):
                raise ValueError(f"{name} taxonomy values must be objects")
            value_id = _nonempty(value.get("id"), f"{name}.value.id")
            if not _ID_RE.fullmatch(value_id):
                raise ValueError(f"invalid taxonomy id: {value_id}")
            if value_id in ids:
                raise ValueError(f"duplicate taxonomy id: {value_id}")
            ids.add(value_id)
            index[name].add(value_id)
            _nonempty(value.get("label"), f"{value_id}.label")
            _nonempty(value.get("definition"), f"{value_id}.definition")
    missing = REQUIRED_DIMENSIONS - names
    if missing:
        raise ValueError(f"missing taxonomy dimensions: {sorted(missing)}")
    if index["acquisition_technique"] & index["execution_environment"]:
        raise ValueError("technique and execution-environment identifiers must be disjoint")
    return validate_safe_json_payload(record)


def taxonomy_index(taxonomy: dict[str, Any]) -> dict[str, set[str]]:
    validate_taxonomy(taxonomy)
    return {
        dimension["dimension"]: {value["id"] for value in dimension["values"]}
        for dimension in taxonomy["dimensions"]
    }


def validate_episode(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != EPISODE_SCHEMA:
        raise ValueError(f"episode schema must be {EPISODE_SCHEMA}")
    episode_id = _nonempty(record.get("episode_id"), "episode_id")
    if not _ID_RE.fullmatch(episode_id):
        raise ValueError("episode_id must be a stable typed identifier")
    _nonempty(record.get("learning_key"), "learning_key")
    if record.get("polarity") not in POLARITIES:
        raise ValueError("episode polarity is invalid")
    source = _mapping(record, "source")
    _nonempty(source.get("name"), "source.name")
    _nonempty(source.get("domain"), "source.domain")
    knowledge = _mapping(record, "knowledge")
    authority = _mapping(record, "authority")
    provenance = _mapping(record, "provenance")
    boundaries = _mapping(record, "boundaries")
    index = taxonomy_index(taxonomy)

    scalar_refs = {
        "acquisition_technique_id": "acquisition_technique",
        "execution_environment_id": "execution_environment",
        "acquisition_outcome_id": "acquisition_outcome",
        "failure_boundary_type_id": "failure_boundary_type",
        "transferability_id": "transferability",
        "change_drift_id": "change_drift",
        "data_quality_yield_id": "data_quality_yield",
        "request_cost_latency_id": "request_cost_latency",
        "privacy_authorization_id": "privacy_authorization",
    }
    for field, dimension in scalar_refs.items():
        value = knowledge.get(field)
        if value is None and field == "failure_boundary_type_id":
            continue
        if value not in index[dimension]:
            raise ValueError(f"{episode_id}.{field} is not in {dimension}")
    list_refs = {
        ("source", "source_characteristic_ids"): "source_characteristic",
        ("knowledge", "evidence_type_ids"): "evidence_type",
        ("knowledge", "semantic_interpretation_ids"): "semantic_interpretation",
        ("provenance", "provenance_class_ids"): "provenance_class",
    }
    parents = {"source": source, "knowledge": knowledge, "provenance": provenance}
    for (parent, field), dimension in list_refs.items():
        values = _nonempty_list(parents[parent].get(field), f"{episode_id}.{field}")
        if len(values) != len(set(values)) or any(value not in index[dimension] for value in values):
            raise ValueError(f"{episode_id}.{field} contains invalid or duplicate taxonomy ids")

    if authority.get("evidence_strength_id") not in index["evidence_strength"]:
        raise ValueError("episode evidence strength is invalid")
    if authority.get("review_authority_id") not in index["review_authority"]:
        raise ValueError("episode review authority is invalid")
    if authority.get("eligibility") != "eligible_reviewed_corpus":
        raise ValueError("included episodes must be eligible for the Reviewed Learning Corpus")
    if authority.get("human_reviewed") is True and authority.get("review_authority_id") != "RA-HUMAN-CONFIRMED":
        raise ValueError("human review cannot be inferred from non-human authority")
    if authority.get("human_reviewed") is False and authority.get("review_authority_id") == "RA-HUMAN-CONFIRMED":
        raise ValueError("human-confirmed authority requires explicit human review")
    references = _nonempty_list(provenance.get("repository_references"), "repository_references")
    if any(not isinstance(ref, str) or not ref.strip() or ref.startswith(("http://", "https://")) for ref in references):
        raise ValueError("episode provenance must use repository-relative references")
    if provenance.get("sanitized") is not True:
        raise ValueError("Reviewed Learning Corpus evidence must be sanitized")
    if boundaries != {
        "observation_is_ground_truth": False,
        "production_authorized": False,
        "production_store": False,
        "scheduler_action": None,
        "automatic_ml_export": False,
    }:
        raise ValueError("episode boundaries must remain non-authorizing and non-exporting")
    return validate_safe_json_payload(record)


def validate_corpus(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != CORPUS_SCHEMA:
        raise ValueError(f"schema must be {CORPUS_SCHEMA}")
    if record.get("taxonomy_schema") != TAXONOMY_SCHEMA:
        raise ValueError("corpus must reference Core Knowledge Taxonomy v1")
    if record.get("production_authorized") is not False or record.get("ml_training_dataset_exists") is not False:
        raise ValueError("corpus cannot authorize production or claim a training dataset exists")
    episodes = _nonempty_list(record.get("episodes"), "episodes")
    episode_ids: set[str] = set()
    active_labels: dict[str, Any] = {}
    superseded_ids = {
        item.get("supersedes_episode_id") for item in episodes
        if isinstance(item, dict) and item.get("supersedes_episode_id")
    }
    for episode in episodes:
        validate_episode(episode, taxonomy)
        episode_id = episode["episode_id"]
        if episode_id in episode_ids:
            raise ValueError(f"duplicate episode id: {episode_id}")
        episode_ids.add(episode_id)
        if episode_id not in superseded_ids:
            key, label = episode["learning_key"], episode["knowledge"].get("semantic_label")
            if key in active_labels and active_labels[key] != label:
                raise ValueError(f"contradictory active labels for {key}")
            active_labels[key] = label
    if superseded_ids - episode_ids:
        raise ValueError("superseded episode reference is missing")
    exclusions = _nonempty_list(record.get("excluded_candidates"), "excluded_candidates")
    for exclusion in exclusions:
        if not isinstance(exclusion, dict):
            raise ValueError("excluded candidates must be objects")
        if exclusion.get("eligibility") not in CORPUS_ELIGIBILITY - {"eligible_reviewed_corpus"}:
            raise ValueError("excluded candidate eligibility is invalid")
        _nonempty(exclusion.get("reason"), "excluded candidate reason")
        _nonempty_list(exclusion.get("repository_references"), "excluded candidate references")
    return validate_safe_json_payload(record)


def validate_coverage_matrix(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != COVERAGE_SCHEMA:
        raise ValueError(f"schema must be {COVERAGE_SCHEMA}")
    if record.get("production_authorized") is not False:
        raise ValueError("coverage matrix must be non-authorizing")
    capabilities = _nonempty_list(record.get("capabilities"), "capabilities")
    ids: set[str] = set()
    for capability in capabilities:
        capability_id = _nonempty(capability.get("capability_id"), "capability_id")
        if capability_id in ids or not _ID_RE.fullmatch(capability_id):
            raise ValueError("coverage capability IDs must be unique typed IDs")
        ids.add(capability_id)
        if capability.get("state") not in COVERAGE_STATES:
            raise ValueError(f"invalid coverage state for {capability_id}")
        _nonempty_list(capability.get("evidence_references"), f"{capability_id}.evidence_references")
        _nonempty(capability.get("gap"), f"{capability_id}.gap")
    return validate_safe_json_payload(record)


def validate_ml_knowledge_map(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != ML_MAP_SCHEMA:
        raise ValueError(f"schema must be {ML_MAP_SCHEMA}")
    if (record.get("training_or_inference_enabled") is not False
            or record.get("dataset_export_enabled") is not False
            or record.get("production_authorized") is not False):
        raise ValueError("ML Knowledge Map must not train, infer, or export")
    for task in _nonempty_list(record.get("tasks"), "tasks"):
        _nonempty(task.get("task_id"), "task_id")
        _nonempty_list(task.get("candidate_inputs"), "candidate_inputs")
        _nonempty(task.get("target_label"), "target_label")
        _nonempty_list(task.get("evidence_sources"), "evidence_sources")
        _nonempty(task.get("label_authority"), "label_authority")
        _nonempty_list(task.get("leakage_risks"), "leakage_risks")
        if task.get("readiness") not in ML_READINESS_STATES:
            raise ValueError("invalid ML readiness state")
    return validate_safe_json_payload(record)


def validate_gap_register(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != GAP_REGISTER_SCHEMA:
        raise ValueError(f"schema must be {GAP_REGISTER_SCHEMA}")
    if record.get("exploration_started") is not False or record.get("production_authorized") is not False:
        raise ValueError("gap register must not start exploration")
    last_rank = 0
    ids: set[str] = set()
    for gap in _nonempty_list(record.get("gaps"), "gaps"):
        gap_id = _nonempty(gap.get("gap_id"), "gap_id")
        rank = gap.get("rank")
        if gap_id in ids or not isinstance(rank, int) or rank != last_rank + 1:
            raise ValueError("gap IDs must be unique and ranks contiguous")
        ids.add(gap_id)
        last_rank = rank
        _nonempty(gap.get("pattern_or_capability"), "pattern_or_capability")
        _nonempty(gap.get("recommended_future_target"), "recommended_future_target")
        _nonempty(gap.get("why"), "gap why")
        _nonempty_list(gap.get("evidence_references"), "gap evidence references")
    return validate_safe_json_payload(record)


def serialize_core_knowledge(record: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic detached JSON without writing it anywhere."""
    return serialize_json_object(record)
