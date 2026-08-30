from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import LIVE_JIB_RETAIL_LIFECYCLE as lifecycle
import WRITE_JIB_VALIDATION_STEP_SUMMARY as step_summary


def fixture(approved: bool) -> dict:
    domain_gates = {
        name: {"passed": approved, "value": value, "required": requirement}
        for name, value, requirement in (
            ("product_catalog_sample", 5 if approved else 2, ">=5 attributable products"),
            ("product_price_completeness", 100.0 if approved else 50.0, ">=85%"),
            ("product_semantic_quality", 100.0, ">=85%"),
            ("sellable_product_identity", 100.0 if approved else 50.0, ">=90%"),
            ("product_repeatability", 100.0, ">=70%"),
            ("provenance", 100.0, ">=95%"),
            ("assigned_technique_execution", 100.0, ">=80%"),
        )
    }
    failed = [] if approved else ["product_catalog_sample", "product_price_completeness", "sellable_product_identity"]
    return {
        "schema": "ku2d.retail-live-lifecycle.v1",
        "source_id": "SRC-018",
        "source_name": "JIB",
        "source_url": "https://www.jib.co.th/web/index.php",
        "domain": "IT Retail",
        "environment": "cloud-hosted-public-read-only",
        "started_at": "2026-08-30T00:00:00+00:00",
        "approved": approved,
        "continuous_enabled": approved,
        "approval_scope": "isolated-staging-db",
        "persisted_assignment": [
            {"technique": "generic_retail_detail_catalog", "label": "Canonical Retail Product Detail Catalog", "score": 70, "tracks": ["product_price"]},
            {"technique": "generic_app_bundle", "label": "JavaScript / App Bundle Mining", "score": 40, "tracks": ["discovery"]},
        ],
        "approval_track_policy": {
            "required": ["discovery", "product_price"],
            "optional": ["promotion"],
            "resolved": ["discovery", "product_price"] if approved else ["discovery"],
            "missing_required": [] if approved else ["product_price"],
        },
        "audit": {
            "audit_passed": approved,
            "hard_failures": failed,
            "quality_score": 95 if approved else 55,
            "quality_label": "strong" if approved else "weak",
            "domain_gate_checks": domain_gates,
            "domain_gate_failures": failed,
            "yield": {"products": 5 if approved else 2},
            "field_quality": {"product_price_pct": 100.0 if approved else 50.0, "product_semantic_quality_pct": 100.0, "provenance_pct": 100.0},
            "repeatability": {"product_repeatability_pct": 100.0},
            "technique_profile": {"fingerprint": "fixture-profile-fingerprint"},
            "sample_records": [
                {"record_type": "ProductCandidate", "sku": f"SKU-{index}", "price": 100 + index}
                for index in range(5 if approved else 2)
            ],
            "warnings": [],
        },
        "scheduler_plan_after_approval": ([{"decision": {"action": "scheduled-acquire"}}] if approved else None),
        "approval_withheld_reason": None if approved else "IT Retail domain gates failed.",
    }


assert lifecycle.resolve_exit_code(fixture(True), require_approved=True) == lifecycle.EXIT_OK
assert lifecycle.resolve_exit_code(fixture(False), require_approved=True) == lifecycle.EXIT_APPROVAL_WITHHELD
assert lifecycle.resolve_exit_code(fixture(False), require_approved=False) == lifecycle.EXIT_OK
assert lifecycle.resolve_exit_code({"technical_failure": {"type": "RuntimeError"}}, require_approved=True) == lifecycle.EXIT_TECHNICAL_FAILURE
inconsistent = fixture(True)
inconsistent["audit"]["domain_gate_failures"] = ["provenance"]
assert lifecycle.resolve_exit_code(inconsistent, require_approved=True) == lifecycle.EXIT_APPROVAL_WITHHELD

with TemporaryDirectory() as td:
    temp = Path(td)
    production_db = temp / "production-approval.sqlite3"
    production_db.write_bytes(b"production-approval-sentinel")
    before = production_db.read_bytes()

    env_keys = ("KU2D_APPROVAL_SCOPE", "KU2D_OPERATIONS_DB", "KU2D_OBSERVATION_DB", "KU2D_JIB_RESULT", "KU2D_JIB_SUMMARY")
    old_env = {key: os.environ.get(key) for key in env_keys}
    original_run = lifecycle.run_lifecycle
    try:
        os.environ["KU2D_APPROVAL_SCOPE"] = "isolated-staging"
        os.environ["KU2D_OPERATIONS_DB"] = str(temp / "isolated-ops.sqlite3")
        os.environ["KU2D_OBSERVATION_DB"] = str(temp / "isolated-obs.sqlite3")
        os.environ["KU2D_JIB_RESULT"] = str(temp / "jib-detail.json")
        os.environ["KU2D_JIB_SUMMARY"] = str(temp / "jib-summary.json")
        lifecycle.isolated_database_paths()

        lifecycle.run_lifecycle = lambda: fixture(False)
        code = lifecycle.main(["--require-approved"])
        assert code == lifecycle.EXIT_APPROVAL_WITHHELD
        assert Path(os.environ["KU2D_JIB_RESULT"]).is_file(), "withheld detailed evidence must be written before exit"
        assert Path(os.environ["KU2D_JIB_SUMMARY"]).is_file(), "withheld compact evidence must be written before exit"
        detail = json.loads(Path(os.environ["KU2D_JIB_RESULT"]).read_text(encoding="utf-8"))
        summary = json.loads(Path(os.environ["KU2D_JIB_SUMMARY"]).read_text(encoding="utf-8"))
        assert detail["approved"] is False
        assert summary["schema"] == "ku2d.retail-live-validation-summary.v1"
        assert summary["approved"] is False
        assert summary["technique_profile_fingerprint"] == "fixture-profile-fingerprint"
        assert summary["scheduler_action"] is None

        lifecycle.run_lifecycle = lambda: fixture(True)
        assert lifecycle.main(["--require-approved"]) == lifecycle.EXIT_OK
        approved_summary = json.loads(Path(os.environ["KU2D_JIB_SUMMARY"]).read_text(encoding="utf-8"))
        assert approved_summary["scheduler_action"] == "scheduled-acquire"
        rendered = step_summary.markdown(approved_summary, [])
        assert "APPROVED (isolated staging only)" in rendered
        assert "production Human Approve" in rendered
        missing, error = step_summary.load_json(temp / "missing.json")
        assert missing is None and "Missing evidence file" in error
        assert production_db.read_bytes() == before, "isolated lifecycle policy test must not touch production approval state"
    finally:
        lifecycle.run_lifecycle = original_run
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

workflow = (REPO / ".github" / "workflows" / "data-acquisition-jib-live.yml").read_text(encoding="utf-8")
assert "LIVE_JIB_RETAIL_LIFECYCLE.py --require-approved" in workflow
assert "name: Summarize JIB lifecycle validation\n        if: always()" in workflow
assert "name: Upload JIB lifecycle evidence\n        if: always()" in workflow
assert "jib-live-summary.json" in workflow

print("JIB authoritative lifecycle validation contract: PASS")
