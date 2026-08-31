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
CANDIDATE_REGISTRY_SCHEMA = "ku2d.candidate-learning-evidence-registry.v1"
HUMAN_CANDIDATE_PACKET_SCHEMA = "ku2d.human-confirmation-candidate-packet.v1"

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
CANDIDATE_STATUSES = {
    "unmerged_draft_observation", "unmerged_draft_boundary",
    "unmerged_deterministic_contract", "seed_only",
}
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
    ml_projection = _mapping(record, "ml_projection")
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
    features = _nonempty_list(
        ml_projection.get("candidate_feature_families"), "candidate_feature_families",
    )
    decision = _mapping(ml_projection, "label_or_decision")
    _nonempty(decision.get("target_family"), "label_or_decision.target_family")
    if decision.get("value") != knowledge.get("semantic_label"):
        raise ValueError("ML label/decision value must preserve the reviewed semantic label")
    if decision.get("authority_id") != authority.get("review_authority_id"):
        raise ValueError("ML label/decision authority must match episode authority")
    excluded = _nonempty_list(
        ml_projection.get("excluded_leakage_fields"), "excluded_leakage_fields",
    )
    if set(features) & set(excluded):
        raise ValueError("feature families and excluded leakage fields must be disjoint")
    if ml_projection.get("training_eligible") is not False:
        raise ValueError("Reviewed corpus episodes are not automatically training eligible")
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
        feature_families = _nonempty_list(task.get("feature_families"), "feature_families")
        _nonempty(task.get("target_label"), "target_label")
        _nonempty(task.get("label_family"), "label_family")
        _nonempty_list(task.get("evidence_sources"), "evidence_sources")
        _nonempty(task.get("label_authority"), "label_authority")
        _nonempty(task.get("authority_requirement"), "authority_requirement")
        _nonempty_list(task.get("exclusion_criteria"), "exclusion_criteria")
        _nonempty_list(task.get("leakage_risks"), "leakage_risks")
        if set(feature_families) & set(task["exclusion_criteria"]):
            raise ValueError("ML feature families and exclusion criteria must be disjoint")
        if task.get("readiness") not in ML_READINESS_STATES:
            raise ValueError("invalid ML readiness state")
    return validate_safe_json_payload(record)


def validate_candidate_registry(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != CANDIDATE_REGISTRY_SCHEMA:
        raise ValueError(f"schema must be {CANDIDATE_REGISTRY_SCHEMA}")
    required_false = (
        "production_authorized", "automatic_promotion_to_reviewed_corpus",
        "ground_truth_authorized", "ml_dataset_export_enabled",
    )
    if any(record.get(key) is not False for key in required_false):
        raise ValueError("Candidate Registry must remain non-authorizing and non-promoting")
    ids: set[str] = set()
    for candidate in _nonempty_list(record.get("candidates"), "candidates"):
        candidate_id = _nonempty(candidate.get("candidate_id"), "candidate_id")
        if candidate_id in ids or not _ID_RE.fullmatch(candidate_id):
            raise ValueError("candidate IDs must be unique typed IDs")
        ids.add(candidate_id)
        _nonempty(candidate.get("source"), "candidate.source")
        _nonempty(candidate.get("domain"), "candidate.domain")
        if candidate.get("polarity") not in POLARITIES:
            raise ValueError("candidate polarity is invalid")
        if candidate.get("candidate_status") not in CANDIDATE_STATUSES:
            raise ValueError("candidate status is invalid")
        _nonempty(candidate.get("observation_summary"), "observation_summary")
        ml_projection = _mapping(candidate, "ml_projection")
        features = _nonempty_list(
            ml_projection.get("candidate_feature_families"), "candidate_feature_families",
        )
        label = _mapping(ml_projection, "label_candidate")
        _nonempty(label.get("target_family"), "label_candidate.target_family")
        _nonempty(label.get("value"), "label_candidate.value")
        excluded = _nonempty_list(
            ml_projection.get("excluded_leakage_fields"), "excluded_leakage_fields",
        )
        if set(features) & set(excluded) or ml_projection.get("training_eligible") is not False:
            raise ValueError("candidate ML projection leaks labels or claims training eligibility")
        authority = _mapping(candidate, "authority")
        if authority != {
            "candidate_only": True,
            "reviewed_corpus_authorized": False,
            "human_confirmed": False,
            "ground_truth_asserted": False,
            "promoted_to_reviewed_episode_id": None,
        }:
            raise ValueError("candidate authority must remain explicitly non-promoted")
        provenance = _mapping(candidate, "provenance")
        if provenance.get("artifact_state") != "open-unmerged-draft-pr":
            raise ValueError("candidate evidence must retain its unmerged Draft PR state")
        if not isinstance(provenance.get("pr_number"), int) or provenance["pr_number"] <= 0:
            raise ValueError("candidate PR number is required")
        if not re.fullmatch(r"[0-9a-f]{40}", str(provenance.get("head_commit_sha") or "")):
            raise ValueError("candidate head commit SHA is invalid")
        _nonempty(provenance.get("source_file"), "candidate provenance.source_file")
        if candidate.get("production_store") is not False or candidate.get("scheduler_action") is not None:
            raise ValueError("candidate evidence cannot store or schedule production work")
    return validate_safe_json_payload(record)


def validate_human_candidate_packet(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != HUMAN_CANDIDATE_PACKET_SCHEMA:
        raise ValueError(f"schema must be {HUMAN_CANDIDATE_PACKET_SCHEMA}")
    if (record.get("explicit_human_authority_required") is not True
            or record.get("production_authorized") is not False
            or record.get("human_confirmation_created") is not False):
        raise ValueError("Human candidate packet must remain an unconfirmed review request")
    ids: set[str] = set()
    for item in _nonempty_list(record.get("items"), "items"):
        item_id = _nonempty(item.get("candidate_id"), "human candidate id")
        if item_id in ids or not _ID_RE.fullmatch(item_id):
            raise ValueError("human candidate IDs must be unique typed IDs")
        ids.add(item_id)
        if item.get("review_status") != "awaiting_explicit_human_authority":
            raise ValueError("human candidate must await explicit human authority")
        if item.get("human_confirmation_record_id") is not None or item.get("final_decision") is not None:
            raise ValueError("candidate packet cannot fabricate Human Confirmation or a final decision")
        _nonempty(item.get("question"), "human candidate question")
        _nonempty_list(item.get("candidate_options"), "candidate_options")
        _nonempty(item.get("system_suggestion"), "system_suggestion")
        _nonempty_list(item.get("evidence_references"), "evidence_references")
        _nonempty(item.get("why_high_value"), "why_high_value")
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
