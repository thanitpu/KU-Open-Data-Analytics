"""Storage-neutral contracts for GitHub-mediated KU2D agent handoffs.

The protocol coordinates work; it does not authorize production activity,
schedule acquisition, write files automatically, or create Learning Memory.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from acquisition_learning_record import serialize_json_object, validate_safe_json_payload


PROMPT_SCHEMA = "ku2d.agent-handoff-prompt.v1"
RESULT_SCHEMA = "ku2d.agent-handoff-result.v1"
ASSISTANT_REVIEW_SCHEMA = "ku2d.agent-handoff-assistant-review.v1"
HUMAN_DECISION_SCHEMA = "ku2d.agent-handoff-human-decision.v1"
QUEUE_SCHEMA = "ku2d.agent-handoff-queue.v1"
BRANCH_HANDOFF_SCHEMA = "ku2d.agent-handoff-branch-handoff.v1"

ACTORS = {"codex", "assistant", "human", "none"}
PROMPT_STATES = {
    "draft", "ready_for_codex", "in_progress", "result_submitted", "reviewed",
    "human_decision_required", "completed", "superseded",
}
RESULT_STATUSES = {"succeeded", "partial", "blocked", "failed"}
REVIEW_RESULTS = {
    "accepted", "correction_required", "rejected", "insufficient_evidence",
    "deferred", "human_decision_required",
}
HUMAN_DECISIONS = {"confirmed", "rejected", "deferred"}

_ID_PATTERNS = {
    "prompt_id": re.compile(r"^KU2D-P-\d{6}$"),
    "result_id": re.compile(r"^KU2D-R-\d{6}$"),
    "review_id": re.compile(r"^KU2D-V-\d{6}$"),
    "human_decision_id": re.compile(r"^KU2D-H-\d{6}$"),
    "handoff_id": re.compile(r"^KU2D-BH-\d{6}$"),
}
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BRANCH_RE = re.compile(r"^(?!/)(?!.*(?:\.\.|//))[A-Za-z0-9][A-Za-z0-9._/-]*[A-Za-z0-9]$")
_TRANSITIONS = {
    "draft": {"ready_for_codex", "superseded"},
    "ready_for_codex": {"in_progress", "result_submitted", "superseded"},
    "in_progress": {"result_submitted", "superseded"},
    "result_submitted": {"reviewed", "human_decision_required", "superseded"},
    "reviewed": {"completed", "human_decision_required", "superseded"},
    "human_decision_required": {"completed", "superseded"},
    "completed": set(),
    "superseded": set(),
}


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _mapping(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{field} must be a JSON array" + ("" if allow_empty else " with entries"))
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} entries must be non-empty strings")
    return value


def _record_id(record: dict[str, Any], key: str) -> str:
    value = _nonempty(record.get(key), key)
    if not _ID_PATTERNS[key].fullmatch(value):
        raise ValueError(f"{key} must use the stable KU2D ID family")
    return value


def _optional_id(value: Any, key: str) -> str | None:
    if value is None:
        return None
    text = _nonempty(value, key)
    if not _ID_PATTERNS[key].fullmatch(text):
        raise ValueError(f"{key} must use the stable KU2D ID family")
    return text


def validate_branch_name(value: Any) -> str:
    """Validate a repository branch name without consulting or changing git state."""
    branch = _nonempty(value, "authoritative_branch")
    if (
        not _BRANCH_RE.fullmatch(branch) or branch.startswith("refs/")
        or branch.endswith((".", "/")) or "@{" in branch
        or any(marker in branch for marker in ("~", "^", ":", "?", "*", "[", "\\"))
    ):
        raise ValueError("authoritative_branch is not a safe branch name")
    return branch


def validate_commit_sha(value: Any, field: str) -> str:
    commit = _nonempty(value, field)
    if not _COMMIT_SHA_RE.fullmatch(commit):
        raise ValueError(f"{field} must be a full lowercase commit SHA")
    return commit


def _prompt_authoritative_branch(record: dict[str, Any]) -> str | None:
    top_level = record.get("authoritative_branch")
    provenance = record.get("provenance")
    provenance_branch = provenance.get("authoritative_branch") if isinstance(provenance, dict) else None
    if top_level is not None:
        top_level = validate_branch_name(top_level)
    if provenance_branch is not None:
        provenance_branch = validate_branch_name(provenance_branch)
    if top_level is not None and provenance_branch is not None and top_level != provenance_branch:
        raise ValueError("Prompt authoritative_branch locations contradict")
    return top_level if top_level is not None else provenance_branch


def _validate_boundaries(record: dict[str, Any]) -> dict[str, Any]:
    boundaries = _mapping(record, "boundaries")
    required = {
        "coordination_only": True,
        "production_authorized": False,
        "automatic_learning_memory_export": False,
        "scheduler_action": None,
    }
    for key, expected in required.items():
        if boundaries.get(key) is not expected:
            raise ValueError(f"boundaries.{key} must be {expected!r}")
    return boundaries


def validate_prompt_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != PROMPT_SCHEMA:
        raise ValueError(f"prompt schema must be {PROMPT_SCHEMA}")
    _record_id(record, "prompt_id")
    _nonempty(record.get("created_at"), "created_at")
    creator = _mapping(record, "created_by")
    if creator.get("actor") not in {"assistant", "human"}:
        raise ValueError("prompt created_by.actor must be assistant or human")
    _nonempty(creator.get("actor_id"), "created_by.actor_id")
    if record.get("status") not in {"draft", "ready_for_codex"}:
        raise ValueError("an immutable Prompt Record must start as draft or ready_for_codex")
    _nonempty(record.get("objective"), "objective")
    _string_list(record.get("instructions"), "instructions", allow_empty=False)
    _mapping(record, "expected_result")
    provenance = _mapping(record, "provenance")
    _prompt_authoritative_branch(record)
    _validate_boundaries(record)
    return validate_safe_json_payload(record)


def validate_result_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != RESULT_SCHEMA:
        raise ValueError(f"result schema must be {RESULT_SCHEMA}")
    result_id = _record_id(record, "result_id")
    prompt_id = _record_id(record, "prompt_id")
    if result_id == prompt_id:
        raise ValueError("Result cannot reference itself")
    _nonempty(record.get("submitted_at"), "submitted_at")
    submitter = _mapping(record, "submitted_by")
    if submitter.get("actor") != "codex":
        raise ValueError("Result must be submitted by codex")
    _nonempty(submitter.get("actor_id"), "submitted_by.actor_id")
    if record.get("status") not in RESULT_STATUSES:
        raise ValueError("Result status is invalid")
    _nonempty(record.get("summary"), "summary")
    _string_list(record.get("evidence_references"), "evidence_references")
    verification = _mapping(record, "verification")
    if not isinstance(verification.get("deterministic_tests_passed"), bool):
        raise ValueError("verification.deterministic_tests_passed must be boolean")
    if not isinstance(verification.get("live_request_count"), int) or verification["live_request_count"] < 0:
        raise ValueError("verification.live_request_count must be a non-negative integer")
    _mapping(record, "provenance")
    _validate_boundaries(record)
    return validate_safe_json_payload(record)


def validate_assistant_review_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != ASSISTANT_REVIEW_SCHEMA:
        raise ValueError(f"assistant review schema must be {ASSISTANT_REVIEW_SCHEMA}")
    review_id = _record_id(record, "review_id")
    prompt_id = _record_id(record, "prompt_id")
    result_id = _record_id(record, "result_id")
    if review_id in {prompt_id, result_id}:
        raise ValueError("Assistant Review cannot reference itself")
    _nonempty(record.get("reviewed_at"), "reviewed_at")
    reviewer = _mapping(record, "reviewed_by")
    if reviewer.get("actor") != "assistant":
        raise ValueError("Assistant Review must retain assistant authority")
    _nonempty(reviewer.get("actor_id"), "reviewed_by.actor_id")
    if reviewer.get("human_authority_claimed") is not False:
        raise ValueError("Assistant Review cannot claim human authority")
    if record.get("review_result") not in REVIEW_RESULTS:
        raise ValueError("Assistant Review result is invalid")
    if not isinstance(record.get("requires_human_decision"), bool):
        raise ValueError("requires_human_decision must be boolean")
    if (record["review_result"] == "human_decision_required") != record["requires_human_decision"]:
        raise ValueError("human-decision review result and flag must agree")
    _nonempty(record.get("reason_code"), "reason_code")
    _nonempty(record.get("explanation"), "explanation")
    _string_list(record.get("evidence_references"), "evidence_references")
    _mapping(record, "provenance")
    _validate_boundaries(record)
    return validate_safe_json_payload(record)


def validate_human_decision_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != HUMAN_DECISION_SCHEMA:
        raise ValueError(f"human decision schema must be {HUMAN_DECISION_SCHEMA}")
    decision_id = _record_id(record, "human_decision_id")
    references = {
        _record_id(record, "prompt_id"), _record_id(record, "result_id"),
        _record_id(record, "review_id"),
    }
    if decision_id in references:
        raise ValueError("Human Decision cannot reference itself")
    decider = _mapping(record, "decided_by")
    if decider.get("actor") != "human":
        raise ValueError("Human Decision requires human authority")
    _nonempty(decider.get("actor_id"), "decided_by.actor_id")
    _nonempty(record.get("decided_at"), "decided_at")
    if record.get("decision") not in HUMAN_DECISIONS:
        raise ValueError("Human Decision value is invalid")
    provenance = _mapping(record, "provenance")
    if provenance.get("decision_source") != "explicit_human_input":
        raise ValueError("Human Decision requires explicit human input provenance")
    _nonempty(record.get("reason_note"), "reason_note")
    _validate_boundaries(record)
    return validate_safe_json_payload(record)


def validate_prompt_state_transition(
    previous_state: str, next_state: str, *, explicit_replay: bool = False,
) -> str:
    if previous_state not in PROMPT_STATES or next_state not in PROMPT_STATES:
        raise ValueError("prompt state is invalid")
    if next_state in _TRANSITIONS[previous_state]:
        return next_state
    if previous_state in {"completed", "superseded"} and next_state == "ready_for_codex" and explicit_replay:
        return next_state
    raise ValueError(f"invalid prompt state transition: {previous_state} -> {next_state}")


def validate_queue_state(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != QUEUE_SCHEMA:
        raise ValueError(f"queue schema must be {QUEUE_SCHEMA}")
    _nonempty(record.get("updated_at"), "updated_at")
    if record.get("authoritative_branch") is not None:
        validate_branch_name(record["authoritative_branch"])
    latest_prompt = _optional_id(record.get("latest_prompt"), "prompt_id")
    latest_result = _optional_id(record.get("latest_result"), "result_id")
    latest_review = _optional_id(record.get("latest_review"), "review_id")
    latest_human = _optional_id(record.get("latest_human_decision"), "human_decision_id")
    states = _mapping(record, "prompt_states")
    for prompt_id, state in states.items():
        _optional_id(prompt_id, "prompt_id")
        if state not in PROMPT_STATES:
            raise ValueError("queue prompt state is invalid")
    completed = _string_list(record.get("completed_prompt_ids"), "completed_prompt_ids")
    if len(completed) != len(set(completed)):
        raise ValueError("completed_prompt_ids contains duplicates")
    for prompt_id in completed:
        _optional_id(prompt_id, "prompt_id")

    action = _mapping(record, "next_action")
    actor = action.get("actor")
    if actor not in ACTORS:
        raise ValueError("next_action.actor is invalid")
    action_prompt = _optional_id(action.get("prompt_id"), "prompt_id")
    action_result = _optional_id(action.get("result_id"), "result_id")
    action_review = _optional_id(action.get("review_id"), "review_id")
    action_human = _optional_id(action.get("human_decision_id"), "human_decision_id")
    if not isinstance(action.get("replay_requested"), bool):
        raise ValueError("next_action.replay_requested must be boolean")
    if actor != "none" and not action_prompt:
        raise ValueError("an actionable queue item requires prompt_id")
    if action_prompt and latest_prompt != action_prompt:
        raise ValueError("next_action.prompt_id must match latest_prompt")
    state = states.get(latest_prompt) if latest_prompt else None
    if actor == "codex":
        if state not in {"ready_for_codex", "in_progress"}:
            raise ValueError("codex may act only on ready or in-progress prompts")
        if latest_prompt in completed and not action["replay_requested"]:
            raise ValueError("completed prompt replay requires explicit request")
        if any(value is not None for value in (action_result, action_review, action_human)):
            raise ValueError("codex action cannot point at downstream records")
    elif actor == "assistant":
        if state != "result_submitted" or not action_result or action_result != latest_result:
            raise ValueError("assistant action requires the latest submitted Result")
        if action_review is not None or action_human is not None:
            raise ValueError("assistant action cannot claim review or human decision")
    elif actor == "human":
        if state != "human_decision_required" or not action_review or action_review != latest_review:
            raise ValueError("human action requires the latest Assistant Review")
        if action_result != latest_result or action_human is not None:
            raise ValueError("human action chain is inconsistent")
    elif any(value is not None for value in (action_prompt, action_result, action_review, action_human)):
        raise ValueError("none action must not reference a pending record")
    for prompt_id in completed:
        replaying = (
            prompt_id == latest_prompt and actor == "codex" and action["replay_requested"]
            and states.get(prompt_id) == "ready_for_codex"
        )
        if states.get(prompt_id) != "completed" and not replaying:
            raise ValueError("completed prompt history may be reopened only by explicit replay")
    return validate_safe_json_payload(record)


def branch_handoff_queue_snapshot(queue_state: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable queue facts needed to prove a branch transition."""
    queue = validate_queue_state(queue_state)
    latest_prompt = queue.get("latest_prompt")
    return {
        "updated_at": queue["updated_at"],
        "authoritative_branch": queue.get("authoritative_branch"),
        "latest_prompt": latest_prompt,
        "prompt_state": (queue.get("prompt_states") or {}).get(latest_prompt),
        "completed_prompt_ids": deepcopy(queue["completed_prompt_ids"]),
        "next_action": deepcopy(queue["next_action"]),
        "branch_handoff": deepcopy(queue.get("branch_handoff")),
    }


