"""Deterministic tests for the KU2D Parked Candidate Review v1."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from parked_candidate_review import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    EXPECTED_SURFACES,
    REVIEW_STATUSES,
    serialize_parked_candidate_review,
    validate_parked_candidate_review,
)


review = json.loads((ROOT / "config" / "parked_candidate_review.json").read_text(encoding="utf-8"))
registry = json.loads(
    (ROOT / "config" / "candidate_learning_evidence_registry.json").read_text(encoding="utf-8")
)


def rejects(mutator, message: str) -> None:
    changed = deepcopy(review)
    mutator(changed)
    try:
        validate_parked_candidate_review(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# PCR1: the authoritative artifact validates and serializes deterministically.
validated = validate_parked_candidate_review(review)
assert validated == review and validated is not review
assert serialize_parked_candidate_review(review) == review

# PCR2: all six exact parked Draft PRs are present at immutable reviewed heads.
surfaces = {item["pr_number"]: item for item in review["parked_surfaces"]}
assert set(surfaces) == set(EXPECTED_SURFACES) == set(range(36, 42))
for pr_number, (branch, head, file_count) in EXPECTED_SURFACES.items():
    assert surfaces[pr_number]["branch"] == branch
    assert surfaces[pr_number]["head_sha"] == head
    assert len(surfaces[pr_number]["unique_files"]) == file_count

# PCR3: every parked PR remains open, Draft, unmerged, and unmodified by review.
assert all(item["open_at_review"] and item["draft_at_review"] for item in surfaces.values())
assert all(not item["merged_at_review"] and not item["mutated_by_review"] for item in surfaces.values())
rejects(lambda item: item["parked_surfaces"][0].update(mutated_by_review=True), "mutated branch validated")

# PCR4: exact historical merge base and integration target remain explicit.
assert {item["historical_base_sha"] for item in surfaces.values()} == {
    "820994f7521ef5f181e96826fdaaee40202b91ba"
}
assert {item["base_branch"] for item in surfaces.values()} == {"integration/data-acquisition-platform"}

# PCR5: every delta file is retained, including three independent CI-file edits.
assert sum(len(item["unique_files"]) for item in surfaces.values()) == 30
assert sum(".github/workflows/data-acquisition-platform-ci.yml" in item["unique_files"] for item in surfaces.values()) == 3

# PCR6: CLE-000001 through CLE-000011 resolve exactly to the current registry.
coverage = {item["candidate_id"]: item for item in review["candidate_coverage"]}
registered = {item["candidate_id"] for item in registry["candidates"]}
assert set(coverage) == registered == {f"KU2D-CLE-{number:06d}" for number in range(1, 12)}

# PCR7: no one-paragraph CLE record is treated as a lossless branch projection.
assert all(item["lossless_projection"] is False for item in coverage.values())
assert review["summary"]["lossless_candidate_projection_count"] == 0

# PCR8: every CLE gap states unique knowledge and exact future promotion evidence.
assert all(item["unrepresented_unique_knowledge"] for item in coverage.values())
assert all(item["future_promotion_evidence"] for item in coverage.values())

# PCR9: candidate coverage remains explicitly non-authorizing.
for item in coverage.values():
    assert item["authority"] == {
        "candidate_only": True,
        "reviewed_corpus_authorized": False,
        "core_knowledge_authorized": False,
        "human_confirmed": False,
        "ground_truth_asserted": False,
        "production_authorized": False,
    }

# PCR10: all 59 claim/capability/boundary findings have exact source provenance.
claims = review["claims"]
assert len(claims) == 59 and len({item["claim_id"] for item in claims}) == 59
all_files = {path for surface in surfaces.values() for path in surface["unique_files"]}
assert all(item["file"] in all_files and item["location"] for item in claims)

# PCR11: every required review status is represented and summary counts reconcile.
status_counts = {status: sum(item["review_status"] == status for item in claims) for status in REVIEW_STATUSES}
assert status_counts == review["summary"]["review_status_counts"]
assert status_counts == {
    "already_integrated_equivalent": 4,
    "candidate_supported": 17,
    "candidate_partially_supported": 10,
    "contradicted_or_stale": 4,
    "insufficient_evidence": 5,
    "duplicate_of_current_knowledge": 8,
    "source_specific_historical_only": 11,
}

# PCR12: every parked PR has a non-empty independently reconciled claim inventory.
surface_counts = review["summary"]["surface_claim_counts"]
assert surface_counts == {
    "KU2D-PC-PR36": 10,
    "KU2D-PC-PR37": 11,
    "KU2D-PC-PR38": 7,
    "KU2D-PC-PR39": 9,
    "KU2D-PC-PR40": 11,
    "KU2D-PC-PR41": 11,
}

# PCR13: candidate-supported findings retain missing promotion evidence and authority.
candidate_claims = [item for item in claims if item["review_status"].startswith("candidate_")]
assert len(candidate_claims) == 27
assert all(item["missing_promotion_evidence"] for item in candidate_claims)
assert all(item["candidate_evidence_ids"] for item in candidate_claims)

# PCR14: partial candidate findings cannot silently become fully represented.
partial_index = next(i for i, item in enumerate(claims) if item["review_status"] == "candidate_partially_supported")
rejects(lambda item: item["claims"][partial_index].update(missing_promotion_evidence=[]), "partial gap vanished")

# PCR15: insufficient findings also fail closed without explicit evidence requirements.
insufficient_index = next(i for i, item in enumerate(claims) if item["review_status"] == "insufficient_evidence")
rejects(lambda item: item["claims"][insufficient_index].update(missing_promotion_evidence=[]), "unsupported gap vanished")

# PCR16: historical-only source/date/request ledgers remain historical-only.
historical = [item for item in claims if item["review_status"] == "source_specific_historical_only"]
assert len(historical) == 11
assert all(item["disposition"] == "retain_historical_only" for item in historical)

# PCR17: current equivalents and duplicates cannot create a candidate promotion.
assert all(item["disposition"] == "use_current_equivalent" for item in claims if item["review_status"] == "already_integrated_equivalent")
assert all(item["disposition"] == "no_new_knowledge" for item in claims if item["review_status"] == "duplicate_of_current_knowledge")

# PCR18: stale Akha, ranking, Lazada, and priority state is rewritten, never promoted.
stale = [item for item in claims if item["review_status"] == "contradicted_or_stale"]
assert len(stale) == 4
assert all(item["disposition"] == "rewrite_before_reuse" for item in stale)

# PCR19: every claim has an exact dependency graph edge set.
graph = review["evidence_dependency_graph"]
assert set(graph) == {item["claim_id"] for item in claims}
assert all(graph[item["claim_id"]] == item["evidence_dependencies"] for item in claims)

# PCR20: dependency graph omissions and mismatches fail closed.
rejects(lambda item: item["evidence_dependency_graph"].pop("KU2D-PCR-000001"), "missing graph edge validated")
rejects(lambda item: item["evidence_dependency_graph"]["KU2D-PCR-000001"].append("KU2D-EV-QUALITY"), "graph mismatch validated")

# PCR21: every evidence dependency resolves to candidate/current/core/synthesis/governance evidence.
nodes = {item["evidence_id"] for item in review["evidence_nodes"]}
assert all(set(item["evidence_dependencies"]) <= nodes for item in claims)
for required in ("KU2D-EV-CANDIDATES", "KU2D-EV-REVIEWED", "KU2D-EV-CORE", "KU2D-EV-SYNTHESIS", "KU2D-EV-GOVERNANCE"):
    assert required in nodes
for node in review["evidence_nodes"]:
    for reference in node["references"]:
        if not reference.startswith("PR:"):
            assert (ROOT / reference.split("#", 1)[0]).is_file(), reference

# PCR22: exact claim authority rejects Reviewed Corpus/Core/Ground Truth/production promotion.
promotion_index = next(i for i, item in enumerate(claims) if item["review_status"] == "candidate_supported")
rejects(lambda item: item["claims"][promotion_index]["authority"].update(reviewed_corpus_authorized=True), "promotion validated")
rejects(lambda item: item["candidate_coverage"][0]["authority"].update(core_knowledge_authorized=True), "core promotion validated")

# PCR23: technique/environment and evidence/interpretation stay separate current rules.
statements = " ".join(item["statement"] for item in claims)
assert "environment escalation" in statements
assert "historical run" in statements
assert "not a validated technique" in statements

# PCR24: display order never becomes demand and product/variant semantics remain explicit.
assert any("display context, not demand" in item["statement"] for item in claims)
assert any("Variant ranges remain ranges" in item["statement"] for item in claims)

# PCR25: price temporal/status evidence remains separate from source role and price role.
assert any("time-specific availability" in item["statement"] for item in claims)
assert any("service price is not Retail Product & Price" in item["statement"] for item in claims)

# PCR26: exact non-authorizing boundary set is immutable.
assert review["boundaries"] == EXPECTED_BOUNDARIES
rejects(lambda item: item["boundaries"].update(live_request_count=1), "live request validated")
rejects(lambda item: item["boundaries"].update(production_authorized=True), "production validated")

# PCR27: parked merge/mutation/delete and knowledge writes stay zero/false.
assert review["summary"]["candidate_promotion_count"] == 0
assert review["summary"]["parked_branch_mutation_count"] == 0
assert review["summary"]["parked_pr_merge_count"] == 0
rejects(lambda item: item["summary"].update(parked_pr_merge_count=1), "parked merge validated")

# PCR28: summary status, disposition, or file-count drift fails closed.
rejects(lambda item: item["summary"].update(unique_file_count=29), "file count drift validated")
rejects(lambda item: item["summary"]["review_status_counts"].update(candidate_supported=16), "status drift validated")

# PCR29: the validator has no filesystem, Git, GitHub, network, DB, or subprocess implementation.
module_text = (ROOT / "acquisition" / "parked_candidate_review.py").read_text(encoding="utf-8")
for forbidden in ("from pathlib", "import requests", "import subprocess", "import sqlite3", "urlopen(", "open(", "import git"):
    assert forbidden not in module_text

# PCR30: normal acquisition runtime does not import this review-only validator.
for folder in ("api", "repository", "control_plane", "service"):
    for path in (ROOT / folder).rglob("*.py"):
        assert "parked_candidate_review" not in path.read_text(encoding="utf-8"), path
for path in (ROOT / "acquisition").glob("*.py"):
    if path.name != "parked_candidate_review.py":
        assert "parked_candidate_review" not in path.read_text(encoding="utf-8"), path

print("Parked Candidate Review deterministic tests passed (PCR1-PCR30).")
