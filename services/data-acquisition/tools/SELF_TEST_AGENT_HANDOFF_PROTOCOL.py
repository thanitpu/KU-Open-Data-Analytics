"""Deterministic tests for KU2D Agent Handoff Protocol v1."""
from __future__ import annotations

import json
import hashlib
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "acquisition") not in sys.path:
    sys.path.insert(0, str(ROOT / "acquisition"))

from agent_handoff_protocol import (
    ASSISTANT_REVIEW_SCHEMA,
    BRANCH_HANDOFF_SCHEMA,
    HUMAN_DECISION_SCHEMA,
    HISTORICAL_MIGRATION_SCHEMA,
    PROMPT_SCHEMA,
    QUEUE_SCHEMA,
    RESULT_SCHEMA,
    branch_handoff,
    branch_handoff_queue_fingerprint,
    serialize_coordination_record_json,
    validate_authoritative_branch,
    validate_agent_handoff_bundle,
    validate_branch_name,
    validate_assistant_review_record,
    validate_branch_handoff_record,
    validate_human_decision_record,
    validate_historical_migration_manifest,
    validate_prompt_record,
    validate_prompt_state_transition,
    validate_queue_state,
    validate_result_record,
)


NOW = "2026-08-31T02:00:00+00:00"
P1, R1, V1, H1 = "KU2D-P-000101", "KU2D-R-000101", "KU2D-V-000101", "KU2D-H-000101"
SOURCE_BRANCH = "codex/ku2d-coffee-evidence-recovery-v1"
TARGET_BRANCH = "codex/ku2d-branch-handoff-protocol-v1"
BASE_SHA = "1" * 40
SOURCE_CLOSE_SHA = "2" * 40


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


def handoff_queues():
    common = {
        "handoff_id": "KU2D-BH-000101", "from_branch": SOURCE_BRANCH,
        "to_branch": TARGET_BRANCH, "base_sha": BASE_SHA, "target_prompt_id": P1,
        "close_source_queue_before_switch": True, "initialize_target_queue": True,
        "human_authority_required": False,
    }
    source = queue("in_progress", "none")
    source["authoritative_branch"] = SOURCE_BRANCH
    source["branch_handoff"] = {"phase": "source_closed", **common}
    target = queue("in_progress", "codex")
    target["authoritative_branch"] = TARGET_BRANCH
    target["branch_handoff"] = {
        "phase": "target_initialized", **common,
        "target_initial_head_sha": BASE_SHA,
        "source_close_commit_sha": SOURCE_CLOSE_SHA,
        "target_initialization_succeeded": True,
    }
    return source, target


def valid_handoff():
    source, target = handoff_queues()
    return branch_handoff(
        from_branch=SOURCE_BRANCH, to_branch=TARGET_BRANCH, base_sha=BASE_SHA,
        close_source_queue_before_switch=True, initialize_target_queue=True,
        target_prompt_id=P1, human_authority_required=False,
        source_queue=source, target_queue=target,
        source_close_commit_sha=SOURCE_CLOSE_SHA, target_initial_head_sha=BASE_SHA,
        target_initialization_succeeded=True, created_at=NOW,
        handoff_id="KU2D-BH-000101",
    )


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

def records_and_blobs(folder, id_key):
    records, blobs = [], {}
    for path in sorted(folder.glob("*.json")):
        payload = path.read_bytes().replace(b"\r\n", b"\n")
        record = json.loads(payload.decode("utf-8"))
        records.append(record)
        blobs[record[id_key]] = payload
    return records, blobs

