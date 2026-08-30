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


def expect_isolation_failure(environ: dict, message: str):
    try:
        lifecycle.isolated_database_paths(environ)
    except RuntimeError:
        return
    raise AssertionError(message)


def write_case(path: Path, value):
    if value is None:
        return
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


with TemporaryDirectory() as td:
    temp = Path(td)
    production_db = temp / "production-approval.sqlite3"
    production_db.write_bytes(b"production-approval-sentinel")
    before = production_db.read_bytes()

    # Resolved isolation paths need not exist, but must be explicit, separate, scoped,
    # and entirely outside the service's default data tree.
    valid_isolation = {
        "KU2D_APPROVAL_SCOPE": "isolated-staging",
        "KU2D_OPERATIONS_DB": str(temp / "guards" / "ops.sqlite3"),
        "KU2D_OBSERVATION_DB": str(temp / "guards" / "obs.sqlite3"),
    }
    assert not Path(valid_isolation["KU2D_OPERATIONS_DB"]).exists()
    op_path, obs_path = lifecycle.isolated_database_paths(valid_isolation)
    assert op_path != obs_path
    expect_isolation_failure({**valid_isolation, "KU2D_APPROVAL_SCOPE": ""}, "missing scope must fail")
    expect_isolation_failure({**valid_isolation, "KU2D_APPROVAL_SCOPE": "production"}, "wrong scope must fail")
    expect_isolation_failure({k: v for k, v in valid_isolation.items() if k != "KU2D_OPERATIONS_DB"}, "missing operations path must fail")
    expect_isolation_failure({k: v for k, v in valid_isolation.items() if k != "KU2D_OBSERVATION_DB"}, "missing observation path must fail")
    expect_isolation_failure({**valid_isolation, "KU2D_OBSERVATION_DB": valid_isolation["KU2D_OPERATIONS_DB"]}, "identical paths must fail")
    service_data = ROOT / "data"
    expect_isolation_failure({**valid_isolation, "KU2D_OPERATIONS_DB": str(service_data / "ops.sqlite3")}, "direct operations default-data path must fail")
    expect_isolation_failure({**valid_isolation, "KU2D_OBSERVATION_DB": str(service_data / "obs.sqlite3")}, "direct observation default-data path must fail")
    expect_isolation_failure({**valid_isolation, "KU2D_OPERATIONS_DB": str(service_data / "nested" / "ops.sqlite3")}, "nested operations default-data path must fail")
    expect_isolation_failure({**valid_isolation, "KU2D_OBSERVATION_DB": str(service_data / "nested" / "obs.sqlite3")}, "nested observation default-data path must fail")

    # The Step Summary must always be appended before its evidence-validity exit code.
    valid_result = fixture(True)
    valid_summary = lifecycle.validation_summary(valid_result)
    summary_cases = [
        ("valid", valid_result, valid_summary, 0, None),
        ("missing-result", None, valid_summary, 1, "Missing evidence file"),
        ("missing-summary", valid_result, None, 1, "Missing evidence file"),
        ("corrupt-result", "{not-json", valid_summary, 1, "Corrupt evidence file"),
        ("corrupt-summary", valid_result, "{not-json", 1, "Corrupt evidence file"),
        ("nonobject-result", [], valid_summary, 1, "expected a JSON object"),
        ("nonobject-summary", valid_result, [], 1, "expected a JSON object"),
    ]
    for name, result_value, summary_value, expected_code, diagnostic in summary_cases:
        case_dir = temp / "step-summary" / name
        case_dir.mkdir(parents=True)
        result_path = case_dir / "result.json"
        summary_path = case_dir / "summary.json"
        output_path = case_dir / "github-step-summary.md"
        write_case(result_path, result_value)
        write_case(summary_path, summary_value)
        code = step_summary.main([
            "--result", str(result_path), "--summary", str(summary_path), "--output", str(output_path)
        ])
        assert code == expected_code, name
        written = output_path.read_text(encoding="utf-8")
        assert "JIB Retail Lifecycle Validation" in written, name
        if diagnostic:
            assert diagnostic in written, name
            assert "Treat this validation as a technical failure" in written, name

    env_keys = ("KU2D_APPROVAL_SCOPE", "KU2D_OPERATIONS_DB", "KU2D_OBSERVATION_DB", "KU2D_JIB_RESULT", "KU2D_JIB_SUMMARY")
    old_env = {key: os.environ.get(key) for key in env_keys}
    original_run = lifecycle.run_lifecycle
    original_write = lifecycle.write_evidence
    original_normalized_sources = lifecycle.normalized_sources
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

        def controlled_failure():
            raise RuntimeError("controlled technical failure")

        lifecycle.run_lifecycle = controlled_failure
        assert lifecycle.main(["--require-approved"]) == lifecycle.EXIT_TECHNICAL_FAILURE
        technical_detail = json.loads(Path(os.environ["KU2D_JIB_RESULT"]).read_text(encoding="utf-8"))
        technical_summary = json.loads(Path(os.environ["KU2D_JIB_SUMMARY"]).read_text(encoding="utf-8"))
        assert technical_detail["technical_failure"]["type"] == "RuntimeError"
        assert technical_detail["approved"] is False
        assert technical_summary["technical_completion"] is False
        assert technical_summary["approved"] is False

        lifecycle.run_lifecycle = original_run
        lifecycle.normalized_sources = lambda: []
        assert lifecycle.main(["--require-approved"]) == lifecycle.EXIT_TECHNICAL_FAILURE
        missing_detail = json.loads(Path(os.environ["KU2D_JIB_RESULT"]).read_text(encoding="utf-8"))
        missing_summary = json.loads(Path(os.environ["KU2D_JIB_SUMMARY"]).read_text(encoding="utf-8"))
        assert missing_detail["technical_failure"]["type"] == "RuntimeError"
        assert "SRC-018" in missing_detail["technical_failure"]["message"]
        assert "not found" in missing_detail["technical_failure"]["message"]
        assert missing_summary["technical_completion"] is False
        assert missing_summary["approved"] is False
        assert missing_summary["scheduler_action"] is None

        lifecycle.run_lifecycle = lambda: fixture(True)

        def fail_evidence_write(*args, **kwargs):
            raise OSError("controlled evidence write failure")

        lifecycle.write_evidence = fail_evidence_write
        assert lifecycle.main(["--require-approved"]) == lifecycle.EXIT_TECHNICAL_FAILURE
        assert production_db.read_bytes() == before, "isolated lifecycle policy test must not touch production approval state"
    finally:
        lifecycle.run_lifecycle = original_run
        lifecycle.write_evidence = original_write
        lifecycle.normalized_sources = original_normalized_sources
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
