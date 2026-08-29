from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_FILE = ROOT / "config" / "domain_playbooks.json"


def load_playbooks() -> dict:
    return json.loads(PLAYBOOK_FILE.read_text(encoding="utf-8"))


def playbook(domain: str) -> dict:
    key = (domain or "").strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")
    aliases = {
        "supermarket_grocery_retail": "supermarket",
        "retail_supermarket": "supermarket",
        "grocery": "supermarket",
        "online_travel_agencies": "ota",
        "online_travel_agency": "ota",
        "travel_ota": "ota",
        "cafe": "coffee",
        "coffee_chain": "coffee",
        "coffee_shop": "coffee",
        "qdiving": "q_diving",
        "scuba": "q_diving",
        "scuba_diving": "q_diving",
    }
    key = aliases.get(key, key)
    return (load_playbooks().get("playbooks") or {}).get(key) or {}


def ranked_patterns(domain: str, clues: Iterable[str] | None = None, track: str | None = None) -> list[dict]:
    pb = playbook(domain)
    clueset = {str(x).strip().lower() for x in (clues or []) if str(x).strip()}
    rows = []
    for p in pb.get("patterns") or []:
        if track and p.get("track") not in {track, "fallback"}:
            continue
        pattern_clues = {str(x).strip().lower() for x in (p.get("clues") or [])}
        matched = sorted(clueset & pattern_clues)
        evidence = p.get("evidence") or {}
        validated = len(evidence.get("validated_sources") or [])
        candidates = len(evidence.get("candidate_sources") or [])
        score = float(p.get("base_priority") or 0) + 4 * len(matched) + min(8, validated * 2) + min(2, candidates)
        rows.append({**p, "matched_clues": matched, "learned_score": round(score, 2)})
    return sorted(rows, key=lambda x: (-x["learned_score"], str(x.get("pattern_id") or "")))


def recommended_sequence(domain: str, clues: Iterable[str] | None = None) -> dict:
    pb = playbook(domain)
    tracks = pb.get("required_business_tracks") or []
    return {
        "domain": domain,
        "label": pb.get("label"),
        "required_tracks": tracks,
        "quality_gates": pb.get("quality_gates") or {},
        "observation_context_required": pb.get("observation_context_required") or [],
        "tracks": {t: ranked_patterns(domain, clues=clues, track=t) for t in tracks},
        "environment_rules": pb.get("environment_rules") or [],
    }
