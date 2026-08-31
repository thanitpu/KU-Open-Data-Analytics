"""Deterministic tests for KU2D Learning Memory v1."""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT / "tools"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from acquisition_learning_memory import (
    assess_ml_dataset_eligibility,
    build_decision_trace,
    build_ground_truth_record,
    build_human_confirmation_record,
    build_review_feedback_record,
    serialize_ground_truth_record,
    serialize_human_confirmation_record,
    serialize_record_json,
    serialize_review_feedback_record,
    validate_ground_truth_record,
    validate_human_confirmation_record,
    validate_learning_memory_bundle,
    validate_review_feedback_record,
)
from acquisition_learning_record import build_learning_record


LEARNING_ID = "lazada-l10-unknown-counter"
REVIEWED_AT = "2026-08-31T04:00:00+00:00"


def learning_record(record_id=LEARNING_ID, final_decision="unknown", system_suggestion=None, usable=True):
    return build_learning_record(
        learning_record_id=record_id, generated_at="2026-08-31T03:00:00+00:00",
        identity={
            "domain": "Commerce Market Observation", "source_id": "lazada-thailand",
            "platform": "lazada-thailand", "source_type": "public-marketplace",
            "surface_type": "keyword-search",
        },
        observation_context={
            "source_surface": "https://www.lazada.co.th/tag/fixture/",
            "observed_at": "2026-08-31T02:00:00+00:00", "public_access": True,
        },
        technique={
            "technique_id": "lazada_rendered_dom_deep_audit",
            "acquisition_mode": "rendered_dom", "technique_version": "v2",
        },
        observed_evidence={
            "evidence_type": "public_counter_display", "raw_public_display_text": "5.5K ชิ้น",
        },
        semantic_labels={"counter_type": final_decision},
        acquisition_outcome={
            "technical_completion": True, "usable_evidence": usable,
            "production_approved": False, "production_store": False, "scheduler_action": None,
        },
        decision={
            "decision_type": "counter_semantics", "system_suggestion": system_suggestion,
            "final_decision": final_decision, "reason_code": "missing_explicit_counter_label",
            "explanation": "Sanitized deterministic evidence.",
            "evidence_references": ["observed_evidence"], "decision_source": "deterministic_rule",
        },
        provenance={
            "source_schema": "ku2d.lazada-rendered-dom-deep-audit.v2",
            "extractor_schema": "ku2d.lazada-rendered-dom-deep-audit.v2",
            "evidence_origin": "sanitized-deterministic-fixture",
            "reviewed_status": "deterministic-not-human-reviewed", "reviewer_provenance": None,
        },
    )


# LM1: a valid accepted review preserves the system proposal.
accepted = build_review_feedback_record(
    review_record_id="review-accepted-counter", reviewed_at=REVIEWED_AT,
    learning_record_id=LEARNING_ID, actor_type="deterministic_validation", actor_id="counter-rule-v1",
    review_result="accepted", system_suggestion="unknown", reviewed_suggestion="unknown",
    proposed_final_decision="unknown", reason_code="missing_explicit_counter_label",
    explanation="The public counter has no explicit sold or order label.",
    evidence_references=["observed_evidence.raw_public_display_text"],
)
assert validate_review_feedback_record(accepted) is accepted

# LM2: correction history keeps both original and reviewed interpretations.
corrected = build_review_feedback_record(
    review_record_id="review-corrected-counter", reviewed_at=REVIEWED_AT,
    learning_record_id=LEARNING_ID, actor_type="assistant_review", actor_id="codex-review",
    review_result="corrected", system_suggestion="sold", reviewed_suggestion="unknown",
    proposed_final_decision="unknown", reason_code="missing_explicit_sold_label",
    explanation="Bare ชิ้น does not establish sold semantics.",
    evidence_references=["observed_evidence.raw_public_display_text"],
)
assert corrected["proposal"] == {"system_suggestion": "sold", "reviewed_suggestion": "unknown"}

# LM3: assistant authority cannot be relabeled as Human Review.
fabricated_assistant = deepcopy(corrected)
fabricated_assistant["review_actor"]["authority_level"] = "human_reviewed"
try:
    validate_review_feedback_record(fabricated_assistant)
    raise AssertionError("assistant review masqueraded as Human Review")
except ValueError:
    pass

