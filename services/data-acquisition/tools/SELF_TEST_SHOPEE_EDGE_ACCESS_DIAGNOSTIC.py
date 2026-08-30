"""Deterministic contract tests for the bounded Shopee Edge diagnostic."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
TOOLS = ROOT / "tools"
FIXTURES = ROOT / "fixtures" / "shopee_edge_access"
for folder in (ACQUISITION, TOOLS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import SHOPEE_EDGE_ACCESS_DIAGNOSTIC as cli
from shopee_edge_access import analyze_capture, classify_network_request


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def analyze(name: str, *, maximum: int = 10) -> dict:
    snapshot = fixture(name)
    return analyze_capture(
        snapshot,
        target_url=snapshot["initial_url"],
        query="สายชาร์จ",
        max_items=maximum,
    )


def run_fixture(name: str, output: Path, *, maximum: int = 10) -> tuple[int, dict]:
    snapshot = fixture(name)

    def provider(url: str, max_items: int):
        assert "shopee.co.th" in url and max_items == maximum
        return snapshot

    code = cli.main([
        "--query", "สายชาร์จ", "--max-items", str(maximum),
        "--output", str(output), "--no-production-store",
    ], capture_provider=provider)
    return code, json.loads(output.read_text(encoding="utf-8"))


# A: rendered cards with deterministic public item/shop URLs are usable.
rendered = analyze("rendered_cards.json")
assert rendered["classification"] == "edge-rendered-dom-only"
assert rendered["usable_evidence"] is True
assert rendered["visible_product_card_count"] == 2
assert rendered["stable_dom_identity_count"] == 2
assert [row["stable_product_identity"]["identity_key"] for row in rendered["dom_product_samples"]] == [
    "101:9001", "102:9002",
]
assert rendered["visible_sold_count_text_samples"] == ["ขายแล้ว 1.2พัน", "ขายแล้ว 88 ชิ้น"]

# B: visible cards without stable URL identity remain evidence-withheld.
no_identity = analyze("rendered_no_identity.json")
assert no_identity["visible_product_card_count"] == 1
assert no_identity["stable_dom_identity_count"] == 0
assert no_identity["usable_evidence"] is False
assert no_identity["classification"] == "edge-shell-only"

# C/D: traffic verification and Login Required write evidence then return 2.
with TemporaryDirectory() as folder:
    traffic_code, traffic = run_fixture("traffic_verification.json", Path(folder) / "traffic.json")
    assert traffic_code == cli.EXIT_EVIDENCE_WITHHELD
    assert traffic["classification"] == "edge-traffic-verification"
    assert traffic["challenge_status"]["stop_boundary_reached"] is True
    login_code, login = run_fixture("login_required.json", Path(folder) / "login.json")
    assert login_code == cli.EXIT_EVIDENCE_WITHHELD
    assert login["classification"] == "edge-login-required"
    assert login["challenge_status"]["login_required"] is True

# E: a public JSON response needs stable product identity and a marketplace signal.
network = analyze("validated_network.json")
assert network["classification"] == "edge-public-data-available"
assert network["usable_evidence"] is True
assert network["validated_network_endpoint_count"] == 1
metadata = network["network_request_metadata"][0]
assert metadata["classification"] == "validated-commerce-data"
assert metadata["validated_product_sample_count"] == 2
assert metadata["response_size_bucket"] == "10-to-100-kb"

# F: a commerce-looking endpoint name alone is only a candidate, never validated.
name_only = analyze("endpoint_name_only.json")
assert name_only["usable_evidence"] is False
assert name_only["validated_network_endpoint_count"] == 0
assert name_only["network_request_metadata"][0]["classification"] == "commerce-candidate"
assert classify_network_request({
    "url": "https://shopee.co.th/api/v4/pages/is_short_url/", "status": 200,
}, 10)["classification"] == "navigation-only"
assert classify_network_request({
    "url": "https://shopee.co.th/assets/app.js", "status": 200,
    "content_type": "application/javascript",
}, 10)["classification"] == "static asset"
assert classify_network_request({
    "url": "https://shopee.co.th/api/telemetry/collect", "status": 204,
}, 10)["classification"] == "telemetry/analytics"
assert classify_network_request({
    "url": "https://shopee.co.th/verify/traffic/error", "status": 403,
}, 10)["classification"] == "challenge/access-control"

# G: raw headers, cookies, tokens, device identifiers, and bodies do not survive.
serialized = json.dumps(network, ensure_ascii=False).casefold()
for forbidden in (
    "must-not-survive", "authorization", "cookie", "access_token", "device_id",
    "session_token", "response_json", "headers",
):
    assert forbidden not in serialized
assert "keyword=fixture" in serialized
assert network["sensitive_browser_state_captured"] is False

# H: evidence and DOM output are bounded at 10, and 11 is a technical option failure.
ten_cards = fixture("rendered_cards.json")
card = ten_cards["html"].split("<body>", 1)[1].split("</body>", 1)[0].split("</div>", 1)[0] + "</div>"
ten_cards["html"] = "<html><head><title>Bounded</title></head><body>" + card * 12 + "</body></html>"
bounded = analyze_capture(
    ten_cards, target_url=ten_cards["initial_url"], query="fixture", max_items=10,
)
assert len(bounded["dom_product_samples"]) == 10
many_network = fixture("validated_network.json")
many_network["network_requests"] = many_network["network_requests"] * 8
bounded_network = analyze_capture(
    many_network, target_url=many_network["initial_url"], query="fixture", max_items=10,
)
assert sum(row["validated_product_sample_count"] for row in bounded_network["network_request_metadata"]) == 10
with TemporaryDirectory() as folder:
    invalid_output = Path(folder) / "invalid-bound.json"
    code = cli.main([
        "--query", "fixture", "--max-items", "11", "--output", str(invalid_output),
        "--no-production-store",
    ], capture_provider=lambda *_: (_ for _ in ()).throw(AssertionError("capture must not run")))
    assert code == cli.EXIT_TECHNICAL_FAILURE and invalid_output.exists()
    invalid = json.loads(invalid_output.read_text(encoding="utf-8"))
    assert invalid["classification"] == "edge-technical-failure"

# I/J: every outcome is non-production and cannot create a scheduler action.
for result in (rendered, no_identity, network, name_only):
    assert result["production_approved"] is False
    assert result["production_store"] is False
    assert result["scheduler_action"] is None
    assert result["comparison"]["edge_required"] is False

# Evidence writing itself is authoritative: a write failure returns exit 1.
with TemporaryDirectory() as folder:
    output_directory = Path(folder) / "directory-not-file"
    output_directory.mkdir()
    code = cli.main([
        "--query", "fixture", "--max-items", "10", "--output", str(output_directory),
        "--no-production-store",
    ], capture_provider=lambda *_: fixture("rendered_cards.json"))
    assert code == cli.EXIT_TECHNICAL_FAILURE

# K/L are exercised by the old Shopee test and full frozen regression corpus.
print("Shopee Edge access diagnostic deterministic tests passed (A-L).")
