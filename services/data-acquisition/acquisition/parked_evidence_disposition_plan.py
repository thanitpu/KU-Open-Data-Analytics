"""Pure validation for the KU2D Parked Evidence Disposition Plan v1.

The plan is advisory and storage-neutral.  This module performs no filesystem,
Git, GitHub, network, database, PR, branch, runtime, scheduler, or ML action.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


PLAN_SCHEMA = "ku2d.parked-evidence-disposition-plan.v1"
DISPOSITIONS = {
    "RETAIN_AS_EVIDENCE",
    "SUPERSEDED_BY_REVIEWED_ARTIFACTS",
    "NEEDS_TARGETED_EVIDENCE_RERUN",
    "ELIGIBLE_FOR_LATER_CLOSURE",
    "NEEDS_HUMAN_ADJUDICATION",
}
EXPECTED_PRS = {
    36: ("codex/overnight-tiktok-shop-commerce-pulse-explore", "9f62c33f933989bb12581fdb3b2a6fb21a1ca6b5"),
    37: ("codex/overnight-marketplace-source-inventory", "0e99926c72cec7e83e259408c153fd6c99fd1492"),
    38: ("codex/overnight-ota-source-expansion", "8c8ac59c5ef852bf2bbd33be6c8ff44e55e00c73"),
    39: ("codex/overnight-coffee-source-expansion", "441c71d678a30cc62b742ea58f23f629a9d1e2d6"),
    40: ("codex/overnight-qdiving-source-expansion", "5f972d456415dbd0d8ae695f02c056e4a7c76e56"),
    41: ("codex/overnight-cross-domain-source-gap-scan", "408e4a3889a70b89b71cbd076b0b980d1aaae2d3"),
    42: ("codex/overnight-acquisition-technique-transfer-matrix", "4c024a480dafda27b0064b3059e34eebaadf353d"),
    43: ("codex/overnight-exploration-summary", "87b700db3e9c2b507530f0427a6a1a2bea9ab3e9"),
}
EXPECTED_AUTHORITY = {
    "planning_only": True,
    "candidate_promoted": False,
    "reviewed_corpus_authorized": False,
    "core_knowledge_authorized": False,
    "human_confirmed": False,
    "ground_truth_asserted": False,
    "production_authorized": False,
}
EXPECTED_BOUNDARIES = {
    "storage_neutral": True,
    "planning_only": True,
    "execute_dispositions": False,
    "parked_pr_close_count": 0,
    "parked_pr_merge_count": 0,
    "parked_branch_mutation_count": 0,
    "branch_deletion_count": 0,
    "candidate_promotion_count": 0,
    "learning_memory_write": False,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "human_confirmation_write": False,
    "ground_truth_write": False,
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
FORBIDDEN_ACTION_KEYS = {
    "close_pr",
    "delete_branch",
    "merge_pr",
    "mutate_ref",
    "mutation_command",
    "close_command",
    "delete_command",
    "merge_command",
    "promote_to_reviewed_corpus",
    "promote_to_core_knowledge",
    "promote_to_ground_truth",
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
            raise ValueError(f"executable disposition fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden_keys(child)


def validate_parked_evidence_disposition_plan(record: dict[str, Any]) -> dict[str, Any]:
    """Validate an exact, non-executing disposition plan."""
    if not isinstance(record, dict) or record.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"schema must be {PLAN_SCHEMA}")
    if record.get("version") != "1.0":
        raise ValueError("plan version must be 1.0")
    _walk_forbidden_keys(record)
    _timestamp(record.get("planned_at"), "planned_at")
    _text(record.get("repository"), "repository")
    _text(record.get("authoritative_branch"), "authoritative_branch")
    _text(record.get("base_branch"), "base_branch")
    _sha(record.get("base_sha"), "base_sha")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("plan boundaries must remain exact and non-executing")

    nodes = _list(record.get("evidence_nodes"), "evidence_nodes")
    evidence_ids: set[str] = set()
    for raw in nodes:
        node = _mapping(raw, "evidence_node")
        evidence_id = _text(node.get("evidence_id"), "evidence_id")
        if evidence_id in evidence_ids:
            raise ValueError("evidence IDs must be unique")
        evidence_ids.add(evidence_id)
        _text(node.get("authority"), "evidence_node.authority")
        _texts(node.get("references"), "evidence_node.references")
        if node.get("authorizes_execution") is not False:
            raise ValueError("evidence nodes cannot authorize disposition execution")

    plans = _list(record.get("pr_plans"), "pr_plans")
    if len(plans) != len(EXPECTED_PRS):
        raise ValueError("exactly eight parked PR plans are required")
    plan_by_pr: dict[int, dict[str, Any]] = {}
    disposition_counts = {item: 0 for item in DISPOSITIONS}
    all_candidate_dependencies: set[str] = set()
    all_claim_dependencies: set[str] = set()
    for raw in plans:
        plan = _mapping(raw, "pr_plan")
        pr_number = plan.get("pr_number")
        if pr_number not in EXPECTED_PRS or pr_number in plan_by_pr:
            raise ValueError("plans must map exactly to parked PRs #36 through #43")
        expected_branch, expected_head = EXPECTED_PRS[pr_number]
        if plan.get("branch") != expected_branch or plan.get("head_sha") != expected_head:
            raise ValueError("parked branch/head provenance drifted")
        if plan.get("base_branch") != "integration/data-acquisition-platform":
            raise ValueError("parked PR base branch drifted")
        _sha(plan.get("historical_base_sha"), "historical_base_sha")
        state = _mapping(plan.get("observed_pr_state"), "observed_pr_state")
        if state != {"open": True, "draft": True, "merged": False, "head_unchanged": True}:
            raise ValueError("parked PR state must remain exact and unchanged")
        disposition = plan.get("planning_disposition")
        if disposition not in DISPOSITIONS:
            raise ValueError("planning disposition is invalid")
        disposition_counts[disposition] += 1
        _text(plan.get("reason"), "reason")
        _texts(plan.get("durably_preserved_knowledge"), "durably_preserved_knowledge")
        not_lossless = _texts(plan.get("not_losslessly_preserved"), "not_losslessly_preserved", nonempty=False)
        dependencies = _texts(plan.get("evidence_dependencies"), "evidence_dependencies")
        if not set(dependencies) <= evidence_ids:
            raise ValueError("plan references an unknown evidence node")
        candidate_dependencies = _texts(
            plan.get("candidate_dependencies"), "candidate_dependencies", nonempty=False
        )
        claim_dependencies = _texts(
            plan.get("claim_dependencies"), "claim_dependencies", nonempty=False
        )
        all_candidate_dependencies.update(candidate_dependencies)
        all_claim_dependencies.update(claim_dependencies)
        prerequisites = _texts(
            plan.get("prerequisites_before_closure"), "prerequisites_before_closure"
        )
        if plan.get("execute_disposition") is not False:
            raise ValueError("plan cannot execute a disposition")
        if plan.get("closure_eligible_now") is not False:
            raise ValueError("this planning checkpoint cannot declare immediate closure eligibility")
        if plan.get("lossless_preservation_claimed") is not False:
            raise ValueError("no parked PR has current lossless-preservation proof")
        if _texts(plan.get("lossless_preservation_proof"), "lossless_preservation_proof", nonempty=False):
            raise ValueError("proof cannot be asserted while lossless preservation is false")
        if not not_lossless:
            raise ValueError("each parked PR must retain a non-lossless preservation gap")
        if not prerequisites:
            raise ValueError("each parked PR needs concrete closure prerequisites")
        if plan.get("future_action_authority") != "explicit-human-decision-required":
            raise ValueError("future close/cleanup action requires explicit human authority")
        if plan.get("live_rerun_authorized") is not False:
            raise ValueError("the plan cannot authorize a live rerun")
        if disposition == "SUPERSEDED_BY_REVIEWED_ARTIFACTS":
            if "KU2D-EV-SYNTHESIS-REVIEW" not in dependencies:
                raise ValueError("superseded synthesis requires Parked Synthesis Review evidence")
        if disposition == "NEEDS_TARGETED_EVIDENCE_RERUN":
            _texts(plan.get("targeted_evidence_requirements"), "targeted_evidence_requirements")
        elif _texts(
            plan.get("targeted_evidence_requirements"),
            "targeted_evidence_requirements",
            nonempty=False,
        ):
            raise ValueError("targeted rerun requirements belong only to rerun dispositions")
        if disposition == "NEEDS_HUMAN_ADJUDICATION":
            _texts(plan.get("human_adjudication_questions"), "human_adjudication_questions")
        elif _texts(
            plan.get("human_adjudication_questions"),
            "human_adjudication_questions",
            nonempty=False,
        ):
            raise ValueError("human questions belong only to adjudication dispositions")
        if disposition == "ELIGIBLE_FOR_LATER_CLOSURE":
            raise ValueError("later-closure eligibility is unsupported without lossless proof")
        if _mapping(plan.get("authority"), "authority") != EXPECTED_AUTHORITY:
            raise ValueError("plan authority must remain exact and non-promoting")
        plan_by_pr[pr_number] = plan

    if set(plan_by_pr) != set(EXPECTED_PRS):
        raise ValueError("parked PR coverage is incomplete")
    expected_candidates = {f"KU2D-CLE-{number:06d}" for number in range(1, 12)}
    if all_candidate_dependencies != expected_candidates:
        raise ValueError("candidate dependencies must cover CLE-000001 through CLE-000011 exactly")
    expected_candidate_claims = {f"KU2D-PCR-{number:06d}" for number in range(1, 60)}
    expected_synthesis_claims = {f"KU2D-SYN-{number:06d}" for number in range(1, 40)}
    if all_claim_dependencies != expected_candidate_claims | expected_synthesis_claims:
        raise ValueError("claim dependencies must cover all 59 candidate and 39 synthesis findings")

    summary = _mapping(record.get("summary"), "summary")
    expected_summary = {
        "parked_pr_count": 8,
        "planning_disposition_counts": disposition_counts,
        "closure_eligible_now_count": 0,
        "lossless_preservation_claim_count": 0,
        "candidate_dependency_count": 11,
        "claim_dependency_count": 98,
        "candidate_promotion_count": 0,
        "parked_pr_close_count": 0,
        "parked_pr_merge_count": 0,
        "parked_branch_mutation_count": 0,
        "branch_deletion_count": 0,
    }
    if summary != expected_summary:
        raise ValueError("plan summary is stale or action counts drifted")

    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_parked_evidence_disposition_plan(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached validated JSON object."""
    return validate_parked_evidence_disposition_plan(record)
