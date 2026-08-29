from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "acquisition", ROOT / "repository"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from source_explorer import explore_url

TARGETS = {
    "SRC-013": "Beauty",
    "SRC-018": "IT Retail",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def source_map():
    obj = json.loads((ROOT / "config" / "source_registry.json").read_text(encoding="utf-8"))
    return {x.get("source_id"): x for x in (obj.get("sources") or [])}


def compact(result: dict) -> dict:
    tech = []
    for x in result.get("technique_results") or []:
        tech.append({
            "technique": x.get("technique"),
            "label": x.get("label"),
            "status": x.get("status"),
            "record_count": x.get("record_count"),
            "record_types": x.get("record_types"),
            "pages_checked": x.get("pages_checked"),
            "potential": x.get("potential") or {},
            "diagnostics": (x.get("diagnostics") or [])[:10],
            "sample_records": (x.get("sample_records") or [])[:5],
        })
    selection = result.get("track_selection") or {}
    return {
        "status": result.get("status"),
        "recommendation": result.get("recommendation"),
        "quality": result.get("quality"),
        "record_count": result.get("record_count"),
        "unique_sample_record_count": result.get("unique_sample_record_count"),
        "record_types": result.get("record_types"),
        "pattern_clues": result.get("pattern_clues") or [],
        "learned_pattern_guidance": result.get("learned_pattern_guidance") or {},
        "recommended_techniques": result.get("recommended_techniques") or [],
        "assigned_techniques": result.get("assigned_techniques") or [],
        "track_recommendations": result.get("track_recommendations") or {},
        "required_track_gaps": selection.get("required_track_gaps") or {},
        "track_candidates": selection.get("candidates") or {},
        "global_recommendations_before_track_selection": selection.get("global_recommendations_before_track_selection") or [],
        "potential_coverage": result.get("potential_coverage") or [],
        "technique_results": tech,
    }


def main():
    sources = source_map()
    payload = {
        "schema": "ku2d.retail-transfer-live-explore.v2",
        "generated_at": now(),
        "execution_environment": "cloud-hosted-public-read-only",
        "policy": "Public official-site access only; no authentication, CAPTCHA, proxy rotation or access-control bypass.",
        "targets": [],
    }
    for sid, domain in TARGETS.items():
        src = sources.get(sid)
        if not src:
            payload["targets"].append({"source_id": sid, "domain": domain, "error": "source not found"})
            continue
        print(f"[{sid}] Explore {src.get('business')} ({domain})", flush=True)
        try:
            result = explore_url(
                src.get("url"),
                domain=domain,
                purpose=src.get("purpose") or "retail_market_intelligence",
                max_pages=min(4, int(src.get("max_pages") or 4)),
                techniques=None,
            )
            payload["targets"].append({
                "source_id": sid,
                "business": src.get("business"),
                "url": src.get("url"),
                "domain": domain,
                "result": compact(result),
            })
        except Exception as e:
            payload["targets"].append({
                "source_id": sid,
                "business": src.get("business"),
                "url": src.get("url"),
                "domain": domain,
                "error": f"{type(e).__name__}: {e}",
            })
    out = Path(os.environ.get("KU2D_RETAIL_TRANSFER_RESULT", ROOT / "validation" / "retail-transfer-live-explore.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"RESULT_FILE={out}")
    for x in payload["targets"]:
        r = x.get("result") or {}
        gaps = sorted((r.get("required_track_gaps") or {}).keys())
        print(f"{x.get('source_id')} {x.get('business')}: records={r.get('record_count')} assigned={r.get('assigned_techniques')} gaps={gaps} error={x.get('error')}")


if __name__ == "__main__":
    main()
