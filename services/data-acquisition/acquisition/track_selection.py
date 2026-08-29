from __future__ import annotations

import math
import re
from typing import Any


def _counts(result: dict) -> dict[str, int]:
    return {str(x.get("type")): int(x.get("count") or 0) for x in (result.get("record_types") or []) if x.get("type")}


def _samples(result: dict, kinds: set[str]) -> list[dict]:
    return [x for x in (result.get("sample_records") or []) if isinstance(x, dict) and x.get("record_type") in kinds]


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _conf(value: Any) -> int:
    return {"high": 12, "medium": 7, "low": 2}.get(str(value or "").lower(), 4)


def _log_score(n: int, cap: int = 26) -> int:
    if n <= 0:
        return 0
    return min(cap, int(round(6 + 6 * math.log10(n + 1))))


def _canonical_identity(record: dict) -> bool:
    if record.get("sku") or record.get("gtin") or record.get("product_id") or record.get("model"):
        return True
    url = str(record.get("source_url") or "")
    if not url:
        return False
    path = re.sub(r"^https?://[^/]+", "", url, flags=re.I).rstrip("/").lower()
    return bool(path and path not in {"", "/th", "/en", "/th-th", "/en-th"} and re.search(r"/(?:product|products|p|item|sku)/|[-_/]\d{5,}(?:\D|$)", path))


def _heuristic_or_marketing(record: dict) -> bool:
    prov = str(record.get("provenance") or "").lower()
    tag = str(record.get("source_tag") or "").lower()
    name = str(record.get("product_name") or "").strip().lower()
    if prov in {"text-pattern", "optimized-retail-text"}:
        return True
    if tag == "marketing" and not _canonical_identity(record):
        return True
    return bool(re.match(r"^(?:ส่งฟรี|ช[้ออ]ปครบ|ซื้อครบ|ลด\s*\d|คูปอง|coupon|discount|free shipping)\b", name, re.I))


def _credible_promotion(record: dict) -> bool:
    if record.get("record_type") != "PromotionCandidate":
        return False
    title = str(record.get("promotion_title") or "").strip()
    offer = str(record.get("offer") or record.get("terms") or "").strip()
    prov = str(record.get("provenance") or "").lower()
    url = str(record.get("source_url") or "").lower()
    if not title or not offer:
        return False
    explicit = bool(re.search(r"(?:\d+\s*%|\d+\s*(?:บาท|baht|thb)|ซื้อ\s*\d|แถม|save\s*\d|coupon|code|ส่วนลด)", title + " " + offer, re.I))
    official_surface = any(x in prov for x in ("promotion", "campaign", "catalogue", "coupon")) or any(x in url for x in ("promo", "promotion", "campaign", "catalogue", "coupon"))
    return explicit or official_surface


