"""Deterministic tests for KU2D Agent Handoff Protocol v1."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "acquisition") not in sys.path:
    sys.path.insert(0, str(ROOT / "acquisition"))

from agent_handoff_protocol import (
    ASSISTANT_REVIEW_SCHEMA,
    HUMAN_DECISION_SCHEMA,
    PROMPT_SCHEMA,
    QUEUE_SCHEMA,
    RESULT_SCHEMA,
    serialize_coordination_record_json,
    validate_authoritative_branch,
    validate_agent_handoff_bundle,
    validate_branch_name,
    validate_assistant_review_record,
    validate_human_decision_record,
    validate_prompt_record,
    validate_prompt_state_transition,
    validate_queue_state,
    validate_result_record,
)


NOW = "2026-08-31T02:00:00+00:00"
P1, R1, V1, H1 = "KU2D-P-000101", "KU2D-R-000101", "KU2D-V-000101", "KU2D-H-000101"


def boundaries():
    return {
        "coordination_only": True,
        "production_authorized": False,
        "automatic_learning_memory_export": False,
        "scheduler_action": None,
    }


def prompt(prompt_id=P1):
    return {
        "schema": PROMPT_SCHEMA, "prompt_id": prompt_id, "created_at": NOW,
        "created_by": {"actor": "assistant", "actor_id": "assistant-review"},
        "status": "ready_for_codex", "objective": "Implement a deterministic fixture task.",
        "instructions": ["Preserve evidence.", "Do not perform live requests."],
        "expected_result": {"next_actor": "assistant"},
        "provenance": {"source": "deterministic-test"}, "boundaries": boundaries(),
    }


def result(result_id=R1, prompt_id=P1):
    return {
        "schema": RESULT_SCHEMA, "result_id": result_id, "prompt_id": prompt_id,
        "submitted_at": NOW, "submitted_by": {"actor": "codex", "actor_id": "codex-test"},
        "status": "succeeded", "summary": "Deterministic implementation completed.",
        "evidence_references": ["commit:test"],
        "verification": {"deterministic_tests_passed": True, "live_request_count": 0},
        "provenance": {"repository": "thanitpu/KU-Open-Data-Analytics"},
        "boundaries": boundaries(),
    }


def review(review_id=V1, prompt_id=P1, result_id=R1, *, require_human=False):
    return {
        "schema": ASSISTANT_REVIEW_SCHEMA, "review_id": review_id,
        "prompt_id": prompt_id, "result_id": result_id, "reviewed_at": NOW,
        "reviewed_by": {
            "actor": "assistant", "actor_id": "assistant-review",
            "human_authority_claimed": False,
        },
        "review_result": "human_decision_required" if require_human else "accepted",
        "requires_human_decision": require_human, "reason_code": "deterministic-review",
        "explanation": "Reviewed repository evidence.", "evidence_references": ["commit:test"],
        "provenance": {"source": "deterministic-test"}, "boundaries": boundaries(),
    }


def human_decision():
    return {
        "schema": HUMAN_DECISION_SCHEMA, "human_decision_id": H1,
        "prompt_id": P1, "result_id": R1, "review_id": V1,
        "decided_at": NOW, "decided_by": {"actor": "human", "actor_id": "human-test-reviewer"},
        "decision": "confirmed", "reason_note": "Explicit deterministic test confirmation.",
        "provenance": {"decision_source": "explicit_human_input"},
        "boundaries": boundaries(),
    }


def queue(state="result_submitted", actor="assistant", *, replay=False):
    latest_result = R1 if state not in {"draft", "ready_for_codex", "in_progress", "superseded"} else None
    latest_review = V1 if state in {"reviewed", "human_decision_required", "completed"} else None
    latest_human = H1 if state == "completed" else None
    action = {
        "actor": actor, "prompt_id": P1 if actor != "none" else None,
        "result_id": R1 if actor in {"assistant", "human"} else None,
        "review_id": V1 if actor == "human" else None,
        "human_decision_id": None, "replay_requested": replay,
    }
    return {
        "schema": QUEUE_SCHEMA, "updated_at": NOW, "latest_prompt": P1,
        "latest_result": latest_result, "latest_review": latest_review,
        "latest_human_decision": latest_human, "prompt_states": {P1: state},
        "completed_prompt_ids": [P1] if state == "completed" else [],
        "next_action": action,
    }


# AH1: a submitted Result has a valid Prompt chain and hands control to assistant.
ready_queue = queue("ready_for_codex", "codex")
submitted_queue = queue()
valid_bundle = validate_agent_handoff_bundle(
    [prompt()], [result()], [], [], submitted_queue, previous_queue_state=ready_queue,
)
assert valid_bundle["queue_state"]["next_action"]["actor"] == "assistant"

# AH2: every record family uses its stable typed identifier.
bad_id = result(result_id="result-101")
try:
    validate_result_record(bad_id)
    raise AssertionError("invalid Result ID validated")
except ValueError:
    pass

# AH3: orphan Result references fail closed.
try:
    validate_agent_handoff_bundle([], [result()], [], [], submitted_queue)
    raise AssertionError("orphan Result validated")
except ValueError:
    pass

# AH4: duplicate identifiers fail closed.
try:
    validate_agent_handoff_bundle([prompt(), deepcopy(prompt())], [result()], [], [], submitted_queue)
    raise AssertionError("duplicate Prompt validated")
except ValueError:
    pass

# AH5: Assistant Review must reference one consistent Prompt/Result chain.
other_prompt = prompt("KU2D-P-000102")
bad_chain = review(prompt_id=other_prompt["prompt_id"])
reviewed_queue = queue("reviewed", "none")
try:
    validate_agent_handoff_bundle([prompt(), other_prompt], [result()], [bad_chain], [], reviewed_queue)
    raise AssertionError("inconsistent review chain validated")
except ValueError:
    pass

# AH6: typed ID families prevent a record from referencing itself.
self_reference = result(prompt_id=R1)
try:
    validate_result_record(self_reference)
    raise AssertionError("self-referencing Result validated")
except ValueError:
    pass

# AH7: only explicit prompt state transitions are accepted.
assert validate_prompt_state_transition("ready_for_codex", "result_submitted") == "result_submitted"
try:
    validate_prompt_state_transition("ready_for_codex", "completed")
    raise AssertionError("invalid state transition validated")
except ValueError:
    pass

# AH8: completed or superseded prompts cannot replay without an explicit request.
try:
    validate_prompt_state_transition("completed", "ready_for_codex")
    raise AssertionError("implicit replay validated")
except ValueError:
    pass
assert validate_prompt_state_transition(
    "completed", "ready_for_codex", explicit_replay=True,
) == "ready_for_codex"
implicit_replay = queue("ready_for_codex", "codex")
implicit_replay["completed_prompt_ids"] = [P1]
try:
    validate_queue_state(implicit_replay)
    raise AssertionError("queue replay without request validated")
except ValueError:
    pass
explicit_replay = deepcopy(implicit_replay)
explicit_replay["next_action"]["replay_requested"] = True
assert validate_queue_state(explicit_replay) is explicit_replay

# AH9: Assistant Review cannot claim Human Decision authority.
fabricated_review = review()
fabricated_review["reviewed_by"]["human_authority_claimed"] = True
try:
    validate_assistant_review_record(fabricated_review)
    raise AssertionError("assistant claimed human authority")
except ValueError:
    pass

# AH10: a Human Decision cannot answer a review that did not request it.
try:
    validate_agent_handoff_bundle(
        [prompt()], [result()], [review()], [human_decision()], queue("completed", "none"),
    )
    raise AssertionError("unrequested Human Decision validated")
except ValueError:
    pass

# AH11: an explicit Human Decision completes a genuinely human-gated chain.
human_review = review(require_human=True)
completed = validate_agent_handoff_bundle(
    [prompt()], [result()], [human_review], [human_decision()], queue("completed", "none"),
)
assert completed["human_decision_records"][H1]["decision"] == "confirmed"

# AH12: fabricated human provenance and sensitive material fail closed.
fabricated_human = human_decision()
fabricated_human["provenance"]["decision_source"] = "assistant_generated"
try:
    validate_human_decision_record(fabricated_human)
    raise AssertionError("fabricated Human Decision provenance validated")
except ValueError:
    pass
sensitive = result()
sensitive["provenance"]["session"] = "prohibited"
try:
    validate_result_record(sensitive)
    raise AssertionError("sensitive coordination material validated")
except ValueError:
    pass

# AH13: canonical JSON serialization is deterministic and non-mutating.
assert serialize_coordination_record_json(result(), validate_result_record) == serialize_coordination_record_json(
    deepcopy(result()), validate_result_record,
)

# AH14: normal acquisition runtime cannot write or import coordination artifacts automatically.
for runtime_folder in ("api", "control_plane", "repository", "service"):
    for runtime_file in (ROOT / runtime_folder).rglob("*.py"):
        runtime_text = runtime_file.read_text(encoding="utf-8")
        assert "agent_handoff_protocol" not in runtime_text, runtime_file
        assert "coordination/queue" not in runtime_text.replace("\\", "/"), runtime_file

# AH15: completed-prompt history cannot be removed from a later queue state.
previous_completed = queue("completed", "none")
new_prompt_id = "KU2D-P-000102"
next_queue = {
    "schema": QUEUE_SCHEMA, "updated_at": NOW, "latest_prompt": new_prompt_id,
    "latest_result": None, "latest_review": None, "latest_human_decision": None,
    "prompt_states": {P1: "completed", new_prompt_id: "ready_for_codex"},
    "completed_prompt_ids": [],
    "next_action": {
        "actor": "codex", "prompt_id": new_prompt_id, "result_id": None,
        "review_id": None, "human_decision_id": None, "replay_requested": False,
    },
}
try:
    validate_agent_handoff_bundle(
        [prompt(), other_prompt], [result()], [human_review], [human_decision()],
        next_queue, previous_queue_state=previous_completed,
    )
    raise AssertionError("completed prompt history was removed")
except ValueError:
    pass

# AH16: all coordination records remain non-authorizing and outside automatic ML export.
for record in (prompt(), result(), review(), human_decision()):
    assert record["boundaries"] == boundaries()

# AH17: bootstrap history remains untouched while its separate v1 projection validates.
bootstrap_path = ROOT / "coordination" / "prompts" / "KU2D-P-000001.json"
v1_prompt_path = ROOT / "coordination" / "v1" / "prompts" / "KU2D-P-000001.json"
bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
v1_prompt = json.loads(v1_prompt_path.read_text(encoding="utf-8"))
assert bootstrap["schema"] == "ku2d.agent-handoff-prompt.bootstrap.v0"
assert validate_prompt_record(v1_prompt)["provenance"]["bootstrap_record"].endswith(
    "coordination/prompts/KU2D-P-000001.json"
)

# AH18: the repository's current v1 history and global latest pointers validate as one bundle.
queue_path = ROOT / "coordination" / "queue.json"
repository_queue = json.loads(queue_path.read_text(encoding="utf-8"))
def records_in(folder):
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]

repository_prompts = records_in(ROOT / "coordination" / "v1" / "prompts")
repository_results = records_in(ROOT / "coordination" / "v1" / "results")
repository_reviews = records_in(ROOT / "coordination" / "v1" / "reviews")
human_folder = ROOT / "coordination" / "v1" / "human-decisions"
repository_humans = records_in(human_folder) if human_folder.is_dir() else []
repository_bundle = validate_agent_handoff_bundle(
    repository_prompts, repository_results, repository_reviews, repository_humans,
    repository_queue,
)
assert repository_bundle["queue_state"]["next_action"]["actor"] in {"codex", "assistant", "human", "none"}
if repository_bundle["queue_state"]["next_action"]["actor"] == "assistant":
    assert repository_bundle["queue_state"]["latest_result"] == repository_bundle["queue_state"]["next_action"]["result_id"]
assert set(repository_bundle["human_decision_records"]) == {
    "KU2D-H-000001", "KU2D-H-000002", "KU2D-H-000004",
}
assert repository_bundle["human_decision_records"]["KU2D-H-000001"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000002"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000004"]["decision"] == "confirmed"
assert validate_authoritative_branch(
    repository_prompts[-1], repository_queue, repository_queue["authoritative_branch"],
) == repository_queue["authoritative_branch"]

# AH19: new branch-authority metadata accepts only the exact checked-out branch.
branch_prompt = prompt()
branch_prompt["provenance"]["authoritative_branch"] = "codex/ku2d-core-knowledge-backfill-v1"
branch_queue = queue("ready_for_codex", "codex")
branch_queue["authoritative_branch"] = "codex/ku2d-core-knowledge-backfill-v1"
assert validate_authoritative_branch(
    branch_prompt, branch_queue, "codex/ku2d-core-knowledge-backfill-v1",
) == "codex/ku2d-core-knowledge-backfill-v1"

# AH20: a stale checked-out branch fails before task execution.
try:
    validate_authoritative_branch(branch_prompt, branch_queue, "codex/stale-branch")
    raise AssertionError("stale authoritative branch validated")
except ValueError:
    pass

# AH21: Prompt and Queue branch authority cannot contradict or be invented.
wrong_queue = deepcopy(branch_queue)
wrong_queue["authoritative_branch"] = "codex/other-branch"
try:
    validate_authoritative_branch(branch_prompt, wrong_queue, "codex/other-branch")
    raise AssertionError("contradictory queue branch validated")
except ValueError:
    pass
invented_queue = queue("ready_for_codex", "codex")
invented_queue["authoritative_branch"] = "codex/invented-branch"
try:
    validate_authoritative_branch(prompt(), invented_queue, "codex/invented-branch")
    raise AssertionError("queue-invented branch authority validated")
except ValueError:
    pass

# AH22: backward-compatible records may omit branch metadata; unsafe refs fail.
assert validate_authoritative_branch(prompt(), queue("ready_for_codex", "codex"), "codex/any") is None
for unsafe_branch in ("refs/heads/main", "codex/../main", "codex/bad branch", "codex/bad~ref"):
    try:
        validate_branch_name(unsafe_branch)
        raise AssertionError(f"unsafe branch validated: {unsafe_branch}")
    except ValueError:
        pass

# AH23: top-level Prompt branch metadata is accepted for the current format,
# while contradictory top-level/provenance declarations fail closed.
top_level_prompt = prompt()
top_level_prompt["authoritative_branch"] = "codex/ku2d-core-knowledge-backfill-v1"
assert validate_authoritative_branch(
    top_level_prompt, branch_queue, "codex/ku2d-core-knowledge-backfill-v1",
) == "codex/ku2d-core-knowledge-backfill-v1"
contradictory_prompt = deepcopy(top_level_prompt)
contradictory_prompt["provenance"]["authoritative_branch"] = "codex/other-branch"
try:
    validate_prompt_record(contradictory_prompt)
    raise AssertionError("contradictory Prompt branch declarations validated")
except ValueError:
    pass

print("Agent Handoff Protocol deterministic tests passed (AH1-AH23).")
