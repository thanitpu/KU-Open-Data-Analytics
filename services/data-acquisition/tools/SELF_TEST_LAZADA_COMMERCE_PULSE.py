from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "acquisition", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from commerce_market_observation import (
    CommerceObservationStore,
    MarketplaceRankingObservation,
    SalesCounterObservation,
    observable_signal_label,
)
import LAZADA_COMMERCE_PULSE_EXPLORE as explorer


FIXTURE = ROOT / "fixtures" / "lazada_commerce_pulse" / "public_structured_response.json"
DOCUMENT = json.loads(FIXTURE.read_text(encoding="utf-8"))
OBSERVED_AT = "2026-08-31T00:00:00+00:00"


def normalize(document=DOCUMENT, max_items=20, surface="keyword-search"):
    return explorer.normalize_public_json(
        document, url="https://www.lazada.co.th/catalog/?q=fixture", surface=surface,
        query="fixture", observed_at=OBSERVED_AT, max_items=max_items,
    )


# A: stable identity comes from canonical public URL or explicit structured ID.
assert explorer.product_id_from_url(
    "https://www.lazada.co.th/products/cable-i100001-s200001.html"
)[0] == "100001"
assert explorer.product_id_from_url("https://example.test/products/cable-i100001.html")[0] is None
records = normalize()
assert [row["platform_product_id"] for row in records] == ["100001", "100002", "100003"]
assert all(row["platform"] == "lazada-thailand" for row in records)
assert normalize({"row": {
    "itemId": "100001", "productUrl": "https://www.lazada.co.th/products/x-i999999.html",
    "name": "contradictory identity",
}}) == []

# B: equal titles never merge distinct stable platform identities.
same_title = [row for row in records if row["title"] == "Fixture Cable"]
assert len(same_title) == 2 and len({row["platform_product_id"] for row in same_title}) == 2

# C/D: same-time, distinct surfaces coexist; a true logical replay deduplicates.
first = SalesCounterObservation(
    platform="lazada-thailand", product_id="100001", observed_sold_count=1200,
    raw_display="1.2k sold", observed_at=OBSERVED_AT, precision="rounded",
    source_surface="https://www.lazada.co.th/catalog/?q=fixture",
    provenance={"surface_type": "keyword-search", "category_or_query": "fixture", "sort_mode": "relevance"},
)
second = replace(
    first, source_surface="https://www.lazada.co.th/shop/example",
    provenance={"surface_type": "shop", "category_or_query": "example", "sort_mode": "popular"},
)
with TemporaryDirectory() as folder:
    store = CommerceObservationStore(
        Path(folder) / "commerce.sqlite3",
        environ={"KU2D_OPERATIONS_DB": str(Path(folder) / "operations.sqlite3")},
    )
    assert store.append("sales_counter", first)["inserted"] is True
    assert store.append("sales_counter", second)["inserted"] is True
    assert store.append("sales_counter", first)["inserted"] is False
    assert len(store.observations()) == 2
    assert len({row["observation_scope"] for row in store.observations()}) == 2

# E: an explicitly sold display is typed and uncertainty is preserved.
sold = records[0]
assert sold["observed_sold_count"] == 1200 and sold["sold_count_precision"] == "rounded"
assert sold["provenance"]["marketplace_counter"]["counter_type"] == "sold"
assert sold["provenance"]["counter_is_transaction_ledger"] is False

# F: order and review signals are never silently converted to sold/fulfilled units.
orders, review_only = records[1], records[2]
assert orders["observed_sold_count"] is None and orders["sold_count_display"] is None
assert orders["provenance"]["marketplace_counter"]["counter_type"] == "orders"
assert "not-assumed-sold-or-fulfilled" in orders["provenance"]["marketplace_counter"]["meaning"]
assert review_only["review_count"] == 9 and review_only["observed_sold_count"] is None
assert review_only["provenance"]["marketplace_counter"]["counter_type"] == "unknown"

# G: explicit currency displays may normalize; raw numeric prices retain unknown scaling.
assert sold["current_price"] == 159.0 and sold["provenance"]["price_semantics"] == "explicit-currency-display"
assert orders["current_price"] is None and orders["provenance"]["raw_price"] == 15900
assert orders["provenance"]["price_semantics"] == "raw-structured-value-scaling-unknown"
assert orders["provenance"]["price_scaling_validated"] is False

# H/I: ranking requires complete context and never supports a national bestseller label.
rank = MarketplaceRankingObservation(
    platform="lazada-thailand", surface_type="keyword-search",
    source_surface="https://www.lazada.co.th/catalog/?q=fixture", category_or_query="fixture",
    sort_mode="relevance", product_id="100001", observed_rank=1, observed_at=OBSERVED_AT,
    provenance={"fixture": True, "national_rank": False},
)
assert rank.observed_rank == 1
try:
    MarketplaceRankingObservation(
        platform="lazada-thailand", surface_type="keyword-search", source_surface="",
        category_or_query="fixture", sort_mode="", product_id="100001", observed_rank=1,
        observed_at=OBSERVED_AT, provenance={},
    )
    raise AssertionError("context-free ranking accepted")
except ValueError:
    pass
assert all("national" not in observable_signal_label(key).casefold() for key in ("cumulative", "velocity", "ranking", "trend"))
assert records[0]["provenance"]["rank_context"]["national_rank"] is False
assert records[0]["provenance"]["rank_context"]["sort_mode"] == "relevance"


def args(output: Path, max_items=10):
    return argparse.Namespace(
        url=None, query="สายชาร์จ", category=None, max_items=max_items,
        output=output, no_production_store=True,
    )


