"""Pure validation for the KU2D Branch/PR Disposition Register v1.

The register is a storage-neutral evidence snapshot.  This module performs no
GitHub operation, git mutation, branch deletion, acquisition, runtime write,
production authorization, scheduling, ML execution, or export.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from acquisition_learning_record import serialize_json_object, validate_safe_json_payload


REGISTRY_SCHEMA = "ku2d.branch-pr-disposition-registry.v1"
DISPOSITIONS = {
    "ACTIVE",
    "MERGED_HISTORICAL",
    "PARKED_REVIEWED",
    "PARKED_UNREVIEWED",
    "NEEDS_REVIEW",
    "SUPERSEDED",
    "SAFE_TO_DELETE_CANDIDATE",
}
PR_STATES = {"open", "closed", "not_opened"}
REVIEW_STATUSES = {"active", "merged_reviewed", "reviewed", "unreviewed", "needs_review"}
KNOWLEDGE_PROJECTIONS = {
    "active_feature_work",
    "integration",
    "learning_memory",
    "reviewed_learning_corpus",
    "core_knowledge",
    "candidate_learning_evidence_only",
    "not_durably_projected",
}
EXPECTED_BOUNDARIES = {
    "storage_neutral": True,
    "branch_mutation_enabled": False,
    "branch_deletion_performed": False,
    "automatic_cleanup": False,
    "live_request_count": 0,
    "runtime_auto_write": False,
    "production_authorized": False,
    "production_store": False,
    "scheduler_action": None,
    "ml_training_or_inference": False,
    "ml_dataset_export": False,
}
FORBIDDEN_ACTION_KEYS = {
    "delete_branch",
    "delete_branches",
    "deletion_command",
    "cleanup_command",
    "execute_cleanup",
    "branch_mutation",
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


def _sha(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    text = _text(value, field)
    if len(text) != 40 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be a lowercase 40-character git SHA")
    return text


def _observed_at(value: Any, field: str) -> str:
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
            raise ValueError(f"executable cleanup/deletion fields are forbidden: {sorted(found)}")
        for child in value.values():
            _walk_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _walk_forbidden_keys(child)


def _validate_pr(branch: dict[str, Any], disposition: str) -> dict[str, Any]:
    pr = _mapping(branch.get("pr"), "branch.pr")
    state = pr.get("state")
    if state not in PR_STATES:
        raise ValueError("branch.pr.state is invalid")
    number = pr.get("number")
    if state == "not_opened":
        if number is not None or pr.get("draft") is not None or pr.get("merged") is not False:
            raise ValueError("not-opened PR state cannot claim a number, draft state, or merge")
    else:
        if not isinstance(number, int) or number <= 0:
            raise ValueError("opened PRs require a positive PR number")
        if not isinstance(pr.get("draft"), bool) or not isinstance(pr.get("merged"), bool):
            raise ValueError("opened PRs require boolean draft and merged fields")
    _text(pr.get("base"), "branch.pr.base")
    if state == "open" and pr.get("merged") is not False:
        raise ValueError("open PR cannot be merged")
    if pr.get("merged") is True and state != "closed":
        raise ValueError("merged PR must be closed")
    if disposition == "ACTIVE" and state not in {"open", "not_opened"}:
        raise ValueError("active branch must have an open or not-yet-opened PR")
    return pr


def _validate_tree_proof(branch: dict[str, Any], pr: dict[str, Any], disposition: str) -> None:
    merge = _mapping(branch.get("merge_proof"), "branch.merge_proof")
    squash_sha = _sha(merge.get("squash_sha"), "merge_proof.squash_sha", nullable=True)
    equivalent = merge.get("tree_equivalent")
    diff_count = merge.get("tree_diff_file_count")
    advisory = branch.get("safe_delete_advisory")
    if disposition == "SAFE_TO_DELETE_CANDIDATE":
        if pr.get("state") != "closed" or pr.get("merged") is not True:
            raise ValueError("safe-delete candidate requires a closed merged PR")
        if squash_sha is None or equivalent is not True or diff_count != 0:
            raise ValueError("safe-delete candidate requires exact merged-tree equivalence proof")
        if advisory is not True or branch.get("tree_loss_risk") != "low":
            raise ValueError("safe-delete candidate must remain advisory with low tree-loss risk")
        if not _text(branch.get("deletion_risk_note"), "deletion_risk_note").lower().startswith("low"):
            raise ValueError("safe-delete candidate requires an explicit low-risk note")
    else:
        if advisory is not False:
            raise ValueError("only safe-delete candidates may carry the advisory flag")
        if disposition in {"ACTIVE", "PARKED_UNREVIEWED", "NEEDS_REVIEW"}:
            if squash_sha is not None or equivalent is not False or diff_count is not None:
                raise ValueError("unmerged branch cannot claim merged-tree equivalence")


def validate_branch_pr_disposition_registry(
    record: dict[str, Any],
    *,
    expected_branch_heads: dict[str, str] | None = None,
    expected_pr_states: dict[str, tuple[int | None, str, bool]] | None = None,
) -> dict[str, Any]:
    """Validate a complete point-in-time governance snapshot.

    Optional expected maps make callers fail closed when fresh repository/PR
    evidence differs from the durable snapshot.  The validator itself remains
    pure and performs no network, git, or filesystem operation.
    """
    if not isinstance(record, dict) or record.get("schema") != REGISTRY_SCHEMA:
        raise ValueError(f"schema must be {REGISTRY_SCHEMA}")
    if record.get("version") != "1.0":
        raise ValueError("registry version must be 1.0")
    _walk_forbidden_keys(record)
    observed_at = _observed_at(record.get("observed_at"), "observed_at")
    _text(record.get("repository"), "repository")
    authoritative = _text(record.get("authoritative_branch"), "authoritative_branch")
    boundaries = _mapping(record.get("boundaries"), "boundaries")
    if boundaries != EXPECTED_BOUNDARIES:
        raise ValueError("registry boundaries must remain storage-neutral and non-authorizing")

    branches = _list(record.get("branches"), "branches")
    names: set[str] = set()
    ids: set[str] = set()
    pr_numbers: set[int] = set()
    disposition_counts = {item: 0 for item in DISPOSITIONS}
    actual_heads: dict[str, str] = {}
    actual_pr_states: dict[str, tuple[int | None, str, bool]] = {}
    active: list[str] = []
    parked_unique: list[str] = []
    safe_candidates: list[str] = []

    for item in branches:
        branch = _mapping(item, "branch")
        branch_id = _text(branch.get("branch_id"), "branch_id")
        name = _text(branch.get("branch"), "branch")
        if branch_id in ids or name in names:
            raise ValueError("branch IDs and names must be unique")
        ids.add(branch_id)
        names.add(name)
        if not name.startswith("codex/"):
            raise ValueError("registry may contain only codex/* branches")
        _text(branch.get("purpose"), "purpose")
        branch_observed_at = _observed_at(branch.get("observed_at"), "branch.observed_at")
        if datetime.fromisoformat(branch_observed_at) > datetime.fromisoformat(observed_at):
            raise ValueError("branch evidence cannot be newer than the registry snapshot")
        head_sha = _sha(branch.get("head_sha"), "head_sha")
        actual_heads[name] = head_sha
        disposition = branch.get("disposition")
        if disposition not in DISPOSITIONS:
            raise ValueError("branch disposition is invalid")
        disposition_counts[disposition] += 1
        pr = _validate_pr(branch, disposition)
        if pr.get("number") is not None:
            if pr["number"] in pr_numbers:
                raise ValueError("PR numbers must be unique across branch records")
            pr_numbers.add(pr["number"])
        actual_pr_states[name] = (pr.get("number"), pr["state"], bool(pr.get("merged")))
        _validate_tree_proof(branch, pr, disposition)

        projections = set(_texts(branch.get("knowledge_projection"), "knowledge_projection"))
        if not projections <= KNOWLEDGE_PROJECTIONS:
            raise ValueError("knowledge projection contains an unsupported state")
        candidate_refs = _texts(
            branch.get("candidate_evidence_references"),
            "candidate_evidence_references",
            nonempty=False,
        )
        reviewed = bool({"reviewed_learning_corpus", "core_knowledge"} & projections)
        if "candidate_learning_evidence_only" in projections:
            if reviewed or "integration" in projections or not candidate_refs:
                raise ValueError("candidate-only evidence cannot be represented as reviewed, core, or integrated")
            if branch.get("review_status") != "unreviewed":
                raise ValueError("candidate-only knowledge must remain unreviewed")
        elif candidate_refs:
            raise ValueError("candidate references require candidate-only projection")

        review_status = branch.get("review_status")
        if review_status not in REVIEW_STATUSES:
            raise ValueError("review status is invalid")
        unique = branch.get("unique_code_unmerged")
        if not isinstance(unique, bool):
            raise ValueError("unique_code_unmerged must be boolean")
        warning = _text(branch.get("unique_work_warning"), "unique_work_warning")
        if unique and "unique unmerged" not in warning.lower():
            raise ValueError("unique work requires an explicit unique-unmerged warning")
        if not unique and warning != "No unique unmerged tree content; merged-tree proof retained.":
            raise ValueError("merged branches must use the exact no-unique-work warning")
        if branch.get("deletion_allowed") is not False:
            raise ValueError("the register cannot authorize deletion")
        _texts(branch.get("dependencies"), "dependencies", nonempty=False)
        _text(branch.get("recommended_next_action"), "recommended_next_action")
        _text(branch.get("deletion_risk_note"), "deletion_risk_note")
        _texts(branch.get("evidence_references"), "evidence_references")

        if disposition == "ACTIVE":
            active.append(name)
            if name != authoritative or branch.get("deletion_allowed") is not False:
                raise ValueError("active branch must be authoritative and non-deletable")
            if not unique or review_status != "active":
                raise ValueError("active branch must retain unique active work")
        if disposition == "PARKED_UNREVIEWED":
            parked_unique.append(name)
            if pr.get("state") != "open" or pr.get("draft") is not True:
                raise ValueError("parked-unreviewed branch must retain an open Draft PR")
            if not unique or review_status != "unreviewed":
                raise ValueError("parked-unreviewed branch must preserve unique unreviewed work")
        if disposition == "SAFE_TO_DELETE_CANDIDATE":
            safe_candidates.append(name)
            if unique:
                raise ValueError("safe-delete candidate cannot retain unique unmerged code")

    if active != [authoritative]:
        raise ValueError("registry must have exactly one authoritative active branch")
    if expected_branch_heads is not None:
        if set(actual_heads) != set(expected_branch_heads):
            raise ValueError("registry branch heads are stale or incomplete")
        stale = {
            name for name, sha in actual_heads.items()
            if name != authoritative and expected_branch_heads.get(name) != sha
        }
        if stale:
            raise ValueError(f"registry branch heads are stale: {sorted(stale)}")
    if expected_pr_states is not None and actual_pr_states != expected_pr_states:
        raise ValueError("registry PR states are stale or incomplete")

    snapshot = _mapping(record.get("snapshot"), "snapshot")
    if snapshot.get("remote_codex_branch_count") != len(branches):
        raise ValueError("snapshot branch count does not reconcile")
    if snapshot.get("associated_pr_count") != len(pr_numbers):
        raise ValueError("snapshot PR count does not reconcile")
    if snapshot.get("source_branch_name_heuristics_used") is not False:
        raise ValueError("branch-name heuristics cannot be disposition authority")
    if snapshot.get("fresh_remote_refs_checked") is not True or snapshot.get("fresh_pr_state_checked") is not True:
        raise ValueError("fresh branch and PR evidence is required")

    summary = _mapping(record.get("summary"), "summary")
    expected_counts = {key: disposition_counts[key] for key in sorted(DISPOSITIONS)}
    if summary.get("disposition_counts") != expected_counts:
        raise ValueError("summary disposition counts do not match branch records")
    if summary.get("active_branch") != authoritative:
        raise ValueError("summary active branch mismatch")
    if summary.get("parked_unique_unmerged_branches") != parked_unique:
        raise ValueError("summary parked unique-work list mismatch")
    if summary.get("safe_to_delete_candidates") != safe_candidates:
        raise ValueError("summary safe-delete candidate list mismatch")
    if summary.get("branch_deletion_count") != 0:
        raise ValueError("branch deletion count must remain zero")

    priorities = _list(record.get("review_priorities"), "review_priorities")
    ranked = []
    for expected_rank, priority in enumerate(priorities, 1):
        priority = _mapping(priority, "review_priority")
        if priority.get("rank") != expected_rank:
            raise ValueError("review priorities must be contiguous and ordered")
        name = _text(priority.get("branch"), "review_priority.branch")
        if name not in parked_unique or name in ranked:
            raise ValueError("review priority must reference each parked-unreviewed branch once")
        ranked.append(name)
        _text(priority.get("pattern_or_capability"), "review_priority.pattern_or_capability")
        _text(priority.get("rationale"), "review_priority.rationale")
    if set(ranked) != set(parked_unique):
        raise ValueError("every parked-unreviewed branch requires review priority guidance")

    return validate_safe_json_payload(record)


def serialize_branch_pr_disposition_registry(record: dict[str, Any]) -> dict[str, Any]:
    validated = validate_branch_pr_disposition_registry(deepcopy(record))
    return serialize_json_object(validated)
