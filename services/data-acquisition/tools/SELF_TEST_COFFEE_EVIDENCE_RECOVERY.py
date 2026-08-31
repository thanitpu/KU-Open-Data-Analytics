"""Deterministic tests for the bounded Coffee evidence-recovery package."""
from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from coffee_evidence_recovery import build_result, normalize_product_detail, validate_package


spec = importlib.util.spec_from_file_location("live_coffee_recovery", ROOT / "tools" / "LIVE_COFFEE_EVIDENCE_RECOVERY.py")
cli = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(cli)

PACKAGE_PATH = ROOT / "config" / "coffee_evidence_recovery_package.json"
FIXTURES = ROOT / "fixtures" / "coffee_evidence_recovery"
package = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
validated = validate_package(package)

# CER1-CER4: the package has exact authorization, targets, and immutable budget.
assert validated["authorization"]["human_decision_id"] == "KU2D-H-000009"
assert validated["rerun_authorization"]["prompt_id"] == "KU2D-P-000027"
assert validated["rerun_authorization"]["human_decision_id"] == "KU2D-H-000010"
assert {target["source_id"] for target in validated["targets"]} == {"roots_coffee", "nana_coffee_roasters"}
assert validated["request_budget"]["maximum_acquisition_attempts"] == 4
assert validated["request_budget"]["retries"] == validated["request_budget"]["pagination"] == 0

roots_target, nana_target = validated["targets"]
roots_html = (FIXTURES / "roots_product.html").read_text(encoding="utf-8")
nana_html = (FIXTURES / "nana_product.html").read_text(encoding="utf-8")
observed = "2026-08-31T10:00:00+00:00"

# CER5-CER12: strict official-detail normalization retains field provenance.
roots = normalize_product_detail(roots_html, roots_target, final_url=roots_target["url"], observed_at=observed)
assert roots["record"]["coffee_product_id"] == "shop.rootsbkk.com:house-blend-coffee"
assert roots["record"]["price"] == 450.0 and roots["record"]["currency"] == "THB"
assert roots["record"]["origin"] == "Pangkhon Village, Chiang Rai"
assert roots["record"]["process"] == "Honey Process and Kenya-style Washed Process"
assert roots["record"]["package_size"] == "500 g"
assert roots["field_provenance"]["price"]["extraction_path"] == "meta[product:price:amount]"
assert roots["sanitized_response"]["raw_html_retained"] is False
assert roots["sanitized_response"]["headers_retained"] is False

nana = normalize_product_detail(nana_html, nana_target, final_url=nana_target["url"], observed_at=observed)
assert nana["record"]["price"] == 470.0 and nana["record"]["availability"] == "InStock"
assert nana["field_provenance"]["price"]["extraction_path"] == "jsonld.Product.offers.price"

# CER13-CER14: menu semantics and non-official identity fail closed.
menu = roots_html.replace("House Blend Coffee", "Hot Latte").replace("Origin: Pangkhon Village, Chiang Rai", "")
menu_target = deepcopy(roots_target)
menu_target["url"] = "https://shop.rootsbkk.com/menu/hot-latte"
menu_result = normalize_product_detail(menu, menu_target, final_url=menu_target["url"], observed_at=observed)
assert menu_result["record"] is None
try:
    normalize_product_detail(roots_html, roots_target, final_url="https://example.com/products/house-blend", observed_at=observed)
    raise AssertionError("outside-host URL was accepted")
except ValueError:
    pass


class Clock:
    def __init__(self):
        self.index = 0

    def __call__(self):
        self.index += 1
        return f"2026-08-31T10:00:{self.index:02d}+00:00"