# LM4: explicit Human Confirmation validates independently of review feedback.
confirmation = build_human_confirmation_record(
    confirmation_record_id="confirmation-counter-unknown", learning_record_id=LEARNING_ID,
    review_record_id=corrected["review_record_id"], confirmation_status="confirmed",
    confirmed_decision="unknown", reason_note="Confirmed from the preserved public label.",
    confirmed_by="ku2d-human-reviewer", confirmed_at="2026-08-31T04:10:00+00:00",
)
assert validate_human_confirmation_record(confirmation) is confirmation

# LM5: fabricated Human Confirmation provenance fails closed.
fabricated_confirmation = deepcopy(confirmation)
fabricated_confirmation["provenance"]["confirmation_source"] = "assistant_generated"
try:
    validate_human_confirmation_record(fabricated_confirmation)
    raise AssertionError("fabricated human provenance validated")
except ValueError:
    pass

# LM6: deterministic-only evidence may create a Ground Truth candidate.
learning = learning_record()
candidate = build_ground_truth_record(
    ground_truth_record_id="ground-counter-candidate", learning_record_id=LEARNING_ID,
    final_label="unknown", status="candidate", confidence="rule-supported",
    authority_basis="deterministic_rule", supporting_review_record_ids=[],
    supporting_human_confirmation_record_ids=[], effective_at="2026-08-31T04:05:00+00:00",
)
bundle_candidate = validate_learning_memory_bundle([learning], [accepted], [], [candidate])
assert bundle_candidate["active_ground_truth_by_learning_record_id"][LEARNING_ID][0] is candidate

# LM7: a human_confirmed claim fails without a genuine matching confirmation.
unproven_human_ground = build_ground_truth_record(
    ground_truth_record_id="ground-unproven-human", learning_record_id=LEARNING_ID,
    final_label="unknown", status="human_confirmed", confidence="claimed",
    authority_basis="human_confirmation", supporting_review_record_ids=[corrected["review_record_id"]],
    supporting_human_confirmation_record_ids=["confirmation-does-not-exist"],
    effective_at="2026-08-31T04:11:00+00:00",
)
try:
    validate_learning_memory_bundle([learning], [corrected], [], [unproven_human_ground])
    raise AssertionError("human_confirmed Ground Truth lacked confirmation")
except ValueError:
    pass

# LM8: a new Ground Truth supersedes rather than mutates the prior candidate.
ground_human = build_ground_truth_record(
    ground_truth_record_id="ground-counter-human", learning_record_id=LEARNING_ID,
    final_label="unknown", status="human_confirmed", confidence="human-confirmed",
    authority_basis="explicit_human_confirmation",
    supporting_review_record_ids=[corrected["review_record_id"]],
    supporting_human_confirmation_record_ids=[confirmation["confirmation_record_id"]],
    supersedes_ground_truth_record_id=candidate["ground_truth_record_id"],
    effective_at="2026-08-31T04:12:00+00:00",
)
bundle_human = validate_learning_memory_bundle(
    [learning], [corrected], [confirmation], [candidate, ground_human],
)
assert candidate["status"] == "candidate"
assert bundle_human["superseded_ground_truth_record_ids"] == [candidate["ground_truth_record_id"]]
assert bundle_human["active_ground_truth_by_learning_record_id"][LEARNING_ID] == [ground_human]
trace = build_decision_trace(
    LEARNING_ID, learning_records=[learning], review_records=[corrected],
    confirmation_records=[confirmation], ground_truth_records=[candidate, ground_human],
)
assert trace["initial_system_suggestion"] == "sold"
assert trace["current_authoritative_label"] == "unknown"
assert trace["human_involved"] is True and trace["has_been_superseded"] is True

# LM9: contradictory active labels fail bundle validation.
contradictory_a = build_ground_truth_record(
    ground_truth_record_id="ground-active-unknown", learning_record_id=LEARNING_ID,
    final_label="unknown", status="candidate", confidence="candidate",
    authority_basis="deterministic_rule", supporting_review_record_ids=[],
    supporting_human_confirmation_record_ids=[], effective_at="2026-08-31T04:20:00+00:00",
)
contradictory_b = build_ground_truth_record(
    ground_truth_record_id="ground-active-sold", learning_record_id=LEARNING_ID,
    final_label="sold", status="candidate", confidence="candidate",
    authority_basis="deterministic_rule", supporting_review_record_ids=[],
    supporting_human_confirmation_record_ids=[], effective_at="2026-08-31T04:21:00+00:00",
)
try:
    validate_learning_memory_bundle([learning], [], [], [contradictory_a, contradictory_b])
    raise AssertionError("contradictory active Ground Truth validated")
