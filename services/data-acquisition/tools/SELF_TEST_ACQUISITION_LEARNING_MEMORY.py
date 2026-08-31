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
    build_human_confirmation_record,
    build_review_feedback_record,
    validate_human_confirmation_record,
    validate_review_feedback_record,
)


LEARNING_ID = "lazada-l10-unknown-counter"
REVIEWED_AT = "2026-08-31T04:00:00+00:00"


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

print("Acquisition Learning Memory deterministic tests passed (LM1-LM5).")