def json_fetch(url):
    return {
        "status": 200, "effective_url": url, "content_type": "application/json",
        "body": FIXTURE.read_bytes(), "truncated": False,
    }


# J: usable stable-identity evidence exits 0 and remains non-production.
with TemporaryDirectory() as folder:
    output = Path(folder) / "usable.json"
    code = explorer.main([
        "--query", "สายชาร์จ", "--max-items", "10", "--output", str(output), "--no-production-store",
    ], fetcher=json_fetch)
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert code == explorer.EXIT_EVIDENCE_OBTAINED and evidence["usable_evidence"] is True
    assert evidence["production_approved"] is False and evidence["production_store"] is False
    assert evidence["scheduler_action"] is None

# K: challenge evidence is written before exit 2.
def challenge_fetch(url):
    return {
        "status": 200, "effective_url": "https://www.lazada.co.th/captcha/verify",
        "content_type": "text/html", "body": b"Verify you are human", "truncated": False,
    }


with TemporaryDirectory() as folder:
    output = Path(folder) / "challenge.json"
    code = explorer.main([
        "--query", "สายชาร์จ", "--max-items", "10", "--output", str(output), "--no-production-store",
    ], fetcher=challenge_fetch)
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert code == explorer.EXIT_EVIDENCE_WITHHELD and evidence["technical_completion"] is True
    assert evidence["challenge_detected"] is True and evidence["usable_evidence"] is False

# L: an application shell is evidence-withheld, never false green.
def shell_fetch(url):
    return {
        "status": 200, "effective_url": url, "content_type": "text/html",
        "body": b"<html><script>window.app={}</script></html>", "truncated": False,
    }


with TemporaryDirectory() as folder:
    output = Path(folder) / "shell.json"
    code = explorer.main([
        "--query", "สายชาร์จ", "--max-items", "10", "--output", str(output), "--no-production-store",
    ], fetcher=shell_fetch)
    assert code == explorer.EXIT_EVIDENCE_WITHHELD and output.exists()

# M: controlled transport failure writes technical evidence and exits 1.
def failing_fetch(url):
    raise RuntimeError("controlled Lazada transport failure")


with TemporaryDirectory() as folder:
    output = Path(folder) / "technical.json"
    code = explorer.main([
        "--query", "สายชาร์จ", "--max-items", "10", "--output", str(output), "--no-production-store",
    ], fetcher=failing_fetch)
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert code == explorer.EXIT_TECHNICAL_FAILURE and evidence["technical_completion"] is False
    assert evidence["technical_failure"]["type"] == "RuntimeError"

# N: evidence-writing failure exits 1.
with TemporaryDirectory() as folder:
    output_directory = Path(folder) / "not-a-file"
    output_directory.mkdir()
    code = explorer.main([
        "--query", "สายชาร์จ", "--max-items", "10", "--output", str(output_directory),
        "--no-production-store",
    ], fetcher=json_fetch)
    assert code == explorer.EXIT_TECHNICAL_FAILURE

# O: limits, public host, and mandatory non-production switch fail closed.
registry = explorer.load_registry()
for invalid in (0, 21):
    try:
        explorer.validate_options(args(Path("unused.json"), max_items=invalid), registry)
        raise AssertionError("invalid max-items accepted")
    except ValueError:
        pass
try:
    explorer.validate_options(argparse.Namespace(
        url="https://example.test/", query=None, category=None, max_items=10,
        output=Path("unused.json"), no_production_store=True,
    ), registry)
    raise AssertionError("non-Lazada host accepted")
except ValueError:
    pass
try:
    explorer.validate_options(argparse.Namespace(
        url=None, query="fixture", category=None, max_items=10,
        output=Path("unused.json"), no_production_store=False,
    ), registry)
    raise AssertionError("production-store option omission accepted")
except ValueError:
    pass

# P: registry is explicit about official seller API and the access ladder.
assert len(registry["techniques"]) == 6
assert registry["official_api_boundary"]["classification"] == "seller-authorized-platform-api-not-public-marketplace-feed"
assert registry["official_api_boundary"]["oauth_or_app_credentials_allowed_in_this_explorer"] is False
assert registry["execution_ladder"][0] == "plain-public-http"
assert registry["domain_boundary"]["production_storage_enabled"] is False
assert registry["domain_boundary"]["cross_platform_product_matching_enabled"] is False
route_findings = explorer._discover_endpoints(
    "'/user/api/loginByToken' '/checkout/api/async' '/catalog/sw.js' '/catalog/products/list'"
)
assert [row["commerce_relevance"] for row in route_findings] == [
    "account-or-auth-non-commerce", "checkout-non-observation",
    "service-worker-non-commerce", "unvalidated-candidate",
]
assert all(row["validated_public_product_data"] is False for row in route_findings)

# Q: the closed Shopee checkpoint and adjacent frozen policies remain intact.
shopee = json.loads((ROOT / "config" / "shopee_commerce_pulse_sources.json").read_text(encoding="utf-8"))
assert shopee["bounded_access_audit"]["public_unauthenticated_acquisition_status"] == "PAUSED"
assert shopee["bounded_access_audit"]["windows_edge_runner"]["classification"] == "edge-traffic-verification"
youtube = json.loads((ROOT / "config" / "youtube_api_policy.json").read_text(encoding="utf-8"))
assert youtube["comments_enabled"] is False
assert youtube["production_scheduling_enabled"] is False

print("Lazada Commerce Pulse deterministic tests passed (A-Q).")