def infer_track_candidates(results: list[dict], quality_gates: dict | None = None) -> dict:
    """Infer track ownership for generic retail techniques from their actual output.

    This is intentionally conservative: raw row volume never qualifies a technique for
    Product & Price unless sampled rows carry attributable product identity and price.
    Discovery candidates are allowed to have zero business facts when they materially
    expand a public catalog frontier. Promotion is optional and only credible promotion
    facts qualify; generic marketing copy does not.
    """
    gates = quality_gates or {}
    min_price = float(gates.get("price_completeness_pct") or 80)
    min_identity = float(gates.get("model_or_sku_completeness_pct") or gates.get("variant_identity_when_present_pct") or 70)
    # Cross-domain transfer starts conservatively but allows canonical detail URLs to
    # supply identity even when retailer-specific SKU fields are not yet normalized.
    min_identity = min(min_identity, 80)

    product: list[dict] = []
    promotion: list[dict] = []
    discovery: list[dict] = []

    for x in results or []:
        if x.get("status") not in {"completed", "success"}:
            continue
        c = _counts(x)
        p = x.get("potential") or {}
        confidence = _conf(p.get("confidence"))
        elapsed = max(0.1, float(x.get("elapsed_seconds") or 0.1))

        ps = _samples(x, {"ProductCandidate", "PriceCandidate"})
        product_count = int(c.get("ProductCandidate") or 0) + int(c.get("PriceCandidate") or 0)
        if product_count and ps:
            price_pct = _pct(sum(r.get("price") is not None for r in ps), len(ps))
            identity_pct = _pct(sum(_canonical_identity(r) for r in ps), len(ps))
            noise_pct = _pct(sum(_heuristic_or_marketing(r) for r in ps), len(ps))
            # A technique must pass attribution gates; text-pattern homepage numerals
            # are evidence of parsing opportunity, not repository-ready product facts.
            eligible = price_pct >= min_price and identity_pct >= min_identity and noise_pct <= 35
            score = _log_score(product_count) + round(price_pct * .20) + round(identity_pct * .20) + confidence
            if noise_pct:
                score -= round(noise_pct * .25)
            if x.get("technique") in {"structured_data", "generic_api_probe"}:
                score += 8
            if x.get("technique") == "generic_browser_rendered":
                score += 4
            product.append({
                "track": "product_price", "technique": x.get("technique"), "technique_label": x.get("label"),
                "score": int(score), "eligible": bool(eligible), "records": product_count,
                "price_completeness_pct": price_pct, "identity_completeness_pct": identity_pct,
                "heuristic_or_marketing_pct": noise_pct,
                "reason": "requires attributable product identity plus price; high-volume marketing/text-pattern rows are rejected",
            })

        promo_samples = _samples(x, {"PromotionCandidate", "PromotionListingItemCandidate"})
        promo_count = int(c.get("PromotionCandidate") or 0) + int(c.get("PromotionListingItemCandidate") or 0)
        if promo_count and promo_samples:
            credible = [r for r in promo_samples if _credible_promotion(r)]
            credible_pct = _pct(len(credible), len(promo_samples))
            fact_count = int(c.get("PromotionCandidate") or 0)
            eligible = fact_count > 0 and credible_pct >= 40
            score = _log_score(promo_count, 22) + round(credible_pct * .30) + confidence
            if fact_count == 0:
                score -= 18
            promotion.append({
                "track": "promotion", "technique": x.get("technique"), "technique_label": x.get("label"),
                "score": int(score), "eligible": bool(eligible), "records": promo_count,
                "credible_promotion_sample_pct": credible_pct, "promotion_fact_records": fact_count,
                "reason": "requires explicit offer/campaign semantics; promotion-listing URLs and generic marketing prose alone do not qualify",
            })

        endpoint_count = int(c.get("EndpointCandidate") or 0) + int(c.get("URLCandidate") or 0) + int(c.get("ProductURLCandidate") or 0)
        discovered = max(
            int(p.get("discovered_urls") or 0), int(p.get("api_candidates") or 0),
            int(p.get("network_urls") or 0), int(p.get("reported_total") or 0), endpoint_count,
        )
        role = str(x.get("operational_role") or "").lower()
        technique = str(x.get("technique") or "")
        if discovered > 0 and (role == "discovery" or endpoint_count > 0 or technique in {
            "generic_sitemap", "generic_app_bundle", "generic_browser_network", "generic_api_probe"
        }):
            score = _log_score(discovered, 34) + confidence
            if p.get("reported_total"):
                score += 12
            if technique == "generic_sitemap":
                score += 10
            elif technique == "generic_browser_network":
                score += 7
            elif technique == "generic_app_bundle":
                score += 5
            discovery.append({
                "track": "discovery", "technique": x.get("technique"), "technique_label": x.get("label"),
                "score": int(score), "eligible": True, "discovered": discovered,
                "reason": "expands the official catalog/API frontier and is scored separately from business-record yield",
            })

    def ranked(rows: list[dict]) -> list[dict]:
        return sorted(rows, key=lambda z: (not z.get("eligible"), -int(z.get("score") or 0), -int(z.get("records") or z.get("discovered") or 0), str(z.get("technique") or "")))

    return {"product_price": ranked(product), "promotion": ranked(promotion), "discovery": ranked(discovery)}


def select_track_profile(results: list[dict], required_tracks: list[str], optional_tracks: list[str] | None = None,
                         quality_gates: dict | None = None) -> tuple[list[dict], dict, dict]:
    candidates = infer_track_candidates(results, quality_gates=quality_gates)
    requested = list(dict.fromkeys(list(required_tracks or []) + list(optional_tracks or [])))
    tracks: dict[str, dict] = {}
    gaps: dict[str, dict] = {}

    for track in requested:
        rows = candidates.get(track) or []
        winner = next((x for x in rows if x.get("eligible")), None)
        if winner:
            tracks[track] = winner
        elif track in set(required_tracks or []):
            gaps[track] = {
                "track": track,
                "status": "required-track-gap",
                "reason": "No tested technique produced evidence that passed the track attribution/quality gate.",
                "best_candidate": rows[0] if rows else None,
            }

    by = {x.get("technique"): x for x in results or []}
    picked: list[dict] = []
    pos: dict[str, int] = {}
    for track in requested:
        winner = tracks.get(track)
        if not winner:
            continue
        key = winner.get("technique")
        src = by.get(key) or {}
        if key in pos:
            rec = picked[pos[key]]
            rec["tracks"].append(track)
            rec["track_scores"][track] = winner.get("score")
            rec["track_evidence"][track] = winner
            rec["score"] = max(int(rec.get("score") or 0), int(winner.get("score") or 0))
            continue
        rec = {
            "technique": key,
            "label": src.get("label") or winner.get("technique_label"),
            "score": int(winner.get("score") or 0),
            "role": "discovery" if track == "discovery" else "acquisition",
            "record_count": int(src.get("record_count") or 0),
            "record_types": src.get("record_types") or [],
            "potential": src.get("potential") or {},
            "elapsed_seconds": src.get("elapsed_seconds") or 0,
            "pages_checked": src.get("pages_checked") or 0,
            "tracks": [track],
            "track_scores": {track: winner.get("score")},
            "track_evidence": {track: winner},
        }
        pos[key] = len(picked)
        picked.append(rec)

    return picked, tracks, {"required_track_gaps": gaps, "candidates": candidates}