def branch_handoff_queue_fingerprint(snapshot: dict[str, Any]) -> str:
    """Fingerprint a detached queue snapshot with canonical JSON."""
    validate_safe_json_payload(snapshot)
    payload = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_handoff_snapshot(snapshot: Any, field: str) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError(f"{field} must be a JSON object")
    _nonempty(snapshot.get("updated_at"), f"{field}.updated_at")
    validate_branch_name(snapshot.get("authoritative_branch"))
    _optional_id(snapshot.get("latest_prompt"), "prompt_id")
    if snapshot.get("prompt_state") not in PROMPT_STATES:
        raise ValueError(f"{field}.prompt_state is invalid")
    completed = _string_list(snapshot.get("completed_prompt_ids"), f"{field}.completed_prompt_ids")
    if len(completed) != len(set(completed)):
        raise ValueError(f"{field}.completed_prompt_ids contains duplicates")
    action = _mapping(snapshot, "next_action")
    if action.get("actor") not in ACTORS or not isinstance(action.get("replay_requested"), bool):
        raise ValueError(f"{field}.next_action is invalid")
    for key, id_key in (
        ("prompt_id", "prompt_id"), ("result_id", "result_id"),
        ("review_id", "review_id"), ("human_decision_id", "human_decision_id"),
    ):
        _optional_id(action.get(key), id_key)
    _mapping(snapshot, "branch_handoff")
    return validate_safe_json_payload(snapshot)


