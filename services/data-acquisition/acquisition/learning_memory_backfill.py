"""Opt-in builders for a small sanitized KU2D Learning Memory backfill."""
from __future__ import annotations

from typing import Any

from acquisition_learning_memory import (
    build_ground_truth_record,
    build_review_feedback_record,
    validate_learning_memory_bundle,
)
from acquisition_learning_record import build_learning_record
from lazada_audit_learning import (
    lazada_correlation_learning_record,
    lazada_counter_learning_record,
    lazada_price_learning_record,
)
from lazada_rendered_dom_audit import audit_surface, correlate_search_detail, counter_evidence, price_evidence


BACKFILL_SOURCE_SCHEMA = "ku2d.learning-memory-backfill-source.v1"
BUNDLE_SCHEMA = "ku2d.learning-memory-bundle.v1"
OBSERVED_AT = "2026-08-31T02:00:00+00:00"


def _surface_record(surface_type: str, *, price=None, counter=None) -> dict[str, Any]:
    return {
        "platform_product_id": "100001", "surface_type": surface_type,
        "source_surface": f"https://www.lazada.co.th/{surface_type}/fixture/",
        "query_or_category": "sanitized-backfill", "observed_at": OBSERVED_AT,
        "observed_display_position": 1, "variant_identity": None,
        "shop_id": None, "seller_id": None, "price": price or {}, "counter": counter or {},
    }


def _audited_price_record(surface_type: str, price_text: str) -> dict[str, Any]:
    entry = {
        "context": {
            "surface_type": surface_type, "query_or_category": "sanitized-backfill",
            "sort_mode": "default", "sort_semantics_explicit": False,
        },
        "capture": {
            "observed_at": OBSERVED_AT,
            "initial_url": f"https://www.lazada.co.th/{surface_type}/fixture/",
            "final_url": f"https://www.lazada.co.th/{surface_type}/fixture/",
            "visible_page_text": "Sanitized public fixture", "visible_product_card_count": 1,
            "visible_cards": [{
                "product_url": "https://www.lazada.co.th/products/fixture-i100001.html",
                "explicit_product_id": "100001", "visible_title": "Sanitized Fixture",
                "current_price_text": price_text, "visible_text": f"Sanitized Fixture {price_text}",
            }],
            "network_requests": [],
        },
    }
    return audit_surface(entry)["records"][0]


def _youtube_learning(case: dict[str, Any], generated_at: str) -> dict[str, Any]:
    label = case["expected_label"]
    return build_learning_record(
        learning_record_id=f"backfill-{case['case_id']}", generated_at=generated_at,
        identity={
            "domain": "q_diving", "source_id": "youtube", "platform": "youtube",
            "source_type": "official-api-public-metadata", "surface_type": "video-metadata",
        },
        observation_context={
            "source_surface": case["video_url"], "observed_at": case["observed_at"],
            "execution_environment": None, "access_class": "official-api-public-metadata",
            "public_access": True, "authentication_required": False,
        },
        technique={
            "technique_id": "youtube_data_api_v3_metadata", "acquisition_mode": "official_api",
            "technique_version": "ku2d.youtube-source-foundation-result.v1",
        },
        observed_evidence={
            "evidence_type": "public_video_metadata", "video_id": case["video_id"],
            "title": case["title"], "description": case["description"],
        },
        semantic_labels={"relevance": label},
        acquisition_outcome={
            "technical_completion": True, "usable_evidence": True,
            "production_approved": False, "production_store": False, "scheduler_action": None,
        },
        decision={
            "decision_type": "youtube_relevance", "system_suggestion": label,
            "final_decision": label, "reason_code": "sanitized_deterministic_fixture",
            "explanation": "Deterministic synthetic backfill; no Human Review is claimed.",
            "evidence_references": ["observed_evidence"], "decision_source": "deterministic_rule",
        },
        provenance={
            "source_schema": "ku2d.youtube-source-foundation-result.v1",
            "extractor_schema": "ku2d.youtube-human-review-package.v1",
            "evidence_origin": "fixtures/youtube_human_review/sanitized_foundation_result.json",
            "reviewed_status": case["review_provenance"], "reviewer_provenance": None,
        },
    )


def _negative_learning(case: dict[str, Any], generated_at: str) -> dict[str, Any]:
    return build_learning_record(
        learning_record_id=f"backfill-{case['case_id']}", generated_at=generated_at,
        identity={
            "domain": "Commerce Market Observation", "source_id": "lazada-thailand",
            "platform": "lazada-thailand", "source_type": "public-marketplace",
            "surface_type": "keyword-search",
        },
        observation_context={
            "source_surface": case["source_surface"], "observed_at": case["observed_at"],
            "execution_environment": None, "access_class": "public-challenge-boundary",
            "public_access": True, "authentication_required": False,
        },
        technique={
            "technique_id": "lazada_browser_access_diagnostic", "acquisition_mode": "rendered_dom",
            "technique_version": "ku2d.lazada-browser-access-diagnostic.v1",
        },
        observed_evidence={
            "evidence_type": "negative_acquisition_outcome",
            "public_display_text": case["public_display_text"], "failure_class": case["expected_label"],
        },
        semantic_labels={"acquisition_result": case["expected_label"]},
        acquisition_outcome={
            "technical_completion": True, "usable_evidence": False, "challenge_reached": True,
            "production_approved": False, "production_store": False, "scheduler_action": None,
        },
        decision={
            "decision_type": "acquisition_outcome", "system_suggestion": None,
            "final_decision": case["expected_label"], "reason_code": "challenge_stop_boundary",
            "explanation": "Existing sanitized challenge fixture; no circumvention occurred.",
            "evidence_references": ["observed_evidence"], "decision_source": "deterministic_rule",
        },
        provenance={
            "source_schema": "ku2d.lazada-browser-access-diagnostic.v1",
            "extractor_schema": "ku2d.lazada-browser-access-diagnostic.v1",
            "evidence_origin": case["source_fixture"],
            "reviewed_status": "deterministic-not-human-reviewed", "reviewer_provenance": None,
        },
    )


