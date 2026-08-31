"""Pure validation for KU2D Evidence Recovery Prioritization v1.

The artifact ranks three reviewed recovery candidates.  It cannot make a
request, execute a rerun, mutate knowledge, or change any PR or branch.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import validate_safe_json_payload


PRIORITIZATION_SCHEMA = "ku2d.evidence-recovery-prioritization.v1"
EXPECTED_PRS = {
    37: {
        "candidate_id": "KU2D-ERP-PR37",
        "branch": "codex/overnight-marketplace-source-inventory",
        "head": "0e99926c72cec7e83e259408c153fd6c99fd1492",
        "cle": {"KU2D-CLE-000002", "KU2D-CLE-000003"},
        "claims": {f"KU2D-PCR-{number:06d}" for number in range(11, 22)},
    },
    39: {
        "candidate_id": "KU2D-ERP-PR39",
        "branch": "codex/overnight-coffee-source-expansion",
        "head": "441c71d678a30cc62b742ea58f23f629a9d1e2d6",
        "cle": {"KU2D-CLE-000006", "KU2D-CLE-000007"},
        "claims": {f"KU2D-PCR-{number:06d}" for number in range(29, 38)},
    },
    40: {
        "candidate_id": "KU2D-ERP-PR40",
        "branch": "codex/overnight-qdiving-source-expansion",
        "head": "5f972d456415dbd0d8ae695f02c056e4a7c76e56",
        "cle": {"KU2D-CLE-000008", "KU2D-CLE-000009", "KU2D-CLE-000010"},
        "claims": {f"KU2D-PCR-{number:06d}" for number in range(38, 49)},
    },
}
EXPECTED_WEIGHTS = {
    "cross_source_domain_reuse_value": 20,
    "evidence_gap_leverage": 25,
    "expected_learning_gain": 20,
    "feasibility_compliance": 15,
    "dependency_reduction": 10,
    "effort_cost": 10,
}
EXPECTED_BOUNDARIES = {
    "storage_neutral": True,
    "planning_only": True,
    "live_request_count": 0,
    "rerun_execution": False,
    "candidate_promotion_count": 0,
    "learning_memory_write": False,
    "reviewed_corpus_write": False,
    "core_knowledge_write": False,
    "human_confirmation_write": False,
    "ground_truth_write": False,
    "parked_pr_close_count": 0,
    "parked_pr_merge_count": 0,
    "parked_ref_mutation_count": 0,
    "branch_deletion_count": 0,
    "cleanup_execution": False,
    "runtime_auto_write": False,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "ml_dataset_export": False,
    "survey_doe_sem_work": False,
    "broader_recommendation_or_ranking": False,
}
EXPECTED_EVIDENCE_SCHEMAS = {
    "ku2d.parked-evidence-disposition-plan.v1",
    "ku2d.parked-candidate-review.v1",
    "ku2d.parked-synthesis-review.v1",
    "ku2d.candidate-learning-evidence-registry.v1",
    "ku2d.branch-pr-disposition-registry.v1",
    "ku2d.core-knowledge-taxonomy.v1",
}
FORBIDDEN_ACTION_KEYS = {
    "execute_rerun",
    "dispatch_rerun",
    "request_url",
    "source_url",
    "browser_command",
    "api_call",
    "close_pr",
    "merge_pr",
    "delete_branch",
    "mutate_ref",
    "cleanup_command",
    "promote_candidate",
    "write_learning_memory",
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
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


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
            raise ValueError(f"executable or mutating fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden_keys(child)


def _rank_key(candidate: dict[str, Any]) -> tuple[int, int, int, int, int]:
    scores = candidate["scores"]
    return (
        -candidate["weighted_points"],
        -scores["evidence_gap_leverage"],
        -scores["feasibility_compliance"],
        -scores["dependency_reduction"],
        candidate["pr_number"],
    )


def validate_evidence_recovery_prioritization(record: dict[str, Any]) -> dict[str, Any]:
    """Validate exact provenance, scoring, recommendation, and zero-action bounds."""
    if not isinstance(record, dict) or record.get("schema") != PRIORITIZATION_SCHEMA:
        raise ValueError(f"schema must be {PRIORITIZATION_SCHEMA}")
    if record.get("version") != "1.0":
        raise ValueError("prioritization version must be 1.0")
    _walk_forbidden_keys(record)
    _timestamp(record.get("prioritized_at"), "prioritized_at")
    _text(record.get("repository"), "repository")
    if record.get("authoritative_branch") != "codex/ku2d-evidence-recovery-prioritization-v1":
        raise ValueError("authoritative branch drifted")
    if record.get("base_branch") != "integration/data-acquisition-platform":
        raise ValueError("base branch drifted")
    if _sha(record.get("base_sha"), "base_sha") != "01d6ad74626ea0e768f7f5f7acf5ddbe71bb7972":
        raise ValueError("merged disposition-plan base SHA drifted")
    if _mapping(record.get("boundaries"), "boundaries") != EXPECTED_BOUNDARIES:
        raise ValueError("boundaries must remain exact, non-executing, and non-authorizing")

    scope = _mapping(record.get("scope"), "scope")
    if scope != {
        "candidate_pr_numbers": [37, 39, 40],
        "required_disposition": "NEEDS_TARGETED_EVIDENCE_RERUN",
        "selection_count": 1,
        "historical_heads_are_immutable": True,
        "current_state_observed": "open-draft-unmerged",
        "live_rerun_authorized": False,
    }:
        raise ValueError("scope must cover exactly PRs #37, #39, and #40 without rerun authority")

    evidence_sources = _list(record.get("evidence_sources"), "evidence_sources")
    evidence_ids: set[str] = set()
    evidence_schemas: set[str] = set()
    for raw in evidence_sources:
        source = _mapping(raw, "evidence_source")
        evidence_id = _text(source.get("evidence_id"), "evidence_id")
        if evidence_id in evidence_ids:
            raise ValueError("evidence IDs must be unique")
        evidence_ids.add(evidence_id)
        evidence_schemas.add(_text(source.get("schema"), "evidence_source.schema"))
        _text(source.get("path"), "evidence_source.path")
        _text(source.get("authority"), "evidence_source.authority")
    if evidence_schemas != EXPECTED_EVIDENCE_SCHEMAS:
        raise ValueError("required merged evidence sources are incomplete")

    model = _mapping(record.get("scoring_model"), "scoring_model")
    if _mapping(model.get("scale"), "scale") != {
        "minimum": 0,
        "maximum": 5,
        "direction": "higher-is-better",
        "integer_scores_only": True,
    }:
        raise ValueError("score scale must remain exact")
    _text(model.get("formula"), "scoring_model.formula")
    criteria = _list(model.get("criteria"), "scoring_model.criteria")
    weights: dict[str, int] = {}
    for raw in criteria:
        criterion = _mapping(raw, "criterion")
        name = _text(criterion.get("criterion"), "criterion.name")
        weight = criterion.get("weight_percent")
        if name in weights or not isinstance(weight, int) or isinstance(weight, bool):
            raise ValueError("criteria must have unique integer weights")
        weights[name] = weight
        _text(criterion.get("rationale"), "criterion.rationale")
    if weights != EXPECTED_WEIGHTS or sum(weights.values()) != 100:
        raise ValueError("criterion weights must remain exact and sum to 100")
    if _texts(model.get("tie_breakers"), "tie_breakers") != [
        "higher evidence_gap_leverage score",
        "higher feasibility_compliance score",
        "higher dependency_reduction score",
        "lower PR number",
    ]:
        raise ValueError("tie breakers must remain deterministic and exact")

    candidates = _list(record.get("candidates"), "candidates")
    if len(candidates) != 3:
        raise ValueError("exactly three candidates are required")
    by_pr: dict[int, dict[str, Any]] = {}
    all_gap_ids: set[str] = set()
    for raw in candidates:
        candidate = _mapping(raw, "candidate")
        pr_number = candidate.get("pr_number")
        if pr_number not in EXPECTED_PRS or pr_number in by_pr:
            raise ValueError("candidates must cover PRs #37, #39, and #40 exactly")
        expected = EXPECTED_PRS[pr_number]
        if candidate.get("candidate_id") != expected["candidate_id"]:
            raise ValueError("candidate ID drifted")
        if candidate.get("branch") != expected["branch"] or candidate.get("head_sha") != expected["head"]:
            raise ValueError("parked branch/head provenance drifted")
        _sha(candidate.get("historical_base_sha"), "historical_base_sha")
        if _mapping(candidate.get("observed_pr_state"), "observed_pr_state") != {
            "open": True,
            "draft": True,
            "merged": False,
            "head_unchanged": True,
        }:
            raise ValueError("parked PR state drifted")
        if candidate.get("planning_disposition") != "NEEDS_TARGETED_EVIDENCE_RERUN":
            raise ValueError("candidate disposition drifted")
        _text(candidate.get("domain"), "candidate.domain")
        candidate_ids = set(_texts(candidate.get("candidate_evidence_ids"), "candidate_evidence_ids"))
        claim_ids = set(_texts(candidate.get("claim_dependency_ids"), "claim_dependency_ids"))
        if candidate_ids != expected["cle"] or claim_ids != expected["claims"]:
            raise ValueError("candidate or claim dependencies drifted")

        mapped_candidates: set[str] = set()
        mapped_claims: set[str] = set()
        for raw_gap in _list(candidate.get("missing_evidence"), "missing_evidence"):
            gap = _mapping(raw_gap, "missing_evidence item")
            gap_id = _text(gap.get("gap_id"), "gap_id")
            if gap_id in all_gap_ids:
                raise ValueError("gap IDs must be globally unique")
            all_gap_ids.add(gap_id)
            _texts(gap.get("target_sources"), "target_sources")
            _text(gap.get("requirement"), "requirement")
            gap_candidates = set(_texts(gap.get("candidate_evidence_ids"), "gap candidate IDs", nonempty=False))
            gap_claims = set(_texts(gap.get("claim_ids"), "gap claim IDs"))
            if not gap_candidates <= candidate_ids or not gap_claims <= claim_ids:
                raise ValueError("gap mapping references an out-of-scope dependency")
            if not isinstance(gap.get("in_targeted_rerun_scope"), bool):
                raise ValueError("gap scope flag must be boolean")
            mapped_candidates.update(gap_candidates)
            mapped_claims.update(gap_claims)
        if mapped_candidates != candidate_ids:
            raise ValueError("every CLE dependency must map to exact missing evidence")

        non_rerun_claims: set[str] = set()
        for raw_claim in _list(
            candidate.get("claims_not_requiring_rerun_evidence"),
            "claims_not_requiring_rerun_evidence",
        ):
            claim = _mapping(raw_claim, "non-rerun claim")
            claim_id = _text(claim.get("claim_id"), "non-rerun claim ID")
            if claim_id in non_rerun_claims:
                raise ValueError("non-rerun claim IDs must be unique")
            non_rerun_claims.add(claim_id)
            _text(claim.get("reason"), "non-rerun claim reason")
        if mapped_claims & non_rerun_claims or mapped_claims | non_rerun_claims != claim_ids:
            raise ValueError("every reviewed claim must map exactly once to a gap or no-rerun reason")

        scores = _mapping(candidate.get("scores"), "scores")
        if set(scores) != set(EXPECTED_WEIGHTS):
            raise ValueError("candidate scores must cover every criterion exactly")
        for name, score in scores.items():
            if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5:
                raise ValueError(f"{name} score must be an integer from 0 through 5")
        rationales = _mapping(candidate.get("score_rationale"), "score_rationale")
        if set(rationales) != set(EXPECTED_WEIGHTS):
            raise ValueError("score rationales must cover every criterion exactly")
        for name, rationale in rationales.items():
            _text(rationale, f"score rationale {name}")
        weighted_points = sum(scores[name] * weight for name, weight in EXPECTED_WEIGHTS.items())
        if candidate.get("weighted_points") != weighted_points:
            raise ValueError("weighted score arithmetic drifted")
        if candidate.get("normalized_score") != weighted_points / 100:
            raise ValueError("normalized score arithmetic drifted")
        if not isinstance(candidate.get("rank"), int):
            raise ValueError("rank must be an integer")
        if candidate.get("rerun_execution_authorized") is not False:
            raise ValueError("a prioritization candidate cannot authorize rerun execution")
        _text(candidate.get("ranking_change_evidence"), "ranking_change_evidence")
        by_pr[pr_number] = candidate

    if set(by_pr) != set(EXPECTED_PRS):
        raise ValueError("candidate PR coverage is incomplete")
    ranked = sorted(by_pr.values(), key=_rank_key)
    for expected_rank, candidate in enumerate(ranked, start=1):
        if candidate["rank"] != expected_rank:
            raise ValueError("candidate ranks do not match deterministic scoring")
        if expected_rank == 1:
            if candidate.get("wait_reason") is not None:
                raise ValueError("the first-ranked candidate cannot have a wait reason")
        else:
            _text(candidate.get("wait_reason"), "wait_reason")

    recommendation = _mapping(record.get("recommendation"), "recommendation")
    winner = ranked[0]
    if recommendation.get("recommended_candidate_id") != winner["candidate_id"]:
        raise ValueError("recommendation must select the unique rank-one candidate")
    if recommendation.get("recommended_pr_number") != winner["pr_number"]:
        raise ValueError("recommended PR must match the rank-one candidate")
    _text(recommendation.get("recommended_scope"), "recommended_scope")
    _text(recommendation.get("reason"), "recommendation.reason")
    if recommendation.get("recommendation_is_execution_authority") is not False:
        raise ValueError("recommendation cannot become execution authority")
    if recommendation.get("separate_human_authorization_required_before_rerun") is not True:
        raise ValueError("a separate human authorization must precede any rerun")
    if recommendation.get("automatic_follow_on") is not False:
        raise ValueError("automatic follow-on is forbidden")

    validate_safe_json_payload(record)
    return deepcopy(record)


def serialize_evidence_recovery_prioritization(record: dict[str, Any]) -> dict[str, Any]:
    """Return a detached validated JSON-safe prioritization object."""
    return validate_evidence_recovery_prioritization(record)
