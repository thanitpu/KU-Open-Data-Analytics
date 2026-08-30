"""Deterministic checks for YouTube Human Review, monitoring, and KU2A handoff."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "acquisition", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from youtube_human_review import (
    CONTENT_ROLES,
    EQUIPMENT_VOCABULARY,
    YouTubeChannelReview,
    YouTubeVideoReview,
    create_knowledge_dataset,
    create_monitoring_plan,
    prepare_review_package,
    suggest_channel_class,
    suggest_commercial_context,
    suggest_relevance,
)
from youtube_source_foundation import load_policy, load_query_profiles
from PREPARE_YOUTUBE_HUMAN_REVIEW import main as prepare_main

FIXTURE = ROOT / "fixtures" / "youtube_human_review" / "sanitized_foundation_result.json"
SCHEMA = ROOT / "config" / "youtube_knowledge_dataset_schema.json"
source = json.loads(FIXTURE.read_text(encoding="utf-8"))
source_before = copy.deepcopy(source)
package = prepare_review_package(source)

# A/B: reviews are separate, pending, and blank; automation produces suggestions only.
assert source == source_before
assert package["review_stage"] == "human-review-pending"
assert all(row["review_status"] == "pending" for row in package["video_reviews"])
assert all(row["review_status"] == "pending" for row in package["channel_reviews"])
assert all(row["relevance"] is None and row["knowledge_use"] is None for row in package["video_reviews"])
assert all(row["source_class"] is None and row["monitoring_decision"] is None for row in package["channel_reviews"])
assert all("suggested_relevance" in row["review_suggestions"] for row in package["candidate_videos"])
assert "human_review_status" not in json.dumps(package)

by_video = {row["video_id"]: row for row in package["candidate_videos"]}
by_channel = {row["channel_id"]: row for row in package["candidate_channels"]}

# C/D/E: core, adjacent, and irrelevant screening is deterministic and location aware.
assert by_video["SAN-TH-BEGINNER"]["review_suggestions"]["suggested_relevance"] == "core"
assert by_video["SAN-EN-KOH-TAO"]["review_suggestions"]["suggested_relevance"] == "core"
assert by_video["SAN-FREEDIVING"]["review_suggestions"]["suggested_relevance"] == "adjacent"
assert "not equivalent" in " ".join(by_video["SAN-FREEDIVING"]["review_suggestions"]["suggestion_basis"])
assert by_video["SAN-PHUKET-SCUBA"]["review_suggestions"]["suggested_relevance"] == "adjacent"
assert "Koh Tao" in " ".join(by_video["SAN-PHUKET-SCUBA"]["review_suggestions"]["suggestion_basis"])
assert by_video["SAN-NONDIVING"]["review_suggestions"]["suggested_relevance"] == "irrelevant"
assert by_video["SAN-AFFILIATE-GEAR"]["review_suggestions"]["suggested_relevance"] == "core"
assert {"mask", "bcd", "regulator"}.issubset(
    set(by_video["SAN-AFFILIATE-GEAR"]["review_suggestions"]["suggested_equipment_topics"])
)
assert {
    "mask", "fins", "wetsuit", "bcd", "regulator", "dive_computer", "tank",
    "underwater_camera", "accessory", "maintenance", "rental", "purchase", "fitting_sizing",
} == set(EQUIPMENT_VOCABULARY)
assert "equipment" in CONTENT_ROLES

# F: operator/travel class hints remain distinguishable and explicitly non-authoritative.
operator_hint = by_channel["SAN-DIVE-OPERATOR"]["review_suggestions"]
travel_hint = by_channel["SAN-TRAVEL-CREATOR"]["review_suggestions"]
assert operator_hint["suggested_source_class"] == "dive_operator"
assert travel_hint["suggested_source_class"] == "travel_dive_creator"
assert operator_hint["authoritative"] is False and travel_hint["authoritative"] is False
assert suggest_channel_class({"channel_title":"Unclassified", "channel_description":"General videos"})["suggested_source_class"] == "other"

# G: disclosed commercial text creates evidence-bearing hints; no hidden sponsorship is inferred.
commercial = by_video["SAN-AFFILIATE-GEAR"]["review_suggestions"]
assert commercial["commercial_context_suggestion"] == "affiliate"
assert any(row["matched_cue"] == "affiliate" for row in commercial["commercial_context_evidence"])
assert commercial["hidden_sponsorship_inferred"] is False
assert by_video["SAN-AFFILIATE-GEAR"]["youtube_paid_product_placement"] is False
quiet = suggest_commercial_context({"title":"Scuba skills", "description":"Neutral lesson"})
assert quiet["commercial_context_suggestion"] == "unknown"
assert quiet["commercial_context_evidence"] == [] and quiet["hidden_sponsorship_inferred"] is False
product_promotion = suggest_commercial_context({"title":"New dive mask - buy now", "description":"Available now"})
assert product_promotion["commercial_context_suggestion"] == "promotional_offer"
assert product_promotion["commercial_context_evidence"]

# H/I/J/K: monitoring requires completed channel approval and an uploads playlist; it stays dry.
operator_candidate = by_channel["SAN-DIVE-OPERATOR"]
pending_review = next(row for row in package["channel_reviews"] if row["channel_id"] == "SAN-DIVE-OPERATOR")
for invalid_review, invalid_candidate in (
    (pending_review, operator_candidate),
    ({**pending_review, "review_status":"reviewed", "source_class":"dive_operator",
      "domain_focus":"diving_specialist", "monitoring_decision":"watch",
      "reviewed_by":"reviewer", "reviewed_at":"2026-08-30T00:00:00Z"}, operator_candidate),
    ({**pending_review, "review_status":"reviewed", "source_class":"dive_operator",
      "domain_focus":"diving_specialist", "monitoring_decision":"approve",
      "reviewed_by":"reviewer", "reviewed_at":"2026-08-30T00:00:00Z"},
     {**operator_candidate, "uploads_playlist_id":None}),
):
    try:
        create_monitoring_plan(invalid_review, invalid_candidate)
        raise AssertionError("unsafe monitoring plan accepted")
    except ValueError:
        pass
approved_channel_review = {
    **pending_review,
    "review_status": "reviewed",
    "source_class": "dive_operator",
    "domain_focus": "diving_specialist",
    "monitoring_decision": "approve",
    "reviewer_note": "Sanitized fixture approval.",
    "reviewed_by": "ku2d-reviewer",
    "reviewed_at": "2026-08-30T00:00:00Z",
}
plan = create_monitoring_plan(approved_channel_review, operator_candidate, cadence="weekly")
assert plan["uploads_playlist_id"] == "UU-SAN-DIVE-OPERATOR"
assert plan["production_enabled"] is False and plan["scheduler_action"] is None
assert set(plan) == {
    "channel_id", "uploads_playlist_id", "source_class", "approved_by", "approved_at",
    "cadence", "production_enabled", "scheduler_action",
}

# L: textual amounts are context candidates, never Product & Price acquisition evidence.
mentions = package["price_mention_candidates"]
assert len(mentions) == 1 and mentions[0]["value"] == "299" and mentions[0]["currency"] == "USD"
assert mentions[0]["record_type"] == "PriceMentionCandidate"
assert mentions[0]["stated_by_source"] is True
assert mentions[0]["current_commerce_price_evidence"] is False
assert mentions[0]["product_price_acquisition_record"] is False
assert "ProductCandidate" not in json.dumps(mentions) and "PriceObservation" not in json.dumps(mentions)

# M: completed review can create a provenance-bearing, explicitly non-production KU2A contract.
reviewed_package = copy.deepcopy(package)
video_review = next(row for row in reviewed_package["video_reviews"] if row["video_id"] == "SAN-EN-KOH-TAO")
video_review.update({
    "review_status": "reviewed",
    "relevance": "core",
    "content_roles": ["training", "beginner_experience"],
    "commercial_context": "none",
    "knowledge_use": "include",
    "reviewer_note": "Suitable for research context.",
    "reviewed_by": "ku2d-reviewer",
    "reviewed_at": "2026-08-30T00:00:00Z",
})
channel_review = next(row for row in reviewed_package["channel_reviews"] if row["channel_id"] == "SAN-DIVE-OPERATOR")
channel_review.update(approved_channel_review)
dataset = create_knowledge_dataset(
    reviewed_package,
    dataset_id="QDIVING-YOUTUBE-SANITIZED-001",
    generated_at="2026-08-30T01:00:00Z",
)
assert dataset["schema"] == "ku2d.youtube-knowledge-dataset.v1"
assert dataset["domain"] == "q_diving" and dataset["source_type"] == "youtube"
assert dataset["included_video_ids"] == ["SAN-EN-KOH-TAO"]
assert dataset["included_channel_ids"] == ["SAN-DIVE-OPERATOR"]
assert dataset["research_collections"] == ["learn_to_dive"]
assert dataset["human_review_summary"]["video_reviews_completed"] == 1
assert dataset["provenance_summary"]["provider"] == "youtube-data-api-v3"
assert dataset["provenance_summary"]["human_review_required"] is True
assert dataset["data_refresh_due_at"] == "2026-09-28T09:00:00+00:00"
assert dataset["production_approved"] is False
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
assert schema["properties"]["production_approved"]["const"] is False
assert set(schema["required"]) == set(dataset)

# N/O: transcript text never enters the review package and comments remain disabled.
assert all(row["transcript_text"] is None for row in source["videos"])
assert "transcript_text" not in json.dumps(package)
policy = load_policy()
assert policy["comments_enabled"] is False and policy["comment_threads_enabled"] is False
assert policy["comment_acquisition_enabled"] is False
assert policy["production_scheduling_enabled"] is False
assert "other" in policy["manual_source_classes"]

# Tool contract is deterministic, compact, and does not leak raw responses or credentials.
secret = "SANITIZED-SECRET-MUST-NOT-LEAK"
tool_source = copy.deepcopy(source)
tool_source["api_key"] = secret
tool_source["raw_api_response"] = {"secret": secret}
with tempfile.TemporaryDirectory() as temp_dir:
    input_path = Path(temp_dir) / "foundation.json"
    output_path = Path(temp_dir) / "review.json"
    input_path.write_text(json.dumps(tool_source), encoding="utf-8")
    assert prepare_main(["--input", str(input_path), "--output", str(output_path)]) == 0
    serialized = output_path.read_text(encoding="utf-8")
    staged = json.loads(serialized)
    assert staged == package
    assert secret not in serialized and "raw_api_response" not in serialized
    assert "thumbnail" not in serialized and "transcript_text" not in serialized

# Equipment Pilot #2 is prepared as exactly two existing profiles, but this test makes no API call.
profile_by_id = {row["profile_id"]: row for row in load_query_profiles()}
equipment_ids = ["QYT-EQUIPMENT-BEGINNER-TH", "QYT-EQUIPMENT-SETUP-EN"]
assert all(profile_id in profile_by_id for profile_id in equipment_ids)
assert all(profile_by_id[profile_id]["research_collection"] == "diving_equipment" for profile_id in equipment_ids)

# Model constructors also preserve pending defaults independent of staging.
assert YouTubeVideoReview("VID").review_status == "pending"
assert YouTubeChannelReview("CHAN").monitoring_decision is None

print("YouTube Human Review and knowledge handoff deterministic contracts: PASS")
