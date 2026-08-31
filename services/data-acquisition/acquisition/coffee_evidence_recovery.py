"""Bounded, non-authorizing Coffee product-detail evidence recovery.

The module is deliberately pure: it validates the reviewed request package,
normalizes an already-fetched official product detail into sanitized evidence,
and evaluates repeatability/Deep Audit gates. Network execution and durable
evidence writes live at the CLI boundary.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup


SCHEMA = "ku2d.coffee-evidence-recovery.v1"
PACKAGE_SCHEMA = "ku2d.coffee-evidence-recovery-package.v1"
TARGET_IDS = {"roots_coffee", "nana_coffee_roasters"}
AUDITED_FIELDS = {
    "coffee_product_id", "product_name", "canonical_url", "price", "currency",
    "price_role", "availability", "variant", "origin", "process",
    "tasting_notes", "roast_level", "package_size", "source", "source_surface",
    "observed_at",
}


def _clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _safe_url(value: Any) -> str | None:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return parsed._replace(query="", fragment="").geturl()


def _allowed_hosts(target: dict[str, Any]) -> set[str]:
    configured = target.get("allowed_hosts") or [target.get("official_host")]
    return {str(host).casefold() for host in configured if str(host or "").strip()}


def _is_allowed_url(value: Any, target: dict[str, Any]) -> bool:
    safe = _safe_url(value)
    return bool(safe and (urlparse(safe).hostname or "").casefold() in _allowed_hosts(target))


def validate_package(package: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(package, dict) or package.get("schema") != PACKAGE_SCHEMA:
        raise ValueError("Coffee recovery package schema is invalid.")
    if package.get("package_id") != "KU2D-CER-000001":
        raise ValueError("Coffee recovery package identity is invalid.")
    authorization = package.get("authorization") or {}
    if authorization.get("prompt_id") != "KU2D-P-000023" or authorization.get("human_decision_id") != "KU2D-H-000009":
        raise ValueError("Coffee recovery authorization provenance is incomplete.")
    if authorization.get("bounded_public_read_only_live_acquisition") is not True:
        raise ValueError("Bounded public read-only acquisition was not authorized.")
    for field in ("candidate_promotion", "knowledge_mutation", "production_authorized"):
        if authorization.get(field) is not False:
            raise ValueError(f"Coffee recovery authorization boundary {field} must remain false.")
    rerun = package.get("rerun_authorization") or {}
    expected_rerun = {
        "prompt_id": "KU2D-P-000027",
        "review_id": "KU2D-V-000026",
        "human_decision_id": "KU2D-H-000010",
        "authoritative_branch": "codex/ku2d-coffee-hardened-rerun-v1",
        "same_reviewed_urls_only": True,
        "single_run": True,
        "candidate_promotion": False,
        "knowledge_mutation": False,
        "production_authorized": False,
    }
    if any(rerun.get(field) != expected for field, expected in expected_rerun.items()):
        raise ValueError("Coffee recovery rerun authorization provenance is incomplete or unsafe.")

    targets = package.get("targets")
    if not isinstance(targets, list) or {row.get("source_id") for row in targets if isinstance(row, dict)} != TARGET_IDS:
        raise ValueError("Coffee recovery must contain exactly the reviewed Roots and Nana targets.")
    if len(targets) != 2:
        raise ValueError("Coffee recovery target count must be two.")
    for target in targets:
        if target.get("surface") != "official-public-product-detail":
            raise ValueError("Coffee recovery targets must remain official public product details.")
        if not _is_allowed_url(target.get("url"), target):
            raise ValueError(f"Coffee recovery target URL is not an allowed official HTTPS URL: {target.get('source_id')}")

    budget = package.get("request_budget") or {}
    expected = {
        "observations_per_source": 2,
        "maximum_acquisition_attempts": 4,
        "maximum_redirects_per_attempt": 2,
        "maximum_transport_requests": 12,
        "retries": 0,
        "pagination": 0,
        "maximum_response_bytes": 1_000_000,
        "timeout_seconds": 15,
    }
    if any(budget.get(key) != value for key, value in expected.items()):
        raise ValueError("Coffee recovery request budget drifted from the reviewed bound.")
    provenance = package.get("raw_to_normalized_provenance") or {}
    if provenance.get("required_for_every_non_null_normalized_field") is not True:
        raise ValueError("Field-level raw-to-normalized provenance must be required.")
    if provenance.get("raw_html_retained") is not False or provenance.get("headers_retained") is not False:
        raise ValueError("Raw HTML and headers must not be retained.")
    boundaries = package.get("boundaries") or {}
    required_true = {"public_official_surfaces_only"}
    required_false = {
        "authentication", "captcha_or_challenge_handling", "access_control_bypass",
        "proxy_rotation", "browser_escalation", "private_api", "production_store",
        "production_approved", "automatic_learning_memory_export",
    }
    if any(boundaries.get(field) is not True for field in required_true):
        raise ValueError("Official-public-only boundary is missing.")
    if any(boundaries.get(field) is not False for field in required_false) or boundaries.get("scheduler_action") is not None:
        raise ValueError("Coffee recovery non-production boundaries are invalid.")
    return deepcopy(package)


def _product_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            root = json.loads(tag.string or tag.get_text() or "")
        except (TypeError, json.JSONDecodeError):
            continue
        stack = list(root) if isinstance(root, list) else [root]
        while stack:
            value = stack.pop()
            if isinstance(value, list):
                stack.extend(value)
                continue
            if not isinstance(value, dict):
                continue
            graph = value.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            types = value.get("@type")
            type_set = {str(item).casefold() for item in types} if isinstance(types, list) else {str(types).casefold()}
            if "product" in type_set:
                products.append(value)
    return products


def _meta(soup: BeautifulSoup, *keys: str) -> tuple[str | None, str | None]:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        value = _clean(tag.get("content")) if tag else ""
        if value:
            return value, f"meta[{key}]"
    return None, None


def _label(text: str, label: str, aliases: tuple[str, ...] = ()) -> tuple[str | None, str | None]:
    names = "|".join(re.escape(item) for item in (label, *aliases))
    boundary = "Origin|Process|Taste Notes?|Tasting Notes?|Roast Level|Roast|Size|Weight|Availability|SKU|Variant"
    match = re.search(rf"(?:{names})\s*[:：]\s*(.{{1,260}}?)(?=\s+(?:{boundary})\s*[:：]|$)", text, re.I)
    value = _clean(match.group(1), 240) if match else ""
    return (value or None), (f"visible-label:{label}" if value else None)


def _number(value: Any) -> float | None:
    try:
        parsed = float(re.sub(r"[^0-9.]", "", str(value or "").replace(",", "")))
    except ValueError:
        return None
    return parsed if 10 <= parsed <= 100_000 else None


def normalize_product_detail(
    html: str,
    target: dict[str, Any],
    *,
    final_url: str,
    observed_at: str,
    http_status: int = 200,
    content_type: str = "text/html",
) -> dict[str, Any]:
    """Return sanitized response evidence and an optional candidate record."""
    if not isinstance(html, str) or not html or not _is_allowed_url(final_url, target):
        raise ValueError("Product detail input is empty or outside the configured official host.")
    soup = BeautifulSoup(html, "html.parser")
    text = _clean(soup.get_text("\n", strip=True), 20_000)
    products = _product_objects(soup)
    product = products[0] if products else {}

    canonical_tag = soup.find("link", attrs={"rel": lambda value: value and "canonical" in str(value).casefold()})
    canonical_raw = _clean(canonical_tag.get("href")) if canonical_tag else ""
    canonical = _safe_url(canonical_raw) if canonical_raw and _is_allowed_url(canonical_raw, target) else _safe_url(final_url)
    canonical_path = "link[rel=canonical]" if canonical_raw and canonical == _safe_url(canonical_raw) else "response.final_url"

    provenance: dict[str, dict[str, Any]] = {}

    def retain(field: str, value: Any, raw: Any, path: str | None) -> Any:
        if value is not None and value != "":
            provenance[field] = {
                "raw_value": _clean(raw, 500),
                "extraction_path": path,
                "source_url": canonical,
                "observed_at": observed_at,
            }
        return value

    name = _clean(product.get("name"), 300) if product else ""
    name_path = "jsonld.Product.name" if name else None
    if not name:
        heading = soup.find("h1")
        name = _clean(heading.get_text(" ", strip=True), 300) if heading else ""
        name_path = "dom.h1" if name else None
    if not name:
        name, name_path = _meta(soup, "og:title", "twitter:title")
        name = _clean(name, 300)

    offer_value = product.get("offers") if isinstance(product, dict) else None
    offers = offer_value if isinstance(offer_value, list) else [offer_value]
    offer = next((item for item in offers if isinstance(item, dict)), {})
    price_raw = offer.get("price") or offer.get("lowPrice")
    price = _number(price_raw)
    price_path = "jsonld.Product.offers.price" if price is not None else None
    currency_raw = offer.get("priceCurrency")
    currency = _clean(currency_raw, 12).upper() or None
    currency_path = "jsonld.Product.offers.priceCurrency" if currency else None
    availability_raw = offer.get("availability")
    availability = _clean(availability_raw).rsplit("/", 1)[-1] or None
    availability_path = "jsonld.Product.offers.availability" if availability else None
    if price is None:
        price_raw, price_path = _meta(soup, "product:price:amount", "og:price:amount")
        price = _number(price_raw)
    if not currency:
        currency_raw, currency_path = _meta(soup, "product:price:currency", "og:price:currency")
        currency = _clean(currency_raw, 12).upper() or ("THB" if price is not None else None)
        currency_path = currency_path or ("explicit-baht-price" if price is not None else None)
    if price is None:
        price_match = re.search(r"(?:฿|THB)\s*([0-9][0-9,.]*)|([0-9][0-9,.]*)\s*(?:฿|THB|บาท)", text, re.I)
        price_raw = next((group for group in price_match.groups() if group), None) if price_match else None
        price = _number(price_raw)
        price_path = "visible-product-currency-text" if price is not None else None
        if price is not None:
            currency, currency_raw, currency_path = "THB", "THB/฿/บาท", "visible-product-currency-text"

    origin, origin_path = _label(text, "Origin", ("แหล่งปลูก", "แหล่งที่มา"))
    process, process_path = _label(text, "Process", ("กระบวนการ",))
    tasting, tasting_path = _label(text, "Taste Notes", ("Tasting Notes", "โน้ตรสชาติ"))
    roast, roast_path = _label(text, "Roast Level", ("Roast", "ระดับการคั่ว"))
    package_size, package_path = _label(text, "Size", ("Weight", "ขนาด"))
    if package_size:
        explicit_size = re.match(r"([0-9]+(?:\.[0-9]+)?\s*(?:g|kg|gram|grams|ก\.?|กก\.?))\b", package_size, re.I)
        if explicit_size:
            package_size = _clean(explicit_size.group(1), 80)
    variant_raw = product.get("sku") or product.get("mpn") or product.get("gtin") if isinstance(product, dict) else None
    variant = _clean(variant_raw, 120) or None
    variant_path = "jsonld.Product.sku|mpn|gtin" if variant else None

    if availability is None:
        if re.search(r"\bsold out\b|สินค้าหมด|out of stock", text, re.I):
            availability, availability_raw, availability_path = "OutOfStock", "sold-out text", "visible-availability-text"
        elif re.search(r"\bin stock\b|มีสินค้า|add to cart", text, re.I):
            availability, availability_raw, availability_path = "InStock", "in-stock/add-to-cart text", "visible-availability-text"

    semantic_attributes = any((origin, process, tasting, roast, package_size))
    coffee_product = bool(products) or bool(
        re.search(r"coffee beans?|roasted coffee|เมล็ดกาแฟ", f"{name} {text[:3000]}", re.I)
    ) or (bool(re.search(r"\bcoffee\b", name, re.I)) and semantic_attributes)
    menu_only = bool(re.search(r"/(?:menu|drink)(?:/|$)", urlparse(canonical or final_url).path, re.I)) or (
        bool(re.search(r"\b(?:iced|hot)\s+(?:latte|americano|espresso|cappuccino)\b", name, re.I)) and not semantic_attributes
    )
    slug = urlparse(canonical or "").path.rstrip("/").split("/")[-1]
    record = None
    if name and price is not None and canonical and slug and coffee_product and not menu_only:
        identity = f"{(urlparse(canonical).hostname or '').casefold()}:{slug.casefold()}"
        record = {
            "record_type": "CoffeeProductCandidate",
            "coffee_product_id": retain("coffee_product_id", identity, canonical, "canonical-url-host-and-slug"),
            "product_name": retain("product_name", name, name, name_path),
            "canonical_url": retain("canonical_url", canonical, canonical_raw or final_url, canonical_path),
            "price": retain("price", price, price_raw, price_path),
            "currency": retain("currency", currency, currency_raw or currency, currency_path),
            "price_role": retain("price_role", "displayed_product_price", price_raw, price_path),
            "availability": retain("availability", availability, availability_raw, availability_path),
            "variant": retain("variant", variant, variant_raw, variant_path),
            "origin": retain("origin", origin, origin, origin_path),
            "process": retain("process", process, process, process_path),
            "tasting_notes": retain("tasting_notes", tasting, tasting, tasting_path),
            "roast_level": retain("roast_level", roast, roast, roast_path),
            "package_size": retain("package_size", package_size, package_size, package_path),
            "source": retain("source", target["source"], target["source"], "recovery-package.target.source"),
            "source_surface": retain("source_surface", target["surface"], target["surface"], "recovery-package.target.surface"),
            "observed_at": retain("observed_at", observed_at, observed_at, "transport.observed_at"),
            "production_approved": False,
            "production_store": False,
            "scheduler_action": None,
        }

    selected_structured = {
        key: _clean(product.get(key), 500)
        for key in ("@type", "name", "sku", "mpn", "gtin")
        if product.get(key) is not None
    }
    if isinstance(offer, dict):
        selected_structured["offer"] = {
            key: _clean(offer.get(key), 200)
            for key in ("price", "lowPrice", "highPrice", "priceCurrency", "availability")
            if offer.get(key) is not None
        }
    sanitized_response = {
        "capture": "sanitized-official-product-detail-fields",
        "http_status": int(http_status),
        "content_type": _clean(content_type, 120),
        "response_bytes": len(html.encode("utf-8")),
        "response_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "final_url": _safe_url(final_url),
        "canonical_url_evidence": canonical,
        "structured_product_subset": selected_structured or None,
        "labeled_field_subset": {
            key: value for key, value in {
                "origin": origin, "process": process, "tasting_notes": tasting,
                "roast_level": roast, "package_size": package_size,
            }.items() if value is not None
        },
        "raw_html_retained": False,
        "headers_retained": False,
    }
    failure_reason = None
    if record is None:
        missing = []
        if not name: missing.append("product_name")
        if price is None: missing.append("attributable_displayed_price")
        if not canonical or not slug: missing.append("canonical_identity")
        if not coffee_product: missing.append("coffee_product_semantics")
        if menu_only: missing.append("retail_product_not_cafe_menu")
        failure_reason = "normalized product withheld: " + ", ".join(missing or ["strict product contract not met"])
    return {
        "sanitized_response": sanitized_response,
        "record": record,
        "field_provenance": provenance,
        "normalization_failure_reason": failure_reason,
    }


def _record_provenance_complete(observation: dict[str, Any]) -> bool:
    record = observation.get("record") or {}
    provenance = observation.get("field_provenance") or {}
    return all(field in provenance for field in AUDITED_FIELDS if record.get(field) is not None)


def build_result(package: dict[str, Any], observations: list[dict[str, Any]], *, completed_at: str) -> dict[str, Any]:
    package = validate_package(package)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        if observation.get("source_id") in TARGET_IDS:
            grouped[observation["source_id"]].append(observation)

    source_audits = []
    warnings: list[str] = []
    hard_failures: list[str] = []
    for target in package["targets"]:
        rows = sorted(grouped[target["source_id"]], key=lambda row: int(row.get("attempt_index") or 0))
        attempted = [row for row in rows if row.get("acquisition_attempted")]
        records = [row for row in attempted if isinstance(row.get("record"), dict)]
        identities = {row["record"].get("coffee_product_id") for row in records if row["record"].get("coffee_product_id")}
        canonicals = {row["record"].get("canonical_url") for row in records if row["record"].get("canonical_url")}
        prices = [row["record"].get("price") for row in records]
        availability = [row["record"].get("availability") for row in records]
        gates = {
            "bounded_attempts_completed": len(attempted) == 2 and all(row.get("transport_completed") for row in attempted),
            "product_identity_and_price_yield": len(records) == 2 and all(row["record"].get("coffee_product_id") and row["record"].get("price") is not None for row in records),
            "official_https_canonical_identity": len(canonicals) == 1 and all(_is_allowed_url(value, target) for value in canonicals),
            "stable_product_identity": len(records) == 2 and len(identities) == 1,
            "field_level_provenance": len(records) == 2 and all(_record_provenance_complete(row) for row in records),
            "retail_product_not_cafe_menu": len(records) == 2 and all(row["record"].get("source_surface") == "official-public-product-detail" for row in records),
        }
        failures = [name for name, passed in gates.items() if not passed]
        hard_failures.extend(f"{target['source_id']}:{name}" for name in failures)
        deviations = []
        if len(set(prices)) > 1:
            deviations.append({"field": "price", "values": prices, "interpretation": "temporal display deviation; transaction price not inferred"})
        if len(set(str(value) for value in availability)) > 1:
            deviations.append({"field": "availability", "values": availability, "interpretation": "temporal availability deviation"})
        access_boundaries = [row.get("access_boundary") for row in attempted if row.get("access_boundary")]
        if access_boundaries:
            warnings.append(f"{target['source_id']} access boundary observed; no technique escalation occurred")
        source_audits.append({
            "source_id": target["source_id"],
            "source": target["source"],
            "attempt_count": len(attempted),
            "retained_record_count": len(records),
            "gate_checks": gates,
            "audit_passed": not failures,
            "hard_failures": failures,
            "repeatability": {
                "identity_repeatability_pct": 100.0 if len(records) == 2 and len(identities) == 1 else 0.0,
                "canonical_repeatability_pct": 100.0 if len(records) == 2 and len(canonicals) == 1 else 0.0,
                "price_values": prices,
                "availability_values": availability,
            },
            "deviations": deviations,
            "access_boundaries": access_boundaries,
        })

    attempted = [row for row in observations if row.get("acquisition_attempted")]
    technical_failures = [row for row in attempted if not row.get("transport_completed")]
    audit_passed = len(source_audits) == 2 and all(row["audit_passed"] for row in source_audits)
    technical_completion = not technical_failures and len(attempted) <= package["request_budget"]["maximum_acquisition_attempts"]
    classification = "evidence_obtained" if technical_completion and audit_passed else (
        "evidence_withheld" if technical_completion else "technical_failure"
    )
    return {
        "schema": SCHEMA,
        "package_id": package["package_id"],
        "completed_at": completed_at,
        "classification": classification,
        "technical_completion": technical_completion,
        "usable_candidate_evidence": audit_passed,
        "observations": observations,
        "deep_audit": {
            "audit_passed": audit_passed,
            "source_audits": source_audits,
            "hard_failures": hard_failures,
            "warnings": warnings,
        },
        "request_accounting": {
            "acquisition_attempts": len(attempted),
            "maximum_acquisition_attempts": package["request_budget"]["maximum_acquisition_attempts"],
            "transport_requests": sum(int(row.get("transport_requests") or 0) for row in attempted),
            "maximum_transport_requests": package["request_budget"]["maximum_transport_requests"],
            "retries": 0,
            "pagination": 0,
        },
        "authority": {
            "candidate_only": True,
            "candidate_evidence_ids": package["authorization"]["candidate_evidence_ids"],
            "candidate_promoted": False,
            "reviewed_corpus_authorized": False,
            "human_confirmed": False,
            "ground_truth_asserted": False,
        },
        "boundaries": {
            "public_read_only": True,
            "raw_html_retained": False,
            "headers_or_session_material_retained": False,
            "production_approved": False,
            "production_store": False,
            "scheduler_action": None,
            "knowledge_mutation": False,
            "automatic_learning_memory_export": False,
        },
    }


def technical_failure_observation(target: dict[str, Any], attempt_index: int, observed_at: str, exc: Exception) -> dict[str, Any]:
    message = re.sub(r"https?://\S+", "[public-url]", _clean(exc, 500))
    return {
        "source_id": target["source_id"],
        "source": target["source"],
        "attempt_index": attempt_index,
        "acquisition_attempted": True,
        "transport_completed": False,
        "transport_requests": int(getattr(exc, "transport_requests", 1) or 1),
        "observed_at": observed_at,
        "technical_failure": {"type": type(exc).__name__, "message": message},
        "access_boundary": None,
        "record": None,
        "field_provenance": {},
        "sanitized_response": None,
    }
