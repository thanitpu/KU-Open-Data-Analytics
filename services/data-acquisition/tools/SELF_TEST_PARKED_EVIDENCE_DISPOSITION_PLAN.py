"""Deterministic tests for KU2D Parked Evidence Disposition Plan v1."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from parked_evidence_disposition_plan import (  # noqa: E402
    DISPOSITIONS,
    EXPECTED_BOUNDARIES,
    EXPECTED_PRS,
    serialize_parked_evidence_disposition_plan,
    validate_parked_evidence_disposition_plan,
)


plan = json.loads(
    (ROOT / "config" / "parked_evidence_disposition_plan.json").read_text(encoding="utf-8")
)
candidate_review = json.loads(
    (ROOT / "config" / "parked_candidate_review.json").read_text(encoding="utf-8")
)
synthesis_review = json.loads(
    (ROOT / "config" / "parked_synthesis_review.json").read_text(encoding="utf-8")
)
candidate_registry = json.loads(
    (ROOT / "config" / "candidate_learning_evidence_registry.json").read_text(encoding="utf-8")
)


def rejects(mutator, message: str) -> None:
    changed = deepcopy(plan)
    mutator(changed)
    try:
        validate_parked_evidence_disposition_plan(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# PED1: the plan validates and serializes as a detached deterministic object.
validated = validate_parked_evidence_disposition_plan(plan)
assert validated == plan and validated is not plan
assert serialize_parked_evidence_disposition_plan(plan) == plan

# PED2: exact PR/branch/head provenance covers #36 through #43.
plans = {item["pr_number"]: item for item in plan["pr_plans"]}
assert set(plans) == set(EXPECTED_PRS) == set(range(36, 44))
for pr_number, (branch, head) in EXPECTED_PRS.items():
    assert plans[pr_number]["branch"] == branch
    assert plans[pr_number]["head_sha"] == head

# PED3: every parked PR remains open, Draft, unmerged, and unchanged.
assert all(
    item["observed_pr_state"]
    == {"open": True, "draft": True, "merged": False, "head_unchanged": True}
    for item in plans.values()
)
rejects(lambda item: item["pr_plans"][0]["observed_pr_state"].update(open=False), "closed PR validated")

# PED4: the common historical base and current integration target remain exact.
assert {item["historical_base_sha"] for item in plans.values()} == {
    "820994f7521ef5f181e96826fdaaee40202b91ba"
}
assert {item["base_branch"] for item in plans.values()} == {"integration/data-acquisition-platform"}

# PED5: every bounded planning disposition is represented or explicitly zero-counted.
counts = {
    disposition: sum(item["planning_disposition"] == disposition for item in plans.values())
    for disposition in DISPOSITIONS
}
assert counts == plan["summary"]["planning_disposition_counts"]
assert counts == {
    "RETAIN_AS_EVIDENCE": 1,
    "SUPERSEDED_BY_REVIEWED_ARTIFACTS": 2,
    "NEEDS_TARGETED_EVIDENCE_RERUN": 3,
    "ELIGIBLE_FOR_LATER_CLOSURE": 0,
    "NEEDS_HUMAN_ADJUDICATION": 2,
}

# PED6: no plan is immediately closure-eligible or claims lossless preservation.
assert all(item["closure_eligible_now"] is False for item in plans.values())
assert all(item["lossless_preservation_claimed"] is False for item in plans.values())
assert all(item["lossless_preservation_proof"] == [] for item in plans.values())

# PED7: lossless or closure claims fail closed without proof.
rejects(lambda item: item["pr_plans"][0].update(lossless_preservation_claimed=True), "lossless claim validated")
rejects(lambda item: item["pr_plans"][0].update(closure_eligible_now=True), "closure eligibility validated")

# PED8: every PR says what is durable and what remains non-lossless.
assert all(item["durably_preserved_knowledge"] for item in plans.values())
assert all(item["not_losslessly_preserved"] for item in plans.values())

# PED9: every PR has concrete prerequisites and future human action authority.
assert all(item["prerequisites_before_closure"] for item in plans.values())
assert {
    item["future_action_authority"] for item in plans.values()
} == {"explicit-human-decision-required"}

# PED10: no disposition is executable and no live rerun is authorized.
assert all(item["execute_disposition"] is False for item in plans.values())
assert all(item["live_rerun_authorized"] is False for item in plans.values())

# PED11: targeted rerun requirements appear only on PRs #37, #39, and #40.
reruns = {
    number for number, item in plans.items()
    if item["planning_disposition"] == "NEEDS_TARGETED_EVIDENCE_RERUN"
}
assert reruns == {37, 39, 40}
assert all(plans[number]["targeted_evidence_requirements"] for number in reruns)
assert all(
    not item["targeted_evidence_requirements"]
    for number, item in plans.items() if number not in reruns
)

# PED12: human adjudication questions appear only on PRs #38 and #41.
adjudication = {
    number for number, item in plans.items()
    if item["planning_disposition"] == "NEEDS_HUMAN_ADJUDICATION"
}
assert adjudication == {38, 41}
assert all(plans[number]["human_adjudication_questions"] for number in adjudication)

# PED13: PR #36 remains retained because unique code/fixtures are not lossless.
assert plans[36]["planning_disposition"] == "RETAIN_AS_EVIDENCE"
assert any("normalizer" in item for item in plans[36]["not_losslessly_preserved"])

# PED14: PRs #42/#43 are superseded by reviewed artifacts, not declared closable.
for number in (42, 43):
    assert plans[number]["planning_disposition"] == "SUPERSEDED_BY_REVIEWED_ARTIFACTS"
    assert "KU2D-EV-SYNTHESIS-REVIEW" in plans[number]["evidence_dependencies"]
    assert plans[number]["closure_eligible_now"] is False

# PED15: all 11 current Candidate Learning Evidence IDs resolve exactly once in union.
candidate_dependencies = {
    dependency for item in plans.values() for dependency in item["candidate_dependencies"]
}
assert candidate_dependencies == {
    item["candidate_id"] for item in candidate_registry["candidates"]
} == {f"KU2D-CLE-{number:06d}" for number in range(1, 12)}

# PED16: PR #36-#41 dependencies cover all 59 candidate-review claims exactly.
candidate_claims = {
    dependency
    for number, item in plans.items() if number <= 41
    for dependency in item["claim_dependencies"]
}
assert candidate_claims == {
    item["claim_id"] for item in candidate_review["claims"]
} == {f"KU2D-PCR-{number:06d}" for number in range(1, 60)}

# PED17: PR #42/#43 dependencies cover all 39 synthesis-review claims exactly.
synthesis_claims = {
    dependency
    for number, item in plans.items() if number >= 42
    for dependency in item["claim_dependencies"]
}
assert synthesis_claims == {
    item["claim_id"] for item in synthesis_review["claims"]
} == {f"KU2D-SYN-{number:06d}" for number in range(1, 40)}

# PED18: PR #42 and #43 claim ranges remain source-surface exact.
assert set(plans[42]["claim_dependencies"]) == {
    item["claim_id"] for item in synthesis_review["claims"]
    if item["source_surface_id"] == "KU2D-HS-PR42"
}
assert set(plans[43]["claim_dependencies"]) == {
    item["claim_id"] for item in synthesis_review["claims"]
    if item["source_surface_id"] == "KU2D-HS-PR43"
}

# PED19: every evidence dependency resolves, and every file reference exists.
nodes = {item["evidence_id"]: item for item in plan["evidence_nodes"]}
assert all(set(item["evidence_dependencies"]) <= set(nodes) for item in plans.values())
for node in nodes.values():
    for reference in node["references"]:
        assert (ROOT / reference).is_file(), reference

# PED20: evidence nodes cannot authorize execution.
assert all(item["authorizes_execution"] is False for item in nodes.values())
rejects(lambda item: item["evidence_nodes"][0].update(authorizes_execution=True), "executing evidence validated")

# PED21: candidate, synthesis, governance, and current contract evidence remain distinct.
assert set(nodes) == {
    "KU2D-EV-GOVERNANCE",
    "KU2D-EV-CANDIDATE-REVIEW",
    "KU2D-EV-SYNTHESIS-REVIEW",
    "KU2D-EV-CANDIDATE-REGISTRY",
    "KU2D-EV-CORE-CURRENT",
}

# PED22: every plan remains non-promoting and non-authorizing.
for item in plans.values():
    assert item["authority"] == {
        "planning_only": True,
        "candidate_promoted": False,
        "reviewed_corpus_authorized": False,
        "core_knowledge_authorized": False,
        "human_confirmed": False,
        "ground_truth_asserted": False,
        "production_authorized": False,
    }

# PED23: authority promotion drift fails closed.
rejects(
    lambda item: item["pr_plans"][0]["authority"].update(reviewed_corpus_authorized=True),
    "Reviewed Corpus promotion validated",
)
rejects(
    lambda item: item["pr_plans"][0]["authority"].update(ground_truth_asserted=True),
    "Ground Truth promotion validated",
)

# PED24: summary counts reconcile and all action counts remain zero.
assert plan["summary"]["parked_pr_count"] == 8
assert plan["summary"]["candidate_dependency_count"] == 11
assert plan["summary"]["claim_dependency_count"] == 98
for key in (
    "closure_eligible_now_count", "lossless_preservation_claim_count",
    "candidate_promotion_count", "parked_pr_close_count", "parked_pr_merge_count",
    "parked_branch_mutation_count", "branch_deletion_count",
):
    assert plan["summary"][key] == 0

# PED25: stale summary or provenance fails closed.
rejects(lambda item: item["summary"].update(claim_dependency_count=97), "stale count validated")
rejects(lambda item: item["pr_plans"][0].update(head_sha="0" * 40), "stale head validated")

# PED26: exact boundaries prohibit close/merge/delete/mutation/live/production/ML/ranking.
assert plan["boundaries"] == EXPECTED_BOUNDARIES
rejects(lambda item: item["boundaries"].update(parked_pr_close_count=1), "close action validated")
rejects(lambda item: item["boundaries"].update(live_request_count=1), "live request validated")
rejects(lambda item: item["boundaries"].update(ml_training_or_inference=True), "ML work validated")

# PED27: executable close/delete/merge/mutation/promotion fields are forbidden anywhere.
for key in (
    "close_pr", "delete_branch", "merge_pr", "mutate_ref",
    "close_command", "promote_to_core_knowledge", "scheduler_command",
):
    rejects(lambda item, field=key: item["pr_plans"][0].update({field: "forbidden"}), f"{key} validated")

# PED28: no ELIGIBLE_FOR_LATER_CLOSURE shortcut is accepted without lossless proof.
rejects(
    lambda item: item["pr_plans"][0].update(
        planning_disposition="ELIGIBLE_FOR_LATER_CLOSURE"
    ),
    "unsupported later closure validated",
)

# PED29: the validator has no I/O, Git, GitHub, network, DB, or subprocess behavior.
module_text = (ROOT / "acquisition" / "parked_evidence_disposition_plan.py").read_text(
    encoding="utf-8"
)
for forbidden in (
    "from pathlib", "import requests", "import subprocess", "import sqlite3",
    "urlopen(", "open(", "import git",
):
    assert forbidden not in module_text

# PED30: normal acquisition runtime does not import this planning-only validator.
for folder in ("api", "repository", "control_plane", "service"):
    for path in (ROOT / folder).rglob("*.py"):
        assert "parked_evidence_disposition_plan" not in path.read_text(encoding="utf-8"), path
for path in (ROOT / "acquisition").glob("*.py"):
    if path.name != "parked_evidence_disposition_plan.py":
        assert "parked_evidence_disposition_plan" not in path.read_text(encoding="utf-8"), path

print("Parked Evidence Disposition Plan deterministic tests passed (PED1-PED30).")
