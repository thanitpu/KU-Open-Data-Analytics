"""Static and offline contract tests for the manual H12 dispatch harness."""
from __future__ import annotations
import json, os, shutil, sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))
sys.path.insert(0, str(ROOT / "tools"))
from LIVE_YOUTUBE_QDIVING_IDENTITY_DISCOVERY import AUTH_SCOPE, authorization, classify_exit_code, run
import LIVE_YOUTUBE_QDIVING_IDENTITY_DISCOVERY as live_runner

workflow = (ROOT.parent.parent / ".github/workflows/youtube-qdiving-identity-discovery.yml").read_text(encoding="utf-8")
for required in ("workflow_dispatch:", "contents: read", "persist-credentials: false", "secrets.KU2D_YOUTUBE_API_KEY",
                 "continuation_authorization_id", "execution_revision", "authorization_record_revision",
                 "KU2D_AUTHORIZED_DECISION_ID",
                 "KU2D_AUTHORIZED_EXECUTION_REVISION", "REPLACE_WITH_REVIEWED_HUMAN_DECISION_ID",
                 "REPLACE_WITH_REVIEWED_40_CHAR_INTEGRATION_SHA", "KU2D_AUTHORIZATION_RECORD_REVISION",
                 "REPLACE_WITH_40_CHAR_DECISION_RECORD_SHA",
                 "ref: ${{ env.KU2D_AUTHORIZATION_RECORD_REVISION }}",
                 "ref: ${{ env.KU2D_AUTHORIZED_EXECUTION_REVISION }}",
                 "Stage exact authorization record without executing repository code",
                 "KU2D_STAGED_AUTHORIZATION_RECORD", "cp --", "chmod 600", "131072",
                 "Set up Python from reviewed execution revision",
                 "Install Data Acquisition dependencies from reviewed execution revision",
                 "Validate staged continuation authorization with reviewed execution code",
                 "Initialize sanitized evidence paths", "RUNNER_TEMP", "GITHUB_RUN_ID",
                 "set +e", "code=$?", "set -e", "if: always()"):
    assert required in workflow
for prohibited in ("schedule:", "push:", "pull_request:", "echo $KU2D_YOUTUBE_API_KEY", "printenv"):
    assert prohibited not in workflow
assert workflow.count("secrets.KU2D_YOUTUBE_API_KEY") == 1