repository_prompts = records_in(ROOT / "coordination" / "v1" / "prompts")
repository_results = records_in(ROOT / "coordination" / "v1" / "results")
repository_reviews, review_blobs = records_and_blobs(
    ROOT / "coordination" / "v1" / "reviews", "review_id",
)
human_folder = ROOT / "coordination" / "v1" / "human-decisions"
repository_humans, human_blobs = (
    records_and_blobs(human_folder, "human_decision_id")
    if human_folder.is_dir() else ([], {})
)
handoff_folder = ROOT / "coordination" / "v1" / "branch-handoffs"
repository_handoffs = records_in(handoff_folder) if handoff_folder.is_dir() else []
migration_folder = ROOT / "coordination" / "v1" / "migrations"
repository_migrations = records_in(migration_folder) if migration_folder.is_dir() else []
repository_bundle = validate_agent_handoff_bundle(
    repository_prompts, repository_results, repository_reviews, repository_humans,
    repository_queue, branch_handoff_records=repository_handoffs,
    historical_migration_records=repository_migrations,
    record_blobs={**review_blobs, **human_blobs},
)
assert repository_bundle["queue_state"]["next_action"]["actor"] in {"codex", "assistant", "human", "none"}
if repository_bundle["queue_state"]["next_action"]["actor"] == "assistant":
    assert repository_bundle["queue_state"]["latest_result"] == repository_bundle["queue_state"]["next_action"]["result_id"]
