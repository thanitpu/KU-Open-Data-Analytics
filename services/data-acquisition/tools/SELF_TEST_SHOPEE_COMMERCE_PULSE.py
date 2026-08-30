from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "acquisition", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from commerce_market_observation import (
    CommerceObservationStore,
    CommerceProductObservation,
    CounterDiscontinuityError,
    MarketplaceRankingObservation,
    SalesCounterObservation,
    build_trending_candidate,
    estimate_sales_velocity,
    observable_signal_label,
    parse_sold_count,
)
import SHOPEE_COMMERCE_PULSE_EXPLORE as explorer


FIXTURES = ROOT / "fixtures" / "shopee_commerce_pulse"


# A-E: exact, abbreviated English, Thai units, plus/lower-bound, and rounded precision.
cases = json.loads((FIXTURES / "sold_count_cases.json").read_text(encoding="utf-8"))["cases"]
for case in cases:
    parsed = parse_sold_count(case["display"])
    assert parsed["observed_sold_count"] == case["count"], (case, parsed)
    assert parsed["precision"] == case["precision"], (case, parsed)
assert parse_sold_count("1.25")["precision"] == "unknown"


def counter(product_id: str, count: int | None, at: str, precision="exact", raw=None):
    return SalesCounterObservation(
        platform="shopee-thailand", product_id=product_id, observed_sold_count=count,
        raw_display=raw or ("unknown" if count is None else str(count)), observed_at=at,
        precision=precision, provenance={"surface": "fixture"},
    )


# F: repeated exact observation supports a labeled estimate.
prior = counter("ITEM-1", 1201, "2026-08-29T00:00:00+00:00")
current = counter("ITEM-1", 1325, "2026-08-29T12:00:00+00:00")
velocity = estimate_sales_velocity(prior, current)
assert velocity.sold_delta == 124 and velocity.elapsed_hours == 12.0
assert velocity.estimated_units_per_hour == 10.33 and velocity.confidence == "high"
assert velocity.is_transaction_ledger is False and "estimate" not in velocity.estimate_basis.casefold()

# G: lower-bound/rounded observations never produce a falsely precise delta.
bounded = estimate_sales_velocity(
    counter("ITEM-1", 300000, "2026-08-29T00:00:00+00:00", "lower_bound", "300k+"),
    counter("ITEM-1", 300000, "2026-08-30T00:00:00+00:00", "lower_bound", "300k+"),
)
assert bounded.sold_delta is None and bounded.estimated_units_per_hour is None
assert bounded.confidence == "indeterminate" and bounded.is_transaction_ledger is False

# H: negative counters fail closed with an explicit discontinuity classification.
try:
    estimate_sales_velocity(
        counter("ITEM-1", 100, "2026-08-29T00:00:00+00:00"),
        counter("ITEM-1", 90, "2026-08-30T00:00:00+00:00"),
    )
    raise AssertionError("negative sold-counter movement accepted")
except CounterDiscontinuityError as exc:
    assert "reset" in str(exc) and "listing change" in str(exc)

# I: rank cannot exist without exact surface/query/sort/time context.
ranking = MarketplaceRankingObservation(
    platform="shopee-thailand", surface_type="keyword-search",
    source_surface="https://shopee.co.th/search?keyword=fixture",
    category_or_query="fixture", sort_mode="bestseller", product_id="ITEM-1",
    observed_rank=1, observed_at="2026-08-30T00:00:00+00:00",
    provenance={"fixture": True},
)
assert ranking.observed_rank == 1 and ranking.sort_mode == "bestseller"
try:
    MarketplaceRankingObservation(
        platform="shopee-thailand", surface_type="keyword-search", source_surface="",
        category_or_query="fixture", sort_mode="", product_id="ITEM-1", observed_rank=1,
        observed_at="2026-08-30T00:00:00+00:00", provenance={},
    )
    raise AssertionError("context-free rank accepted")
except ValueError:
    pass

# J/K/N: append-only store links only stable identities and never enables production.
with TemporaryDirectory() as folder:
    db = Path(folder) / "commerce.sqlite3"
    store = CommerceObservationStore(db, environ={"KU2D_OPERATIONS_DB": str(Path(folder) / "operations.sqlite3")})
    assert store.production_store_enabled is False
    first = store.append("sales_counter", prior)
    second = store.append("sales_counter", current)
    other = store.append("sales_counter", counter("ITEM-2", 50, "2026-08-29T12:00:00+00:00"))
    duplicate = store.append("sales_counter", current)
    assert first["inserted"] and second["inserted"] and other["inserted"]
    assert duplicate["inserted"] is False
    rows = store.observations()
    assert len(rows) == 3
    assert len([row for row in rows if row["product_id"] == "ITEM-1"]) == 2
    assert len([row for row in rows if row["product_id"] == "ITEM-2"]) == 1
    assert all(row["production_approved"] == 0 for row in rows)
    try:
        CommerceObservationStore(db, environ={"KU2D_OPERATIONS_DB": str(db)})
        raise AssertionError("operations DB reused as commerce store")
    except ValueError:
        pass

# L: generic marketplace observations cannot generate a national-best-seller claim.
labels = [observable_signal_label(key) for key in ("cumulative", "velocity", "ranking", "trend")]
assert labels == [
    "Highest Observable Sold Count", "Fastest Rising",
    "Strongest Marketplace Rank", "Cross-observation Trending",
]
assert all("thailand's #1" not in label.casefold() and "national" not in label.casefold() for label in labels)