def build_sanitized_historical_bundle(source: dict[str, Any]) -> dict[str, Any]:
    """Build an explicit in-memory bundle; never write or mutate runtime state."""
    if source.get("schema") != BACKFILL_SOURCE_SCHEMA:
        raise ValueError(f"Expected {BACKFILL_SOURCE_SCHEMA}")
    generated_at = str(source.get("generated_at") or "")
    if not generated_at:
        raise ValueError("Backfill generated_at is required")
    learning_records: list[dict[str, Any]] = []

    for case in source.get("lazada_price_cases") or []:
        price = price_evidence(
            case["input"], price_surface=case["surface_type"],
            source_surface=f"https://www.lazada.co.th/{case['surface_type']}/fixture/",
            observed_at=OBSERVED_AT, platform_product_id="100001",
        )
        observation = price["price_observations"][0]
        if observation["price_role"] != case["expected_label"]:
            raise ValueError(f"Backfill label mismatch: {case['case_id']}")
        learning_records.append(lazada_price_learning_record(
            _surface_record(case["surface_type"], price=price), observation,
            learning_record_id=f"backfill-lazada-{case['case_id']}", generated_at=generated_at,
        ))

    correlation_case = source["lazada_price_correlation"]
    search = _audited_price_record("keyword-search", correlation_case["search_price_text"])
    detail = _audited_price_record("product-detail", correlation_case["detail_price_text"])
    comparison = correlate_search_detail(search, detail)
    if comparison["price_relation"] != correlation_case["expected_label"]:
        raise ValueError("Backfill correlation label mismatch")
    learning_records.append(lazada_correlation_learning_record(
        comparison, source_surface=search["source_surface"], observed_at=search["observed_at"],
        learning_record_id=f"backfill-lazada-{correlation_case['case_id']}", generated_at=generated_at,
    ))

    for case in source.get("lazada_counter_cases") or []:
        counter = counter_evidence({"counter_text": case["counter_text"]})
        if counter["counter_type"] != case["expected_label"]:
            raise ValueError(f"Backfill counter label mismatch: {case['case_id']}")
        learning_records.append(lazada_counter_learning_record(
            _surface_record("keyword-search", counter=counter),
            learning_record_id=f"backfill-lazada-{case['case_id']}", generated_at=generated_at,
        ))

    learning_records.extend(_youtube_learning(case, generated_at) for case in source.get("youtube_cases") or [])
    learning_records.append(_negative_learning(source["negative_case"], generated_at))

    review_records, ground_truth_records = [], []
    for learning in learning_records:
        learning_id = learning["learning_record_id"]
        final_label = learning["decision"]["final_decision"]
        review = build_review_feedback_record(
            review_record_id=f"review-{learning_id}", reviewed_at=generated_at,
            learning_record_id=learning_id, actor_type="deterministic_validation",
            actor_id="historical-backfill-validator-v1", review_result="accepted",
            system_suggestion=final_label, reviewed_suggestion=final_label,
            proposed_final_decision=final_label, reason_code="historical_fixture_rule_confirmed",
            explanation="Existing sanitized deterministic evidence was replayed without live access.",
            evidence_references=["observed_evidence"],
            source_domain=learning["identity"]["domain"], source_reference=learning["provenance"]["evidence_origin"],
        )
        review_records.append(review)
        ground_truth_records.append(build_ground_truth_record(
            ground_truth_record_id=f"ground-{learning_id}", learning_record_id=learning_id,
            final_label=final_label, status="deterministic_confirmed", confidence="rule-confirmed",
            authority_basis="deterministic_validation",
            supporting_review_record_ids=[review["review_record_id"]],
            supporting_human_confirmation_record_ids=[], effective_at=generated_at,
            source_reference=learning["provenance"]["evidence_origin"],
        ))

    bundle = {
        "schema": BUNDLE_SCHEMA, "generated_at": generated_at,
        "learning_records": learning_records, "review_records": review_records,
        "confirmation_records": [], "ground_truth_records": ground_truth_records,
        "production_approved": False, "production_store": False, "scheduler_action": None,
    }
    validate_learning_memory_bundle(
        bundle["learning_records"], bundle["review_records"],
        bundle["confirmation_records"], bundle["ground_truth_records"],
    )
    return bundle
