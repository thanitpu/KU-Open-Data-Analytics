"""Analyze one sanitized, unauthenticated Lazada browser page-load capture.

The reviewed browser controller supplies a bounded capture containing visible
card and resource metadata only. This CLI writes evidence before exit and does
not launch Edge, authenticate, or persist browser state.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlparse


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from lazada_browser_access import analyze_capture, technical_failure_result


EXIT_EVIDENCE_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2
MAX_ITEMS = 10


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded Lazada normal-browser access diagnostic")
    target = value.add_mutually_exclusive_group(required=True)
    target.add_argument("--query")
    target.add_argument("--url")
    value.add_argument("--max-items", type=int, default=10)
    value.add_argument("--capture-file", type=Path)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--no-production-store", action="store_true")
    return value


def target(args: argparse.Namespace) -> tuple[str, str | None]:
    if not args.no_production_store:
        raise ValueError("--no-production-store is required.")
    if args.max_items < 1 or args.max_items > MAX_ITEMS:
        raise ValueError("--max-items must be between 1 and 10.")
    query = str(args.query or "").strip() or None
    url = str(args.url or "").strip()
    if query:
        url = f"https://www.lazada.co.th/catalog/?q={quote_plus(query)}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in {"lazada.co.th", "www.lazada.co.th"}:
        raise ValueError("Only public HTTPS Lazada Thailand customer surfaces are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are prohibited.")
    return url, query


def capture_from_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        raise RuntimeError("A sanitized capture from the reviewed normal browser context is required.")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Browser capture must be a JSON object.")
    return document


def _write_evidence(output: Path, result: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main(
    argv=None,
    *,
    capture_provider: Callable[[str, int], dict[str, Any]] | None = None,
) -> int:
    args = parser().parse_args(argv)
    url, query = None, str(args.query or "").strip() or None
    result: dict[str, Any]
    exit_code = EXIT_TECHNICAL_FAILURE
    try:
        url, query = target(args)
        snapshot = capture_provider(url, args.max_items) if capture_provider else capture_from_file(args.capture_file)
        result = analyze_capture(snapshot, target_url=url, query=query, max_items=args.max_items)
        exit_code = EXIT_EVIDENCE_OBTAINED if result["usable_evidence"] else EXIT_EVIDENCE_WITHHELD
    except Exception as exc:
        result = technical_failure_result(
            target_url=url or args.url, query=query, max_items=args.max_items, exc=exc,
        )
    try:
        _write_evidence(args.output, result)
    except Exception as exc:
        print(f"Lazada browser diagnostic evidence writing failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    print(json.dumps({
        "schema": result["schema"], "classification": result["classification"],
        "technical_completion": result["technical_completion"],
        "usable_evidence": result["usable_evidence"],
        "visible_product_card_count": result["visible_product_card_count"],
        "stable_dom_identity_count": result["stable_dom_identity_count"],
        "validated_network_endpoint_count": result["validated_network_endpoint_count"],
        "production_store": result["production_store"],
        "scheduler_action": result["scheduler_action"],
        "output": str(args.output), "exit_classification": exit_code,
    }, ensure_ascii=False, sort_keys=True))
    if exit_code != EXIT_EVIDENCE_OBTAINED:
        print(f"Lazada browser evidence withheld: {result.get('failure_reason')}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
