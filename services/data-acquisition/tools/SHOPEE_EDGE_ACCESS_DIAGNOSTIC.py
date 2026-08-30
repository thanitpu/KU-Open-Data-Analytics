"""One-page, unauthenticated Shopee Thailand diagnostic for Windows Edge.

The browser starts with a fresh temporary profile and performs only the page
load requested by the operator. Evidence is written before the exit code is
returned. No production store, approval, scheduling, login, or challenge
handling is available in this tool.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import quote, quote_plus, urlparse
from urllib.request import Request, urlopen

from websockets.sync.client import connect


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from shopee_edge_access import analyze_capture, sanitize_url, technical_failure_result


EXIT_EVIDENCE_OBTAINED = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2
MAX_ITEMS = 10
MAX_SANITIZED_JSON_BYTES = 200_000


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded Shopee access diagnostic using Windows Edge")
    target = value.add_mutually_exclusive_group(required=True)
    target.add_argument("--query")
    target.add_argument("--url")
    value.add_argument("--max-items", type=int, default=10)
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
        url = f"https://shopee.co.th/search?keyword={quote_plus(query)}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in {"shopee.co.th", "www.shopee.co.th"}:
        raise ValueError("Only public HTTPS Shopee Thailand customer surfaces are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are prohibited.")
    return url, query


def _edge_candidates(environ: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []
    configured = str(environ.get("KU2D_EDGE_BINARY") or "").strip()
    if configured:
        candidates.append(Path(configured))
    for key in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        root = str(environ.get(key) or "").strip()
        if root:
            candidates.append(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return candidates


def find_edge(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    for candidate in _edge_candidates(env):
        if candidate.is_file():
            return candidate
    raise RuntimeError("Microsoft Edge executable was not found on the Windows Edge Runner.")


def _safe_console_summary(stderr: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for line in str(stderr or "").splitlines():
        lowered = line.casefold()
        if not any(marker in lowered for marker in ("error", "failed", "warning", "exception")):
            continue
        safe = re.sub(r"https?://[^\s]+", "[public-url-redacted-from-console]", " ".join(line.split()))
        safe = re.sub(r"(?i)(token|cookie|authorization|session|device[_-]?id)\s*[:=]\s*\S+", r"\1=[redacted]", safe)
        output.append({"level": "error-or-warning", "message": safe[:300]})
        if len(output) >= 20:
            break
    return output


def _new_debug_target(port: int, url: str) -> dict[str, Any]:
    request = Request(
        f"http://127.0.0.1:{port}/json/new?{quote(url, safe='')}",
        method="PUT",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _cdp_command(
    connection: Any,
    sequence: list[int],
    method: str,
    params: dict[str, Any] | None = None,
    event_queue: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sequence[0] += 1
    command_id = sequence[0]
    connection.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
    while True:
        message = json.loads(connection.recv(timeout=10))
        if message.get("id") == command_id:
            return message
        if event_queue is not None and message.get("method"):
            event_queue.append(message)


def _capture_via_cdp(port: int, url: str) -> dict[str, Any]:
    target = _new_debug_target(port, "about:blank")
    websocket_url = target.get("webSocketDebuggerUrl")
    if not websocket_url:
        raise RuntimeError("Edge DevTools target did not expose a WebSocket URL.")
    requests: dict[str, dict[str, Any]] = {}
    console: list[dict[str, Any]] = []
    final_url = url
    loaded = False
    challenge_seen = False
    sequence = [0]
    pending_events: list[dict[str, Any]] = []
    with connect(websocket_url, origin="http://localhost", open_timeout=5, close_timeout=2) as connection:
        _cdp_command(connection, sequence, "Network.enable", {
            "maxTotalBufferSize": MAX_SANITIZED_JSON_BYTES * 5,
            "maxResourceBufferSize": MAX_SANITIZED_JSON_BYTES,
        }, pending_events)
        _cdp_command(connection, sequence, "Page.enable", event_queue=pending_events)
        _cdp_command(connection, sequence, "Runtime.enable", event_queue=pending_events)
        _cdp_command(connection, sequence, "Log.enable", event_queue=pending_events)
        _cdp_command(connection, sequence, "Page.navigate", {"url": url}, pending_events)
        deadline = time.monotonic() + 30
        quiet_deadline: float | None = None
        while time.monotonic() < deadline and not challenge_seen:
            if quiet_deadline is not None and time.monotonic() >= quiet_deadline:
                break
            if pending_events:
                message = pending_events.pop(0)
            else:
                try:
                    message = json.loads(connection.recv(timeout=1))
                except TimeoutError:
                    continue
            method = message.get("method")
            params = message.get("params") or {}
            if method == "Network.requestWillBeSent":
                request = params.get("request") or {}
                request_url = str(request.get("url") or "")
                request_id = str(params.get("requestId") or "")
                if request_id and request_url:
                    requests.setdefault(request_id, {
                        "url": request_url,
                        "method": str(request.get("method") or "GET"),
                        "status": None, "content_type": None, "response_size": 0,
                    })
                    if "/verify/traffic/" in request_url.casefold():
                        final_url, challenge_seen = request_url, True
            elif method == "Network.responseReceived":
                response = params.get("response") or {}
                request_id = str(params.get("requestId") or "")
                response_url = str(response.get("url") or "")
                row = requests.setdefault(request_id, {"url": response_url, "method": "GET"})
                row.update({
                    "url": response_url or row.get("url"),
                    "status": int(response.get("status") or 0) or None,
                    "content_type": str(response.get("mimeType") or "") or None,
                    "response_size": int(response.get("encodedDataLength") or 0),
                })
                if "/verify/traffic/" in response_url.casefold() or row.get("status") in {401, 403, 429}:
                    if "/verify/traffic/" in response_url.casefold():
                        final_url = response_url
                    challenge_seen = True
            elif method == "Network.loadingFinished":
                row = requests.get(str(params.get("requestId") or ""))
                if row is not None:
                    row["response_size"] = int(params.get("encodedDataLength") or row.get("response_size") or 0)
                    row["loaded"] = True
            elif method == "Page.frameNavigated":
                frame = params.get("frame") or {}
                if not frame.get("parentId") and frame.get("url"):
                    final_url = str(frame["url"])
                    if "/verify/traffic/" in final_url.casefold():
                        challenge_seen = True
            elif method == "Page.loadEventFired":
                loaded = True
                quiet_deadline = time.monotonic() + 3
            elif method == "Runtime.exceptionThrown":
                details = params.get("exceptionDetails") or {}
                console.append({"level": "exception", "message": str(details.get("text") or "JavaScript exception")})
            elif method == "Log.entryAdded":
                entry = params.get("entry") or {}
                if str(entry.get("level") or "").casefold() in {"error", "warning"}:
                    console.append({"level": str(entry.get("level")), "message": str(entry.get("text") or "")})
        if challenge_seen:
            try:
                _cdp_command(connection, sequence, "Page.stopLoading")
            except Exception:
                pass
        for request_id, row in list(requests.items()):
            content_type = str(row.get("content_type") or "").casefold()
            safe_url = sanitize_url(row.get("url"))
            host = urlparse(safe_url).hostname if safe_url and safe_url.startswith("http") else None
            size = int(row.get("response_size") or 0)
            if (
                row.get("loaded") and "json" in content_type and host in {"shopee.co.th", "www.shopee.co.th"}
                and 0 < size <= MAX_SANITIZED_JSON_BYTES and not challenge_seen
            ):
                response = _cdp_command(connection, sequence, "Network.getResponseBody", {"requestId": request_id})
                body = (response.get("result") or {}).get("body")
                if body and (response.get("result") or {}).get("base64Encoded"):
                    try:
                        body = base64.b64decode(body).decode("utf-8")
                    except (ValueError, UnicodeDecodeError):
                        body = None
                if body and len(body.encode("utf-8")) <= MAX_SANITIZED_JSON_BYTES:
                    try:
                        row["response_json"] = json.loads(body)
                    except json.JSONDecodeError:
                        pass
        evaluation = _cdp_command(connection, sequence, "Runtime.evaluate", {
            "expression": "({html:document.documentElement.outerHTML,title:document.title,url:location.href})",
            "returnByValue": True,
        })
        value = (((evaluation.get("result") or {}).get("result") or {}).get("value") or {})
        final_url = str(value.get("url") or final_url)
        official_requests = []
        for row in requests.values():
            safe = sanitize_url(row.get("url"))
            hostname = urlparse(safe).hostname if safe and safe.startswith("http") else None
            if hostname in {"shopee.co.th", "www.shopee.co.th"}:
                official_requests.append(row)
        return {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "initial_url": url,
            "final_url": final_url,
            "title": str(value.get("title") or ""),
            "html": str(value.get("html") or ""),
            "network_requests": official_requests[:100],
            "console_errors_summary": _safe_console_summary("\n".join(str(row.get("message") or "") for row in console)),
            "page_load_event_observed": loaded,
        }


def capture_edge_page(url: str, max_items: int) -> dict[str, Any]:
    """Run one normal, fresh-profile Edge page load and return bounded metadata."""
    del max_items  # the analyzer applies the evidence bound after capture
    if os.name != "nt":
        raise RuntimeError("Shopee Edge diagnostic requires the reviewed Windows Edge Runner.")
    edge = find_edge()
    with TemporaryDirectory(prefix="ku2d-shopee-edge-") as folder:
        temporary = Path(folder)
        profile = temporary / "fresh-profile"
        command = [
            str(edge),
            "--headless=new",
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            "--disable-default-apps",
            "--remote-debugging-port=0",
            "--remote-allow-origins=http://localhost",
            f"--user-data-dir={profile}",
            "about:blank",
        ]
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=False,
        )
        try:
            port_file = profile / "DevToolsActivePort"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not port_file.is_file():
                if process.poll() is not None:
                    raise RuntimeError(f"Microsoft Edge exited before DevTools became available ({process.returncode}).")
                time.sleep(0.1)
            if not port_file.is_file():
                raise RuntimeError("Microsoft Edge DevTools did not become available within 10 seconds.")
            port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
            return _capture_via_cdp(port, url)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _write_evidence(output: Path, result: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None, *, capture_provider: Callable[[str, int], dict[str, Any]] = capture_edge_page) -> int:
    args = parser().parse_args(argv)
    url, query = None, str(args.query or "").strip() or None
    result: dict[str, Any]
    exit_code = EXIT_TECHNICAL_FAILURE
    try:
        url, query = target(args)
        snapshot = capture_provider(url, args.max_items)
        result = analyze_capture(snapshot, target_url=url, query=query, max_items=args.max_items)
        exit_code = EXIT_EVIDENCE_OBTAINED if result["usable_evidence"] else EXIT_EVIDENCE_WITHHELD
    except Exception as exc:
        result = technical_failure_result(target_url=url or args.url, query=query, max_items=args.max_items, exc=exc)
    try:
        _write_evidence(args.output, result)
    except Exception as exc:
        print(f"Shopee Edge diagnostic evidence writing failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    print(json.dumps({
        "schema": result["schema"],
        "classification": result["classification"],
        "technical_completion": result["technical_completion"],
        "usable_evidence": result["usable_evidence"],
        "visible_product_card_count": result["visible_product_card_count"],
        "validated_network_endpoint_count": result["validated_network_endpoint_count"],
        "production_store": result["production_store"],
        "scheduler_action": result["scheduler_action"],
        "output": str(args.output),
        "exit_classification": exit_code,
    }, ensure_ascii=False, sort_keys=True))
    if exit_code != EXIT_EVIDENCE_OBTAINED:
        print(f"Shopee Edge evidence withheld: {result.get('failure_reason')}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
