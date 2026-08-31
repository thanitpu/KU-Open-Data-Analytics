"""Pure quality-foundation contracts for future KU2D Core Intelligence.

This module performs validation and deterministic agreement calculations only.
It performs no I/O, acquisition, runtime writes, production authorization, ML,
embedding, scheduling, or automatic promotion into Core Knowledge.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from acquisition_learning_record import serialize_json_object, validate_safe_json_payload
from core_knowledge import taxonomy_index, validate_taxonomy


CODEBOOK_SCHEMA = "ku2d.core-knowledge-codebook.v1"
EVIDENCE_CHAIN_SCHEMA = "ku2d.evidence-interpretation-chain.v1"
CODING_CHAIN_SCHEMA = "ku2d.iterative-coding-chain.v1"
MEMO_SCHEMA = "ku2d.analytical-memo.v1"
NEGATIVE_CASE_SCHEMA = "ku2d.negative-deviant-case.v1"
FINDING_VERIFICATION_SCHEMA = "ku2d.finding-verification.v1"
INDEPENDENT_CODING_SCHEMA = "ku2d.independent-coding-record.v1"
RELIABILITY_REPORT_SCHEMA = "ku2d.semantic-reliability-report.v1"
DISPLAY_PROJECTION_SCHEMA = "ku2d.quality-analysis-projection.v1"
QUALITY_LOOP_SCHEMA = "ku2d.quality-loop-state.v1"

CODE_KINDS = {"semantic_code"}
CODING_CLASSIFICATIONS = {"coded", "no_existing_code_fits", "novel_pattern_candidate"}
MEMO_STATUSES = {"working_hypothesis", "pattern_candidate", "reviewed_pattern"}
VERIFICATION_RESULTS = {"passed", "failed", "skipped", "pending"}
CODER_TYPES = {"codex", "assistant", "human", "deterministic_fixture"}
QUALITY_LOOP_STAGES = (
    "observed_evidence", "first_cycle_code", "codebook_check", "second_cycle_code",
    "negative_case_check", "analytical_memo", "pattern_candidate",
    "finding_verification", "independent_coding_check",
    "human_adjudication_if_needed", "reviewed_pattern_core_knowledge",
)
NON_AUTHORIZING = {
    "ground_truth_asserted": False,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "ml_dataset_export": False,
    "automatic_runtime_write": False,
}


def _text(value: Any, field: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str, *, nonempty: bool = True) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "a non-empty" if nonempty else "a"
        raise ValueError(f"{field} must be {qualifier} list")
    return value


def _texts(value: Any, field: str, *, nonempty: bool = True) -> list[str]:
    items = _list(value, field, nonempty=nonempty)
    result = [_text(item, field) for item in items]
    if len(result) != len(set(result)):
        raise ValueError(f"{field} must not contain duplicates")
    return result


def _boundaries(record: dict[str, Any]) -> None:
    if record.get("boundaries") != NON_AUTHORIZING:
        raise ValueError("quality contracts must remain non-authorizing and side-effect free")


def validate_codebook(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    validate_taxonomy(taxonomy)
    if not isinstance(record, dict) or record.get("schema") != CODEBOOK_SCHEMA:
        raise ValueError(f"codebook schema must be {CODEBOOK_SCHEMA}")
    if record.get("taxonomy_schema") != taxonomy["schema"]:
        raise ValueError("codebook taxonomy schema mismatch")
    if record.get("taxonomy_version") != taxonomy["version"]:
        raise ValueError("codebook taxonomy version mismatch")
    if record.get("backward_compatible_adapter") is not True:
        raise ValueError("v1 codebook must adapt the existing taxonomy without replacing it")
    if record.get("production_authorized") is not False:
        raise ValueError("codebook cannot authorize production")
    taxonomy_ids = {item for values in taxonomy_index(taxonomy).values() for item in values}
    codes = _list(record.get("codes"), "codes")
    code_ids: set[str] = set()
    for code in codes:
        code = _mapping(code, "code")
        code_id = _text(code.get("code_id"), "code_id")
        if code_id in code_ids or code_id not in taxonomy_ids:
            raise ValueError(f"duplicate or unsupported code_id: {code_id}")
        code_ids.add(code_id)
        if code.get("code_kind") not in CODE_KINDS:
            raise ValueError("codebook entries must be semantic codes, not descriptors or themes")
        _text(code.get("definition"), f"{code_id}.definition")
        for field in (
            "include_when", "exclude_when", "positive_examples", "counter_examples",
            "evidence_required",
        ):
            _texts(code.get(field), f"{code_id}.{field}")
        parent = code.get("parent_code_id")
        if parent is not None and parent not in taxonomy_ids:
            raise ValueError(f"unsupported parent code for {code_id}")
        for field in ("child_code_ids", "commonly_confused_with"):
            for related in _texts(code.get(field), f"{code_id}.{field}", nonempty=False):
                if related not in taxonomy_ids or related == code_id:
                    raise ValueError(f"invalid related code {related} for {code_id}")
    boundaries = _mapping(record.get("boundaries"), "boundaries")
    if boundaries != {
        "ground_truth_authorized": False, "production_authorized": False,
        "scheduler_action": None, "ml_execution_or_export": False,
    }:
        raise ValueError("codebook boundaries are invalid")
    return validate_safe_json_payload(record)


def codebook_index(record: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_codebook(record, taxonomy)
    return {item["code_id"]: item for item in record["codes"]}


def validate_evidence_chain(
    record: dict[str, Any], codebook: dict[str, Any], taxonomy: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != EVIDENCE_CHAIN_SCHEMA:
        raise ValueError(f"evidence chain schema must be {EVIDENCE_CHAIN_SCHEMA}")
    _text(record.get("chain_id"), "chain_id")
    codes = codebook_index(codebook, taxonomy)
    raw = _mapping(record.get("raw_evidence"), "raw_evidence")
    raw_id = _text(raw.get("evidence_id"), "raw_evidence.evidence_id")
    if raw.get("stage") != "raw_observed_evidence" or raw.get("immutable") is not True:
        raise ValueError("raw evidence must be explicit and immutable")
    if "value" not in raw:
        raise ValueError("raw evidence value is required")
    _texts(raw.get("provenance_references"), "raw_evidence.provenance_references")
    prepared = _mapping(record.get("prepared_evidence"), "prepared_evidence")
    if prepared.get("stage") != "prepared_evidence" or prepared.get("raw_evidence_id") != raw_id:
        raise ValueError("prepared evidence must reference, not overwrite, raw evidence")
    _text(prepared.get("prepared_evidence_id"), "prepared_evidence_id")
    _texts(prepared.get("preparation_steps"), "preparation_steps")
    descriptors = _list(record.get("descriptors"), "descriptors")
    descriptor_ids: set[str] = set()
    for descriptor in descriptors:
        descriptor = _mapping(descriptor, "descriptor")
        descriptor_id = _text(descriptor.get("descriptor_id"), "descriptor_id")
        if descriptor_id in descriptor_ids or descriptor_id in codes:
            raise ValueError("descriptor IDs must be unique and cannot substitute for codes")
        descriptor_ids.add(descriptor_id)
        if descriptor.get("kind") != "descriptor":
            raise ValueError("descriptor kind must remain descriptor")
        _text(descriptor.get("description"), "descriptor.description")
        _texts(descriptor.get("evidence_references"), "descriptor.evidence_references")
    coded = _list(record.get("codes"), "codes")
    used_codes: set[str] = set()
    for item in coded:
        item = _mapping(item, "coded item")
        code_id = _text(item.get("code_id"), "coded.code_id")
        if item.get("kind") != "semantic_code" or code_id not in codes:
            raise ValueError("a descriptor or theme cannot silently substitute for a semantic code")
        used_codes.add(code_id)
        refs = _texts(item.get("descriptor_references"), "descriptor_references")
        if not set(refs).issubset(descriptor_ids):
            raise ValueError("code references unknown descriptors")
    interpretations = _list(record.get("interpretations"), "interpretations")
    interpretation_ids: set[str] = set()
    for item in interpretations:
        item = _mapping(item, "interpretation")
        interpretation_id = _text(item.get("interpretation_id"), "interpretation_id")
        if interpretation_id in interpretation_ids or interpretation_id in used_codes:
            raise ValueError("interpretation cannot replace or reuse a semantic code identifier")
        interpretation_ids.add(interpretation_id)
        if item.get("kind") != "interpretation":
            raise ValueError("interpretation kind must remain explicit")
        if not set(_texts(item.get("code_references"), "code_references")).issubset(used_codes):
            raise ValueError("interpretation references unknown codes")
        _text(item.get("statement"), "interpretation.statement")
    for decision in _list(record.get("decisions"), "decisions"):
        decision = _mapping(decision, "decision")
        if decision.get("kind") != "decision":
            raise ValueError("decision kind must remain explicit")
        _text(decision.get("decision_id"), "decision_id")
        if not set(_texts(decision.get("interpretation_references"), "interpretation_references")).issubset(interpretation_ids):
            raise ValueError("decision references unknown interpretations")
        _text(decision.get("authority_source"), "authority_source")
        if decision.get("production_authorized") is not False:
            raise ValueError("quality decisions cannot authorize production")
    _boundaries(record)
    return validate_safe_json_payload(record)


def validate_coding_chain(
    record: dict[str, Any], codebook: dict[str, Any], taxonomy: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != CODING_CHAIN_SCHEMA:
        raise ValueError(f"coding chain schema must be {CODING_CHAIN_SCHEMA}")
    _text(record.get("coding_chain_id"), "coding_chain_id")
    _text(record.get("sample_or_episode_id"), "sample_or_episode_id")
    code_ids = set(codebook_index(codebook, taxonomy))
    first = _mapping(record.get("first_cycle"), "first_cycle")
    first_id = _text(first.get("coding_id"), "first_cycle.coding_id")
    _validate_coding_state(first, code_ids, expected_cycle="first_cycle")
    second = record.get("second_cycle")
    if second is not None:
        second = _mapping(second, "second_cycle")
        _validate_coding_state(second, code_ids, expected_cycle="second_cycle")
        if second.get("refines_coding_id") != first_id:
            raise ValueError("second-cycle coding must reference retained first-cycle coding")
        if record.get("first_cycle_retained") is not True:
            raise ValueError("first-cycle coding cannot be overwritten")
    elif record.get("first_cycle_retained") is not True:
        raise ValueError("first-cycle coding must remain retained")
    _texts(record.get("provenance_references"), "provenance_references")
    _boundaries(record)
    return validate_safe_json_payload(record)


def _validate_coding_state(state: dict[str, Any], code_ids: set[str], *, expected_cycle: str) -> None:
    if state.get("cycle") != expected_cycle:
        raise ValueError(f"coding cycle must be {expected_cycle}")
    _text(state.get("coding_id"), "coding_id")
    classification = state.get("classification")
    if classification not in CODING_CLASSIFICATIONS:
        raise ValueError("coding classification is invalid")
    labels = _texts(state.get("code_ids"), "code_ids", nonempty=False)
    if any(item not in code_ids for item in labels):
        raise ValueError("coding references unsupported codebook IDs")
    if classification == "coded" and not labels:
        raise ValueError("coded state requires a semantic code")
    if classification != "coded" and labels:
        raise ValueError("open-ontology states cannot be coerced into existing codes")
    if classification == "no_existing_code_fits" and state.get("novel_pattern_candidate") is not False:
        raise ValueError("no_existing_code_fits must remain distinct from novel_pattern_candidate")
    if classification == "novel_pattern_candidate" and state.get("novel_pattern_candidate") is not True:
        raise ValueError("novel pattern candidates must be explicit")
    _texts(state.get("evidence_references"), "coding.evidence_references")
    _text(state.get("coder_actor_type"), "coder_actor_type")


def validate_analytical_memo(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != MEMO_SCHEMA:
        raise ValueError(f"analytical memo schema must be {MEMO_SCHEMA}")
    _text(record.get("memo_id"), "memo_id")
    _texts(record.get("observed_episode_or_evidence_references"), "observed references")
    _text(record.get("emerging_concept_or_working_hypothesis"), "working hypothesis")
    _texts(record.get("supporting_evidence"), "supporting_evidence")
    _texts(record.get("counter_evidence_or_negative_cases"), "counter_evidence_or_negative_cases")
    _texts(record.get("unresolved_questions"), "unresolved_questions")
    author = _mapping(record.get("author"), "author")
    _text(author.get("actor_id"), "author.actor_id")
    if author.get("actor_type") not in CODER_TYPES:
        raise ValueError("memo author type is invalid")
    if record.get("status") not in MEMO_STATUSES:
        raise ValueError("memo status is invalid")
    _texts(record.get("provenance_references"), "memo provenance")
    if record.get("append_only_in_meaning") is not True or record.get("supersedes_memo_id") == record.get("memo_id"):
        raise ValueError("analytical memo history must be append-only in meaning")
    _boundaries(record)
    return validate_safe_json_payload(record)


def validate_negative_case(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != NEGATIVE_CASE_SCHEMA:
        raise ValueError(f"negative case schema must be {NEGATIVE_CASE_SCHEMA}")
    _text(record.get("negative_case_id"), "negative_case_id")
    for field in (
        "expected_pattern", "contradictory_observation", "policy_or_taxonomy_impact",
        "learning_value",
    ):
        _text(record.get(field), field)
    _texts(record.get("alternative_explanations"), "alternative_explanations")
    _texts(record.get("evidence_references"), "evidence_references")
    if record.get("discarded_as_failure") is not False:
        raise ValueError("negative cases are first-class learning evidence")
    _boundaries(record)
    return validate_safe_json_payload(record)


def assess_finding_verification(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != FINDING_VERIFICATION_SCHEMA:
        raise ValueError(f"finding verification schema must be {FINDING_VERIFICATION_SCHEMA}")
    _text(record.get("verification_id"), "verification_id")
    _text(record.get("finding_id"), "finding_id")
    checks = _list(record.get("checks"), "checks")
    names: set[str] = set()
    required_failed = False
    pending = False
    for check in checks:
        check = _mapping(check, "verification check")
        name = _text(check.get("check"), "check")
        if name in names:
            raise ValueError("finding verification checks must be unique")
        names.add(name)
        result = check.get("result")
        if result not in VERIFICATION_RESULTS:
            raise ValueError("verification result is invalid")
        if not isinstance(check.get("required"), bool):
            raise ValueError("verification check required must be boolean")
        if result == "skipped":
            _text(check.get("justification"), "skipped check justification")
        if result in {"passed", "failed"}:
            _texts(check.get("evidence_references"), "verification evidence references")
        elif check.get("evidence_references") not in ([], None):
            _texts(check.get("evidence_references"), "verification evidence references", nonempty=False)
        if check["required"] and result != "passed":
            required_failed = True
        if result == "pending":
            pending = True
    required_names = {
        "raw_evidence_return", "provenance_completeness", "alternative_explanation_review",
        "negative_deviant_case_search", "limitation_statement",
    }
    if not required_names.issubset(names):
        raise ValueError("finding verification omits foundational checks")
    if record.get("policy_authority_required") is True:
        human_checks = [item for item in checks if item["check"] == "human_confirmation"]
        if not human_checks or not human_checks[0]["required"]:
            raise ValueError("policy findings require an explicit Human Confirmation gate")
    eligible = not required_failed and not pending
    if record.get("eligible_for_reviewed_core_knowledge") is not eligible:
        raise ValueError("finding eligibility contradicts verification checks")
    if record.get("promoted_to_reviewed_core_knowledge") is True:
        raise ValueError("quality-foundation verification cannot auto-promote findings")
    _text(record.get("limitation_statement"), "limitation_statement")
    _boundaries(record)
    result = deepcopy(record)
    result["gate_status"] = "eligible_for_separate_review" if eligible else "withheld"
    return serialize_json_object(validate_safe_json_payload(result))


def validate_independent_coding_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != INDEPENDENT_CODING_SCHEMA:
        raise ValueError(f"independent coding schema must be {INDEPENDENT_CODING_SCHEMA}")
    _text(record.get("independent_coding_id"), "independent_coding_id")
    _text(record.get("sample_or_episode_id"), "sample_or_episode_id")
    _text(record.get("task"), "task")
    _text(record.get("codebook_version"), "codebook_version")
    coder = _mapping(record.get("coder"), "coder")
    _text(coder.get("coder_id"), "coder_id")
    if coder.get("coder_type") not in CODER_TYPES:
        raise ValueError("coder type is invalid")
    if record.get("independent") is not True or record.get("blinded_to_other_labels") is not True:
        raise ValueError("independent coding records must remain blinded and separate")
    _texts(record.get("labels"), "labels", nonempty=False)
    if record.get("agreement_status") not in {"not_compared", "agreement", "disagreement"}:
        raise ValueError("agreement status is invalid")
    if not isinstance(record.get("adjudication_needed"), bool):
        raise ValueError("adjudication_needed must be boolean")
    if record["agreement_status"] == "disagreement" and record["adjudication_needed"] is not True:
        raise ValueError("disagreement requires adjudication")
    metrics = record.get("reliability_metrics")
    if metrics is not None:
        _mapping(metrics, "reliability_metrics")
    _texts(record.get("provenance_references"), "coding provenance")
    _boundaries(record)
    return validate_safe_json_payload(record)


def agreement_rate(label_pairs: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = _list(label_pairs, "label_pairs")
    disagreements = []
    agreements = 0
    for pair in pairs:
        pair = _mapping(pair, "label pair")
        sample_id = _text(pair.get("sample_or_episode_id"), "sample_or_episode_id")
        left = tuple(sorted(_texts(pair.get("labels_a"), "labels_a", nonempty=False)))
        right = tuple(sorted(_texts(pair.get("labels_b"), "labels_b", nonempty=False)))
        if left == right:
            agreements += 1
        else:
            disagreements.append({"sample_or_episode_id": sample_id, "labels_a": list(left), "labels_b": list(right)})
    return {
        "status": "calculated", "sample_size": len(pairs), "agreement_count": agreements,
        "agreement_rate": round(agreements / len(pairs), 6),
        "disagreement_cases": disagreements,
    }


def cohens_kappa(label_pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(label_pairs, list) or len(label_pairs) < 2:
        return {"status": "not_applicable", "reason": "at least two paired categorical samples are required", "sample_size": len(label_pairs or [])}
    left: list[str] = []
    right: list[str] = []
    for pair in label_pairs:
        if not isinstance(pair, dict):
            raise ValueError("kappa pairs must be objects")
        labels_a = _texts(pair.get("labels_a"), "labels_a")
        labels_b = _texts(pair.get("labels_b"), "labels_b")
        if len(labels_a) != 1 or len(labels_b) != 1:
            return {"status": "not_applicable", "reason": "Cohen kappa requires one categorical label per coder per sample", "sample_size": len(label_pairs)}
        left.append(labels_a[0])
        right.append(labels_b[0])
    categories = sorted(set(left) | set(right))
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    expected = sum((left.count(cat) / len(left)) * (right.count(cat) / len(right)) for cat in categories)
    if expected == 1:
        return {"status": "not_applicable", "reason": "expected agreement is one; kappa denominator is zero", "sample_size": len(label_pairs)}
    return {
        "status": "calculated", "sample_size": len(label_pairs),
        "observed_agreement": round(observed, 6), "expected_agreement": round(expected, 6),
        "kappa": round((observed - expected) / (1 - expected), 6),
        "categories": categories,
    }


def build_semantic_reliability_report(
    *, report_id: str, task_pairs: dict[str, list[dict[str, Any]]], provenance_references: list[str],
) -> dict[str, Any]:
    _text(report_id, "report_id")
    if not isinstance(task_pairs, dict) or not task_pairs:
        raise ValueError("task_pairs must be a non-empty mapping")
    task_results = []
    for task in sorted(task_pairs):
        _text(task, "task")
        agreement = agreement_rate(task_pairs[task])
        task_results.append({
            "task": task, "sample_size": agreement["sample_size"],
            "agreement_rate": agreement["agreement_rate"],
            "disagreement_cases": agreement["disagreement_cases"],
            "chance_corrected_agreement": cohens_kappa(task_pairs[task]),
        })
    result = {
        "schema": RELIABILITY_REPORT_SCHEMA, "report_id": report_id,
        "task_results": task_results, "aggregate_score_hidden": False,
        "aggregate_score": None,
        "provenance_references": _texts(provenance_references, "provenance_references"),
        "human_inter_rater_reliability_claimed": False,
        "boundaries": deepcopy(NON_AUTHORIZING),
    }
    return serialize_json_object(validate_safe_json_payload(result))


def validate_analysis_projection(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != DISPLAY_PROJECTION_SCHEMA:
        raise ValueError(f"analysis projection schema must be {DISPLAY_PROJECTION_SCHEMA}")
    _text(record.get("projection_id"), "projection_id")
    if record.get("projection_type") not in {
        "source_x_technique", "evidence_x_interpretation", "pattern_negative_case_summary",
    }:
        raise ValueError("projection type is invalid")
    for cell in _list(record.get("cells"), "cells"):
        cell = _mapping(cell, "projection cell")
        _text(cell.get("cell_id"), "cell_id")
        _text(cell.get("row_key"), "row_key")
        _text(cell.get("column_key"), "column_key")
        _texts(cell.get("evidence_references"), "cell evidence_references")
        if cell.get("display_confers_authority") is not False:
            raise ValueError("analysis display cannot confer authority")
    _boundaries(record)
    return validate_safe_json_payload(record)


def validate_quality_loop(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != QUALITY_LOOP_SCHEMA:
        raise ValueError(f"quality loop schema must be {QUALITY_LOOP_SCHEMA}")
    _text(record.get("quality_loop_id"), "quality_loop_id")
    stages = _list(record.get("stages"), "stages")
    positions = []
    for stage in stages:
        stage = _mapping(stage, "quality loop stage")
        name = _text(stage.get("stage"), "stage")
        if name not in QUALITY_LOOP_STAGES:
            raise ValueError("unsupported quality-loop stage")
        positions.append(QUALITY_LOOP_STAGES.index(name))
        if stage.get("status") not in {"completed", "pending", "not_required", "withheld"}:
            raise ValueError("quality-loop stage status is invalid")
        _text(stage.get("reason"), "quality-loop stage reason")
        _texts(stage.get("record_references"), "stage record references", nonempty=False)
    if positions != sorted(set(positions)) or positions[0] != 0:
        raise ValueError("quality-loop stages must be unique, ordered, and start with observed evidence")
    by_name = {item["stage"]: item for item in stages}
    final_stage = by_name.get("reviewed_pattern_core_knowledge")
    verification_stage = by_name.get("finding_verification")
    if final_stage and final_stage["status"] == "completed":
        if not verification_stage or verification_stage["status"] != "completed":
            raise ValueError("reviewed Core Knowledge requires a completed Finding Verification stage")
    if record.get("every_episode_must_complete_all_stages") is not False:
        raise ValueError("not every episode must reach every quality-loop stage")
    _boundaries(record)
    return validate_safe_json_payload(record)
