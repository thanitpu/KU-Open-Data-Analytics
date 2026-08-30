"""Deterministic Deep Audit tests for the Lazada rendered-DOM pattern."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT / "tools"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from commerce_market_observation import CommerceObservationStore, CommerceProductObservation
from lazada_rendered_dom_audit import build_audit, counter_evidence, price_evidence, rating_review_evidence
import LAZADA_RENDERED_DOM_DEEP_AUDIT as cli


FIXTURE = ROOT / "fixtures" / "lazada_rendered_dom_audit" / "audit_package.json"
ENTRIES = json.loads(FIXTURE.read_text(encoding="utf-8"))["surfaces"]
audit = build_audit(ENTRIES, max_items=10)
surfaces = {surface["surface_type"]: surface for surface in audit["surfaces"]}
search = surfaces["keyword-search"]["records"][0]
detail = surfaces["product-detail"]["records"][0]
category = surfaces["category"]["records"][0]
shop = surfaces["shop"]["records"][0]

# A: canonical item identity survives every surface.
assert {row["platform_product_id"] for row in (search, detail, category, shop)} == {"100001"}
assert all(row["identity_basis"] == "canonical-public-product-url" for row in (search, detail, category, shop))
assert all(surface["stable_identity_pct"] == 100.0 for surface in surfaces.values())

# B: search/detail correlation uses the same item without asserting variant equivalence.
correlation = audit["product_detail_correlation"]
assert correlation["same_item_identity"] is True
assert correlation["title_consistent"] is True
assert correlation["price_consistent_or_within_detail_range"] is True
assert correlation["variant_equivalence_asserted"] is False

# C: same item/time/different surfaces coexist in the generic scoped store.
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

# D: an unlabeled bare-item counter retains a numeric parse but never becomes sold.
assert search["counter"]["counter_type"] == "unknown"
assert search["counter"]["raw_display"] == "5.5K ชิ้น"
assert search["counter"]["numeric_parse"] == 5500
assert search["counter"]["precision"] == "rounded"
assert search["counter"]["observed_sold_count"] is None
assert search["counter"]["semantic_confidence"] == "unlabeled-display"

# E: unlabeled parenthetical counts do not become reviews.
assert search["rating_review"]["unlabeled_parenthetical_count_raw"] == "(714)"
assert search["rating_review"]["unlabeled_parenthetical_count_classification"] == "unknown-not-review"
assert search["rating_review"]["review_count"] is None
assert detail["rating_review"]["review_count"] == 412

# F/G/H: current, explicit original, and variation range remain separate.
assert search["price"]["current_price"] == 159.0
assert search["price"]["current_price_raw"] == "฿159.00"
assert detail["price"]["original_price"] == 229.0
assert detail["price"]["original_price_raw"] == "฿229.00"
assert detail["price"]["variation_range_raw"] == "฿159.00 - ฿199.00"
assert detail["price"]["variation_min_price"] == 159.0
assert detail["price"]["variation_max_price"] == 199.0
assert detail["price"]["hidden_numeric_scaling_inferred"] is False

# I: generic relevance order remains only observed display position.
assert search["observed_display_position"] == 1
assert search["marketplace_ranking_observation"] is None

# J: an explicit bestseller surface may create a fully contextual rank.
ranking = category["marketplace_ranking_observation"]
assert ranking["observed_rank"] == 1
assert ranking["surface_type"] == "category"
assert ranking["category_or_query"] == "mobile-accessories"
assert ranking["sort_mode"] == "bestseller"
assert ranking["provenance"]["national_rank"] is False

# K: unknown counter semantics block sales velocity and full longitudinal readiness.
assert audit["longitudinal_readiness"]["sales_velocity_ready"] is False
assert audit["longitudinal_readiness"]["ready_for_longitudinal_observation"] is False
assert audit["longitudinal_readiness"]["status"] == "Partial"
assert "counter semantics are not explicitly sold or orders" in audit["longitudinal_readiness"]["blocking_reasons"]

# Dimension decisions remain independent.
assert audit["pattern_decisions"] == {
    "product_identity_price": "Approved candidate",
    "ranking_display_order": "Approved candidate",
    "sold_order_counter": "Needs review",
    "longitudinal_observation": "Partial",
}

# L/M/N: production controls are immutable.
assert audit["production_approved"] is False
assert audit["production_store"] is False
assert audit["scheduler_action"] is None
assert all(surface["production_approved"] is False for surface in audit["surfaces"])

# Focused parser regressions cover explicit orders/sold and raw price separation.
assert counter_evidence({"counter_text": "120 orders"})["counter_type"] == "orders"
assert counter_evidence({"counter_text": "ขายแล้ว 88 ชิ้น"})["counter_type"] == "sold"
assert rating_review_evidence({"visible_text": "(999)"})["review_count"] is None
numeric_price = price_evidence({"visible_text": "15900"})
assert numeric_price["current_price"] is None and numeric_price["hidden_numeric_scaling_inferred"] is False

# CLI writes a usable audit before exit 0.
with TemporaryDirectory() as folder:
    output = Path(folder) / "audit.json"
    code = cli.main([
        "--input", str(FIXTURE), "--max-items", "10", "--output", str(output),
        "--no-production-store",
    ])
    written = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_AUDIT_OBTAINED and written["technical_completion"] is True
    assert written["production_store"] is False

# O is enforced by the complete deterministic corpus; explicitly retain the
# previously integrated browser pilot decision.
registry = json.loads((ROOT / "config" / "lazada_commerce_pulse_sources.json").read_text(encoding="utf-8"))
assert registry["bounded_browser_pilot"]["classification"] == "lazada-rendered-dom-only"
assert registry["bounded_browser_pilot"]["production_approved"] is False

print("Lazada rendered-DOM Deep Audit deterministic tests passed (A-O).")
