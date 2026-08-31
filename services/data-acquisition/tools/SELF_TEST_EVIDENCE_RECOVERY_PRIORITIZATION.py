"""Deterministic tests for KU2D Evidence Recovery Prioritization v1."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from evidence_recovery_prioritization import (  # noqa: E402
    EXPECTED_BOUNDARIES,
    EXPECTED_PRS,
    EXPECTED_WEIGHTS,
    serialize_evidence_recovery_prioritization,
    validate_evidence_recovery_prioritization,
)


def load(name: str) -> dict:
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


artifact = load("evidence_recovery_prioritization.json")
plan = load("parked_evidence_disposition_plan.json")
candidate_review = load("parked_candidate_review.json")
candidate_registry = load("candidate_learning_evidence_registry.json")
governance = load("branch_pr_disposition_registry.json")
synthesis_review = load("parked_synthesis_review.json")
core_taxonomy = load("core_knowledge_taxonomy.json")


def rejects(mutator, message: str) -> None:
    changed = deepcopy(artifact)
    mutator(changed)
    try:
        validate_evidence_recovery_prioritization(changed)
        raise AssertionError(message)
    except ValueError:
        pass


# ERP1: the artifact validates and serializes as a detached JSON object.
validated = validate_evidence_recovery_prioritization(artifact)
assert validated == artifact and validated is not artifact
assert serialize_evidence_recovery_prioritization(artifact) == artifact

# ERP2: scope is exact and does not authorize a live rerun.
assert artifact["scope"]["candidate_pr_numbers"] == [37, 39, 40]
assert artifact["scope"]["selection_count"] == 1
assert artifact["scope"]["live_rerun_authorized"] is False
rejects(lambda item: item["scope"].update(live_rerun_authorized=True), "live rerun authorized")

# ERP3: all required integrated evidence families are explicit.
assert {item["schema"] for item in artifact["evidence_sources"]} == {
    plan["schema"],
    candidate_review["schema"],
    synthesis_review["schema"],
    candidate_registry["schema"],
    governance["schema"],
    core_taxonomy["schema"],
}

# ERP4: weights are transparent, deterministic, and total 100.
weights = {
    item["criterion"]: item["weight_percent"]
    for item in artifact["scoring_model"]["criteria"]
}
assert weights == EXPECTED_WEIGHTS and sum(weights.values()) == 100
rejects(
    lambda item: item["scoring_model"]["criteria"][0].update(weight_percent=21),
    "weight drift validated",
)

# ERP5: each required decision criterion has an explicit rationale.
assert all(item["rationale"] for item in artifact["scoring_model"]["criteria"])

# ERP6: candidate PR/branch/head provenance is exact.
candidates = {item["pr_number"]: item for item in artifact["candidates"]}
assert set(candidates) == set(EXPECTED_PRS)
for pr_number, expected in EXPECTED_PRS.items():
    assert candidates[pr_number]["branch"] == expected["branch"]
    assert candidates[pr_number]["head_sha"] == expected["head"]
rejects(lambda item: item["candidates"][0].update(head_sha="0" * 40), "stale head validated")

# ERP7: fresh parked state remains open, Draft, unmerged, and unchanged.
assert all(
    item["observed_pr_state"]
    == {"open": True, "draft": True, "merged": False, "head_unchanged": True}
    for item in candidates.values()
)
rejects(
    lambda item: item["candidates"][0]["observed_pr_state"].update(open=False),
    "closed parked PR validated",
)

# ERP8: all three candidates retain the reviewed disposition exactly.
plan_by_pr = {item["pr_number"]: item for item in plan["pr_plans"]}
assert all(
    item["planning_disposition"]
    == plan_by_pr[number]["planning_disposition"]
    == "NEEDS_TARGETED_EVIDENCE_RERUN"
    for number, item in candidates.items()
)

# ERP9: candidate dependencies match the disposition plan and CLE registry.
registry_ids = {item["candidate_id"] for item in candidate_registry["candidates"]}
for number, item in candidates.items():
    assert set(item["candidate_evidence_ids"]) == set(plan_by_pr[number]["candidate_dependencies"])
    assert set(item["candidate_evidence_ids"]) <= registry_ids

# ERP10: reviewed claim dependencies match the disposition plan exactly.
review_claims = {item["claim_id"] for item in candidate_review["claims"]}
for number, item in candidates.items():
    assert set(item["claim_dependency_ids"]) == set(plan_by_pr[number]["claim_dependencies"])
    assert set(item["claim_dependency_ids"]) <= review_claims

# ERP11: every CLE dependency maps to an explicit missing-evidence item.
for item in candidates.values():
    mapped = {
        candidate_id
        for gap in item["missing_evidence"]
        for candidate_id in gap["candidate_evidence_ids"]
    }
    assert mapped == set(item["candidate_evidence_ids"])

# ERP12: every claim maps exactly once to a gap or no-rerun reason.
for item in candidates.values():
    gap_claims = [claim for gap in item["missing_evidence"] for claim in gap["claim_ids"]]
    non_rerun = [entry["claim_id"] for entry in item["claims_not_requiring_rerun_evidence"]]
    assert not set(gap_claims) & set(non_rerun)
    assert set(gap_claims) | set(non_rerun) == set(item["claim_dependency_ids"])

# ERP13: missing-evidence requirements name sources and exact review dependencies.
assert all(
    gap["target_sources"] and gap["requirement"] and gap["claim_ids"]
    for item in candidates.values() for gap in item["missing_evidence"]
)

# ERP14: out-of-scope marketplace research remains explicit, not silently ranked as rerun work.
marketplace_future = [
    gap for gap in candidates[37]["missing_evidence"]
    if gap["in_targeted_rerun_scope"] is False
]
assert len(marketplace_future) == 1
assert set(marketplace_future[0]["target_sources"]) == {"Kaidee", "Temu", "AliExpress"}

# ERP15: Coffee repair is evidence-before-exit for Roots and Nana.
coffee_text = " ".join(gap["requirement"] for gap in candidates[39]["missing_evidence"])
assert "evidence-before-exit" in coffee_text
assert {source for gap in candidates[39]["missing_evidence"] for source in gap["target_sources"]} == {
    "Roots Coffee", "Nana Coffee Roasters"
}

# ERP16: Q-Diving preserves three distinct source roles and Human Review authority.
qdiving_text = " ".join(gap["requirement"] for gap in candidates[40]["missing_evidence"])
assert "Human Review" in qdiving_text
assert {source for gap in candidates[40]["missing_evidence"] for source in gap["target_sources"]} == {
    "SSI Blog", "Scubadoo Koh Tao", "Aquamaster Thailand"
}

# ERP17: score arithmetic is exact for every candidate.
for item in candidates.values():
    expected_points = sum(
        item["scores"][criterion] * weight
        for criterion, weight in EXPECTED_WEIGHTS.items()
    )
    assert item["weighted_points"] == expected_points
    assert item["normalized_score"] == expected_points / 100
rejects(lambda item: item["candidates"][0].update(weighted_points=999), "bad arithmetic validated")

# ERP18: scores are integer 0-5 values only.
assert all(
    isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 5
    for item in candidates.values() for score in item["scores"].values()
)
rejects(
    lambda item: item["candidates"][0]["scores"].update(expected_learning_gain=4.5),
    "fractional score validated",
)

# ERP19: all score decisions have criterion-specific evidence rationale.
assert all(set(item["score_rationale"]) == set(EXPECTED_WEIGHTS) for item in candidates.values())

# ERP20: deterministic totals rank Coffee first, Q-Diving second, Marketplace third.
assert [(item["pr_number"], item["normalized_score"], item["rank"]) for item in sorted(candidates.values(), key=lambda value: value["rank"])] == [
    (39, 4.5, 1), (40, 4.3, 2), (37, 3.7, 3)
]
rejects(lambda item: item["candidates"][0].update(rank=1), "invalid rank validated")

# ERP21: exactly one first rerun is recommended and it is PR #39.
recommendation = artifact["recommendation"]
assert recommendation["recommended_candidate_id"] == "KU2D-ERP-PR39"
assert recommendation["recommended_pr_number"] == 39
rejects(
    lambda item: item["recommendation"].update(recommended_pr_number=40),
    "non-winner recommendation validated",
)

# ERP22: the recommendation is never execution authority or automatic follow-on.
assert recommendation["recommendation_is_execution_authority"] is False
assert recommendation["separate_human_authorization_required_before_rerun"] is True
assert recommendation["automatic_follow_on"] is False
rejects(
    lambda item: item["recommendation"].update(recommendation_is_execution_authority=True),
    "execution authority validated",
)

# ERP23: both waiting candidates explain delay and evidence that could change ranking.
assert candidates[39]["wait_reason"] is None
for number in (37, 40):
    assert candidates[number]["wait_reason"]
    assert candidates[number]["ranking_change_evidence"]

# ERP24: the stated Q-Diving effort change would deterministically change the ranking.
q_scores = dict(candidates[40]["scores"], effort_cost=5)
q_points = sum(q_scores[name] * weight for name, weight in EXPECTED_WEIGHTS.items())
assert q_points == 460 and q_points > candidates[39]["weighted_points"]

# ERP25: no candidate can authorize its own rerun.
assert all(item["rerun_execution_authorized"] is False for item in candidates.values())
rejects(
    lambda item: item["candidates"][1].update(rerun_execution_authorized=True),
    "candidate rerun authority validated",
)

# ERP26: all planning/runtime/knowledge/security boundaries remain exact.
assert artifact["boundaries"] == EXPECTED_BOUNDARIES
rejects(lambda item: item["boundaries"].update(live_request_count=1), "live request validated")
rejects(lambda item: item["boundaries"].update(core_knowledge_write=True), "knowledge write validated")

# ERP27: executable/mutating fields are rejected anywhere in the artifact.
rejects(lambda item: item.update(execute_rerun=True), "executable field validated")
rejects(lambda item: item["recommendation"].update(close_pr=39), "PR action validated")

# ERP28: duplicate or out-of-scope gap mappings fail closed.
rejects(
    lambda item: item["candidates"][0]["missing_evidence"].append(
        deepcopy(item["candidates"][0]["missing_evidence"][0])
    ),
    "duplicate gap validated",
)
rejects(
    lambda item: item["candidates"][0]["missing_evidence"][0]["claim_ids"].append("KU2D-PCR-000029"),
    "cross-PR claim mapping validated",
)

# ERP29: governance provenance matches the exact parked branches and heads.
governance_by_pr = {
    item["pr"]["number"]: item for item in governance["branches"]
    if item["pr"]["number"] in EXPECTED_PRS
}
assert set(governance_by_pr) == set(EXPECTED_PRS)
for number, item in candidates.items():
    assert governance_by_pr[number]["branch"] == item["branch"]
    assert governance_by_pr[number]["head_sha"] == item["head_sha"]
    assert governance_by_pr[number]["pr"] == {
        "number": number,
        "state": "open",
        "draft": True,
        "merged": False,
        "base": "integration/data-acquisition-platform",
    }

# ERP30: validation is planning-only and creates no broader production ranking.
assert artifact["boundaries"]["broader_recommendation_or_ranking"] is False
assert artifact["boundaries"]["production_authorized"] is False
assert artifact["boundaries"]["scheduler_action"] is None

print("Evidence Recovery Prioritization deterministic tests passed (ERP1-ERP30).")
