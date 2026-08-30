"""Deterministic contract tests for bounded Lazada normal-browser evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
TOOLS = ROOT / "tools"
FIXTURES = ROOT / "fixtures" / "lazada_browser_access"
for folder in (ACQUISITION, TOOLS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import LAZADA_BROWSER_ACCESS_DIAGNOSTIC as cli
from lazada_browser_access import analyze_capture, classify_network_request, stable_product_identity


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def analyze(name: str, maximum: int = 10) -> dict:
    snapshot = fixture(name)
    return analyze_capture(
        snapshot, target_url=snapshot["initial_url"], query="สายชาร์จ", max_items=maximum,
    )


def run_fixture(name: str, output: Path, maximum: int = 10) -> tuple[int, dict]:
    snapshot = fixture(name)

    def provider(url: str, max_items: int):
        assert "lazada.co.th" in url and max_items == maximum
        return snapshot

    code = cli.main([
        "--query", "สายชาร์จ", "--max-items", str(maximum),
        "--output", str(output), "--no-production-store",
    ], capture_provider=provider)
    return code, json.loads(output.read_text(encoding="utf-8"))


# A: actual rendered DOM with canonical Lazada item URLs is usable.
html_snapshot = {
    "observed_at": "2026-08-31T01:00:00+00:00",
    "initial_url": "https://www.lazada.co.th/catalog/?q=fixture",
    "final_url": "https://www.lazada.co.th/tag/fixture/?q=fixture",
    "title": "Rendered DOM fixture",
    "html": """<html><body>
      <div data-qa-locator='product-item' data-item-id='100001'>
        <a href='https://www.lazada.co.th/products/cable-i100001-s200001.html' title='Cable'>
          <span>฿159.00</span><span>รีวิว 12</span><span>ขายแล้ว 88 ชิ้น</span>
        </a>
      </div></body></html>""",
    "network_requests": [],
}
html_result = analyze_capture(
    html_snapshot, target_url=html_snapshot["initial_url"], query="fixture", max_items=10,
)
assert html_result["classification"] == "lazada-rendered-dom-only"
assert html_result["usable_evidence"] is True
assert html_result["stable_dom_identity_count"] == 1
assert html_result["dom_product_samples"][0]["stable_product_identity"]["platform_product_id"] == "100001"

# B: a visible card without stable identity remains evidence-withheld.
no_identity = analyze("rendered_no_identity.json")
assert no_identity["visible_product_card_count"] == 1
assert no_identity["stable_dom_identity_count"] == 0
assert no_identity["usable_evidence"] is False
assert no_identity["classification"] == "lazada-shell-only"

# C: contradictory URL and explicit item IDs are rejected.
contradictory = analyze("contradictory_identity.json")
assert contradictory["stable_dom_identity_count"] == 0
assert contradictory["usable_evidence"] is False
assert stable_product_identity(
    "https://www.lazada.co.th/products/x-i100001.html", explicit_id="999999",
) is None

# D/E/F: reviews stay independent, order labels stay orders, and explicit
# currency strings normalize conservatively.
rendered = analyze("rendered_cards.json")
assert rendered["classification"] == "lazada-rendered-dom-only"
assert rendered["usable_evidence"] is True
assert rendered["visible_product_card_count"] == 2
sold, orders = rendered["dom_product_samples"]
assert sold["visible_rating_or_review_text"] == "รีวิว 412"
assert sold["marketplace_counter"]["counter_type"] == "sold"
assert sold["marketplace_counter"]["observed_sold_count"] == 1200
assert orders["visible_rating_or_review_text"] == "review 30"
assert orders["marketplace_counter"]["counter_type"] == "orders"
assert orders["marketplace_counter"]["observed_sold_count"] is None
assert sold["normalized_price"] == 159.0 and orders["normalized_price"] == 299.0
assert sold["price_semantics"] == "explicit-currency-display"
ordinary_header = fixture("rendered_cards.json")
ordinary_header["visible_page_text"] += " ลงชื่อเข้าใช้ สมัครสมาชิก"
ordinary_result = analyze_capture(
    ordinary_header, target_url=ordinary_header["initial_url"], query="fixture", max_items=10,
)
assert ordinary_result["classification"] == "lazada-rendered-dom-only"
ambiguous_piece = analyze_capture({
    **fixture("rendered_cards.json"),
    "visible_cards": [{
        "product_url": "https://www.lazada.co.th/products/pdp-i100009.html",
        "explicit_product_id": "100009", "visible_title": "Ambiguous pieces",
        "visible_text": "Ambiguous pieces ฿25.00 5.5K ชิ้น (714)",
    }],
}, target_url="https://www.lazada.co.th/catalog/?q=fixture", query="fixture", max_items=10)
ambiguous_counter = ambiguous_piece["dom_product_samples"][0]["marketplace_counter"]
assert ambiguous_counter["raw_display"] == "5.5K ชิ้น"
assert ambiguous_counter["counter_type"] == "unknown"
assert ambiguous_counter["observed_sold_count"] is None

# G/I: unscaled structured price stays raw/unknown; identity plus a signal is
# required before a public response becomes validated-commerce-data.
network = analyze("validated_network.json")
assert network["classification"] == "lazada-public-data-available"
assert network["validated_network_endpoint_count"] == 1
metadata = network["network_request_metadata"][0]
assert metadata["classification"] == "validated-commerce-data"
assert metadata["validated_product_sample_count"] == 2
numeric_price = next(
    row for row in metadata["validated_product_samples"]
    if row["platform_product_id"] == "100002"
)
assert numeric_price["visible_or_structured_price"] is None
assert numeric_price["raw_price"] == 15900
assert numeric_price["price_semantics"] == "raw-structured-value-scaling-unknown"

# H: endpoint naming alone is insufficient.
name_only = analyze("endpoint_name_only.json")
assert name_only["usable_evidence"] is False
assert name_only["validated_network_endpoint_count"] == 0
assert name_only["network_request_metadata"][0]["classification"] == "commerce-candidate"
assert classify_network_request({
    "url": "https://www.lazada.co.th/user/api/loginByToken", "status": 200,
}, 10)["classification"] == "account-or-auth-non-commerce"

# J: login and traffic verification both write evidence before exit 2.
with TemporaryDirectory() as folder:
    login_code, login = run_fixture("login_required.json", Path(folder) / "login.json")
    traffic_code, traffic = run_fixture("traffic_verification.json", Path(folder) / "traffic.json")
    assert login_code == cli.EXIT_EVIDENCE_WITHHELD
    assert login["classification"] == "lazada-login-required"
    assert login["challenge_status"]["stop_boundary_reached"] is True
    assert traffic_code == cli.EXIT_EVIDENCE_WITHHELD
    assert traffic["classification"] == "lazada-traffic-verification"
    assert traffic["challenge_status"]["stop_boundary_reached"] is True

# K: raw response bodies, headers, cookies, and sensitive query values never
# survive the analyzer.
serialized = json.dumps(network, ensure_ascii=False).casefold()
for forbidden in (
    "must-not-survive", "authorization", "cookie", "access_token",
    "response_json", "headers", "device_id", "session_token",
):
    assert forbidden not in serialized
assert network["sensitive_browser_state_captured"] is False

# L: output is bounded to 10; max-items 11 is a technical option failure with
# evidence written before exit 1.
many = fixture("rendered_cards.json")
many["visible_cards"] = many["visible_cards"] * 6
bounded = analyze_capture(many, target_url=many["initial_url"], query="fixture", max_items=10)
assert len(bounded["dom_product_samples"]) == 10
with TemporaryDirectory() as folder:
    output = Path(folder) / "invalid.json"
    code = cli.main([
        "--query", "fixture", "--max-items", "11", "--output", str(output),
        "--no-production-store",
    ], capture_provider=lambda *_: (_ for _ in ()).throw(AssertionError("capture must not run")))
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_TECHNICAL_FAILURE
    assert evidence["classification"] == "lazada-technical-failure"

# M/N: all outcomes are hard-coded non-production with no scheduler action.
for result in (html_result, no_identity, contradictory, rendered, network, name_only):
    assert result["production_approved"] is False
    assert result["production_store"] is False
    assert result["scheduler_action"] is None
    assert result["comparison"]["edge_required"] is False

# Evidence-writing failure is authoritative.
with TemporaryDirectory() as folder:
    output_directory = Path(folder) / "directory-not-file"
    output_directory.mkdir()
    code = cli.main([
        "--query", "fixture", "--max-items", "10", "--output", str(output_directory),
        "--no-production-store",
    ], capture_provider=lambda *_: fixture("rendered_cards.json"))
    assert code == cli.EXIT_TECHNICAL_FAILURE

# O/P are exercised by the Lazada Explore test and complete frozen corpus; keep
# an explicit adjacent-policy guard here as well.
shopee = json.loads((ROOT / "config" / "shopee_commerce_pulse_sources.json").read_text(encoding="utf-8"))
assert shopee["bounded_access_audit"]["public_unauthenticated_acquisition_status"] == "PAUSED"
lazada = json.loads((ROOT / "config" / "lazada_commerce_pulse_sources.json").read_text(encoding="utf-8"))
browser_pilot = lazada["bounded_browser_pilot"]
assert browser_pilot["classification"] == "lazada-rendered-dom-only"
assert browser_pilot["stable_identity_sample_count"] == 10
assert browser_pilot["visible_item_counter_semantics"].startswith("bare Thai ชิ้น")
assert browser_pilot["windows_edge_required_for_rendered_dom_evidence"] is False
assert browser_pilot["production_approved"] is False
assert browser_pilot["production_store"] is False
assert browser_pilot["scheduler_action"] is None
youtube = json.loads((ROOT / "config" / "youtube_api_policy.json").read_text(encoding="utf-8"))
assert youtube["comments_enabled"] is False
assert youtube["production_scheduling_enabled"] is False

print("Lazada browser access diagnostic deterministic tests passed (A-P).")
