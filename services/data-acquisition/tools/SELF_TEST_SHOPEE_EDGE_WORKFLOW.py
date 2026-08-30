"""Static contract checks for the manual Shopee Windows Edge workflow."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "shopee-edge-access-diagnostic.yml"
EDGE_WORKFLOW = ROOT / ".github" / "workflows" / "data-acquisition-edge-live.yml"
SETUP = ROOT / "services" / "data-acquisition" / "tools" / "SETUP_KU2D_EDGE_RUNNER_WINDOWS.ps1"

text = WORKFLOW.read_text(encoding="utf-8")
edge_workflow = EDGE_WORKFLOW.read_text(encoding="utf-8")
setup = SETUP.read_text(encoding="utf-8")

# A/H: the workflow has exactly a manual trigger, without push, PR, or schedule.
trigger = text.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
assert "workflow_dispatch:" in trigger
for forbidden_trigger in ("push:", "pull_request:", "schedule:"):
    assert forbidden_trigger not in trigger

# B: use GitHub's default Windows/x64 labels plus only repository-evidenced
# custom acquisition/location labels.
labels = "runs-on: [self-hosted, Windows, X64, ku2d-acquisition, thailand]"
assert labels in text
assert "runs-on: [self-hosted, ku2d-acquisition, windows, thailand]" in edge_workflow
assert "actions-runner-win-x64" in setup
for configured_label in ("ku2d-acquisition", "thailand", "windows"):
    assert configured_label in setup

# Inputs are constrained to the first reviewed query and bounded item count.
assert re.search(r"(?m)^      query:\s*$", trigger)
assert "default: 'สายชาร์จ'" in trigger
assert re.search(r"(?m)^      max_items:\s*$", trigger)
assert "default: '10'" in trigger
assert not re.search(r"(?m)^      url:\s*$", trigger)

# C: both PowerShell and Python enforce the 1-10 bound before browser launch.
assert "[int]::TryParse" in text
assert "$maxItems -lt 1 -or $maxItems -gt 10" in text
assert "--max-items '${{ steps.preflight.outputs.max_items }}'" in text

diagnostic_block = text.split("- name: Run one bounded Shopee Edge diagnostic", 1)[1].split(
    "- name: Write diagnostic step summary", 1
)[0]
assert diagnostic_block.count("tools/SHOPEE_EDGE_ACCESS_DIAGNOSTIC.py") == 1

# D/E/I: the live invocation is non-production and receives no secret or access state.
assert "--no-production-store" in diagnostic_block
assert "${{ secrets." not in text
for forbidden_argument in ("--proxy", "--cookie", "--login", "--session", "--profile", "--url"):
    assert forbidden_argument not in diagnostic_block.casefold()

# F: exit 2 is an evidence-withheld diagnostic success; technical codes fail.
assert "if ($diagnosticExit -eq 0)" in diagnostic_block
assert "if ($diagnosticExit -eq 2)" in diagnostic_block
assert "execution_outcome=evidence-withheld" in diagnostic_block
assert "not a technical workflow failure" in diagnostic_block
assert "throw \"Shopee Edge diagnostic failed technically" in diagnostic_block

# G: only the external sanitized JSON is eligible for short-lived upload.
assert "KU2D_EVIDENCE_PATH: C:\\KU2D-Runtime\\commerce\\shopee-edge-${{ github.run_id }}.json" in text
upload = text.split("- name: Upload sanitized diagnostic JSON", 1)[1]
assert "path: ${{ env.KU2D_EVIDENCE_PATH }}" in upload
assert "retention-days: 7" in upload
assert "steps.evidence.outputs.exists == 'true'" in upload
for forbidden_artifact in ("netlog", "screenshot", "browser cache", "profile"):
    assert forbidden_artifact not in upload.casefold()

# Preflight and summary expose only the reviewed operational metadata.
for required in (
    "Runner OS", "Runner architecture", "Python version", "Repository checkout",
    "Microsoft Edge version", "External runtime output directory",
    "Diagnostic exit code", "Classification", "technical_completion",
    "usable_evidence", "visible_product_card_count",
    "validated_network_endpoint_count", "production_store", "scheduler_action",
):
    assert required in text
assert "persist-credentials: false" in text
assert "ref: integration/data-acquisition-platform" in text

# J is enforced by the complete deterministic corpus; this test guards its CI hook.
ci = (ROOT / ".github" / "workflows" / "data-acquisition-platform-ci.yml").read_text(encoding="utf-8")
assert "python tools/SELF_TEST_SHOPEE_EDGE_WORKFLOW.py" in ci
assert "'.github/workflows/shopee-edge-access-diagnostic.yml'" in ci

print("Shopee Edge workflow static contract tests passed (A-J).")
