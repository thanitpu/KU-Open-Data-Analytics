"""Storage-neutral contracts for GitHub-mediated KU2D agent handoffs.

The protocol coordinates work; it does not authorize production activity,
schedule acquisition, write files automatically, or create Learning Memory.
"""
from __future__ import annotations

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
}
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
    _mapping(record, "provenance")
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
) -> dict[str, Any]:
    """Fail closed on broken chains, authority, queue state, and replay."""
    prompts = _index(prompt_records, "prompt_id", validate_prompt_record)
    results = _index(result_records, "result_id", validate_result_record)
    reviews = _index(assistant_review_records, "review_id", validate_assistant_review_record)
    humans = _index(human_decision_records, "human_decision_id", validate_human_decision_record)
    queue = validate_queue_state(queue_state)

    all_ids = list(prompts) + list(results) + list(reviews) + list(humans)
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
    for record_id in (queue.get("latest_result"), queue.get("latest_review"), queue.get("latest_human_decision")):
        if record_id:
            record = results.get(record_id) or reviews.get(record_id) or humans.get(record_id)
            if record["prompt_id"] != latest_prompt:
                raise ValueError("queue latest pointers do not share the latest Prompt")

    state = queue["prompt_states"].get(latest_prompt) if latest_prompt else None
    latest_result = queue.get("latest_result")
    latest_review = queue.get("latest_review")
    latest_human = queue.get("latest_human_decision")
    actor = queue["next_action"]["actor"]
    if state in {"draft", "ready_for_codex", "in_progress", "superseded"}:
        if any(value is not None for value in (latest_result, latest_review, latest_human)):
            raise ValueError("pre-result or superseded queue state cannot expose downstream latest pointers")
    elif state == "result_submitted":
        if not latest_result or latest_review is not None or latest_human is not None or actor != "assistant":
            raise ValueError("result_submitted state requires an unreviewed Result and assistant action")
    elif state == "reviewed":
        if not latest_result or not latest_review or latest_human is not None or actor != "none":
            raise ValueError("reviewed state requires Result and Assistant Review with no pending actor")
        if reviews[latest_review]["requires_human_decision"]:
            raise ValueError("a review requiring human authority cannot use reviewed terminal state")
    elif state == "human_decision_required":
        if not latest_result or not latest_review or latest_human is not None or actor != "human":
            raise ValueError("human_decision_required state requires a pending human action")
        if not reviews[latest_review]["requires_human_decision"]:
            raise ValueError("human queue action lacks a matching review request")
    elif state == "completed":
        if not latest_result or not latest_review or actor != "none" or latest_prompt not in queue["completed_prompt_ids"]:
            raise ValueError("completed state requires a reviewed Result and completed history")
        if reviews[latest_review]["requires_human_decision"] and not latest_human:
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
        "queue_state": queue,
    }


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
