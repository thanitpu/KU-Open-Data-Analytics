"""Opt-in Learning Record exporters for sanitized Lazada Deep Audit evidence.

Nothing imports this adapter from the acquisition runtime. Callers explicitly
select deterministic evidence to serialize; no records are stored automatically.
"""
from __future__ import annotations

from typing import Any

from acquisition_learning_record import build_learning_record
from lazada_rendered_dom_audit import PLATFORM, SCHEMA as AUDIT_SCHEMA


def _outcome(*, usable_evidence: bool = True, stable_identity: bool = True) -> dict[str, Any]:
    return {
        "technical_completion": True,
        "usable_evidence": usable_evidence,
        "challenge_reached": False,
        "authentication_required": False,
        "stable_identity_available": stable_identity,
        "production_approved": False,
        "production_store": False,
        "scheduler_action": None,
    }


def _provenance() -> dict[str, Any]:
    return {
        "source_schema": AUDIT_SCHEMA,
        "extractor_schema": AUDIT_SCHEMA,
        "commit_reference": None,
        "evidence_origin": "sanitized-deterministic-fixture",
        "reviewed_status": "deterministic-not-human-reviewed",
        "reviewer_provenance": None,
    }


def _identity(surface_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": "Commerce Market Observation",
        "source_id": PLATFORM,
        "platform": PLATFORM,
        "source_type": "public-marketplace",
        "surface_type": surface_record.get("surface_type"),
    }


def _context(surface_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_surface": surface_record.get("source_surface"),
        "query_or_category": surface_record.get("query_or_category"),
        "observed_at": surface_record.get("observed_at"),
        "execution_environment": None,
        "access_class": "public-rendered-evidence",
        "public_access": True,
        "authentication_required": False,
    }


def _technique() -> dict[str, Any]:
    return {
        "technique_id": "lazada_rendered_dom_deep_audit",
        "acquisition_mode": "rendered_dom",
        "technique_version": AUDIT_SCHEMA,
    }


def lazada_price_learning_record(
    surface_record: dict[str, Any], price_observation: dict[str, Any], *,
    learning_record_id: str, generated_at: str,
) -> dict[str, Any]:
    role = str(price_observation.get("price_role") or "unknown")
    current_available = surface_record.get("price", {}).get("current_price") is not None
    return build_learning_record(
        learning_record_id=learning_record_id,
        generated_at=generated_at,
        identity=_identity(surface_record),
        observation_context=_context(surface_record),
        technique=_technique(),
        observed_evidence={
            "evidence_type": "public_price_display",
            "raw_public_display_text": price_observation.get("observed_price_raw"),
            "normalized_amount": price_observation.get("observed_price"),
            "explicit_currency": price_observation.get("explicit_currency"),
            "visible_cue": price_observation.get("visible_label_or_cue"),
            "product_identity": surface_record.get("platform_product_id"),
            "explicit_variant_identity": surface_record.get("variant_identity"),
            "shop_id": surface_record.get("shop_id"),
            "seller_id": surface_record.get("seller_id"),
            "surface_position": surface_record.get("observed_display_position"),
            "structured_provenance_reference": price_observation.get("provenance"),
        },
        semantic_labels={
            "price_role": role,
            "conditional": bool(price_observation.get("conditional")),
            "variant_equivalence_status": price_observation.get("variant_equivalence_status") or "unknown",
            "compatibility_current_price_available": current_available,
            "canonical_price_asserted": False,
            "canonical_price": None,
        },
        acquisition_outcome=_outcome(stable_identity=bool(surface_record.get("platform_product_id"))),
        decision={
            "decision_type": "price_semantics",
            "system_suggestion": None,
            "final_decision": role,
            "reason_code": f"explicit_or_conservative_price_role:{role}",
            "explanation": "A deterministic reviewed rule classified sanitized public display evidence.",
            "evidence_references": ["observed_evidence"],
            "decision_source": "deterministic_rule",
        },
        provenance=_provenance(),
    )