assert set(repository_bundle["human_decision_records"]) == {
    "KU2D-H-000001", "KU2D-H-000002", "KU2D-H-000004", "KU2D-H-000005",
    "KU2D-H-000006", "KU2D-H-000007", "KU2D-H-000008", "KU2D-H-000009",
    "KU2D-H-000010", "KU2D-H-000011", "KU2D-H-000012", "KU2D-H-000013", "KU2D-H-000014", "KU2D-H-000015",
    "KU2D-H-000016", "KU2D-H-000018", "KU2D-H-000019", "KU2D-H-000020",
}
assert repository_bundle["human_decision_records"]["KU2D-H-000001"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000002"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000004"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000005"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000006"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000007"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000008"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000009"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000010"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000011"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000012"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000013"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000014"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000015"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000016"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000018"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000019"]["decision"] == "confirmed"
assert repository_bundle["human_decision_records"]["KU2D-H-000020"]["decision"] == "confirmed"
assert set(repository_bundle["historical_records"]) == {"KU2D-V-000047", "KU2D-H-000017"}
assert all(
    record["active_authority"] is False
    for record in repository_bundle["historical_records"].values()
)
assert validate_authoritative_branch(
    repository_prompts[-1], repository_queue, repository_queue["authoritative_branch"],
    repository_handoffs[-1] if repository_handoffs else None,
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

# AH24: one valid handoff closes source authority before initializing target authority.
handoff = valid_handoff()
assert handoff["schema"] == BRANCH_HANDOFF_SCHEMA
assert validate_branch_handoff_record(handoff)["to_branch"] == TARGET_BRANCH

# AH25: source and target cannot both retain an active codex action.
dual_source, dual_target = handoff_queues()
dual_source["next_action"] = deepcopy(dual_target["next_action"])
try:
    branch_handoff(
        from_branch=SOURCE_BRANCH, to_branch=TARGET_BRANCH, base_sha=BASE_SHA,
        close_source_queue_before_switch=True, initialize_target_queue=True,
        target_prompt_id=P1, human_authority_required=False,
        source_queue=dual_source, target_queue=dual_target,
        source_close_commit_sha=SOURCE_CLOSE_SHA, target_initial_head_sha=BASE_SHA,
        target_initialization_succeeded=True, created_at=NOW,
        handoff_id="KU2D-BH-000101",
    )
    raise AssertionError("dual-authority branch handoff validated")
except ValueError:
    pass

# AH26: switching before the source-close phase fails closed.
early_source, early_target = handoff_queues()
early_source["branch_handoff"]["phase"] = "target_initialized"
try:
    branch_handoff(
        from_branch=SOURCE_BRANCH, to_branch=TARGET_BRANCH, base_sha=BASE_SHA,
        close_source_queue_before_switch=True, initialize_target_queue=True,
        target_prompt_id=P1, human_authority_required=False,
        source_queue=early_source, target_queue=early_target,
        source_close_commit_sha=SOURCE_CLOSE_SHA, target_initial_head_sha=BASE_SHA,
        target_initialization_succeeded=True, created_at=NOW,
        handoff_id="KU2D-BH-000101",
    )
    raise AssertionError("switch-before-close branch handoff validated")
except ValueError:
    pass

# AH27: a source snapshot changed after signing is stale evidence.
stale_handoff = valid_handoff()
stale_handoff["source_queue_snapshot"]["updated_at"] = "2026-08-31T02:00:01+00:00"
try:
    validate_branch_handoff_record(stale_handoff)
    raise AssertionError("stale source queue snapshot validated")
except ValueError:
    pass

# AH28: target initialization must begin from the exact declared base commit.
mismatched_head = valid_handoff()
mismatched_head["target_initial_head_sha"] = "3" * 40
try:
    validate_branch_handoff_record(mismatched_head)
    raise AssertionError("mismatched branch base/head validated")
except ValueError:
    pass

# AH29: a target codex action cannot carry a downstream Result pointer.
bad_pointer = valid_handoff()
bad_pointer["target_queue_snapshot"]["next_action"]["result_id"] = R1
bad_pointer["target_queue_fingerprint"] = branch_handoff_queue_fingerprint(
    bad_pointer["target_queue_snapshot"]
)
try:
    validate_branch_handoff_record(bad_pointer)
    raise AssertionError("inappropriate target downstream pointer validated")
except ValueError:
    pass

# AH30: failed target initialization and human-authority substitution both fail closed.
failed_initialization = valid_handoff()
failed_initialization["target_initialization_succeeded"] = False
try:
    validate_branch_handoff_record(failed_initialization)
    raise AssertionError("failed target initialization validated")
except ValueError:
    pass
human_substitution = valid_handoff()
human_substitution["human_authority_required"] = True
try:
    validate_branch_handoff_record(human_substitution)
    raise AssertionError("mechanical handoff claimed human authority")
except ValueError:
    pass

# AH31: an immutable source Prompt can authorize work on the target only through
# the exact handoff record; the same bundle fails without that proof.
migrated_prompt = prompt()
migrated_prompt["authoritative_branch"] = SOURCE_BRANCH
_, migrated_queue = handoff_queues()
assert validate_authoritative_branch(
    migrated_prompt, migrated_queue, TARGET_BRANCH, handoff,
) == TARGET_BRANCH
try:
    validate_authoritative_branch(migrated_prompt, migrated_queue, TARGET_BRANCH)
    raise AssertionError("migrated Prompt validated without branch handoff proof")
except ValueError:
    pass
assert validate_agent_handoff_bundle(
    [migrated_prompt], [], [], [], migrated_queue,
    branch_handoff_records=[handoff],
)["branch_handoff_records"]["KU2D-BH-000101"]["to_branch"] == TARGET_BRANCH
try:
    validate_agent_handoff_bundle([migrated_prompt], [], [], [], migrated_queue)
    raise AssertionError("migrated queue bundle validated without handoff record")
except ValueError:
    pass

# AH32: the repository migration is exact, visible, and non-authoritative.
assert len(repository_migrations) == 2
assert validate_historical_migration_manifest(repository_migrations[0])["migration_id"] == (
    "KU2D-M-000001"
)
assert set(repository_bundle["historical_records"]) == {"KU2D-V-000047", "KU2D-H-000017"}
assert all(
    item["active_authority"] is False
    for item in repository_bundle["historical_records"].values()
)
assert repository_bundle["proactive_human_decision_ids"] == [
    "KU2D-H-000018", "KU2D-H-000019",
]
assert repository_bundle["review_flag_compatibility_ids"] == ["KU2D-V-000050"]

def repository_validation(*, migrations=None, reviews=None, humans=None, blobs=None, queue_state=None):
    return validate_agent_handoff_bundle(
        repository_prompts, repository_results,
        repository_reviews if reviews is None else reviews,
        repository_humans if humans is None else humans,
        repository_queue if queue_state is None else queue_state,
        branch_handoff_records=repository_handoffs,
        historical_migration_records=(
            repository_migrations if migrations is None else migrations
        ),
        record_blobs={**review_blobs, **human_blobs} if blobs is None else blobs,
    )

def json_blob(record):
    payload = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()
    return payload, digest

# AH33: an unlisted invalid historical record still fails closed.
try:
    repository_validation(migrations=[])
    raise AssertionError("unlisted invalid record validated")
except ValueError:
    pass

# AH34: any historical or replacement hash mismatch fails closed.
bad_hash = deepcopy(repository_migrations)
bad_hash[0]["entries"][0]["historical_blob_sha"] = "0" * 40
try:
    repository_validation(migrations=bad_hash)
    raise AssertionError("mismatched historical blob hash validated")
except ValueError:
    pass
bad_replacement_hash = deepcopy(repository_migrations)
bad_replacement_hash[0]["entries"][0]["replacement_blob_sha"] = "0" * 40
try:
    repository_validation(migrations=bad_replacement_hash)
    raise AssertionError("mismatched replacement blob hash validated")
except ValueError:
    pass

# AH35: a missing canonical replacement fails closed.
missing_replacement = [
    item for item in repository_reviews if item["review_id"] != "KU2D-V-000048"
]
try:
    repository_validation(reviews=missing_replacement)
    raise AssertionError("missing canonical replacement validated")
except ValueError:
    pass

# AH36: an exact-hash replacement that does not validate still fails closed.
invalid_replacement_reviews = deepcopy(repository_reviews)
invalid_replacement = next(
    item for item in invalid_replacement_reviews if item["review_id"] == "KU2D-V-000048"
)
invalid_replacement["review_result"] = "invalid"
invalid_blob, invalid_sha = json_blob(invalid_replacement)
invalid_manifest = deepcopy(repository_migrations)
invalid_manifest[0]["entries"][0]["replacement_blob_sha"] = invalid_sha
invalid_blobs = {**review_blobs, **human_blobs, "KU2D-V-000048": invalid_blob}
try:
    repository_validation(
        migrations=invalid_manifest, reviews=invalid_replacement_reviews, blobs=invalid_blobs,
    )
    raise AssertionError("invalid canonical replacement validated")
except ValueError:
    pass

# AH37: raw bytes are mandatory proof for each pinned record.
missing_blob = {**review_blobs, **human_blobs}
missing_blob.pop("KU2D-H-000017")
try:
    repository_validation(blobs=missing_blob)
    raise AssertionError("migration without raw historical bytes validated")
except ValueError:
    pass

# AH38: a migrated historical record cannot be a current Queue authority pointer.
historical_authority_queue = deepcopy(repository_queue)
historical_authority_queue["latest_review"] = "KU2D-V-000047"
try:
    repository_validation(queue_state=historical_authority_queue)
    raise AssertionError("historical review acted as current authority")
except ValueError:
    pass

# AH39: circular or superseded replacement mappings fail at manifest validation.
circular_manifest = deepcopy(repository_migrations[0])
circular_manifest["entries"].append({
    "record_kind": "assistant_review",
    "historical_record_id": "KU2D-V-000048",
    "historical_blob_sha": "afba89a6d66014840d833f0fc03f72b89f5e9e76",
    "replacement_record_id": "KU2D-V-000047",
    "replacement_blob_sha": "702bda7d0b7822ef7b34257a5a177cfe5deb4820",
})
try:
    validate_historical_migration_manifest(circular_manifest)
    raise AssertionError("circular historical migration validated")
except ValueError:
    pass

# AH40: a manifest cannot suppress an already valid active record.
valid_as_historical = deepcopy(repository_migrations)
valid_as_historical[0]["entries"][0] = {
    "record_kind": "assistant_review",
    "historical_record_id": "KU2D-V-000048",
    "historical_blob_sha": "afba89a6d66014840d833f0fc03f72b89f5e9e76",
    "replacement_record_id": "KU2D-V-000049",
    "replacement_blob_sha": hashlib.sha1(
        f"blob {len(review_blobs['KU2D-V-000049'])}\0".encode("ascii")
        + review_blobs["KU2D-V-000049"]
    ).hexdigest(),
}
try:
    repository_validation(migrations=valid_as_historical)
    raise AssertionError("valid active review was suppressed as historical")
except ValueError:
    pass

# AH41: proactive Human Decisions remain rejected unless exact-pinned.
unpinned_proactive = deepcopy(repository_migrations)
unpinned_proactive[0]["proactive_human_decisions"] = []
try:
    repository_validation(migrations=unpinned_proactive)
    raise AssertionError("unlisted proactive Human Decision validated")
except ValueError:
    pass

# AH42: a proactive Human Decision or Review hash mismatch fails closed.
bad_proactive_human_hash = deepcopy(repository_migrations)
bad_proactive_human_hash[0]["proactive_human_decisions"][0][
    "human_decision_blob_sha"
] = "0" * 40
try:
    repository_validation(migrations=bad_proactive_human_hash)
    raise AssertionError("mismatched proactive Human Decision hash validated")
except ValueError:
    pass
bad_proactive_review_hash = deepcopy(repository_migrations)
bad_proactive_review_hash[0]["proactive_human_decisions"][0][
    "assistant_review_blob_sha"
] = "0" * 40
try:
    repository_validation(migrations=bad_proactive_review_hash)
    raise AssertionError("mismatched proactive Assistant Review hash validated")
except ValueError:
    pass

# AH43: duplicate proactive decision/review pins fail closed.
duplicate_proactive = deepcopy(repository_migrations[0])
duplicate_proactive["proactive_human_decisions"].append(
    deepcopy(duplicate_proactive["proactive_human_decisions"][0])
)
try:
    validate_historical_migration_manifest(duplicate_proactive)
    raise AssertionError("duplicate proactive authority pin validated")
except ValueError:
    pass

# AH44: normal unrequested Human Decisions remain rejected without migrations.
try:
    validate_agent_handoff_bundle(
        [prompt()], [result()], [review()], [human_decision()], queue("completed", "none"),
    )
    raise AssertionError("general unrequested Human Decision bypassed the queue gate")
except ValueError:
    pass

# AH45: the exact V50 bytes remain immutable while bundle interpretation is canonical.
raw_v50 = next(item for item in repository_reviews if item["review_id"] == "KU2D-V-000050")
assert raw_v50["review_result"] == "accepted" and raw_v50["requires_human_decision"] is True
assert repository_bundle["assistant_review_records"]["KU2D-V-000050"]["review_result"] == "human_decision_required"
try:
    validate_assistant_review_record(raw_v50)
    raise AssertionError("contradictory raw V50 validated without exact compatibility")
except ValueError:
    pass

# AH46: omitting the exact compatibility migration exposes the invalid record.
try:
    repository_validation(migrations=[repository_migrations[0]])
    raise AssertionError("V50 validated without compatibility manifest")
except ValueError:
    pass

# AH47: either review or Human Decision hash drift fails closed.
bad_flag_review_hash = deepcopy(repository_migrations)
bad_flag_review_hash[1]["review_flag_compatibility"][0]["assistant_review_blob_sha"] = "0" * 40
try:
    repository_validation(migrations=bad_flag_review_hash)
    raise AssertionError("review flag compatibility accepted a mismatched review hash")
except ValueError:
    pass
bad_flag_human_hash = deepcopy(repository_migrations)
bad_flag_human_hash[1]["review_flag_compatibility"][0]["human_decision_blob_sha"] = "0" * 40
try:
    repository_validation(migrations=bad_flag_human_hash)
    raise AssertionError("review flag compatibility accepted a mismatched Human Decision hash")
except ValueError:
    pass

# AH48: only accepted -> human_decision_required is a valid compatibility meaning.
bad_flag_semantics = deepcopy(repository_migrations[1])
bad_flag_semantics["review_flag_compatibility"][0]["canonical_review_result"] = "accepted"
try:
    validate_historical_migration_manifest(bad_flag_semantics)
    raise AssertionError("invalid review flag compatibility semantics validated")
except ValueError:
    pass

# AH49: duplicate compatibility pins fail closed.
duplicate_flag_pin = deepcopy(repository_migrations[1])
duplicate_flag_pin["review_flag_compatibility"].append(
    deepcopy(duplicate_flag_pin["review_flag_compatibility"][0])
)
try:
    validate_historical_migration_manifest(duplicate_flag_pin)
    raise AssertionError("duplicate review flag compatibility pin validated")
except ValueError:
    pass

# AH50: an empty migration without any exact-pinned action is invalid.
empty_migration = deepcopy(repository_migrations[1])
empty_migration["review_flag_compatibility"] = []
try:
    validate_historical_migration_manifest(empty_migration)
    raise AssertionError("empty compatibility migration validated")
except ValueError:
    pass

print("Agent Handoff Protocol deterministic tests passed (AH1-AH50).")