def validate_branch_handoff_record(record: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless one source queue is closed before one target is initialized."""
    if not isinstance(record, dict) or record.get("schema") != BRANCH_HANDOFF_SCHEMA:
        raise ValueError(f"branch handoff schema must be {BRANCH_HANDOFF_SCHEMA}")
    _record_id(record, "handoff_id")
    _nonempty(record.get("created_at"), "created_at")
    from_branch = validate_branch_name(record.get("from_branch"))
    to_branch = validate_branch_name(record.get("to_branch"))
    if from_branch == to_branch:
        raise ValueError("branch handoff source and target must differ")
    base_sha = validate_commit_sha(record.get("base_sha"), "base_sha")
    target_head = validate_commit_sha(record.get("target_initial_head_sha"), "target_initial_head_sha")
    validate_commit_sha(record.get("source_close_commit_sha"), "source_close_commit_sha")
    if target_head != base_sha:
        raise ValueError("target initial head must exactly match branch handoff base_sha")
    target_prompt = _record_id({"prompt_id": record.get("target_prompt_id")}, "prompt_id")
    required = {
        "close_source_queue_before_switch": True,
        "initialize_target_queue": True,
        "target_initialization_succeeded": True,
        "human_authority_required": False,
    }
    for field, expected in required.items():
        if record.get(field) is not expected:
            raise ValueError(f"branch handoff {field} must be {expected!r}")

    source = _validate_handoff_snapshot(record.get("source_queue_snapshot"), "source_queue_snapshot")
    target = _validate_handoff_snapshot(record.get("target_queue_snapshot"), "target_queue_snapshot")
    if source["authoritative_branch"] != from_branch or target["authoritative_branch"] != to_branch:
        raise ValueError("branch handoff queue authority does not match from/to branches")
    if source["latest_prompt"] != target_prompt or target["latest_prompt"] != target_prompt:
        raise ValueError("branch handoff target_prompt_id does not match queue snapshots")
    if source["prompt_state"] != "in_progress" or target["prompt_state"] != "in_progress":
        raise ValueError("branch handoff Prompt must remain in progress across initialization")
    source_action = source["next_action"]
    target_action = target["next_action"]
    if source_action.get("actor") != "none" or any(
        source_action.get(field) is not None
        for field in ("prompt_id", "result_id", "review_id", "human_decision_id")
    ):
        raise ValueError("source queue must close before branch switch")
    if target_action.get("actor") != "codex" or target_action.get("prompt_id") != target_prompt:
        raise ValueError("initialized target queue must assign the target Prompt to codex")
    if any(target_action.get(field) is not None for field in ("result_id", "review_id", "human_decision_id")):
        raise ValueError("target codex action cannot carry downstream pointers")
    if source_action.get("replay_requested") or target_action.get("replay_requested"):
        raise ValueError("mechanical branch handoff cannot replay a completed Prompt")
    if set(source["completed_prompt_ids"]) - set(target["completed_prompt_ids"]):
        raise ValueError("target initialization removed completed Prompt history")

    source_marker = source["branch_handoff"]
    target_marker = target["branch_handoff"]
    common = {
        "handoff_id": record["handoff_id"], "from_branch": from_branch,
        "to_branch": to_branch, "base_sha": base_sha, "target_prompt_id": target_prompt,
        "close_source_queue_before_switch": True, "initialize_target_queue": True,
        "human_authority_required": False,
    }
    if source_marker.get("phase") != "source_closed" or any(source_marker.get(key) != value for key, value in common.items()):
        raise ValueError("source queue branch-handoff marker is stale or incomplete")
    if target_marker.get("phase") != "target_initialized" or any(target_marker.get(key) != value for key, value in common.items()):
        raise ValueError("target queue branch-handoff marker is stale or incomplete")
    if target_marker.get("target_initialization_succeeded") is not True:
        raise ValueError("target queue initialization did not succeed")
    if target_marker.get("target_initial_head_sha") != target_head:
        raise ValueError("target queue initial-head provenance is inconsistent")
    if target_marker.get("source_close_commit_sha") != record.get("source_close_commit_sha"):
        raise ValueError("target queue source-close provenance is inconsistent")

    if record.get("source_queue_fingerprint") != branch_handoff_queue_fingerprint(source):
        raise ValueError("source queue snapshot is stale or modified")
    if record.get("target_queue_fingerprint") != branch_handoff_queue_fingerprint(target):
        raise ValueError("target queue snapshot is stale or modified")
    _validate_boundaries(record)
    return validate_safe_json_payload(record)


def branch_handoff(
    *,
    from_branch: str,
    to_branch: str,
    base_sha: str,
    close_source_queue_before_switch: bool,
    initialize_target_queue: bool,
    target_prompt_id: str,
    human_authority_required: bool,
    source_queue: dict[str, Any],
    target_queue: dict[str, Any],
    source_close_commit_sha: str,
    target_initial_head_sha: str,
    target_initialization_succeeded: bool,
    created_at: str,
    handoff_id: str = "KU2D-BH-000001",
) -> dict[str, Any]:
    """Build a deterministic, storage-neutral mechanical branch-handoff proof."""
    source_snapshot = branch_handoff_queue_snapshot(source_queue)
    target_snapshot = branch_handoff_queue_snapshot(target_queue)
    record = {
        "schema": BRANCH_HANDOFF_SCHEMA,
        "handoff_id": handoff_id,
        "created_at": created_at,
        "from_branch": from_branch,
        "to_branch": to_branch,
        "base_sha": base_sha,
        "close_source_queue_before_switch": close_source_queue_before_switch,
        "initialize_target_queue": initialize_target_queue,
        "target_prompt_id": target_prompt_id,
        "human_authority_required": human_authority_required,
        "source_close_commit_sha": source_close_commit_sha,
        "target_initial_head_sha": target_initial_head_sha,
        "target_initialization_succeeded": target_initialization_succeeded,
        "source_queue_snapshot": source_snapshot,
        "target_queue_snapshot": target_snapshot,
        "source_queue_fingerprint": branch_handoff_queue_fingerprint(source_snapshot),
        "target_queue_fingerprint": branch_handoff_queue_fingerprint(target_snapshot),
        "boundaries": {
            "coordination_only": True,
            "production_authorized": False,
            "automatic_learning_memory_export": False,
            "scheduler_action": None,
        },
    }
    return validate_branch_handoff_record(record)


def _index(records: list[dict[str, Any]], id_key: str, validator) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        validator(record)
        record_id = record[id_key]
        if record_id in indexed:
            raise ValueError(f"duplicate {id_key}: {record_id}")
        indexed[record_id] = record
    return indexed


def validate_agent_handoff_bundle(
    prompt_records: list[dict[str, Any]], result_records: list[dict[str, Any]],
    assistant_review_records: list[dict[str, Any]], human_decision_records: list[dict[str, Any]],
    queue_state: dict[str, Any], *, previous_queue_state: dict[str, Any] | None = None,
    branch_handoff_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fail closed on broken chains, authority, queue state, and replay."""
    prompts = _index(prompt_records, "prompt_id", validate_prompt_record)
    results = _index(result_records, "result_id", validate_result_record)
    reviews = _index(assistant_review_records, "review_id", validate_assistant_review_record)
    humans = _index(human_decision_records, "human_decision_id", validate_human_decision_record)
    handoffs = _index(
        branch_handoff_records or [], "handoff_id", validate_branch_handoff_record,
    )
    queue = validate_queue_state(queue_state)

    all_ids = list(prompts) + list(results) + list(reviews) + list(humans) + list(handoffs)
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("coordination record IDs must be globally unique")
    for result in results.values():
        if result["prompt_id"] not in prompts:
            raise ValueError("orphan Result prompt_id")
    for review in reviews.values():
        result = results.get(review["result_id"])
        if review["prompt_id"] not in prompts or not result:
            raise ValueError("orphan Assistant Review chain")
        if result["prompt_id"] != review["prompt_id"]:
            raise ValueError("Assistant Review prompt/result chain is inconsistent")
    for human in humans.values():
        review = reviews.get(human["review_id"])
        result = results.get(human["result_id"])
        if not review or not result or human["prompt_id"] not in prompts:
            raise ValueError("orphan Human Decision chain")
        if not review["requires_human_decision"]:
            raise ValueError("Human Decision answers a review that did not request human authority")
        if {review["prompt_id"], result["prompt_id"]} != {human["prompt_id"]}:
            raise ValueError("Human Decision prompt chain is inconsistent")
        if review["result_id"] != human["result_id"]:
            raise ValueError("Human Decision result/review chain is inconsistent")

    for prompt_id in queue["prompt_states"]:
        if prompt_id not in prompts:
            raise ValueError("queue references an unknown Prompt")
    pointer_sets = (
        (queue.get("latest_prompt"), prompts, "Prompt"),
        (queue.get("latest_result"), results, "Result"),
        (queue.get("latest_review"), reviews, "Assistant Review"),
        (queue.get("latest_human_decision"), humans, "Human Decision"),
    )
    for record_id, records, label in pointer_sets:
        if record_id is not None and record_id not in records:
            raise ValueError(f"queue latest pointer references an unknown {label}")
    latest_prompt = queue.get("latest_prompt")
    state = queue["prompt_states"].get(latest_prompt) if latest_prompt else None
    latest_result = queue.get("latest_result")
    latest_review = queue.get("latest_review")
    latest_human = queue.get("latest_human_decision")
    actor = queue["next_action"]["actor"]
    if latest_prompt:
        prompt_branch = _prompt_authoritative_branch(prompts[latest_prompt])
        queue_branch = queue.get("authoritative_branch")
        if prompt_branch is not None and queue_branch != prompt_branch:
            matching_handoffs = [
                handoff for handoff in handoffs.values()
                if handoff["target_prompt_id"] == latest_prompt
                and handoff["from_branch"] == prompt_branch
                and handoff["to_branch"] == queue_branch
            ]
            if len(matching_handoffs) != 1:
                raise ValueError(
                    "queue authoritative_branch must match the latest Prompt or one valid branch handoff"
                )
    prompt_results = [record for record in results.values() if record["prompt_id"] == latest_prompt]
    prompt_reviews = [record for record in reviews.values() if record["prompt_id"] == latest_prompt]
    prompt_humans = [record for record in humans.values() if record["prompt_id"] == latest_prompt]
    if state in {"draft", "ready_for_codex", "in_progress", "superseded"}:
        if prompt_results or prompt_reviews or prompt_humans:
            raise ValueError("pre-result or superseded Prompt cannot have downstream records")
    elif state == "result_submitted":
        current_result = results.get(latest_result)
        if (
            not current_result or current_result["prompt_id"] != latest_prompt
            or len(prompt_results) != 1 or prompt_reviews or prompt_humans or actor != "assistant"
        ):
            raise ValueError("result_submitted state requires an unreviewed Result and assistant action")
    elif state == "reviewed":
        current_result = results.get(latest_result)
        current_review = reviews.get(latest_review)
        if (
            not current_result or current_result["prompt_id"] != latest_prompt
            or not current_review or current_review["prompt_id"] != latest_prompt
            or prompt_humans or actor != "none"
        ):
            raise ValueError("reviewed state requires Result and Assistant Review with no pending actor")
        if current_review["requires_human_decision"]:
            raise ValueError("a review requiring human authority cannot use reviewed terminal state")
    elif state == "human_decision_required":
        current_result = results.get(latest_result)
        current_review = reviews.get(latest_review)
        if (
            not current_result or current_result["prompt_id"] != latest_prompt
            or not current_review or current_review["prompt_id"] != latest_prompt
            or prompt_humans or actor != "human"
        ):
            raise ValueError("human_decision_required state requires a pending human action")
        if not current_review["requires_human_decision"]:
            raise ValueError("human queue action lacks a matching review request")
    elif state == "completed":
        current_result = results.get(latest_result)
        current_review = reviews.get(latest_review)
        current_human = humans.get(latest_human) if latest_human else None
        if (
            not current_result or current_result["prompt_id"] != latest_prompt
            or not current_review or current_review["prompt_id"] != latest_prompt
            or actor != "none" or latest_prompt not in queue["completed_prompt_ids"]
        ):
            raise ValueError("completed state requires a reviewed Result and completed history")
        if current_review["requires_human_decision"] and (
            not current_human or current_human["prompt_id"] != latest_prompt
        ):
            raise ValueError("completed human-gated review lacks Human Decision")

    if previous_queue_state is not None:
        previous = validate_queue_state(previous_queue_state)
        if previous.get("latest_prompt") == latest_prompt and latest_prompt:
            validate_prompt_state_transition(
                previous["prompt_states"][latest_prompt], queue["prompt_states"][latest_prompt],
                explicit_replay=queue["next_action"]["replay_requested"],
            )
        missing_completed = set(previous["completed_prompt_ids"]) - set(queue["completed_prompt_ids"])
        if missing_completed:
            raise ValueError("completed prompt history is append-only")
    return {
        "prompt_records": prompts,
        "result_records": results,
        "assistant_review_records": reviews,
        "human_decision_records": humans,
        "branch_handoff_records": handoffs,
        "queue_state": queue,
    }


def validate_authoritative_branch(
    prompt_record: dict[str, Any], queue_state: dict[str, Any], checked_out_branch: str,
    branch_handoff_record: dict[str, Any] | None = None,
) -> str | None:
    """Fail closed when an actionable handoff names a different checked-out branch.

    Older v1 Prompt/Queue records may omit branch metadata. Once a Prompt names an
    authoritative branch, its Queue must repeat it and Codex must supply the exact
    locally checked-out branch before acting.
    """
    validate_prompt_record(prompt_record)
    validate_queue_state(queue_state)
    expected = _prompt_authoritative_branch(prompt_record)
    queued = queue_state.get("authoritative_branch")
    if expected is None:
        if queued is not None:
            raise ValueError("queue cannot invent authoritative_branch absent from Prompt")
        return None
    expected = validate_branch_name(expected)
    if queued != expected:
        if branch_handoff_record is None:
            raise ValueError("queue authoritative_branch does not match Prompt")
        handoff = validate_branch_handoff_record(branch_handoff_record)
        if (
            handoff["target_prompt_id"] != prompt_record["prompt_id"]
            or handoff["from_branch"] != expected
            or handoff["to_branch"] != queued
        ):
            raise ValueError("branch handoff does not authorize this Prompt/Queue transition")
        expected = queued
    actual = validate_branch_name(checked_out_branch)
    if actual != expected:
        raise ValueError(
            f"stale-branch handoff: expected {expected!r}, checked out {actual!r}"
        )
    return expected


def serialize_coordination_record(record: dict[str, Any], validator) -> dict[str, Any]:
    validator(record)
    return serialize_json_object(record)


def serialize_coordination_record_json(record: dict[str, Any], validator) -> str:
    return json.dumps(
        serialize_coordination_record(record, validator), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def detached_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return an explicit detached copy for callers constructing append-only artifacts."""
    validate_safe_json_payload(record)
    return deepcopy(record)
