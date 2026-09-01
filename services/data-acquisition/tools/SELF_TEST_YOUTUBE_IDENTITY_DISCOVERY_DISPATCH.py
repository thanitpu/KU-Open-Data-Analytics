"""Static and offline contract tests for the manual H12 dispatch harness."""
from __future__ import annotations
import json, sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))
sys.path.insert(0, str(ROOT / "tools"))
from LIVE_YOUTUBE_QDIVING_IDENTITY_DISCOVERY import AUTH_SCOPE, authorization, run

workflow = (ROOT.parent.parent / ".github/workflows/youtube-qdiving-identity-discovery.yml").read_text(encoding="utf-8")
for required in ("workflow_dispatch:", "contents: read", "persist-credentials: false", "secrets.KU2D_YOUTUBE_API_KEY",
                 "continuation_authorization_id", "integration/data-acquisition-platform", "if: always()"):
    assert required in workflow
for prohibited in ("schedule:", "push:", "pull_request:", "echo $KU2D_YOUTUBE_API_KEY", "printenv"):
    assert prohibited not in workflow

with TemporaryDirectory() as temp:
    root = Path(temp); decision = root / "KU2D-H-TEST.json"; output = root / "evidence.json"
    record = {"human_decision_id": "KU2D-H-TEST", "decision": "confirmed", "authorized_scope": AUTH_SCOPE}
    decision.write_text(json.dumps(record), encoding="utf-8")
    assert authorization(decision, "KU2D-H-TEST") == record
    assert run(output, decision, "KU2D-H-TEST") == 2
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["request_quota_ledger"]["request_count"] == 0
    assert evidence["credential_preflight"]["secret_read_or_logged"] is False
    assert evidence["boundaries"]["comments_acquired"] is False
    bad = dict(record); bad["authorized_scope"] = {"operation": "broadened"}
    decision.write_text(json.dumps(bad), encoding="utf-8")
    try: authorization(decision, "KU2D-H-TEST")
    except ValueError: pass
    else: raise AssertionError("broadened authorization accepted")

print("YouTube H12 manual dispatch deterministic tests passed (YIDW1-YIDW16).")