# M and scoring contract: production approval is fixed false and weights stay non-authoritative.
product = CommerceProductObservation(
    platform="shopee-thailand", platform_product_id="ITEM-1", seller_id="SELLER-1", shop_id="SHOP-1",
    title="Fixture", brand="Brand", category="mobile-accessories", current_price=159.0,
    original_price=199.0, discount_pct=20.1, rating=4.8, review_count=412,
    observed_sold_count=1200, sold_count_display="1.2k sold", sold_count_precision="rounded",
    source_surface="fixture-search", source_rank=3, source_query="fixture",
    observed_at="2026-08-30T00:00:00+00:00", provenance={"fixture": True}, publicly_observable=True,
)
assert product.production_approved is False
trend = build_trending_candidate(
    platform="shopee-thailand", product_id="ITEM-1", observed_at=product.observed_at,
    cumulative_signal=1200, velocity_signal=0.8, rank_strength=0.7,
    rank_improvement=0.5, review_growth=0.2, repeated_surface_presence=0.9,
)
assert trend.production_approved is False and trend.weights_authoritative is False
assert trend.raw_signals == {"cumulative_sold_count": 1200, "estimated_units_per_hour": 0.8}
assert trend.scoring_version == "commerce-pulse-provisional-v1"

# Explorer fixture: public JSON normalization is bounded and keeps price scaling uncertain.
fixture_body = (FIXTURES / "public_structured_response.json").read_bytes()


def fixture_fetch(url):
    return {
        "status": 200, "effective_url": url, "content_type": "application/json",
        "body": fixture_body, "truncated": False,
    }


registry = explorer.load_registry()
args = argparse.Namespace(
    url=None, query="สายชาร์จ", category=None, max_items=1,
    output=Path("unused.json"), no_production_store=True,
)
result = explorer.explore(args, fetcher=fixture_fetch, registry=registry)
assert result["usable_evidence"] is True and len(result["sample_normalized_records"]) == 1
sample = result["sample_normalized_records"][0]
assert sample["platform_product_id"] == "123456789" and sample["production_approved"] is False
assert sample["sold_count_precision"] == "rounded" and sample["observed_sold_count"] == 1200
assert sample["provenance"]["price_scale"].startswith("unknown")
assert result["production_store"] is False and result["scheduler_action"] is None

# A traffic-verification redirect is an access challenge even when HTTP status is 200.
def verification_fetch(url):
    return {
        "status": 200,
        "effective_url": "https://shopee.co.th/verify/traffic/error?type=4",
        "content_type": "text/html", "body": b"Login Required", "truncated": False,
    }


blocked = explorer.explore(args, fetcher=verification_fetch, registry=registry)
assert blocked["challenge_detected"] is True
assert blocked["challenge_reason"] == "redirected-to-shopee-traffic-verification"
assert blocked["usable_evidence"] is False

# Explorer never returns false green: missing usable evidence exits 2 after writing diagnostics.
def shell_fetch(url):
    return {
        "status": 200, "effective_url": url, "content_type": "text/html",
        "body": b"<html><script>fetch('/api/v4/pages/is_short_url/')</script></html>",
        "truncated": False,
    }


with TemporaryDirectory() as folder:
    output = Path(folder) / "shell-result.json"
    exit_code = explorer.main([
        "--url", "https://shopee.co.th/top.selected", "--max-items", "10",
        "--output", str(output), "--no-production-store",
    ], fetcher=shell_fetch)
    assert exit_code == explorer.EXIT_EVIDENCE_WITHHELD and output.exists()
    diagnostic = json.loads(output.read_text(encoding="utf-8"))
    assert diagnostic["technical_completion"] is True and diagnostic["usable_evidence"] is False
    assert diagnostic["failure_reason"].startswith("reachable-application-shell")
    assert diagnostic["discovered_public_endpoints"][0]["commerce_relevance"] == "navigation-only"

# A transport failure is also evidence-before-exit and remains production-disabled.
def failed_fetch(url):
    raise RuntimeError(f"controlled transport failure for {urlparse_guard(url)}")


def urlparse_guard(url):
    assert "shopee.co.th" in url
    return "official-shopee-surface"


with TemporaryDirectory() as folder:
    output = Path(folder) / "technical-result.json"
    exit_code = explorer.main([
        "--query", "ขนม", "--max-items", "5", "--output", str(output),
        "--no-production-store",
    ], fetcher=failed_fetch)
    assert exit_code == explorer.EXIT_TECHNICAL_FAILURE and output.exists()
    diagnostic = json.loads(output.read_text(encoding="utf-8"))
    assert diagnostic["technical_completion"] is False and diagnostic["production_store"] is False
    assert diagnostic["technical_failure"]["type"] == "RuntimeError"

# Registry surface/seed/access contracts are deterministic and do not auto-require Edge.
assert len(registry["techniques"]) == 6
assert {row["category_id"] for row in registry["pilot_seed_registry"]["categories"]} == {
    "beauty", "mobile-accessories", "household", "fashion", "food-snacks", "pet-supplies",
}
assert registry["domain_boundary"]["production_approved"] is False
assert registry["domain_boundary"]["production_storage_enabled"] is False
assert registry["bounded_access_audit"]["windows_edge_runner"] == "not-required-or-tested"
assert registry["scoring_contract"]["authoritative"] is False

# O/P are enforced by the complete deterministic corpus; this test also guards shared policy files.
youtube_policy = json.loads((ROOT / "config" / "youtube_api_policy.json").read_text(encoding="utf-8"))
assert youtube_policy["comments_enabled"] is False
assert youtube_policy["production_scheduling_enabled"] is False
assert youtube_policy["arbitrary_transcript_acquisition_enabled"] is False

print("Shopee Commerce Pulse deterministic tests passed (A-P).")
