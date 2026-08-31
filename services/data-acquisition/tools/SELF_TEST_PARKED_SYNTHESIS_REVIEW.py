"""Deterministic tests for the KU2D Parked Synthesis Review v1."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from parked_synthesis_review import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    REVIEW_STATUSES,
    serialize_parked_synthesis_review,
    validate_parked_synthesis_review,
)


review = json.loads((ROOT / "config" / "parked_synthesis_review.json").read_text(encoding="utf-8"))
candidate_registry = json.loads(
    (ROOT / "config" / "candidate_learning_evidence_registry.json").read_text(encoding="utf-8")
)
reviewed_corpus = json.loads(
    (ROOT / "config" / "reviewed_learning_corpus.json").read_text(encoding="utf-8")
)


def rejects(mutator, message: str) -> None:
    changed = deepcopy(review)
    mutator(changed)
    try:
        validate_parked_synthesis_review(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# PSR1: the authoritative artifact validates and serializes deterministically.
validated = validate_parked_synthesis_review(review)
assert validated == review
assert serialize_parked_synthesis_review(review) == review
assert validated is not review

# PSR2: exact parked surfaces retain PR, branch, head, base, and file provenance.
surfaces = {item["pr_number"]: item for item in review["historical_surfaces"]}
assert set(surfaces) == {42, 43}
assert surfaces[42]["branch"] == "codex/overnight-acquisition-technique-transfer-matrix"
assert surfaces[42]["head_sha"] == "4c024a480dafda27b0064b3059e34eebaadf353d"
assert surfaces[43]["branch"] == "codex/overnight-exploration-summary"
assert surfaces[43]["head_sha"] == "87b700db3e9c2b507530f0427a6a1a2bea9ab3e9"
assert {item["historical_base_sha"] for item in surfaces.values()} == {
    "820994f7521ef5f181e96826fdaaee40202b91ba"
}

# PSR3: parked surfaces remain open Draft evidence and are not mutated or merged.
assert all(item["open_draft_at_review"] is True for item in surfaces.values())
assert all(item["mutated_or_merged_by_review"] is False for item in surfaces.values())
rejects(lambda item: item["historical_surfaces"][0].update(mutated_or_merged_by_review=True), "mutated parked surface validated")

# PSR4: every historical operational assertion remains ledger-only and non-promoting.
assert len(review["historical_assertions"]) == 9
assert all(item["authority"] == "historical_unreviewed_ledger_only" for item in review["historical_assertions"])
assert all(item["promotion_authorized"] is False for item in review["historical_assertions"])

# PSR5: all 39 distinct synthesis claims have unique exact claim-level provenance.
claims = review["claims"]
assert len(claims) == 39
assert len({item["claim_id"] for item in claims}) == 39
assert all(item["source_surface_id"] in {"KU2D-HS-PR42", "KU2D-HS-PR43"} for item in claims)
assert all(item["location"] and item["statement"] for item in claims)

# PSR6: every bounded review status is represented and counts reconcile.
status_counts = {status: sum(item["review_status"] == status for item in claims) for status in REVIEW_STATUSES}
assert status_counts == review["summary"]["review_status_counts"]
assert status_counts == {
    "already_integrated_equivalent": 9,
    "candidate_supported": 9,
    "candidate_partially_supported": 3,
    "contradicted_or_stale": 3,
    "insufficient_evidence": 7,
    "duplicate_of_current_knowledge": 8,
}

# PSR7: the explicit dependency graph covers every claim and exactly matches it.
graph = review["evidence_dependency_graph"]
assert set(graph) == {item["claim_id"] for item in claims}
assert all(graph[item["claim_id"]] == item["evidence_dependencies"] for item in claims)

# PSR8: every dependency resolves to a durable reviewed/candidate/governance node.
nodes = {item["evidence_id"]: item for item in review["evidence_nodes"]}
assert len(nodes) == len(review["evidence_nodes"])
assert all(set(item["evidence_dependencies"]) <= set(nodes) for item in claims)

# PSR9: current-equivalent and duplicate claims use current durable authority.
for item in claims:
    if item["review_status"] in {"already_integrated_equivalent", "duplicate_of_current_knowledge"}:
        authorities = {nodes[node_id]["authority"] for node_id in item["evidence_dependencies"]}
        assert authorities & {"reviewed_current", "human_confirmed_policy", "governance_only"}

# PSR10: candidate-supported claims depend on Candidate Learning Evidence and remain candidate synthesis.
candidate_claims = [
    item for item in claims
    if item["review_status"] in {"candidate_supported", "candidate_partially_supported"}
]
assert len(candidate_claims) == 12
for item in candidate_claims:
    assert any(nodes[node_id]["authority"] == "candidate_only" for node_id in item["evidence_dependencies"])
    assert item["disposition"] == "retain_candidate_synthesis"

# PSR11: partial and insufficient claims fail closed without missing-evidence requirements.
partial_index = next(i for i, item in enumerate(claims) if item["review_status"] == "candidate_partially_supported")
insufficient_index = next(i for i, item in enumerate(claims) if item["review_status"] == "insufficient_evidence")
rejects(lambda item: item["claims"][partial_index].update(missing_evidence_requirements=[]), "partial claim without gap validated")
rejects(lambda item: item["claims"][insufficient_index].update(missing_evidence_requirements=[]), "unsupported claim without gap validated")

# PSR12: stale claims must be rewritten or retired rather than silently retained.
stale = [item for item in claims if item["review_status"] == "contradicted_or_stale"]
assert len(stale) == 3
assert {item["disposition"] for item in stale} <= {"rewrite_before_reuse", "retire_historical_claim"}

# PSR13: current duplicates explicitly create no new knowledge.
duplicates = [item for item in claims if item["review_status"] == "duplicate_of_current_knowledge"]
assert len(duplicates) == 8
assert all(item["disposition"] == "no_new_knowledge" for item in duplicates)

# PSR14: no claim can authorize Reviewed Corpus, Core Knowledge, Ground Truth, or production.
for item in claims:
    assert item["authority"] == {
        "reviewed_corpus_authorized": False,
        "core_knowledge_authorized": False,
        "ground_truth_authorized": False,
        "production_authorized": False,
    }
promotion_index = next(i for i, item in enumerate(claims) if item["review_status"] == "candidate_supported")
rejects(
    lambda item: item["claims"][promotion_index]["authority"].update(reviewed_corpus_authorized=True),
    "candidate synthesis promotion validated",
)

# PSR15: candidate evidence nodes resolve exactly to the current candidate registry.
registered_candidate_ids = {item["candidate_id"] for item in candidate_registry["candidates"]}
review_candidate_refs = {
    reference.rsplit("#", 1)[-1]
    for node in review["evidence_nodes"] if node["authority"] == "candidate_only"
    for reference in node["references"]
}
assert review_candidate_refs == registered_candidate_ids
assert all(item["authority"]["reviewed_corpus_authorized"] is False for item in candidate_registry["candidates"])

# PSR16: reviewed dependencies resolve to current Reviewed Learning Corpus episodes.
reviewed_ids = {item["episode_id"] for item in reviewed_corpus["episodes"]}
reviewed_refs = {
    reference.rsplit("#", 1)[-1]
    for node in review["evidence_nodes"]
    if node["authority"] in {"reviewed_current", "human_confirmed_policy", "deterministic_contract_only"}
    for reference in node["references"]
}
assert reviewed_refs == reviewed_ids

# PSR17: an unknown evidence dependency fails closed.
rejects(lambda item: item["claims"][0]["evidence_dependencies"].append("KU2D-EV-UNKNOWN"), "unknown evidence validated")

# PSR18: a missing graph claim or a graph mismatch fails closed.
rejects(lambda item: item["evidence_dependency_graph"].pop("KU2D-SYN-000001"), "incomplete graph validated")
rejects(lambda item: item["evidence_dependency_graph"]["KU2D-SYN-000001"].append("KU2D-EV-GOVERNANCE"), "mismatched graph validated")

# PSR19: summary status and disposition drift fails closed.
rejects(lambda item: item["summary"]["review_status_counts"].update(candidate_supported=8), "stale status count validated")
rejects(lambda item: item["summary"]["disposition_counts"].update(retain_candidate_synthesis=11), "stale disposition count validated")

# PSR20: candidate evidence nodes cannot authorize promotion.
candidate_node_index = next(i for i, item in enumerate(review["evidence_nodes"]) if item["authority"] == "candidate_only")
rejects(lambda item: item["evidence_nodes"][candidate_node_index].update(promotion_authorized=True), "promoting evidence node validated")

# PSR21: historical ledger statements cannot become authoritative or promoting.
rejects(lambda item: item["historical_assertions"][0].update(authority="reviewed_current"), "authoritative historical ledger validated")
rejects(lambda item: item["historical_assertions"][0].update(promotion_authorized=True), "promoting ledger validated")

# PSR22: exact non-authorizing boundaries are enforced.
assert review["boundaries"] == EXPECTED_BOUNDARIES
rejects(lambda item: item["boundaries"].update(production_authorized=True), "production authority validated")
rejects(lambda item: item["boundaries"].update(live_request_count=1), "live request validated")
rejects(lambda item: item["boundaries"].update(ml_training_or_inference=True), "ML execution validated")

# PSR23: branch deletion, mutation, or merge counts cannot enter the review.
rejects(lambda item: item["boundaries"].update(branch_deletion_count=1), "branch deletion validated")
rejects(lambda item: item["boundaries"].update(parked_branch_mutation_count=1), "branch mutation validated")
rejects(lambda item: item["summary"].update(parked_branch_merge_count=1), "parked merge validated")

# PSR24: executable promotion, deletion, merge, mutation, or scheduling fields are forbidden.
for forbidden in (
    "promote_to_reviewed_corpus", "delete_branch", "merge_branch", "mutation_command", "scheduler_command"
):
    rejects(lambda item, key=forbidden: item.update({key: "forbidden"}), "executable action field validated")

# PSR25: the mixed-authority strongest-evidence claim is explicitly stale and rewritten.
mixed = next(item for item in claims if item["claim_id"] == "KU2D-SYN-000028")
assert mixed["review_status"] == "contradicted_or_stale"
assert mixed["disposition"] == "rewrite_before_reuse"

# PSR26: the old P0-P3 ranking is retired and cannot become ranking behavior.
ranking = next(item for item in claims if item["claim_id"] == "KU2D-SYN-000039")
assert ranking["review_status"] == "contradicted_or_stale"
assert ranking["disposition"] == "retire_historical_claim"
assert review["boundaries"]["broader_recommendation_or_ranking"] is False

# PSR27: exact historical traffic and Q-Diving count claims remain historical-only.
for claim_id in ("KU2D-SYN-000029", "KU2D-SYN-000037"):
    item = next(claim for claim in claims if claim["claim_id"] == claim_id)
    assert item["review_status"] == "insufficient_evidence"
    assert item["disposition"] == "retain_historical_only"

# PSR28: technique/environment, evidence/interpretation, demand, and identity policies remain current-only.
for claim_id in ("KU2D-SYN-000012", "KU2D-SYN-000013", "KU2D-SYN-000019", "KU2D-SYN-000020"):
    item = next(claim for claim in claims if claim["claim_id"] == claim_id)
    assert item["review_status"] == "duplicate_of_current_knowledge"
    assert item["disposition"] == "no_new_knowledge"

# PSR29: the validator has no I/O, git, GitHub, network, database, or subprocess implementation.
module_text = (ROOT / "acquisition" / "parked_synthesis_review.py").read_text(encoding="utf-8")
for forbidden_text in (
    "import requests", "import subprocess", "import sqlite3", "from pathlib", "open(", "urlopen(", "import git"
):
    assert forbidden_text not in module_text

# PSR30: normal acquisition runtime does not import the synthesis-review validator.
for folder in ("api", "repository", "control_plane", "service"):
    for path in (ROOT / folder).rglob("*.py"):
        assert "parked_synthesis_review" not in path.read_text(encoding="utf-8"), path
for path in (ROOT / "acquisition").glob("*.py"):
    if path.name != "parked_synthesis_review.py":
        assert "parked_synthesis_review" not in path.read_text(encoding="utf-8"), path

print("Parked Synthesis Review deterministic tests passed (PSR1-PSR30).")