def lazada_correlation_learning_record(
    comparison: dict[str, Any], *, source_surface: str, observed_at: str,
    learning_record_id: str, generated_at: str,
) -> dict[str, Any]:
    stub = {
        "surface_type": "keyword-search-to-product-detail",
        "source_surface": source_surface,
        "query_or_category": "cross-surface-correlation",
        "observed_at": observed_at,
    }
    relation = comparison.get("price_relation") or "unknown"
    return build_learning_record(
        learning_record_id=learning_record_id, generated_at=generated_at,
        identity=_identity(stub), observation_context=_context(stub), technique=_technique(),
        observed_evidence={
            "evidence_type": "cross_surface_price_comparison",
            "product_identity": comparison.get("platform_product_id"),
            "search_observed_amount": comparison.get("search_comparison_price"),
            "detail_observed_amount": comparison.get("detail_comparison_price"),
            "variant_evidence": comparison.get("variant_equivalence_evidence") or [],
        },
        semantic_labels={
            "price_relation": relation,
            "search_price_role": comparison.get("search_comparison_price_role"),
            "detail_price_role": comparison.get("detail_comparison_price_role"),
            "variant_equivalence_status": comparison.get("variant_equivalence_status") or "unknown",
            "canonical_price_asserted": bool(comparison.get("canonical_price_asserted")),
            "canonical_price": comparison.get("canonical_price"),
        },
        acquisition_outcome=_outcome(stable_identity=bool(comparison.get("same_product_identity"))),
        decision={
            "decision_type": "cross_surface_price_relation",
            "system_suggestion": None,
            "final_decision": relation,
            "reason_code": relation,
            "explanation": comparison.get("comparison_reason"),
            "evidence_references": ["observed_evidence"],
            "decision_source": "deterministic_rule",
        },
        provenance=_provenance(),
    )


def lazada_counter_learning_record(
    surface_record: dict[str, Any], *, learning_record_id: str, generated_at: str,
) -> dict[str, Any]:
    counter = surface_record.get("counter") or {}
    counter_type = counter.get("counter_type") or "unknown"
    return build_learning_record(
        learning_record_id=learning_record_id, generated_at=generated_at,
        identity=_identity(surface_record), observation_context=_context(surface_record), technique=_technique(),
        observed_evidence={
            "evidence_type": "public_counter_display",
            "raw_public_display_text": counter.get("raw_display"),
            "safe_numeric_parse": counter.get("numeric_parse"),
            "precision": counter.get("precision"),
            "product_identity": surface_record.get("platform_product_id"),
            "surface_position": surface_record.get("observed_display_position"),
        },
        semantic_labels={
            "counter_type": counter_type,
            "eligible_for_sales_velocity": bool(counter.get("eligible_for_sales_velocity")),
        },
        acquisition_outcome=_outcome(stable_identity=bool(surface_record.get("platform_product_id"))),
        decision={
            "decision_type": "counter_semantics",
            "system_suggestion": None,
            "final_decision": counter_type,
            "reason_code": "explicit_counter_label" if counter_type != "unknown" else "missing_explicit_counter_label",
            "explanation": "Only an explicit sold or order label determines counter semantics.",
            "evidence_references": ["observed_evidence"],
            "decision_source": "deterministic_rule",
        },
        provenance=_provenance(),
    )


def lazada_rating_learning_record(
    surface_record: dict[str, Any], *, learning_record_id: str, generated_at: str,
) -> dict[str, Any]:
    rating = surface_record.get("rating_review") or {}
    classification = rating.get("unlabeled_parenthetical_count_classification") or "unknown"
    return build_learning_record(
        learning_record_id=learning_record_id, generated_at=generated_at,
        identity=_identity(surface_record), observation_context=_context(surface_record), technique=_technique(),
        observed_evidence={
            "evidence_type": "public_parenthetical_display",
            "raw_public_display_text": rating.get("unlabeled_parenthetical_count_raw"),
            "product_identity": surface_record.get("platform_product_id"),
        },
        semantic_labels={"review_rating_semantics": classification},
        acquisition_outcome=_outcome(stable_identity=bool(surface_record.get("platform_product_id"))),
        decision={
            "decision_type": "review_rating_semantics",
            "system_suggestion": None,
            "final_decision": classification,
            "reason_code": "missing_explicit_review_or_rating_label",
            "explanation": "An unlabeled parenthetical count is not promoted to a review count.",
            "evidence_references": ["observed_evidence"],
            "decision_source": "deterministic_rule",
        },
        provenance=_provenance(),
    )
