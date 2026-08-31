"""Run the reviewed Roots/Nana Coffee evidence-recovery package.

Every request is preceded by a durable pending-attempt ledger write and every
response is sanitized and written before the next request or process exit.
The tool has no production, approval, browser, authentication, or retry path.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from coffee_evidence_recovery import (
    SCHEMA,
    build_result,
    normalize_product_detail,
    technical_failure_observation,
    validate_package,
)


EXIT_EVIDENCE_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2
DEFAULT_PACKAGE = ROOT / "config" / "coffee_evidence_recovery_package.json"
USER_AGENT = "KU2D-Evidence-Recovery/1.0 (+https://github.com/thanitpu/KU-Open-Data-Analytics)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded Roots/Nana Coffee official-detail evidence recovery")
    value.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--no-production-store", action="store_true")
    return value


def _allowed_hosts(target: dict[str, Any]) -> set[str]:
    return {
        str(host).casefold()
        for host in (target.get("allowed_hosts") or [target.get("official_host")])
        if str(host or "").strip()
    }


def _safe_official_url(url: str, target: dict[str, Any]) -> str:
    parsed = urlparse(str(url or "").strip())
    if (
        parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
        or parsed.hostname.casefold() not in _allowed_hosts(target)
    ):
        raise ValueError("Request or redirect left the configured official HTTPS host.")
    return parsed._replace(query="", fragment="").geturl()


class AccessBoundaryError(RuntimeError):
    def __init__(self, message: str, *, transport_requests: int = 1):
        super().__init__(message)
        self.transport_requests = transport_requests


class _RedirectTracker(HTTPRedirectHandler):
    def __init__(self, target: dict[str, Any], maximum_redirects: int):
        super().__init__()
        self.target = target
        self.maximum_redirects = maximum_redirects
        self.redirects: list[dict[str, Any]] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        transport_requests = 1 + len(self.redirects)
        if len(self.redirects) >= self.maximum_redirects:
            raise AccessBoundaryError("Official response exceeded the redirect bound.", transport_requests=transport_requests)
        try:
            safe = _safe_official_url(newurl, self.target)
        except ValueError as exc:
            raise AccessBoundaryError(str(exc), transport_requests=transport_requests) from exc
        self.redirects.append({"status": int(code), "url": safe})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_bounded(response, maximum_bytes: int) -> tuple[str, int, bool]:  # noqa: ANN001
    raw = response.read(maximum_bytes + 1)
    exceeded = len(raw) > maximum_bytes
    retained = raw[:maximum_bytes]
    charset = response.headers.get_content_charset() or "utf-8"
    return retained.decode(charset, "replace"), len(raw), exceeded


def _access_marker(status: int, body: str) -> tuple[str | None, dict[str, Any] | None]:
    if status in {401, 403, 429}:
        classification = f"http_status_{status}"
        return classification, {"detector": "http-status", "marker": status, "confidence": "explicit"}
    bounded = body[:250_000]
    soup = None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(bounded, "html.parser")
    except Exception:
        pass
    title = " ".join((soup.title.get_text(" ", strip=True) if soup and soup.title else "").split()).casefold()
    visible = " ".join((soup.get_text(" ", strip=True) if soup else "").split()).casefold()
    checks = (
        ("captcha_or_human_verification", "verify you are human", title, "document-title"),
        ("captcha_or_human_verification", "verify you are human", visible, "visible-text"),
        ("access_denied", "access denied", title, "document-title"),
        ("access_denied", "access denied", visible[:2_000], "leading-visible-text"),
        ("traffic_verification", "/verify/traffic/", bounded.casefold(), "document-route-marker"),
        ("anti_bot_challenge", "cf-chl-", bounded.casefold(), "challenge-markup"),
    )
    for classification, marker, haystack, evidence_path in checks:
        if marker in haystack:
            return classification, {
                "detector": "bounded-visible-challenge-v2",
                "marker": marker,
                "evidence_path": evidence_path,
                "confidence": "explicit-screening-evidence",
            }
    if soup and soup.find(attrs={"class": re.compile(r"(?:^|\s)(?:g-recaptcha|h-captcha)(?:\s|$)", re.I)}):
        return "captcha_or_human_verification", {
            "detector": "bounded-visible-challenge-v2",
            "marker": "captcha-widget",
            "evidence_path": "dom-class",
            "confidence": "explicit-screening-evidence",
        }
    return None, None


def fetch_public_detail(target: dict[str, Any], budget: dict[str, Any], attempt_index: int) -> dict[str, Any]:
    """Perform one unauthenticated official GET with bounded redirects/body."""
    del attempt_index
    url = _safe_official_url(target["url"], target)
    tracker = _RedirectTracker(target, int(budget["maximum_redirects_per_attempt"]))
    opener = build_opener(tracker)
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9",
            "Accept-Language": "th-TH,th;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    maximum = int(budget["maximum_response_bytes"])
    timeout = int(budget["timeout_seconds"])
    try:
        with opener.open(request, timeout=timeout) as response:
            body, bytes_read, exceeded = _read_bounded(response, maximum)
            status = int(getattr(response, "status", 200))
            final_url = _safe_official_url(response.geturl(), target)
            content_type = str(response.headers.get("Content-Type") or "")
    except HTTPError as exc:
        body, bytes_read, exceeded = _read_bounded(exc, maximum)
        status = int(exc.code)
        final_url = _safe_official_url(exc.geturl(), target)
        content_type = str(exc.headers.get("Content-Type") or "") if exc.headers else ""
    except AccessBoundaryError:
        raise
    except URLError as exc:
        failure = RuntimeError(f"Public official request failed: {type(exc.reason).__name__}")
        failure.transport_requests = 1 + len(tracker.redirects)  # type: ignore[attr-defined]
        raise failure from exc

    access_boundary, access_boundary_evidence = _access_marker(status, body)
    if exceeded:
        access_boundary = "response_size_limit"
        access_boundary_evidence = {
            "detector": "response-byte-limit", "marker": maximum,
            "confidence": "explicit",
        }
        body = ""
    return {
        "transport_completed": True,
        "transport_requests": 1 + len(tracker.redirects),
        "http_status": status,
        "final_url": final_url,
        "content_type": content_type,
        "response_bytes_read": bytes_read,
        "redirect_chain": tracker.redirects,
        "access_boundary": access_boundary,
        "access_boundary_evidence": access_boundary_evidence,
        "body": body,
    }


def _write_evidence(output: Path, result: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def _prepared_result(package: dict[str, Any], observations: list[dict[str, Any]], state: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "package_id": package["package_id"],
        "run_state": state,
        "technical_completion": False,
        "observations": observations,
        "request_accounting": {
            "acquisition_attempts_started": sum(row.get("acquisition_attempted") is not False for row in observations),
            "maximum_acquisition_attempts": package["request_budget"]["maximum_acquisition_attempts"],
            "retries": 0,
            "pagination": 0,
        },
        "boundaries": {
            "public_read_only": True,
            "raw_html_retained": False,
            "headers_or_session_material_retained": False,
            "production_approved": False,
            "production_store": False,
            "scheduler_action": None,
            "knowledge_mutation": False,
        },
    }


def run_recovery(
    package: dict[str, Any],
    output: Path,
    *,
    fetch_provider: Callable[[dict[str, Any], dict[str, Any], int], dict[str, Any]] = fetch_public_detail,
    clock: Callable[[], str] = _now,
) -> dict[str, Any]:
    package = validate_package(package)
    observations: list[dict[str, Any]] = []
    _write_evidence(output, _prepared_result(package, observations, "prepared-before-first-request"))
    stop_all = False
    for target in package["targets"]:
        for attempt_index in range(1, int(package["request_budget"]["observations_per_source"]) + 1):
            observed_at = clock()
            pending = {
                "source_id": target["source_id"],
                "source": target["source"],
                "attempt_index": attempt_index,
                "acquisition_attempted": False,
                "transport_completed": False,
                "observed_at": observed_at,
                "state": "request-pending",
            }
            observations.append(pending)
            _write_evidence(output, _prepared_result(package, observations, "request-ledger-written-before-network"))
            pending["acquisition_attempted"] = True
            pending["state"] = "request-completed"
            try:
                fetched = fetch_provider(target, package["request_budget"], attempt_index)
                pending.update({
                    "transport_completed": bool(fetched.get("transport_completed")),
                    "transport_requests": int(fetched.get("transport_requests") or 0),
                    "http_status": fetched.get("http_status"),
                    "final_url": fetched.get("final_url"),
                    "content_type": fetched.get("content_type"),
                    "response_bytes_read": fetched.get("response_bytes_read"),
                    "redirect_chain": fetched.get("redirect_chain") or [],
                    "access_boundary": fetched.get("access_boundary"),
                    "access_boundary_evidence": fetched.get("access_boundary_evidence"),
                    "technical_failure": None,
                })
                body = str(fetched.get("body") or "")
                if pending["transport_completed"] and not pending["access_boundary"] and body:
                    try:
                        normalized = normalize_product_detail(
                            body, target, final_url=str(fetched.get("final_url") or target["url"]),
                            observed_at=observed_at, http_status=int(fetched.get("http_status") or 0),
                            content_type=str(fetched.get("content_type") or ""),
                        )
                    except Exception as exc:
                        normalized = {
                            "record": None, "field_provenance": {}, "sanitized_response": None,
                            "normalization_failure_reason": f"{type(exc).__name__}: {re.sub(r'https?://\\S+', '[public-url]', str(exc))[:400]}",
                        }
                    pending.update(normalized)
                else:
                    pending.update({
                        "record": None, "field_provenance": {}, "sanitized_response": {
                            "capture": "sanitized-access-boundary-metadata",
                            "http_status": pending.get("http_status"),
                            "content_type": pending.get("content_type"),
                            "response_bytes_read": pending.get("response_bytes_read"),
                            "final_url": pending.get("final_url"),
                            "access_boundary_evidence": pending.get("access_boundary_evidence"),
                            "raw_html_retained": False,
                            "headers_retained": False,
                        },
                        "normalization_failure_reason": "extraction not attempted because an access/environment boundary was observed",
                    })
            except AccessBoundaryError as exc:
                pending.update({
                    "transport_completed": True,
                    "transport_requests": exc.transport_requests,
                    "access_boundary": "redirect_boundary",
                    "technical_failure": None,
                    "record": None,
                    "field_provenance": {},
                    "sanitized_response": None,
                    "normalization_failure_reason": str(exc),
                })
            except Exception as exc:
                observations[-1] = technical_failure_observation(target, attempt_index, observed_at, exc)
                stop_all = True
            _write_evidence(output, _prepared_result(package, observations, "response-sanitized-and-retained"))
            if (
                stop_all
                or observations[-1].get("access_boundary")
                or (attempt_index == 1 and not isinstance(observations[-1].get("record"), dict))
            ):
                break
        if stop_all:
            break
    result = build_result(package, observations, completed_at=clock())
    result["run_state"] = "complete"
    _write_evidence(output, result)
    return result


def _load_package(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Coffee recovery package must be a JSON object.")
    return value


def main(
    argv=None,
    *,
    fetch_provider: Callable[[dict[str, Any], dict[str, Any], int], dict[str, Any]] = fetch_public_detail,
    clock: Callable[[], str] = _now,
) -> int:
    args = parser().parse_args(argv)
    if not args.no_production_store:
        print("Coffee evidence recovery requires --no-production-store.", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    try:
        result = run_recovery(_load_package(args.package), args.output, fetch_provider=fetch_provider, clock=clock)
    except Exception as exc:
        print(f"Coffee evidence recovery failed before durable completion: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    exit_code = EXIT_EVIDENCE_OBTAINED if result["usable_candidate_evidence"] else (
        EXIT_EVIDENCE_WITHHELD if result["technical_completion"] else EXIT_TECHNICAL_FAILURE
    )
    print(json.dumps({
        "schema": result["schema"],
        "classification": result["classification"],
        "technical_completion": result["technical_completion"],
        "usable_candidate_evidence": result["usable_candidate_evidence"],
        "acquisition_attempts": result["request_accounting"]["acquisition_attempts"],
        "transport_requests": result["request_accounting"]["transport_requests"],
        "deep_audit_passed": result["deep_audit"]["audit_passed"],
        "production_approved": result["boundaries"]["production_approved"],
        "production_store": result["boundaries"]["production_store"],
        "scheduler_action": result["boundaries"]["scheduler_action"],
        "output": str(args.output),
        "exit_classification": exit_code,
    }, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
