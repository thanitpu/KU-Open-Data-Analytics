"""Static and offline contract tests for the manual H12 dispatch harness."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))
sys.path.insert(0, str(ROOT / "tools"))
from LIVE_YOUTUBE_QDIVING_IDENTITY_DISCOVERY import AUTH_SCOPE, authorization, classify_exit_code, run

workflow = (ROOT.parent.parent / ".github/workflows/youtube-qdiving-identity-discovery.yml").read_text(encoding="utf-8")
for required in ("workflow_dispatch:", "contents: read", "persist-credentials: false", "secrets.KU2D_YOUTUBE_API_KEY",
                 "continuation_authorization_id", "execution_revision", "authorization_record_revision",
                 "KU2D_AUTHORIZED_DECISION_ID",
                 "KU2D_AUTHORIZED_EXECUTION_REVISION", "REPLACE_WITH_REVIEWED_HUMAN_DECISION_ID",
                 "REPLACE_WITH_REVIEWED_40_CHAR_INTEGRATION_SHA", "KU2D_AUTHORIZATION_RECORD_REVISION",
                 "REPLACE_WITH_40_CHAR_DECISION_RECORD_SHA",
                 "ref: ${{ env.KU2D_AUTHORIZATION_RECORD_REVISION }}",
                 "ref: ${{ env.KU2D_AUTHORIZED_EXECUTION_REVISION }}",
                 "set +e", "code=$?", "set -e", "if: always()"):
    assert required in workflow
for prohibited in ("schedule:", "push:", "pull_request:", "echo $KU2D_YOUTUBE_API_KEY", "printenv"):
    assert prohibited not in workflow
assert workflow.count("secrets.KU2D_YOUTUBE_API_KEY") == 1

with TemporaryDirectory() as temp:
    root = Path(temp); decision = root / "KU2D-H-TEST.json"; output = root / "evidence.json"
    revision = "a" * 40
    record = {"human_decision_id": "KU2D-H-TEST", "decision": "confirmed", "authorized_scope": AUTH_SCOPE,
              "authorized_execution_revision": revision,
              "authorized_execution_branch": "integration/data-acquisition-platform"}
    decision.write_text(json.dumps(record), encoding="utf-8")
    assert authorization(decision, "KU2D-H-TEST", revision) == record
    with patch.dict(os.environ, {"KU2D_YOUTUBE_API_KEY": ""}):
        assert run(output, decision, "KU2D-H-TEST", revision) == 2
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["request_quota_ledger"]["request_count"] == 0
    assert evidence["credential_preflight"]["secret_read_or_logged"] is False
    assert evidence["boundaries"]["comments_acquired"] is False
    bad = dict(record); bad["authorized_scope"] = {"operation": "broadened"}
    decision.write_text(json.dumps(bad), encoding="utf-8")
    try: authorization(decision, "KU2D-H-TEST", revision)
    except ValueError: pass
    else: raise AssertionError("broadened authorization accepted")
    decision.write_text(json.dumps(record), encoding="utf-8")
    for bad_revision in ("main", "A" * 40, "b" * 40):
        try: authorization(decision, "KU2D-H-TEST", bad_revision)
        except ValueError: pass
        else: raise AssertionError("unbound or mutable execution revision accepted")
    wrong_branch = dict(record); wrong_branch["authorized_execution_branch"] = "main"
    decision.write_text(json.dumps(wrong_branch), encoding="utf-8")
    try: authorization(decision, "KU2D-H-TEST", revision)
    except ValueError: pass
    else: raise AssertionError("non-integration execution authority accepted")

assert classify_exit_code(0) == {"outcome": "candidate-evidence-obtained", "step_success": True}
assert classify_exit_code(2) == {"outcome": "evidence-withheld", "step_success": True}
assert classify_exit_code(1) == {"outcome": "technical-failure", "step_success": False}
assert classify_exit_code(17) == {"outcome": "technical-failure", "step_success": False}

run_block = workflow[workflow.index("set +e"):workflow.index("Write sanitized Step Summary")]
assert run_block.index("set +e") < run_block.index("python tools/LIVE_YOUTUBE") < run_block.index("code=$?") < run_block.index("set -e")
assert "if [ \"$code\" = 2 ]; then" in run_block and "exit 0" in run_block
assert "outcome=technical-failure" in run_block and 'exit "$code"' in run_block
assert "Upload sanitized identity evidence" in workflow and "if: always()" in workflow
anchor_block = workflow[workflow.index("Validate immutable launcher trust anchors"):workflow.index("Checkout immutable authorization record revision")]
assert "^[0-9a-f]{40}$" in anchor_block
assert "KU2D_REQUESTED_EXECUTION_REVISION" in anchor_block and "KU2D_AUTHORIZED_EXECUTION_REVISION" in anchor_block
assert "KU2D_REQUESTED_AUTHORIZATION_ID" in anchor_block and "KU2D_AUTHORIZED_DECISION_ID" in anchor_block
assert "KU2D_REQUESTED_AUTHORIZATION_RECORD_REVISION" in anchor_block and "KU2D_AUTHORIZATION_RECORD_REVISION" in anchor_block
assert workflow.index("Validate immutable launcher trust anchors") < workflow.index("Checkout immutable authorization record revision")
assert workflow.index("Checkout immutable authorization record revision") < workflow.index("Validate exact continuation authorization")
assert workflow.index("Validate exact continuation authorization") < workflow.index("Checkout immutable reviewed execution revision")
assert workflow.index("Checkout immutable reviewed execution revision") < workflow.index("KU2D_YOUTUBE_API_KEY")

print("YouTube H12 manual dispatch deterministic tests passed (YIDW1-YIDW45).")
