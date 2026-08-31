"""Deterministic Deep Audit tests for the Lazada rendered-DOM pattern."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT / "tools"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from commerce_market_observation import CommerceObservationStore, CommerceProductObservation
from lazada_rendered_dom_audit import (
    audit_surface,
    build_audit,
    correlate_search_detail,
    counter_evidence,
    price_evidence,
    rating_review_evidence,
)
import LAZADA_RENDERED_DOM_DEEP_AUDIT as cli


FIXTURE = ROOT / "fixtures" / "lazada_rendered_dom_audit" / "audit_package.json"
ENTRIES = json.loads(FIXTURE.read_text(encoding="utf-8"))["surfaces"]


def record(surface_type: str, **overrides):
    row = {
        "product_url": "https://www.lazada.co.th/products/fixture-cable-i100001-s200001.html",
        "explicit_product_id": "100001",
        "visible_title": "Fixture Cable 100W",
        "visible_text": "Fixture Cable 100W",
        **overrides,
    }
    entry = {
        "context": {
            "surface_type": surface_type,
            "query_or_category": "fixture",
            "sort_mode": "default",
            "sort_semantics_explicit": False,
        },
        "capture": {
            "observed_at": "2026-08-31T02:00:00+00:00",
            "initial_url": f"https://www.lazada.co.th/{surface_type}/fixture/",
            "final_url": f"https://www.lazada.co.th/{surface_type}/fixture/",
            "visible_page_text": "Fixture public surface",
            "visible_product_card_count": 1,
            "visible_cards": [row],
            "network_requests": [],
        },
    }
    return audit_surface(entry)["records"][0]


audit = build_audit(ENTRIES, max_items=10)
surfaces = {surface["surface_type"]: surface for surface in audit["surfaces"]}
search = surfaces["keyword-search"]["records"][0]
detail = surfaces["product-detail"]["records"][0]
category = surfaces["category"]["records"][0]
shop = surfaces["shop"]["records"][0]

# A: equal explicit amounts are an exact match, without canonicalization.
exact = correlate_search_detail(
    record("keyword-search", current_price_text="฿25"),
    record("product-detail", current_price_text="฿25"),
)
assert exact["price_relation"] == "exact_match"
assert exact["same_product_identity"] is True
assert exact["same_variant_identity"] == "unknown"
assert exact["canonical_price_asserted"] is False and exact["canonical_price"] is None

# B: a search amount inside an explicit detail range has a scoped relation only.
within_range = correlate_search_detail(
    record("keyword-search", current_price_text="฿25"),
    record("product-detail", current_price_text="฿49", variation_price_text="฿25 - ฿49"),
)
assert within_range["price_relation"] == "search_within_detail_variant_range"
assert within_range["price_consistent_or_within_detail_range"] is True
assert within_range["canonical_price_asserted"] is False

# C: same product, differing amounts and no variant evidence remain unresolved.
unresolved = correlate_search_detail(
    record("keyword-search", current_price_text="฿25"),
    record("product-detail", current_price_text="฿49"),
)
assert unresolved["same_variant_identity"] == "unknown"
assert unresolved["variant_equivalence_status"] == "unknown"
assert unresolved["price_relation"] == "different_unresolved"
assert unresolved["canonical_price"] is None

# D: explicit from-price/current roles explain representation, not variant identity.
role_explained = correlate_search_detail(
    record("keyword-search", current_price_text="เริ่มต้น ฿25"),
    record("product-detail", current_price_text="฿49"),
)
assert role_explained["price_relation"] == "different_but_explained_by_explicit_roles"
assert role_explained["same_variant_identity"] == "unknown"
assert role_explained["canonical_price_asserted"] is False
from_price_record = record("keyword-search", current_price_text="เริ่มต้น ฿25")["price"]
assert from_price_record["price_observations"][0]["price_role"] == "from_price"
assert from_price_record["current_price"] is None

# E: current and original displays remain independent observations.
current_original = price_evidence({"current_price_text": "฿49", "original_price_text": "฿79"})
assert current_original["current_price"] == 49.0
assert current_original["original_price"] == 79.0
assert {item["price_role"] for item in current_original["price_observations"]} == {"current", "original"}

# F: voucher savings are conditional observations and never current price.
voucher = price_evidence({"visible_text": "ลดเพิ่ม ฿10"})
assert voucher["current_price"] is None
assert voucher["price_observations"][0]["price_role"] == "voucher_or_conditional"
assert voucher["price_observations"][0]["conditional"] is True

# G: an unlabeled amount is retained as unknown rather than promoted to current.
unlabeled_price = price_evidence({"visible_text": "฿25"})
assert unlabeled_price["current_price"] is None
assert unlabeled_price["price_observations"][0]["price_role"] == "unknown_display_price"

# H: explicit different variants are not comparable even under the same product.
different_variant = correlate_search_detail(
    record("keyword-search", current_price_text="฿25", variant_id="variant-a"),
    record("product-detail", current_price_text="฿25", variant_id="variant-b"),
)
assert different_variant["same_variant_identity"] is False
assert different_variant["variant_equivalence_status"] == "different"
assert different_variant["price_relation"] == "not_comparable"

# I: same explicit variant with differing unexplained amounts remains unresolved.
same_variant = correlate_search_detail(
    record("keyword-search", current_price_text="฿25", sku_id="sku-a"),
    record("product-detail", current_price_text="฿49", sku_id="sku-a"),
)
assert same_variant["same_variant_identity"] is True
assert same_variant["variant_equivalence_status"] == "same"
assert same_variant["price_relation"] == "different_unresolved"

# J: category/shop price evidence is surface-scoped and conveys no rank/demand.
scoped_category = record("category", current_price_text="฿25")
scoped_shop = record("shop", current_price_text="฿25")
for scoped, expected_surface in ((scoped_category, "category"), (scoped_shop, "shop")):
    observation = scoped["price"]["price_observations"][0]
    assert observation["price_surface"] == expected_surface
    assert observation["source_surface"] == scoped["source_surface"]
    assert scoped["marketplace_ranking_observation"] is None
    assert not ({"rank", "demand"} & set(observation))

# K: a bare Thai item counter keeps its parse but remains semantically unknown.
assert search["counter"]["counter_type"] == "unknown"
assert search["counter"]["raw_display"] == "5.5K ชิ้น"
assert search["counter"]["numeric_parse"] == 5500
assert search["counter"]["precision"] == "rounded"
assert search["counter"]["observed_sold_count"] is None
assert search["counter"]["eligible_for_sales_velocity"] is False

# L: an unlabeled parenthetical count remains unknown-not-review.
assert search["rating_review"]["unlabeled_parenthetical_count_raw"] == "(714)"
assert search["rating_review"]["unlabeled_parenthetical_count_classification"] == "unknown-not-review"
assert search["rating_review"]["review_count"] is None

# M: all execution and approval controls stay disabled.
assert audit["production_approved"] is False
assert audit["production_store"] is False
assert audit["scheduler_action"] is None
assert all(surface["production_approved"] is False for surface in audit["surfaces"])

# N: sanitized fixtures and output contain no credential/session material.
def keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).casefold()
            yield from keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from keys(child)


for document in (json.loads(FIXTURE.read_text(encoding="utf-8")), audit):
    forbidden = {"authorization", "cookie", "cookies", "credential", "credentials", "session", "token", "device_id"}
    assert not (forbidden & set(keys(document)))

# P: an untyped visible-price field remains an unknown display observation.
visible_price = price_evidence({"visible_price_text": "฿25"})
assert visible_price["price_observations"][0]["price_role"] == "unknown_display_price"
assert visible_price["current_price"] is None

# Q: the explicitly typed current-price field remains compatible current price.
typed_current = price_evidence({"current_price_text": "฿25"})
assert typed_current["price_observations"][0]["price_role"] == "current"
assert typed_current["current_price"] == 25.0

# R: a from-price in a typed current slot is authoritative evidence, not current.
typed_from = price_evidence({"current_price_text": "เริ่มต้น ฿25"})
assert typed_from["price_observations"][0]["price_role"] == "from_price"
assert typed_from["current_price"] is None
assert typed_from["current_price_raw"] is None
assert typed_from["current_price_semantics"] == "not-observed"

# S: the same conservative rule applies to an untyped visible-price slot.
visible_from = price_evidence({"visible_price_text": "เริ่มต้น ฿25"})
assert visible_from["price_observations"][0]["price_role"] == "from_price"
assert visible_from["current_price"] is None

# T: an explicitly typed promotional selling price may populate compatibility current.
promotional = price_evidence({"promotional_price_text": "โปรโมชั่น ฿49"})
assert promotional["price_observations"][0]["price_role"] == "promotional"
assert promotional["current_price"] == 49.0

# U/V: voucher and member amounts remain conditional evidence only.
explicit_voucher = price_evidence({"voucher_text": "ลดเพิ่ม ฿10"})
member_price = price_evidence({"member_price_text": "สมาชิก ฿39"})
assert explicit_voucher["price_observations"][0]["price_role"] == "voucher_or_conditional"
assert explicit_voucher["current_price"] is None
assert member_price["price_observations"][0]["price_role"] == "member_or_account_conditional"
assert member_price["current_price"] is None

# W: explicit variation endpoints remain authoritative observations independent of current.
variation_only = price_evidence({"variation_price_text": "฿25–฿49"})
assert [item["price_role"] for item in variation_only["price_observations"]] == ["variation_min", "variation_max"]
assert [item["observed_price"] for item in variation_only["price_observations"]] == [25.0, 49.0]
assert variation_only["current_price"] is None

# A reviewed cue may type visible_price_text; its field name alone never does.
cued_visible_current = price_evidence({
    "visible_price_text": "฿25", "visible_price_text_cue": "selling price",
})
assert cued_visible_current["price_observations"][0]["price_role"] == "current"
assert cued_visible_current["current_price"] == 25.0

# X/Y: the 25/49 result and all earlier A-O invariants remain unchanged.
assert unresolved["same_product_identity"] is True
assert unresolved["variant_equivalence_status"] == "unknown"
assert unresolved["price_relation"] == "different_unresolved"
assert unresolved["canonical_price_asserted"] is False
assert unresolved["canonical_price"] is None

# Existing identity, generic scope, ranking, parser, and CLI contracts remain.
assert {row["platform_product_id"] for row in (search, detail, category, shop)} == {"100001"}
assert all(row["identity_basis"] == "canonical-public-product-url" for row in (search, detail, category, shop))
assert audit["product_detail_correlation"]["price_relation"] == "exact_match"
assert audit["product_detail_correlation"]["variant_equivalence_asserted"] is False
assert detail["price"]["original_price"] == 229.0
assert detail["price"]["variation_min_price"] == 159.0
assert detail["price"]["variation_max_price"] == 199.0
assert all(item["platform_product_id"] == "100001" for item in detail["price"]["price_observations"])
assert all(item["observed_at"] == detail["observed_at"] for item in detail["price"]["price_observations"])
assert all(item["hidden_numeric_scaling_inferred"] is False for item in (search["price"], detail["price"]))
ranking = category["marketplace_ranking_observation"]
assert ranking["observed_rank"] == 1 and ranking["provenance"]["national_rank"] is False
assert audit["longitudinal_readiness"]["status"] == "Partial"
assert audit["pattern_decisions"] == {
    "product_identity_price": "Approved candidate",
    "ranking_display_order": "Approved candidate",
    "sold_order_counter": "Needs review",
    "longitudinal_observation": "Partial",
}
assert counter_evidence({"counter_text": "120 orders"})["counter_type"] == "orders"
assert counter_evidence({"counter_text": "ขายแล้ว 88 ชิ้น"})["counter_type"] == "sold"
assert rating_review_evidence({"visible_text": "(999)"})["review_count"] is None
assert price_evidence({"visible_text": "15900"})["current_price"] is None


def product(source: str) -> CommerceProductObservation:
    return CommerceProductObservation(
        platform="lazada-thailand", platform_product_id="100001", seller_id=None, shop_id=None,
        title="Fixture Cable", brand=None, category=None, current_price=159.0,
        original_price=None, discount_pct=None, rating=None, review_count=None,
        observed_sold_count=None, sold_count_display=None, sold_count_precision="unknown",
        source_surface=source, source_rank=None, source_query="fixture",
        observed_at="2026-08-31T02:00:00+00:00", provenance={"fixture": True},
        publicly_observable=True,
    )


with TemporaryDirectory() as folder:
    store = CommerceObservationStore(
        Path(folder) / "commerce.sqlite3",
        environ={"KU2D_OPERATIONS_DB": str(Path(folder) / "operations.sqlite3")},
    )
    first = store.append("commerce_product", product("https://www.lazada.co.th/tag/fixture/"))
    second = store.append("commerce_product", product("https://www.lazada.co.th/products/fixture-i100001.html"))
    replay = store.append("commerce_product", product("https://www.lazada.co.th/tag/fixture/"))
    assert first["inserted"] and second["inserted"] and replay["inserted"] is False
    assert len(store.observations()) == 2

with TemporaryDirectory() as folder:
    output = Path(folder) / "audit.json"
    code = cli.main(["--input", str(FIXTURE), "--max-items", "10", "--output", str(output), "--no-production-store"])
    written = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_AUDIT_OBTAINED and written["technical_completion"] is True
    assert written["production_store"] is False

# O: the separately integrated PR #34 deterministic diagnostic still passes.
browser_regression = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "SELF_TEST_LAZADA_BROWSER_ACCESS_DIAGNOSTIC.py")],
    cwd=ROOT, capture_output=True, text=True, check=False,
)
assert browser_regression.returncode == 0, browser_regression.stdout + browser_regression.stderr

registry = json.loads((ROOT / "config" / "lazada_commerce_pulse_sources.json").read_text(encoding="utf-8"))
assert registry["bounded_browser_pilot"]["classification"] == "lazada-rendered-dom-only"
assert registry["bounded_browser_pilot"]["production_approved"] is False
durable_correlation = registry["rendered_dom_deep_audit"]["search_detail_correlation"]
assert durable_correlation["search_price"] == 25.0 and durable_correlation["detail_price"] == 49.0
assert durable_correlation["variant_equivalence_status"] == "unknown"
assert durable_correlation["price_relation"] == "different_unresolved"
assert durable_correlation["canonical_price_asserted"] is False
assert durable_correlation["canonical_price"] is None

# AA: an explicit promotional selling-price cue may populate compatibility current.
special_price = price_evidence({"promotional_price_text": "ราคาพิเศษ ฿49"})
assert special_price["price_observations"][0]["price_role"] == "promotional"
assert special_price["current_price"] == 49.0

# AB-AD: explicit discount/savings amounts remain evidence, never product price.
for display in ("ลด ฿10", "ประหยัด ฿10", "discount ฿10 off"):
    savings = price_evidence({"promotional_price_text": display})
    assert savings["price_observations"][0]["price_role"] == "promotional_discount"
    assert savings["price_observations"][0]["observed_price"] == 10.0
    assert savings["current_price"] is None

# AE: a promotional field without an explicit selling/savings cue stays unknown.
ambiguous_promotion = price_evidence({"promotional_price_text": "โปร ฿10"})
assert ambiguous_promotion["price_observations"][0]["price_role"] == "unknown_display_price"
assert ambiguous_promotion["current_price"] is None

print("Lazada rendered-DOM Deep Audit deterministic tests passed (A-AF).")
