from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def load_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, f"Missing evidence file: `{path}`"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"Corrupt evidence file `{path}`: {type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return None, f"Invalid evidence file `{path}`: expected a JSON object."
    return value, None


def markdown(summary: dict | None, errors: list[str]) -> str:
    lines = ["## JIB Retail Lifecycle Validation", ""]
    if errors:
        lines.extend(["> [!CAUTION]", "> Validation evidence is missing or unreadable."])
        lines.extend([f"> {error}" for error in errors])
        lines.append("")
    if not summary:
        lines.append("No trustworthy lifecycle summary is available. Treat this validation as a technical failure.")
        return "\n".join(lines) + "\n"

    audit = summary.get("base_deep_audit") or {}
    tracks = summary.get("tracks") or {}
    metrics = summary.get("metrics") or {}
    approved = bool(summary.get("approved"))
    lines.extend([
        f"**Approval result:** {'APPROVED (isolated staging only)' if approved else 'WITHHELD'}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Source | {summary.get('source_name') or summary.get('source_id')} |",
        f"| Environment | {summary.get('execution_environment')} |",
        f"| Technical completion | {summary.get('technical_completion')} |",
        f"| Base Deep Audit passed | {audit.get('passed')} |",
        f"| Quality | {audit.get('quality_score')} / {audit.get('quality_label')} |",
        f"| Required tracks | {', '.join(tracks.get('required') or []) or 'none'} |",
        f"| Resolved tracks | {', '.join(tracks.get('resolved') or []) or 'none'} |",
        f"| Missing required tracks | {', '.join(tracks.get('missing_required') or []) or 'none'} |",
        f"| Product sample count | {metrics.get('product_sample_count')} |",
        f"| Price completeness | {metrics.get('price_completeness_pct')}% |",
        f"| Identity completeness | {metrics.get('identity_completeness_pct')}% |",
        f"| Repeatability | {metrics.get('repeatability_pct')}% |",
        f"| Provenance | {metrics.get('provenance_pct')}% |",
        f"| Scheduler action | {summary.get('scheduler_action') or 'none'} |",
        "",
    ])
    failures = summary.get("domain_gate_failures") or []
    if failures:
        lines.append("**Domain gate failures:** " + ", ".join(str(x) for x in failures))
        lines.append("")
    reason = summary.get("approval_withheld_reason")
    if reason:
        lines.append("**Approval withheld reason:** " + str(reason))
        lines.append("")
    lines.append("Workflow execution, lifecycle technical completion, isolated staging approval, and production Human Approve are distinct states.")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--output", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    args = parser.parse_args(argv)

    summary, summary_error = load_json(Path(args.summary))
    _, result_error = load_json(Path(args.result))
    errors = [x for x in (summary_error, result_error) if x]
    text = markdown(summary, errors)
    print(text)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as stream:
            stream.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
