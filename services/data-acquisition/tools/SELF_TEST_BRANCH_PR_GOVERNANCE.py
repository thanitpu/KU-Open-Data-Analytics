"""Deterministic tests for KU2D Branch/PR Governance v1."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "acquisition") not in sys.path:
    sys.path.insert(0, str(ROOT / "acquisition"))

from branch_pr_governance import (
    DISPOSITIONS,
    EXPECTED_BOUNDARIES,
    REGISTRY_SCHEMA,
    serialize_branch_pr_disposition_registry,
    validate_branch_pr_disposition_registry,
)


def load(name: str):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def rejects(mutator, message: str) -> None:
    broken = deepcopy(registry)
    mutator(broken)
    try:
        validate_branch_pr_disposition_registry(broken)
        raise AssertionError(message)
    except ValueError:
        pass


registry = load("branch_pr_disposition_registry.json")
candidate_registry = load("candidate_learning_evidence_registry.json")
branches = registry["branches"]
by_name = {item["branch"]: item for item in branches}
expected_names = {
    "codex/data-acquisition-agent", "codex/jib-validation-knowledge",
    "codex/ku2d-branch-governance-v1", "codex/ku2d-core-intelligence-v1",
    "codex/ku2d-core-knowledge-backfill-v1", "codex/ku2d-learning-memory-v1",
    "codex/lazada-browser-access-experiment", "codex/lazada-commerce-pulse-explore",
    "codex/lazada-rendered-dom-deep-audit",
    "codex/overnight-acquisition-technique-transfer-matrix",
    "codex/overnight-coffee-source-expansion",
    "codex/overnight-cross-domain-source-gap-scan",
    "codex/overnight-exploration-summary",
    "codex/overnight-marketplace-source-inventory",
    "codex/overnight-ota-source-expansion",
    "codex/overnight-qdiving-source-expansion",
    "codex/overnight-tiktok-shop-commerce-pulse-explore",
    "codex/promote-shopee-edge-workflow", "codex/retail-enrichment-policy-fix",
    "codex/shopee-commerce-pulse-explore", "codex/shopee-edge-access-experiment",
    "codex/wire-shopee-edge-runner", "codex/youtube-equipment-pilot-learning",
    "codex/youtube-human-review-equipment", "codex/youtube-source-foundation",
}

# BG1: schema and complete point-in-time snapshot validate.
assert registry["schema"] == REGISTRY_SCHEMA
validated = validate_branch_pr_disposition_registry(registry)
assert validated == registry

# BG2: exact remote branch count and names reconcile without name-derived authority.
assert len(branches) == registry["snapshot"]["remote_codex_branch_count"] == 25
assert set(by_name) == expected_names
assert registry["snapshot"]["source_branch_name_heuristics_used"] is False

# BG3: branch IDs, names, and opened PR linkages are unique.
assert len({item["branch_id"] for item in branches}) == 25
assert len(by_name) == 25
opened_prs = [item["pr"]["number"] for item in branches if item["pr"]["number"] is not None]
assert len(opened_prs) == len(set(opened_prs)) == registry["snapshot"]["associated_pr_count"]

# BG4: the authoritative branch is the sole active, non-deletable branch.
active = [item for item in branches if item["disposition"] == "ACTIVE"]
assert len(active) == 1
assert active[0]["branch"] == registry["authoritative_branch"]
assert active[0]["deletion_allowed"] is False
assert active[0]["unique_code_unmerged"] is True

# BG5: all safe-delete candidates retain closed/merged/tree-equivalence proof.
safe = [item for item in branches if item["disposition"] == "SAFE_TO_DELETE_CANDIDATE"]
assert len(safe) == 16
for item in safe:
    assert item["pr"]["state"] == "closed" and item["pr"]["merged"] is True
    assert item["merge_proof"]["tree_equivalent"] is True
    assert item["merge_proof"]["tree_diff_file_count"] == 0
    assert item["merge_proof"]["squash_sha"]
    assert item["tree_loss_risk"] == "low"
    assert item["safe_delete_advisory"] is True
    assert item["deletion_allowed"] is False

# BG6: deletion-safe claims without exact proof fail closed.
safe_index = branches.index(safe[0])
rejects(lambda item: item["branches"][safe_index]["merge_proof"].update(tree_equivalent=False), "missing tree proof validated")

# BG7: active branches cannot become deletable or safe-delete candidates.
active_index = branches.index(active[0])
rejects(lambda item: item["branches"][active_index].update(deletion_allowed=True), "deletable active branch validated")
rejects(lambda item: item["branches"][active_index].update(disposition="SAFE_TO_DELETE_CANDIDATE"), "active safe-delete claim validated")

# BG8: all eight open Draft branches preserve unique unmerged work.
parked = [item for item in branches if item["disposition"] == "PARKED_UNREVIEWED"]
assert len(parked) == 8
assert all(item["pr"]["state"] == "open" and item["pr"]["draft"] is True for item in parked)
assert all(item["unique_code_unmerged"] is True for item in parked)
assert all(item["deletion_allowed"] is False for item in parked)

# BG9: parked-unreviewed work cannot claim reviewed status.
parked_index = branches.index(parked[0])
rejects(lambda item: item["branches"][parked_index].update(review_status="reviewed"), "unreviewed branch marked reviewed")

# BG10: candidate-only projection never implies integration, reviewed corpus, or Core Knowledge.
candidate_only = [item for item in parked if item["knowledge_projection"] == ["candidate_learning_evidence_only"]]
assert len(candidate_only) == 6
assert all(item["candidate_evidence_references"] for item in candidate_only)
candidate_index = branches.index(candidate_only[0])
rejects(
    lambda item: item["branches"][candidate_index]["knowledge_projection"].append("reviewed_learning_corpus"),
    "candidate-only knowledge promoted to reviewed corpus",
)

# BG11: all 11 Candidate Learning Evidence IDs are represented exactly once.
registered_candidate_ids = {
    reference for item in candidate_only for reference in item["candidate_evidence_references"]
}
source_candidate_ids = {item["candidate_id"] for item in candidate_registry["candidates"]}
assert registered_candidate_ids == source_candidate_ids
assert all(item["authority"]["reviewed_corpus_authorized"] is False for item in candidate_registry["candidates"])

# BG12: unique work must carry a clear loss warning.
rejects(lambda item: item["branches"][parked_index].update(unique_work_warning="preserve"), "missing unique-work warning validated")

# BG13: contradictory PR state fails closed.
rejects(lambda item: item["branches"][safe_index]["pr"].update(state="open"), "open merged PR validated")

# BG14: missing provenance fails closed.
rejects(lambda item: item["branches"][parked_index].update(evidence_references=[]), "missing evidence validated")

# BG15: fresh expected branch-head reconciliation detects stale or missing evidence.
expected_heads = {item["branch"]: item["head_sha"] for item in branches}
validate_branch_pr_disposition_registry(registry, expected_branch_heads=expected_heads)
# The active branch necessarily advances when publishing the register; all
# non-active historical/parked refs remain exact and fail closed on drift.
advanced_active_heads = dict(expected_heads)
advanced_active_heads[registry["authoritative_branch"]] = "f" * 40
validate_branch_pr_disposition_registry(registry, expected_branch_heads=advanced_active_heads)
stale_heads = dict(expected_heads)
stale_heads[parked[0]["branch"]] = "0" * 40
try:
    validate_branch_pr_disposition_registry(registry, expected_branch_heads=stale_heads)
    raise AssertionError("stale branch evidence validated")
except ValueError:
    pass

# BG16: fresh expected PR-state reconciliation detects stale PR evidence.
expected_prs = {
    item["branch"]: (item["pr"]["number"], item["pr"]["state"], item["pr"]["merged"])
    for item in branches
}
validate_branch_pr_disposition_registry(registry, expected_pr_states=expected_prs)
stale_prs = dict(expected_prs)
stale_prs[parked[0]["branch"]] = (parked[0]["pr"]["number"], "closed", False)
try:
    validate_branch_pr_disposition_registry(registry, expected_pr_states=stale_prs)
    raise AssertionError("stale PR evidence validated")
except ValueError:
    pass

# BG17: branch-count and disposition summaries cannot drift from records.
rejects(lambda item: item["snapshot"].update(remote_codex_branch_count=24), "stale branch count validated")
rejects(lambda item: item["summary"]["disposition_counts"].update(ACTIVE=2), "stale summary validated")
assert set(registry["summary"]["disposition_counts"]) == DISPOSITIONS

# BG18: every parked branch has pattern/capability review priority, with synthesis last.
priorities = registry["review_priorities"]
assert len(priorities) == 8
assert {item["branch"] for item in priorities} == {item["branch"] for item in parked}
assert priorities[-1]["branch"] == "codex/overnight-exploration-summary"
rejects(lambda item: item["review_priorities"].pop(), "missing review priority validated")

# BG19: no executable deletion or cleanup field may enter the registry.
assert registry["cleanup_governance"]["deletion_action_present"] is False
assert registry["cleanup_governance"]["automatic_or_bulk_cleanup_allowed"] is False
for forbidden in ("delete_branch", "cleanup_command", "execute_cleanup"):
    rejects(lambda item, key=forbidden: item.update({key: "forbidden"}), "executable cleanup field validated")

# BG20: storage, runtime, production, scheduling, live, and ML boundaries are exact.
assert registry["boundaries"] == EXPECTED_BOUNDARIES
rejects(lambda item: item["boundaries"].update(production_authorized=True), "production authority validated")
rejects(lambda item: item["boundaries"].update(ml_training_or_inference=True), "ML execution validated")
rejects(lambda item: item["boundaries"].update(live_request_count=1), "live request validated")

# BG21: the governance module has no I/O/network/git/subprocess implementation.
module_text = (ROOT / "acquisition" / "branch_pr_governance.py").read_text(encoding="utf-8")
for forbidden_text in ("import requests", "import subprocess", "import sqlite3", "from pathlib", "open(", "urlopen("):
    assert forbidden_text not in module_text

# BG22: acquisition runtime modules do not import governance validation.
for folder in ("api", "repository", "control_plane", "service"):
    for path in (ROOT / folder).rglob("*.py"):
        assert "branch_pr_governance" not in path.read_text(encoding="utf-8"), path
for path in (ROOT / "acquisition").glob("*.py"):
    if path.name != "branch_pr_governance.py":
        assert "branch_pr_governance" not in path.read_text(encoding="utf-8"), path

# BG23: deterministic serialization preserves the validated object and contains no sensitive fields.
serialized = serialize_branch_pr_disposition_registry(registry)
assert serialized == registry
serialized_text = json.dumps(serialized, ensure_ascii=False, sort_keys=True)
for forbidden_text in ("authorization", "cookie", "session_token", "api_key", "password"):
    assert forbidden_text not in serialized_text.lower()

# BG24: every record retains timezone-aware evidence no newer than the snapshot.
assert all(
    datetime.fromisoformat(item["observed_at"]) <= datetime.fromisoformat(registry["observed_at"])
    for item in branches
)
assert active[0]["observed_at"] == registry["observed_at"]
rejects(lambda item: item["branches"][0].update(observed_at="2026-08-31T13:00:31"), "timezone-free evidence validated")

# BG25: the register performs no deletion, mutation, live request, production, or ML action.
assert registry["summary"]["branch_deletion_count"] == 0
assert all(item["deletion_allowed"] is False for item in branches)
assert registry["boundaries"]["branch_mutation_enabled"] is False
assert registry["boundaries"]["live_request_count"] == 0
assert registry["boundaries"]["production_authorized"] is False
assert registry["boundaries"]["scheduler_action"] is None
assert registry["boundaries"]["ml_training_or_inference"] is False
assert registry["boundaries"]["ml_dataset_export"] is False

print("Branch/PR Governance deterministic tests passed (BG1-BG25).")
