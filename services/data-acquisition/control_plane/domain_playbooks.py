from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_FILE = ROOT / "config" / "domain_playbooks.json"
SUPERMARKET_PATTERN_FILE = ROOT / "config" / "supermarket_acquisition_patterns.json"
RETAIL_CORE_FILE = ROOT / "config" / "retail_commerce_core_patterns.json"
RETAIL_VALIDATIONS_FILE = ROOT / "config" / "retail_domain_validations.json"


def load_playbooks() -> dict:
    return json.loads(PLAYBOOK_FILE.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_supermarket_patterns() -> dict:
    return _load_json(SUPERMARKET_PATTERN_FILE)


def load_retail_core() -> dict:
    return _load_json(RETAIL_CORE_FILE)


def load_retail_validations() -> dict:
    return _load_json(RETAIL_VALIDATIONS_FILE)


def _supermarket_overlay(pb: dict) -> dict:
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
            ev["candidate_sources"] = [x for x in (ev.get("candidate_sources") or []) if x not in set(ev["validated_sources"])]
        item["evidence"] = ev
        patterns.append(item)
    out["patterns"] = patterns
    return out


def _retail_specialized_playbook(domain: str) -> dict:
    core = load_retail_core()
    validation_registry = load_retail_validations()
    domain_validation = (validation_registry.get("domains") or {}).get(domain) or {}
    spec = (core.get("domain_specializations") or {}).get(domain) or {}
    if not spec:
        return {}
    labels = {"beauty": "Beauty / Personal Care Retail", "it_retail": "IT / Electronics Retail"}
    clue_map = {
        "RC-P01": ["json_api", "rest_api", "catalog_endpoint", "product_endpoint", "graphql"],
        "RC-P02": ["product_sitemap", "sitemap_product_urls", "detail_pages", "canonical_product"],
        "RC-P03": ["product_cards", "ssr_listing", "accessible_text", "rendered"],
        "RC-P04": ["robots", "sitemap", "sitemap_index", "reported_total", "pagination", "graphql", "api_candidate", "network_urls"],
        "RC-P05": ["promotion", "campaign", "coupon", "offer", "sale"],
        "RC-P06": ["split_track"],
        "RC-P07": ["cloud_access_blocked", "edge_required"],
    }
    validation_by_pattern_track: dict[tuple[str, str], list[dict]] = {}
    for source in domain_validation.get("live_validated_sources") or []:
        for track, track_validation in (source.get("validated_tracks") or {}).items():
            for pattern_id in track_validation.get("validated_pattern_ids") or []:
                evidence = {
                    "source_id": source.get("source_id"),
                    "source_name": source.get("source_name"),
                    "status": source.get("status"),
                    "validation_scope": source.get("validation_scope"),
                    "production_approved": bool(source.get("production_approved")),
                    "technique": track_validation.get("technique"),
                    "technique_label": track_validation.get("technique_label"),
                    "technique_profile_fingerprint": source.get("technique_profile_fingerprint"),
                    "durable_evidence_file": source.get("durable_evidence_file"),
                }
                validation_by_pattern_track.setdefault((str(pattern_id), str(track)), []).append(evidence)
    rows = []
    for p in core.get("core_patterns") or []:
        if domain not in (p.get("applicable_domains") or []):
            continue
        tracks = p.get("tracks") or []
        for track in tracks:
            if track in {"orchestration", "execution_environment"}:
                continue
            domain_evidence = validation_by_pattern_track.get((str(p.get("pattern_id")), str(track)), [])
            rows.append({
                "pattern_id": p.get("pattern_id"),
                "label": p.get("name"),
                "track": track,
                "base_priority": p.get("priority"),
                "clues": clue_map.get(p.get("pattern_id"), []),
                "evidence": {
                    "validated_sources": [x.get("source_name") for x in domain_evidence if x.get("source_name")],
                    "domain_validated_sources": domain_evidence,
                    "transferred_from_domain": "supermarket",
                    "upstream_validated_sources": (core.get("derived_from") or {}).get("validated_sources") or [],
                },
                "transfer_status": "domain-live-validated" if domain_evidence else "cross-domain-candidate",
            })
    live_validated_sources = [
        {
            "source_id": source.get("source_id"),
            "source_name": source.get("source_name"),
            "status": source.get("status"),
            "validation_scope": source.get("validation_scope"),
            "production_approved": bool(source.get("production_approved")),
        }
        for source in (domain_validation.get("live_validated_sources") or [])
    ]
    return {
        "label": labels[domain],
        "required_business_tracks": list((core.get("shared_tracks") or {}).get("required") or []),
        "optional_business_tracks": list((core.get("shared_tracks") or {}).get("optional") or []),
        "quality_gates": spec.get("quality_gates") or {},
        "observation_context_required": spec.get("required_context") or [],
        "variant_dimensions": spec.get("variant_dimensions") or [],
        "patterns": rows,
        "environment_rules": [{
            "condition": "cloud_access_blocked",
            "action": "prefer_edge_runner",
            "reason": "Use a qualified normal operating network only after public cloud/datacenter access failure is evidenced; do not bypass access controls."
        }],
        "learned_pattern_library": {
            "schema": core.get("schema"),
            "version": core.get("version"),
            "validation_registry_schema": validation_registry.get("schema"),
            "transfer_status": domain_validation.get("validation_status") or "inherited-not-yet-domain-validated",
            "live_validated_sources": live_validated_sources,
            "derived_from": core.get("derived_from") or {},
        },
    }


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
        "beauty_retail": "beauty",
        "cosmetics": "beauty",
        "personal_care": "beauty",
        "it": "it_retail",
        "electronics": "it_retail",
        "electronics_retail": "it_retail",
        "computer_retail": "it_retail",
    }
    key = aliases.get(key, key)
    if key in {"beauty", "it_retail"}:
        return _retail_specialized_playbook(key)
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
        upstream = len(evidence.get("upstream_validated_sources") or [])
        transfer_bonus = min(4, upstream) if not validated else 0
        score = float(p.get("base_priority") or 0) + 4 * len(matched) + min(8, validated * 2) + min(2, candidates) + transfer_bonus
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
        "variant_dimensions": pb.get("variant_dimensions") or [],
        "tracks": {t: ranked_patterns(domain, clues=clues, track=t) for t in tracks},
        "optional_track_patterns": {t: ranked_patterns(domain, clues=clues, track=t) for t in optional},
        "environment_rules": pb.get("environment_rules") or [],
        "learned_pattern_library": pb.get("learned_pattern_library") or {},
    }