# CER15-CER22: real main flow writes the request ledger before every fake request,
# obtains four retained observations, passes Deep Audit, and exits 0.
with TemporaryDirectory() as folder:
    output = Path(folder) / "coffee.json"
    calls = []

    def successful_provider(target, budget, attempt_index):
        pending = json.loads(output.read_text(encoding="utf-8"))
        assert pending["run_state"] == "request-ledger-written-before-network"
        assert pending["observations"][-1]["acquisition_attempted"] is False
        calls.append((target["source_id"], attempt_index))
        html = roots_html if target["source_id"] == "roots_coffee" else nana_html
        return {
            "transport_completed": True, "transport_requests": 1, "http_status": 200,
            "final_url": target["url"], "content_type": "text/html; charset=utf-8",
            "response_bytes_read": len(html.encode("utf-8")), "redirect_chain": [],
            "access_boundary": None, "body": html,
        }

    code = cli.main([
        "--package", str(PACKAGE_PATH), "--output", str(output), "--no-production-store",
    ], fetch_provider=successful_provider, clock=Clock())
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_EVIDENCE_OBTAINED
    assert calls == [("roots_coffee", 1), ("roots_coffee", 2), ("nana_coffee_roasters", 1), ("nana_coffee_roasters", 2)]
    assert evidence["technical_completion"] is True and evidence["usable_candidate_evidence"] is True
    assert evidence["deep_audit"]["audit_passed"] is True and evidence["deep_audit"]["hard_failures"] == []
    assert evidence["request_accounting"]["acquisition_attempts"] == 4
    assert evidence["request_accounting"]["transport_requests"] == 4
    assert all(row["sanitized_response"]["raw_html_retained"] is False for row in evidence["observations"])
    assert all(row["record"]["production_approved"] is False for row in evidence["observations"])
    assert evidence["authority"]["candidate_promoted"] is False
    assert evidence["boundaries"]["scheduler_action"] is None

# CER23-CER28: an unusable first observation stops only that source. The next
# source may make its second observation only after yielding a strict record.
with TemporaryDirectory() as folder:
    output = Path(folder) / "staged-stop.json"
    calls = []

    def staged_provider(target, budget, attempt_index):
        pending = json.loads(output.read_text(encoding="utf-8"))
        assert pending["run_state"] == "request-ledger-written-before-network"
        assert pending["observations"][-1]["acquisition_attempted"] is False
        calls.append((target["source_id"], attempt_index))
        html = "<html><title>About our cafe</title><p>Welcome</p></html>" if target["source_id"] == "roots_coffee" else nana_html
        return {
            "transport_completed": True, "transport_requests": 1, "http_status": 200,
            "final_url": target["url"], "content_type": "text/html; charset=utf-8",
            "response_bytes_read": len(html.encode("utf-8")), "redirect_chain": [],
            "access_boundary": None, "body": html,
        }

    code = cli.main([
        "--package", str(PACKAGE_PATH), "--output", str(output), "--no-production-store",
    ], fetch_provider=staged_provider, clock=Clock())
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_EVIDENCE_WITHHELD
    assert calls == [("roots_coffee", 1), ("nana_coffee_roasters", 1), ("nana_coffee_roasters", 2)]
    assert evidence["request_accounting"]["acquisition_attempts"] == 3
    roots_rows = [row for row in evidence["observations"] if row["source_id"] == "roots_coffee"]
    nana_rows = [row for row in evidence["observations"] if row["source_id"] == "nana_coffee_roasters"]
    assert len(roots_rows) == 1 and roots_rows[0]["record"] is None
    assert len(nana_rows) == 2 and all(isinstance(row["record"], dict) for row in nana_rows)

# CER29-CER32: access evidence is durably written, exits 2, and is not called a parser failure.
with TemporaryDirectory() as folder:
    output = Path(folder) / "withheld.json"

    def access_provider(target, budget, attempt_index):
        if target["source_id"] == "roots_coffee":
            return {
                "transport_completed": True, "transport_requests": 1, "http_status": 403,
                "final_url": target["url"], "content_type": "text/html", "response_bytes_read": 100,
                "redirect_chain": [], "access_boundary": "http_status_403", "body": "Access denied",
            }
        html = nana_html
        return {
            "transport_completed": True, "transport_requests": 1, "http_status": 200,
            "final_url": target["url"], "content_type": "text/html", "response_bytes_read": len(html),
            "redirect_chain": [], "access_boundary": None, "body": html,
        }

    code = cli.main(["--output", str(output), "--no-production-store"], fetch_provider=access_provider, clock=Clock())
    withheld = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_EVIDENCE_WITHHELD
    assert withheld["technical_completion"] is True and withheld["usable_candidate_evidence"] is False
    assert withheld["observations"][0]["access_boundary"] == "http_status_403"
    assert withheld["observations"][0]["normalization_failure_reason"].startswith("extraction not attempted")

# CER33-CER35: transport failure is written before exit 1.
with TemporaryDirectory() as folder:
    output = Path(folder) / "technical.json"

    def failing_provider(target, budget, attempt_index):
        raise RuntimeError("controlled network failure")

    code = cli.main(["--output", str(output), "--no-production-store"], fetch_provider=failing_provider, clock=Clock())
    technical = json.loads(output.read_text(encoding="utf-8"))
    assert code == cli.EXIT_TECHNICAL_FAILURE
    assert technical["technical_completion"] is False
    assert technical["observations"][0]["technical_failure"]["type"] == "RuntimeError"

