"""Build bounded Lazada rendered-DOM Deep Audit evidence from sanitized captures."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from lazada_rendered_dom_audit import build_audit, technical_failure_result


EXIT_AUDIT_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded Lazada rendered-DOM Deep Audit")
    value.add_argument("--input", type=Path, required=True)
    value.add_argument("--max-items", type=int, default=10)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--no-production-store", action="store_true")
    return value


def _read_input(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("surfaces"), list):
        raise ValueError("Deep Audit input must be an object containing a surfaces list.")
    return document["surfaces"]


def _write(output: Path, result: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    exit_code = EXIT_TECHNICAL_FAILURE
    try:
        if not args.no_production_store:
            raise ValueError("--no-production-store is required.")
        result = build_audit(_read_input(args.input), max_items=args.max_items)
        usable = any(surface["retained_product_count"] for surface in result["surfaces"])
        exit_code = EXIT_AUDIT_OBTAINED if result["technical_completion"] and usable else EXIT_EVIDENCE_WITHHELD
    except Exception as exc:
        result = technical_failure_result(exc)
    try:
        _write(args.output, result)
    except Exception as exc:
        print(f"Lazada rendered-DOM Deep Audit evidence writing failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    print(json.dumps({
        "schema": result["schema"], "technical_completion": result["technical_completion"],
        "surface_count": len(result.get("surfaces") or []),
        "retained_product_count": sum(row.get("retained_product_count", 0) for row in result.get("surfaces") or []),
        "production_store": result["production_store"], "scheduler_action": result["scheduler_action"],
        "output": str(args.output), "exit_classification": exit_code,
    }, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