except ValueError:
    pass

# LM10: unknown/unresolved is an allowed final Ground Truth label.
unknown_ground = build_ground_truth_record(
    ground_truth_record_id="ground-unknown-valid", learning_record_id=LEARNING_ID,
    final_label="unknown", status="deterministic_confirmed", confidence="rule-confirmed",
    authority_basis="deterministic_rule", supporting_review_record_ids=[],
    supporting_human_confirmation_record_ids=[], effective_at="2026-08-31T04:22:00+00:00",
)
assert validate_ground_truth_record(unknown_ground)["final_label"] == "unknown"

# LM11: a failed/negative acquisition outcome remains valid learning evidence.
negative_learning = learning_record("negative-application-shell", "application-shell-only", usable=False)
assert validate_learning_memory_bundle([negative_learning], [], [], [])["learning_records"]

# LM12: sensitive material fails validation and is excluded from eligibility.
sensitive_learning = deepcopy(learning)
sensitive_learning["observed_evidence"]["cookie"] = "prohibited"
try:
    validate_learning_memory_bundle([sensitive_learning], [], [], [])
    raise AssertionError("sensitive learning bundle validated")
except ValueError:
    pass
assert assess_ml_dataset_eligibility(
    LEARNING_ID, learning_records=[sensitive_learning], review_records=[],
    confirmation_records=[], ground_truth_records=[],
)["state"] == "excluded"

# LM13: orphan Review Feedback fails referential integrity.
orphan_review = deepcopy(accepted)
orphan_review["target"]["learning_record_id"] = "missing-learning"
try:
    validate_learning_memory_bundle([learning], [orphan_review], [], [])
    raise AssertionError("orphan review validated")
except ValueError:
    pass

# LM14: orphan Human Confirmation references fail.
orphan_confirmation = deepcopy(confirmation)
orphan_confirmation["review_record_id"] = "missing-review"
try:
    validate_learning_memory_bundle([learning], [corrected], [orphan_confirmation], [])
    raise AssertionError("orphan confirmation validated")
except ValueError:
    pass

# LM15: self-superseding Ground Truth fails at record validation.
try:
    build_ground_truth_record(
        ground_truth_record_id="ground-self", learning_record_id=LEARNING_ID,
        final_label="unknown", status="candidate", confidence="candidate",
        authority_basis="deterministic_rule", supporting_review_record_ids=[],
        supporting_human_confirmation_record_ids=[], supersedes_ground_truth_record_id="ground-self",
        effective_at="2026-08-31T04:30:00+00:00",
    )
    raise AssertionError("self-superseding Ground Truth validated")
except ValueError:
    pass

# LM16: all record types serialize deterministically and without mutation.
assert serialize_review_feedback_record(corrected) == serialize_review_feedback_record(deepcopy(corrected))
assert serialize_human_confirmation_record(confirmation) == serialize_human_confirmation_record(deepcopy(confirmation))
assert serialize_ground_truth_record(ground_human) == serialize_ground_truth_record(deepcopy(ground_human))
assert serialize_record_json(corrected, validate_review_feedback_record) == serialize_record_json(
    deepcopy(corrected), validate_review_feedback_record,
)

# LM17/LM18/LM19: eligibility respects authority and contradictions.
assert assess_ml_dataset_eligibility(
    LEARNING_ID, learning_records=[learning], review_records=[corrected],
    confirmation_records=[], ground_truth_records=[],
)["state"] == "review_required"
assert assess_ml_dataset_eligibility(
    LEARNING_ID, learning_records=[learning], review_records=[corrected],
    confirmation_records=[confirmation], ground_truth_records=[candidate, ground_human],
)["state"] == "human_confirmed"
assert assess_ml_dataset_eligibility(
    LEARNING_ID, learning_records=[learning], review_records=[], confirmation_records=[],
    ground_truth_records=[contradictory_a, contradictory_b],
)["state"] == "ineligible"

print("Acquisition Learning Memory deterministic tests passed (LM1-LM19).")