# CER36-CER39: missing safety flag, impossible evidence path, budget drift, and
# rerun-authorization drift fail.
assert cli.main(["--output", "unused.json"], fetch_provider=lambda *_: None) == cli.EXIT_TECHNICAL_FAILURE
with TemporaryDirectory() as folder:
    parent_file = Path(folder) / "not-a-directory"
    parent_file.write_text("x", encoding="utf-8")
    assert cli.main(["--output", str(parent_file / "evidence.json"), "--no-production-store"], fetch_provider=lambda *_: None) == cli.EXIT_TECHNICAL_FAILURE
drifted = deepcopy(package)
drifted["request_budget"]["maximum_acquisition_attempts"] = 5
try:
    validate_package(drifted)
    raise AssertionError("request budget drift was accepted")
except ValueError:
    pass
drifted = deepcopy(package)
drifted["rerun_authorization"]["human_decision_id"] = "KU2D-H-000009"
try:
    validate_package(drifted)
    raise AssertionError("rerun authorization drift was accepted")
except ValueError:
    pass

# CER40-CER42: script-only captcha words do not create a false boundary, while
# explicit visible challenges and access status do.
assert cli._access_marker(200, "<script>const captcha='optional';</script><h1>House Blend Coffee</h1>") == (None, None)
visible_boundary, visible_evidence = cli._access_marker(200, "<title>Verify you are human</title>")
assert visible_boundary == "captcha_or_human_verification" and visible_evidence["evidence_path"] == "document-title"
status_boundary, status_evidence = cli._access_marker(403, "")
assert status_boundary == "http_status_403" and status_evidence["confidence"] == "explicit"

# CER43: a price deviation is temporal evidence and does not invent a transaction price.
observations = []
for index, price in enumerate((450.0, 460.0), 1):
    row = {
        "source_id": "roots_coffee", "source": "Roots Coffee", "attempt_index": index,
        "acquisition_attempted": True, "transport_completed": True, "transport_requests": 1,
        "record": deepcopy(roots["record"]), "field_provenance": deepcopy(roots["field_provenance"]),
    }
    row["record"]["price"] = price
    observations.append(row)
for index in (1, 2):
    observations.append({
        "source_id": "nana_coffee_roasters", "source": "Nana Coffee Roasters", "attempt_index": index,
        "acquisition_attempted": True, "transport_completed": True, "transport_requests": 1,
        "record": deepcopy(nana["record"]), "field_provenance": deepcopy(nana["field_provenance"]),
    })
deviant = build_result(package, observations, completed_at=observed)
roots_audit = next(row for row in deviant["deep_audit"]["source_audits"] if row["source_id"] == "roots_coffee")
assert roots_audit["deviations"][0]["interpretation"] == "temporal display deviation; transaction price not inferred"

# CER44-CER55: the retained live artifact is bounded, non-authorizing, and
# honest about the first detector's screening-only stop classification.
live_path = ROOT.parents[1] / "docs" / "validation" / "coffee-evidence-recovery-2026-08-31.json"
live = json.loads(live_path.read_text(encoding="utf-8"))
assert live["schema"] == "ku2d.coffee-evidence-recovery.v1"
assert live["classification"] == "evidence_withheld"
assert live["technical_completion"] is True and live["usable_candidate_evidence"] is False
assert live["request_accounting"]["acquisition_attempts"] == live["request_accounting"]["transport_requests"] == 2
assert live["request_accounting"]["retries"] == live["request_accounting"]["pagination"] == 0
assert {row["source_id"] for row in live["observations"]} == {"roots_coffee", "nana_coffee_roasters"}
assert all(row["access_boundary_evidence"]["challenge_not_independently_confirmed"] is True for row in live["observations"])
assert all(row["record"] is None and not row["field_provenance"] for row in live["observations"])
assert live["deep_audit"]["audit_passed"] is False
assert live["authority"]["candidate_promoted"] is False
assert live["boundaries"]["production_approved"] is live["boundaries"]["production_store"] is False
assert live["boundaries"]["scheduler_action"] is None and live["boundaries"]["knowledge_mutation"] is False

print("Coffee evidence recovery deterministic tests passed (CER1-CER55).")
