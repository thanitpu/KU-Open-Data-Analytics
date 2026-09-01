"""P59 one-time, non-production, tracked multi-source campaign CLI."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
for folder in (ROOT, ROOT / "acquisition"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from domain_export_bundle import build_export_bundle, verify_export_bundle  # noqa: E402
from round_robin_campaign import (  # noqa: E402
    CampaignValidationError, ProviderBoundary, RoundRobinCampaign, VisitContext,
    VisitResult, atomic_write_json, load_campaign_manifest, sanitized_url,
    verify_sealed_ledger,
)


MANIFEST_PATH = ROOT / "config" / "multi_source_round_robin_manifest_v1.json"
DEFAULT_OUTPUT = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / "KU2D" / "P59"
LOTUS_BATCH_ENDPOINT = "https://api-o2o.lotuss.com/lotuss-mobile-bff/product/v4/products"


def git_identity() -> tuple[str, str]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=REPO, text=True).strip()
    if len(sha) != 40 or len(tree) != 40:
        raise RuntimeError("exact Git code identity is unavailable")
    return sha, tree


def artifact_delivery_preflight(output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    repo = REPO.resolve()
    if output_dir == repo or output_dir.is_relative_to(repo):
        raise CampaignValidationError("live output directory must remain outside Git")
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = output_dir / ".ku2d-p59-delivery-probe"
    probe.write_text("downloadable-outside-git\n", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "downloadable-outside-git\n":
        raise RuntimeError("artifact delivery probe was not readable")
    probe.unlink()
    return {
        "output_directory": str(output_dir), "outside_git": True,
        "writable": True, "delivery_surface": "Codex local artifact link/path",
    }


def _tracked_fetch(context: VisitContext, original):
    def fetch(url, timeout=15, headers=None):
        try:
            return context.provider_call(
                url, lambda: original(url, timeout=timeout, headers=headers),
            )
        except ProviderBoundary as exc:
            context.access_boundary = str(exc)
            return {"ok": False, "status": 0, "error": f"ProviderBoundary: {exc}", "url": sanitized_url(url)}
    return fetch


@contextmanager
def tracked_supermarket_transport(context: VisitContext):
    import actual_acquisition
    import lotus_advanced
    import lotus_multitechnique
    import supermarket_techniques

    original_lotus_get = lotus_advanced.get
    original_supermarket_get = supermarket_techniques.get
    original_fetch = actual_acquisition.fetch
    originals = {
        "lotus_get": original_lotus_get,
        "supermarket_get": original_supermarket_get,
        "actual_fetch": original_fetch,
        "lotus_fetch": lotus_multitechnique.fetch,
        "browser_render": supermarket_techniques.browser_render,
        "lotus_browser_netlog": lotus_multitechnique.browser_netlog,
    }
    lotus_advanced.get = _tracked_fetch(context, original_lotus_get)
    supermarket_techniques.get = _tracked_fetch(context, original_supermarket_get)
    actual_acquisition.fetch = _tracked_fetch(context, original_fetch)
    lotus_multitechnique.fetch = actual_acquisition.fetch
    supermarket_techniques.browser_render = lambda *args, **kwargs: {"ok": False, "error": "browser_disabled_by_p59_method_lock"}
    lotus_multitechnique.browser_netlog = lambda *args, **kwargs: {"ok": False, "error": "endpoint_rediscovery_disabled_by_p59_method_lock"}
    try:
        yield supermarket_techniques, lotus_multitechnique
    finally:
        lotus_advanced.get = originals["lotus_get"]
        supermarket_techniques.get = originals["supermarket_get"]
        actual_acquisition.fetch = originals["actual_fetch"]
        lotus_multitechnique.fetch = originals["lotus_fetch"]
        supermarket_techniques.browser_render = originals["browser_render"]
        lotus_multitechnique.browser_netlog = originals["lotus_browser_netlog"]


def supermarket_adapter(source: dict[str, Any], context: VisitContext) -> VisitResult:
    visit = context.source_state["visits"]
    with tracked_supermarket_transport(context) as (techniques, lotus):
        if source["source_id"] == "SRC-001":
            result = techniques.tops_product_catalog(
                "https://www.tops.co.th/th", max_pages=8, progressive=True,
                operational_config={"max_sitemaps": 16, "offset": (visit - 1) * 8},
            )
        elif source["source_id"] == "SRC-002":
            result = lotus.lotus_catalog_api_materialize(
                "https://www.lotuss.com/th", max_pages=1,
                operational_config={
                    "batch_endpoint": LOTUS_BATCH_ENDPOINT, "seller_id": "3",
                    "max_batch_size": 99, "origin": "https://www.lotuss.com",
                    "sku_offset": (visit - 1) * 99,
                },
            )
        elif source["source_id"] == "SRC-004":
            result = techniques.bigc_product_catalog(
                "https://www.bigc.co.th/", max_pages=8, progressive=True,
                operational_config={
                    "max_sitemaps": 18, "offset": (visit - 1) * 8,
                    "browser_mode": "disabled",
                },
            )
        elif source["source_id"] == "SRC-005":
            page_start = (visit - 1) * 5 + 1
            remaining_pages = max(0, 8 - (page_start - 1))
            if remaining_pages <= 0:
                return VisitResult("success", [], frontier_exhausted=True)
            result = techniques.makro_pro_catalog(
                "https://www.makro.pro/th/c/search", max_pages=min(5, remaining_pages),
                progressive=True,
                operational_config={
                    "catalog_url": "https://www.makro.pro/th/c/search", "page_size": 20,
                    "page_start": page_start, "browser_mode": "disabled",
                },
            )
        else:
            raise RuntimeError(f"no P59 adapter for {source['source_id']}")
    rows = result.get("rows") or []
    if context.access_boundary:
        outcome = "boundary"
    else:
        outcome = "success"
    exhausted = visit >= source["budgets"]["max_visits"]
    if source["source_id"] in {"SRC-001", "SRC-004"} and len(rows) >= source["budgets"]["max_records"]:
        exhausted = True
    if source["source_id"] == "SRC-005" and visit >= 2:
        exhausted = True
    return VisitResult(outcome, rows, quota_delta=0, frontier_exhausted=exhausted, warning=context.access_boundary)


def fixture_replay(manifest: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    if ledger.get("sealed_live") is not True:
        raise CampaignValidationError("fixture replay requires sealed live ledger")
    before = ledger["provider_operations"]
    rows = []
    for source in manifest["sources"]:
        checks = []
        for relative in source["fixture_paths"]:
            path = ROOT / relative
            if not path.is_file():
                raise FileNotFoundError(f"declared fixture missing: {relative}")
            payload = path.read_bytes()
            if not payload:
                raise ValueError(f"declared fixture empty: {relative}")
            if path.suffix.lower() == ".json":
                parsed = json.loads(payload.decode("utf-8"))
                if not isinstance(parsed, (dict, list)):
                    raise ValueError(f"fixture must contain a JSON object/array: {relative}")
                check = "json-parse-and-shape"
            else:
                payload.decode("utf-8")
                check = "utf8-nonempty-replay"
            checks.append({"path": relative, "check": check, "bytes": len(payload)})
        rows.append({
            "source_id": source["source_id"],
            "status": "passed" if checks else "not_available",
            "fixtures": checks,
            "provider_operations": 0,
        })
    if ledger["provider_operations"] != before:
        raise RuntimeError("fixture replay changed provider-operation count")
    return {
        "schema": "ku2d.multi-source-fixture-report.v1", "run_id": ledger["run_id"],
        "sealed_live": True, "provider_operations_before": before,
        "provider_operations_after": ledger["provider_operations"],
        "provider_operations": 0, "sources": rows,
    }


def run_canary(manifest: dict[str, Any], output_dir: Path, run_id: str) -> dict[str, Any]:
    import lotus_advanced
    sha, tree = git_identity()
    checkpoint = output_dir / f"{run_id}.canary-ledger.json"
    runner = RoundRobinCampaign(manifest, checkpoint, {}, run_id=run_id)
    runner.set_code_identity(sha, tree)
    findings = []
    roots = {
        "SRC-001": "https://www.tops.co.th/th",
        "SRC-002": "https://www.lotuss.com/th",
        "SRC-004": "https://www.bigc.co.th/",
        "SRC-005": "https://www.makro.pro/th/c/search",
    }
    for source_id in manifest["source_order"]:
        source = next(row for row in manifest["sources"] if row["source_id"] == source_id)
        if source["preflight_status"] != "live_eligible":
            continue
        state = runner.ledger["source_states"][source_id]
        state["visits"] = 1
        context = VisitContext(runner, source, state)
        response = context.provider_call(
            roots[source_id], lambda url=roots[source_id]: lotus_advanced.get(url, timeout=source["budgets"]["timeout_seconds"]),
        )
        findings.append({
            "source_id": source_id, "sanitized_url": sanitized_url(roots[source_id]),
            "http_status": int(response.get("status") or 0), "ok": bool(response.get("ok")),
            "access_boundary": context.access_boundary,
        })
        if context.access_boundary:
            state.update(state="to_be_skipped", reason=context.access_boundary)
        else:
            state.update(state="exhausted", reason="canary_only_complete")
    runner.ledger.update(
        ended_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sealed_live=True, stop_reason="canary_complete", pending_operation=None,
    )
    runner._checkpoint()
    report = {
        "schema": "ku2d.multi-source-prelive-canary.v1", "run_id": run_id,
        "code_sha": sha, "code_tree": tree, "findings": findings,
        "provider_operations": runner.ledger["provider_operations"], "quota": 0,
        "production_store": False,
    }
    atomic_write_json(output_dir / f"{run_id}.canary-report.json", report)
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("preflight", "canary", "execute"), required=True)
    parser.add_argument("--acknowledge-one-time-p59", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-production-store", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    manifest = load_campaign_manifest(args.manifest)
    delivery = artifact_delivery_preflight(args.output_dir)
    output_dir = Path(delivery["output_directory"])
    if args.mode == "preflight":
        result = {"ok": True, "provider_operations": 0, "quota": 0, "artifact_delivery": delivery}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not args.acknowledge_one_time_p59:
        print(json.dumps({"ok": False, "error": "--acknowledge-one-time-p59 is required"}, indent=2))
        return 1
    if args.mode == "canary":
        report = run_canary(manifest, output_dir, args.run_id)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if any(row["access_boundary"] for row in report["findings"]) else 0
    checkpoint = output_dir / f"{args.run_id}.live-ledger.json"
    adapters = {source_id: supermarket_adapter for source_id in ("SRC-001", "SRC-002", "SRC-004", "SRC-005")}
    if args.resume:
        runner = RoundRobinCampaign.resume(manifest, checkpoint, adapters, run_id=args.run_id)
    else:
        if checkpoint.exists():
            raise CampaignValidationError("run checkpoint already exists; use --resume only for an unsealed interrupted run")
        runner = RoundRobinCampaign(manifest, checkpoint, adapters, run_id=args.run_id)
        sha, tree = git_identity()
        runner.set_code_identity(sha, tree)
    ledger = verify_sealed_ledger(runner.run())
    fixture_report = fixture_replay(manifest, ledger)
    fixture_path = output_dir / f"{args.run_id}.fixture-report.json"
    atomic_write_json(fixture_path, fixture_report)
    bundle = build_export_bundle(ledger, manifest, fixture_report, output_dir)
    verify_export_bundle(Path(bundle["zip_path"]), Path(bundle["delivery_manifest_path"]))
    summary = {
        "ok": True, "run_id": args.run_id, "stop_reason": ledger["stop_reason"],
        "accepted_unique": ledger["accepted_unique"], "observations": ledger["observations"],
        "provider_operations": ledger["provider_operations"], "quota": ledger["quota"],
        "rounds_completed": ledger["rounds_completed"], "sealed_live": ledger["sealed_live"],
        "fixture_provider_operations": fixture_report["provider_operations"],
        "zip_path": bundle["zip_path"], "zip_sha256": bundle["zip_sha256"],
        "delivery_manifest_path": bundle["delivery_manifest_path"],
        "production_store": False, "scheduler_action": None,
    }
    atomic_write_json(output_dir / f"{args.run_id}.summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ledger["stop_reason"] in {"empty_active_source_set", "global_unique_record_ceiling"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
