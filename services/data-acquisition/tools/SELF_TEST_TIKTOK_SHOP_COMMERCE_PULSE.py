"""Deterministic tests for bounded TikTok Shop Commerce Pulse exploration."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "acquisition", ROOT / "tools"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from tiktok_shop_commerce_pulse import counter_semantics, explicit_baht, normalize_html, normalize_json, product_identity
import TIKTOK_SHOP_COMMERCE_PULSE_EXPLORE as cli


FIXTURES = ROOT / "fixtures" / "tiktok_shop_commerce_pulse"
DOCUMENT = json.loads((FIXTURES / "public_product.json").read_text(encoding="utf-8"))
HTML = (FIXTURES / "public_product.html").read_text(encoding="utf-8")
URL = "https://shop.tiktok.com/th/pdp/fixture/1734348352735249462"
OBSERVED = "2026-08-31T04:00:00+00:00"

# A: canonical public URL provides stable identity; title alone never does.
identity = product_identity(URL)
assert identity["platform_product_id"] == "1734348352735249462"
assert identity["identity_basis"] == "canonical-public-product-url"
assert product_identity("https://example.com/th/pdp/x/1734348352735249462") is None
assert product_identity("", explicit_id="not-numeric") is None

# B: contradictory explicit and URL identities are rejected.
assert product_identity(URL, explicit_id="1734348352735249999") is None

# C: explicit baht price is normalized without hidden scaling.
assert explicit_baht("฿144.00") == 144.0
assert explicit_baht("14400") is None

# D: sold and order labels remain distinct non-ledger evidence.
sold = counter_semantics("จำหน่ายไป 12")
orders = counter_semantics("12 orders")
unknown = counter_semantics("12 ชิ้น")
assert sold["counter_type"] == "sold" and sold["numeric_parse"] == 12
assert orders["counter_type"] == "orders" and orders["numeric_parse"] == 12
assert unknown["counter_type"] == "unknown" and unknown["is_transaction_ledger"] is False

# E: structured public normalization reuses the generic Commerce observation.
records = normalize_json(DOCUMENT, page_url=URL, source_surface="product-detail", query=None,
                         observed_at=OBSERVED, max_items=10)
assert len(records) == 1
record = records[0]
assert record["platform"] == "tiktok-shop-thailand"
assert record["platform_product_id"] == "1734348352735249462"
assert record["current_price"] == 144.0 and record["original_price"] == 199.0
assert record["observed_sold_count"] == 12 and record["sold_count_precision"] == "exact"
assert record["shop_id"] == "shop-fixture"
assert record["production_approved"] is False

# F: embedded public JSON in HTML preserves identity and provenance.
html_records = normalize_html(HTML, page_url=URL, source_surface="product-detail", query=None,
                              observed_at=OBSERVED, max_items=10)
assert len(html_records) == 1
assert html_records[0]["provenance"]["transport"] == "public-structured-json"

# G: access controls are a stop boundary.
assert cli.challenge_status("verify you are human", 200, URL)[0] is True
assert cli.challenge_status("normal public product", 200, URL)[0] is False

# H: valid public evidence exits 0 and is written before exit.
def usable_fetcher(_url):
    return {"status": 200, "effective_url": URL, "content_type": "text/html; charset=utf-8",
            "body": HTML.encode("utf-8"), "truncated": False}


with TemporaryDirectory() as folder:
    output = Path(folder) / "usable.json"
    code = cli.main(["--url", URL, "--max-items", "10", "--output", str(output),
                     "--no-production-store"], fetcher=usable_fetcher)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_EVIDENCE_OBTAINED
    assert written["technical_completion"] is True and written["usable_evidence"] is True
    assert written["production_approved"] is False and written["production_store"] is False
    assert written["scheduler_action"] is None and written["request_count"] == 1

# I: shell-only and challenge results exit 2 with evidence.
def shell_fetcher(_url):
    return {"status": 200, "effective_url": "https://shop.tiktok.com/th/", "content_type": "text/html",
            "body": b"<html><title>TikTok Shop</title></html>", "truncated": False}


def challenge_fetcher(_url):
    return {"status": 403, "effective_url": URL, "content_type": "text/html",
            "body": b"access denied", "truncated": False}


with TemporaryDirectory() as folder:
    for name, fetcher in (("shell", shell_fetcher), ("challenge", challenge_fetcher)):
        output = Path(folder) / f"{name}.json"
        code = cli.main(["--url", URL, "--output", str(output), "--no-production-store"], fetcher=fetcher)
        written = json.loads(output.read_text(encoding="utf-8"))
        assert code == cli.EXIT_EVIDENCE_WITHHELD and written["technical_completion"] is True
        assert written["usable_evidence"] is False and written["production_store"] is False

# J: technical and option failures return 1 after writing evidence.
def failing_fetcher(_url):
    raise RuntimeError("controlled public transport failure")


with TemporaryDirectory() as folder:
    output = Path(folder) / "technical.json"
    code = cli.main(["--url", URL, "--output", str(output), "--no-production-store"], fetcher=failing_fetcher)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_TECHNICAL_FAILURE and written["technical_completion"] is False
    assert written["technical_failure"]["type"] == "RuntimeError"

with TemporaryDirectory() as folder:
    output = Path(folder) / "unsafe.json"
    code = cli.main(["--url", "https://example.com/product/12345678", "--output", str(output),
                     "--no-production-store"])
    assert code == cli.EXIT_TECHNICAL_FAILURE and output.exists()

# K: the official API boundary is explicit and immutable.
registry = json.loads((ROOT / "config" / "tiktok_shop_commerce_pulse_sources.json").read_text(encoding="utf-8"))
assert registry["official_api_boundary"]["national_public_marketplace_feed"] is False
assert registry["official_api_boundary"]["seller_creator_or_partner_authorization_required"] is True
assert registry["domain_boundary"]["production_approved"] is False
assert registry["domain_boundary"]["production_storage_enabled"] is False
assert registry["domain_boundary"]["scheduler_action"] is None

print("TikTok Shop Commerce Pulse deterministic tests passed (A-K).")
