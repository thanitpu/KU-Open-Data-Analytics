"""Deterministic tests for the storage-neutral Acquisition Learning Record seed."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT / "tools"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from acquisition_learning_record import (
    SCHEMA,
    build_learning_record,
    serialize_learning_record,
    serialize_learning_record_json,
    validate_learning_record,
)
from lazada_audit_learning import (
    lazada_correlation_learning_record,
    lazada_counter_learning_record,
    lazada_price_learning_record,
    lazada_rating_learning_record,
)
from lazada_rendered_dom_audit import (
    audit_surface,
    correlate_search_detail,
    counter_evidence,
    price_evidence,
    rating_review_evidence,
)


GENERATED_AT = "2026-08-31T03:00:00+00:00"
OBSERVED_AT = "2026-08-31T02:00:00+00:00"


def surface_record(*, price=None, counter=None, rating=None, surface_type="keyword-search"):
    return {
        "platform_product_id": "100001",
        "surface_type": surface_type,
        "source_surface": f"https://www.lazada.co.th/{surface_type}/fixture/",
        "query_or_category": "fixture",
        "observed_at": OBSERVED_AT,
        "observed_display_position": 1,
        "variant_identity": None,
        "shop_id": None,
        "seller_id": None,
        "price": price or {},
        "counter": counter or {},
        "rating_review": rating or {},
    }


def observed_price(row):
    price = price_evidence(
        row, price_surface="keyword-search",
        source_surface="https://www.lazada.co.th/keyword-search/fixture/",
        observed_at=OBSERVED_AT, platform_product_id="100001",
    )
    return surface_record(price=price), price


def price_record(record_id, row, index=0):
    surface, price = observed_price(row)
    return lazada_price_learning_record(
        surface, price["price_observations"][index],
        learning_record_id=record_id, generated_at=GENERATED_AT,
    )


# L1-L8: representative sanitized price semantics are exported as separated
# observed evidence and deterministic labels.
l1_unknown = price_record("lazada-l1-unknown-display", {"visible_price_text": "฿25"})
l2_current = price_record("lazada-l2-current", {"current_price_text": "฿25"})
l3_from = price_record("lazada-l3-from", {"current_price_text": "เริ่มต้น ฿25"})
l4_promotional = price_record("lazada-l4-promotional", {"promotional_price_text": "ราคาพิเศษ ฿49"})
l5_discount = price_record("lazada-l5-discount", {"promotional_price_text": "ลด ฿10"})
l6_voucher = price_record("lazada-l6-voucher", {"voucher_text": "ลดเพิ่ม ฿10"})
l7_member = price_record("lazada-l7-member", {"member_price_text": "สมาชิก ฿39"})
variation_surface, variation_price = observed_price({"variation_price_text": "฿25–฿49"})
l8_variation = [
    lazada_price_learning_record(
        variation_surface, observation,
        learning_record_id=f"lazada-l8-{observation['price_role']}", generated_at=GENERATED_AT,
    )
    for observation in variation_price["price_observations"]
]
assert l1_unknown["semantic_labels"]["price_role"] == "unknown_display_price"
assert l2_current["semantic_labels"]["price_role"] == "current"
assert l3_from["semantic_labels"]["price_role"] == "from_price"
assert l4_promotional["semantic_labels"]["price_role"] == "promotional"
assert l5_discount["semantic_labels"]["price_role"] == "promotional_discount"
assert l6_voucher["semantic_labels"]["price_role"] == "voucher_or_conditional"
assert l7_member["semantic_labels"]["price_role"] == "member_or_account_conditional"
assert [record["semantic_labels"]["price_role"] for record in l8_variation] == ["variation_min", "variation_max"]
assert l2_current["semantic_labels"]["compatibility_current_price_available"] is True
assert all(record["semantic_labels"]["compatibility_current_price_available"] is False for record in (
    l1_unknown, l3_from, l5_discount, l6_voucher, l7_member, *l8_variation,
))


def audited_record(surface_type: str, price_text: str):
    entry = {
        "context": {
            "surface_type": surface_type, "query_or_category": "fixture",
            "sort_mode": "default", "sort_semantics_explicit": False,
        },
        "capture": {
            "observed_at": OBSERVED_AT,
            "initial_url": f"https://www.lazada.co.th/{surface_type}/fixture/",
            "final_url": f"https://www.lazada.co.th/{surface_type}/fixture/",
            "visible_page_text": "Fixture public surface", "visible_product_card_count": 1,
            "visible_cards": [{
                "product_url": "https://www.lazada.co.th/products/fixture-i100001.html",
                "explicit_product_id": "100001", "visible_title": "Fixture",
                "current_price_text": price_text, "visible_text": f"Fixture {price_text}",
            }],
            "network_requests": [],
        },
    }
    return audit_surface(entry)["records"][0]


# L9: unresolved search/detail difference remains a non-canonical learning label.
comparison = correlate_search_detail(
    audited_record("keyword-search", "฿25"), audited_record("product-detail", "฿49"),
)
l9_comparison = lazada_correlation_learning_record(
    comparison, source_surface="https://www.lazada.co.th/keyword-search/fixture/",
    observed_at=OBSERVED_AT, learning_record_id="lazada-l9-different-unresolved",
    generated_at=GENERATED_AT,
)
assert l9_comparison["semantic_labels"]["price_relation"] == "different_unresolved"
assert l9_comparison["semantic_labels"]["variant_equivalence_status"] == "unknown"
assert l9_comparison["semantic_labels"]["canonical_price_asserted"] is False
assert l9_comparison["semantic_labels"]["canonical_price"] is None

# L10/L11: negative and explicit counter semantics both remain available.
unknown_counter_surface = surface_record(counter=counter_evidence({"counter_text": "5.5K ชิ้น"}))
sold_counter_surface = surface_record(counter=counter_evidence({"counter_text": "ขายแล้ว 88 ชิ้น"}))
l10_counter = lazada_counter_learning_record(
    unknown_counter_surface, learning_record_id="lazada-l10-unknown-counter", generated_at=GENERATED_AT,
)
l11_counter = lazada_counter_learning_record(
    sold_counter_surface, learning_record_id="lazada-l11-explicit-sold", generated_at=GENERATED_AT,
)
assert l10_counter["semantic_labels"]["counter_type"] == "unknown"
assert l10_counter["observed_evidence"]["safe_numeric_parse"] == 5500
assert l10_counter["semantic_labels"]["eligible_for_sales_velocity"] is False
assert l11_counter["semantic_labels"]["counter_type"] == "sold"
assert l11_counter["observed_evidence"]["precision"] == "exact"

# L12: an unlabeled parenthetical display remains unknown-not-review.
parenthetical_surface = surface_record(rating=rating_review_evidence({"visible_text": "(714)"}))
l12_rating = lazada_rating_learning_record(
    parenthetical_surface, learning_record_id="lazada-l12-unknown-parenthetical", generated_at=GENERATED_AT,
)
assert l12_rating["semantic_labels"]["review_rating_semantics"] == "unknown-not-review"

# LG1-LG5 are the valid current, unknown, from, unresolved, and unknown-counter
# records above. Every one validates against the generic contract.
for record in (l2_current, l1_unknown, l3_from, l9_comparison, l10_counter):
    assert validate_learning_record(record) is record
    assert record["schema"] == SCHEMA

# LG6/LG7: a sanitized negative outcome and an unknown label are first-class.
negative = build_learning_record(
    learning_record_id="synthetic-negative-application-shell",
    generated_at=GENERATED_AT,
    identity={
        "domain": "Commerce Market Observation", "source_id": "synthetic-public-source",
        "platform": "synthetic-public-source", "source_type": "public-marketplace",
        "surface_type": "keyword-search",
    },
    observation_context={
        "source_surface": "https://example.invalid/public-search", "observed_at": OBSERVED_AT,
        "execution_environment": "cloud-hosted", "access_class": "public-no-auth",
        "public_access": True, "authentication_required": False,
    },
    technique={"technique_id": "synthetic_plain_http", "acquisition_mode": "plain_http", "technique_version": None},
    observed_evidence={"evidence_type": "negative_acquisition_outcome", "failure_class": "application-shell-only"},
    semantic_labels={"acquisition_result": "unknown"},
    acquisition_outcome={
        "technical_completion": True, "usable_evidence": False, "challenge_reached": False,
        "authentication_required": False, "stable_identity_available": False,
        "production_approved": False, "production_store": False, "scheduler_action": None,
    },
    decision={
        "decision_type": "acquisition_outcome", "system_suggestion": None,
        "final_decision": "unknown", "reason_code": "application_shell_only",
        "explanation": "Sanitized synthetic negative contract test.",
        "evidence_references": ["observed_evidence"], "decision_source": "deterministic_rule",
    },
    provenance={
        "source_schema": "synthetic-negative.v1", "extractor_schema": None,
        "commit_reference": None, "evidence_origin": "sanitized-synthetic-test",
        "reviewed_status": "deterministic-not-human-reviewed", "reviewer_provenance": None,
    },
)
assert negative["acquisition_outcome"]["usable_evidence"] is False
assert negative["semantic_labels"]["acquisition_result"] == "unknown"

# LG8: identity and provenance are fail-closed.
for mutation in ("identity", "provenance"):
    malformed = deepcopy(l2_current)
    malformed[mutation] = {}
    try:
        validate_learning_record(malformed)
        raise AssertionError(f"missing {mutation} unexpectedly validated")
    except ValueError:
        pass

contradictory_canonical = deepcopy(l9_comparison)
contradictory_canonical["semantic_labels"]["canonical_price"] = 25.0
try:
    validate_learning_record(contradictory_canonical)
    raise AssertionError("contradictory canonical price unexpectedly validated")
except ValueError:
    pass

# LG9: prohibited key names and token-like values are rejected.
for unsafe_evidence in (
    {"cookie": "redacted"}, {"note": "access_token=not-allowed"},
    {"browser_profile": "profile-data"}, {"storage_state": "state-data"},
):
    unsafe = deepcopy(l2_current)
    unsafe["observed_evidence"].update(unsafe_evidence)
    try:
        validate_learning_record(unsafe)
        raise AssertionError("sensitive learning evidence unexpectedly validated")
    except ValueError:
        pass

# LG10/LG11: Lazada records retain disabled production state and never invent Human Review.
all_lazada = [
    l1_unknown, l2_current, l3_from, l4_promotional, l5_discount, l6_voucher,
    l7_member, *l8_variation, l9_comparison, l10_counter, l11_counter, l12_rating,
]
assert all(record["acquisition_outcome"]["production_approved"] is False for record in all_lazada)
assert all(record["acquisition_outcome"]["production_store"] is False for record in all_lazada)
assert all(record["acquisition_outcome"]["scheduler_action"] is None for record in all_lazada)
assert all(record["decision"]["decision_source"] == "deterministic_rule" for record in all_lazada)
assert all(record["provenance"]["reviewer_provenance"] is None for record in all_lazada)
fabricated_review = deepcopy(l2_current)
fabricated_review["decision"]["decision_source"] = "human_review"
try:
    validate_learning_record(fabricated_review)
    raise AssertionError("unproven Human Review unexpectedly validated")
except ValueError:
    pass

# LG12: canonical serialization is deterministic, JSON safe, and one-object-per-line ready.
first_json = serialize_learning_record_json(l9_comparison)
second_json = serialize_learning_record_json(deepcopy(l9_comparison))
assert first_json == second_json
assert "\n" not in first_json
assert json.loads(first_json) == serialize_learning_record(l9_comparison)

print("Acquisition Learning Record deterministic tests passed (L1-L12, LG1-LG12).")