with TemporaryDirectory() as temp:
    root = Path(temp)
    workspace = root / "workspace"
    runner_temp = root / "runner-temp"
    decision = workspace / "services/data-acquisition/coordination/v1/human-decisions/KU2D-H-000999.json"
    staged = runner_temp / "KU2D-H-000999.json"
    output = runner_temp / "evidence.json"
    revision = "a" * 40
    record = {"human_decision_id": "KU2D-H-000999", "decision": "confirmed", "authorized_scope": AUTH_SCOPE,
              "authorized_execution_revision": revision,
              "authorized_execution_branch": "integration/data-acquisition-platform"}
    decision.parent.mkdir(parents=True)
    runner_temp.mkdir()
    decision.write_text(json.dumps(record), encoding="utf-8")
    shutil.copyfile(decision, staged)
    shutil.rmtree(workspace)
    workspace.mkdir()
    workspace_decision = workspace / "services/data-acquisition/coordination/v1/human-decisions/KU2D-H-000999.json"
    assert not workspace_decision.exists()
    assert not staged.is_relative_to(workspace)
    assert staged.is_file() and authorization(staged, "KU2D-H-000999", revision) == record

    with patch.object(live_runner, "api_status", return_value={"configured": False}) as status_check:
        assert run(output, staged, "KU2D-H-000999", revision) == 2
    status_check.assert_called_once_with()
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["request_quota_ledger"]["request_count"] == 0
    assert evidence["credential_preflight"]["secret_read_or_logged"] is False
    assert evidence["boundaries"]["comments_acquired"] is False

    cases = []
    missing = runner_temp / "missing.json"
    cases.append(("missing staged record", missing, "KU2D-H-000999", revision))
    malformed = runner_temp / "malformed.json"; malformed.write_text("{", encoding="utf-8")
    cases.append(("malformed staged record", malformed, "KU2D-H-000999", revision))
    wrong_id = dict(record); wrong_id["human_decision_id"] = "KU2D-H-000998"
    wrong_id_path = runner_temp / "wrong-id.json"; wrong_id_path.write_text(json.dumps(wrong_id), encoding="utf-8")
    cases.append(("wrong decision ID", wrong_id_path, "KU2D-H-000999", revision))
    wrong_sha = dict(record); wrong_sha["authorized_execution_revision"] = "b" * 40
    wrong_sha_path = runner_temp / "wrong-sha.json"; wrong_sha_path.write_text(json.dumps(wrong_sha), encoding="utf-8")
    cases.append(("wrong execution SHA", wrong_sha_path, "KU2D-H-000999", revision))
    wrong_branch = dict(record); wrong_branch["authorized_execution_branch"] = "main"
    wrong_branch_path = runner_temp / "wrong-branch.json"; wrong_branch_path.write_text(json.dumps(wrong_branch), encoding="utf-8")
    cases.append(("wrong branch", wrong_branch_path, "KU2D-H-000999", revision))
    broadened = dict(record); broadened["authorized_scope"] = {"operation": "broadened"}
    broadened_path = runner_temp / "broadened.json"; broadened_path.write_text(json.dumps(broadened), encoding="utf-8")
    cases.append(("broadened scope", broadened_path, "KU2D-H-000999", revision))
    unconfirmed = dict(record); unconfirmed["decision"] = "withheld"
    unconfirmed_path = runner_temp / "unconfirmed.json"; unconfirmed_path.write_text(json.dumps(unconfirmed), encoding="utf-8")
    cases.append(("unconfirmed decision", unconfirmed_path, "KU2D-H-000999", revision))
    cases.append(("workspace path after replacement", workspace_decision, "KU2D-H-000999", revision))

    for index, (label, path, decision_id, requested_revision) in enumerate(cases):
        provider_boundary_calls = []
        def forbidden_status():
            provider_boundary_calls.append(label)
            raise AssertionError("provider boundary reached before authorization")
        negative_output = runner_temp / f"negative-{index}.json"
        with patch.object(live_runner, "api_status", side_effect=forbidden_status):
            try:
                run(negative_output, path, decision_id, requested_revision)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            else:
                raise AssertionError(f"{label} was accepted")
        assert provider_boundary_calls == [], f"{label} reached provider preflight"
        assert not negative_output.exists(), f"{label} wrote runtime evidence"

    for bad_revision in ("main", "A" * 40, "b" * 40):
        try: authorization(staged, "KU2D-H-000999", bad_revision)
        except ValueError: pass
        else: raise AssertionError("unbound or mutable execution revision accepted")

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
assert "^KU2D-H-[0-9]{6}$" in anchor_block
assert "KU2D_REQUESTED_EXECUTION_REVISION" in anchor_block and "KU2D_AUTHORIZED_EXECUTION_REVISION" in anchor_block
assert "KU2D_REQUESTED_AUTHORIZATION_ID" in anchor_block and "KU2D_AUTHORIZED_DECISION_ID" in anchor_block
assert "KU2D_REQUESTED_AUTHORIZATION_RECORD_REVISION" in anchor_block and "KU2D_AUTHORIZATION_RECORD_REVISION" in anchor_block
assert workflow.index("Validate immutable launcher trust anchors") < workflow.index("Checkout immutable authorization record revision")
authorization_checkout_block = workflow[workflow.index("Checkout immutable authorization record revision"):workflow.index("Checkout immutable reviewed execution revision")]
assert "Stage exact authorization record without executing repository code" in authorization_checkout_block
assert "$(git rev-parse HEAD)" in authorization_checkout_block
assert "RUNNER_TEMP" in authorization_checkout_block and "cp --" in authorization_checkout_block
assert "python" not in authorization_checkout_block.lower()
assert "pip install" not in authorization_checkout_block.lower()
assert "requirements.txt" not in authorization_checkout_block
assert workflow.index("Checkout immutable authorization record revision") < workflow.index("Stage exact authorization record without executing repository code")
assert workflow.index("Stage exact authorization record without executing repository code") < workflow.index("Checkout immutable reviewed execution revision")
assert workflow.index("Checkout immutable reviewed execution revision") < workflow.index("Set up Python from reviewed execution revision")
assert workflow.index("Set up Python from reviewed execution revision") < workflow.index("Install Data Acquisition dependencies from reviewed execution revision")
assert workflow.index("Install Data Acquisition dependencies from reviewed execution revision") < workflow.index("Validate staged continuation authorization with reviewed execution code")
assert workflow.index("Validate staged continuation authorization with reviewed execution code") < workflow.index("KU2D_YOUTUBE_API_KEY")
assert '--authorization-record "${KU2D_STAGED_AUTHORIZATION_RECORD}"' in run_block
assert "coordination/v1/human-decisions/${KU2D_AUTHORIZATION_ID}.json" not in run_block
assert "${{ runner.temp }}" not in workflow

print("YouTube H12 two-checkout dispatch deterministic tests passed (YIDW1-YIDW72).")
