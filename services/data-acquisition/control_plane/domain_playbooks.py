from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_FILE = ROOT / "config" / "domain_playbooks.json"
SUPERMARKET_PATTERN_FILE = ROOT / "config" / "supermarket_acquisition_patterns.json"


def load_playbooks() -> dict:
    return json.loads(PLAYBOOK_FILE.read_text(encoding="utf-8"))


def load_supermarket_patterns() -> dict:
    if not SUPERMARKET_PATTERN_FILE.is_file():
        return {}
    return json.loads(SUPERMARKET_PATTERN_FILE.read_text(encoding="utf-8"))


def _supermarket_overlay(pb: dict) -> dict:
    """Overlay learned supermarket policy/evidence without duplicating the whole playbook.

    The pattern registry is the learned source of truth for required/optional business
    tracks and validated cross-site evidence. Domain playbooks still own generic clue
    ranking and quality-gate definitions.
    """
    lib = load_supermarket_patterns()
    policy = lib.get("policy") or {}
    out = dict(pb)
    if policy.get("required_tracks"):
        out["required_business_tracks"] = list(policy["required_tracks"])
    out["optional_business_tracks"] = list(policy.get("optional_tracks") or [])
    out["learned_pattern_library"] = {
        "schema": lib.get("schema"),
        "version": lib.get("version"),
        "validated_sources": [x.get("business") for x in (lib.get("validated_sources") or []) if x.get("business")],
        "selection_waterfall": lib.get("selection_waterfall") or [],
    }

    # Promote learned evidence into the generic playbook patterns so ranking can learn
    # from the five-source supermarket phase while preserving existing clue logic.
    learned = {
        "public_catalog_api": ["Lotus's"],
        "sitemap_product_detail": ["Big C", "Tops"],
        "rendered_product_listing": ["Makro", "Gourmet Market"],
        "browser_network_discovery": ["Gourmet Market"],
        "official_promotion_surface": ["Lotus's", "Big C", "Makro", "Tops"],
        "sitemap_discovery": ["Big C", "Tops"],
    }
    patterns = []
    for p in pb.get("patterns") or []:
        item = dict(p)
        ev = dict(item.get("evidence") or {})
        if item.get("pattern_id") in learned:
            ev["validated_sources"] = learned[item["pattern_id"]]
            candidates = [x for x in (ev.get("candidate_sources") or []) if x not in set(ev["validated_sources"])]
            ev["candidate_sources"] = candidates
        item["evidence"] = ev
        patterns.append(item)
    out["patterns"] = patterns
    return out


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
    pb = (load_playbooks().get("playbooks") or {}).get(key) or {}
    return _supermarket_overlay(pb) if key == "supermarket" and pb else pb


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
    optional = pb.get("optional_business_tracks") or []
    return {
        "domain": domain,
        "label": pb.get("label"),
        "required_tracks": tracks,
        "optional_tracks": optional,
        "quality_gates": pb.get("quality_gates") or {},
        "observation_context_required": pb.get("observation_context_required") or [],
        "tracks": {t: ranked_patterns(domain, clues=clues, track=t) for t in tracks},
        "optional_track_patterns": {t: ranked_patterns(domain, clues=clues, track=t) for t in optional},
        "environment_rules": pb.get("environment_rules") or [],
        "learned_pattern_library": pb.get("learned_pattern_library") or {},
    }
