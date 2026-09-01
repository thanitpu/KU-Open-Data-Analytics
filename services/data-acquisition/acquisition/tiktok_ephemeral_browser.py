"""Bounded public TikTok discovery in disposable Chrome/Edge profiles.

Only sanitized public identities leave this module. Cookie values, browser
storage, raw DOM, headers, bodies, request URLs, and browser profiles are never
returned or persisted.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from websockets.sync.client import connect


PROVIDER_LIMIT = 40
PRECONNECT_LIMIT = 10
MAX_RECORDS_PER_TOPIC = 5
MAX_OEMBED_BYTES = 200_000
CANONICAL_VIDEO = re.compile(
    r"^https://(?:www\.)?tiktok\.com/@(?P<creator>[A-Za-z0-9._-]+)/video/(?P<video_id>[0-9]+)$",
    re.IGNORECASE,
)


def observed_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_tiktok_host(value: str | None) -> bool:
    host = str(value or "").rstrip(".").casefold()
    return host == "tiktok.com" or host.endswith(".tiktok.com")


def canonical_video_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not is_tiktok_host(parsed.hostname):
        return None
    if parsed.username or parsed.password:
        return None
    match = re.fullmatch(r"/@([A-Za-z0-9._-]+)/video/([0-9]+)/?", parsed.path)
    if not match:
        return None
    return f"https://www.tiktok.com/@{match.group(1)}/video/{match.group(2)}"


def video_identity(url: str) -> tuple[str, str]:
    match = CANONICAL_VIDEO.fullmatch(url)
    if not match:
        raise ValueError("canonical TikTok video URL is required")
    return match.group("video_id"), match.group("creator")


def sanitize_discovery_candidates(rows: Any, *, maximum: int = 20) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        canonical = canonical_video_url(row.get("href"))
        if not canonical:
            continue
        video_id, creator = video_identity(canonical)
        if video_id in seen:
            continue
        seen.add(video_id)
        text = " ".join(str(row.get("text") or "").split())[:300]
        result.append({
            "video_id": video_id,
            "creator_handle": creator,
            "canonical_url": canonical,
            "visible_context": text,
        })
        if len(result) >= maximum:
            break
    return result


def topic_qualified(topic: str, *values: Any) -> bool:
    text = " ".join(str(value or "") for value in values).casefold()
    dive = any(word in text for word in ("ดำน้ำ", "scuba", "diving", "dive ", "diver"))
    if not dive:
        return False
    if topic == "Diving lesson":
        return any(word in text for word in (
            "เรียน", "สอน", "ครู", "คอร์ส", "หลักสูตร", "lesson", "course",
            "training", "instructor", "open water", "divemaster", "certif",
        ))
    if topic == "Diving equipment":
        return any(word in text for word in (
            "อุปกรณ์", "หน้ากาก", "ตีนกบ", "เรกูเลเตอร์", "regulator", "gear",
            "equipment", "mask", "fins", "wetsuit", "bcd", "dive computer",
            "tank", "octopus",
        ))
    raise ValueError("unsupported TikTok topic")


@dataclass
class OperationLedger:
    provider_limit: int = PROVIDER_LIMIT
    preconnect_limit: int = PRECONNECT_LIMIT
    rows: list[dict[str, Any]] = field(default_factory=list)

    def begin(self, *, phase: str, round_id: str, operation: str, topic: str | None = None,
              public_identity: str | None = None) -> dict[str, Any]:
        if any(row["status"] == "started" for row in self.rows):
            raise RuntimeError("the previous operation must be finalized first")
        if self.provider_reached >= self.provider_limit or self.preconnect_failures >= self.preconnect_limit:
            raise RuntimeError("an operation budget is exhausted")
        row = {
            "sequence": len(self.rows) + 1,
            "started_at": observed_at(),
            "completed_at": None,
            "phase": phase,
            "round_id": round_id,
            "operation": operation,
            "topic": topic,
            "public_identity": public_identity,
            "status": "started",
            "provider_reached": None,
            "response_status": None,
            "candidate_count": 0,
            "retained_count": 0,
            "failure_code": None,
            "quota_delta": 0,
        }
        self.rows.append(row)
        return row

    def finish(self, row: dict[str, Any], *, provider_reached: bool,
               response_status: int | None = None, candidate_count: int = 0,
               retained_count: int = 0, failure_code: str | None = None) -> None:
        if row is not self.rows[-1] or row["status"] != "started":
            raise RuntimeError("only the active operation may be finalized")
        row.update({
            "completed_at": observed_at(),
            "status": "provider_reached" if provider_reached else "preconnect_failure",
            "provider_reached": provider_reached,
            "response_status": response_status,
            "candidate_count": int(candidate_count),
            "retained_count": int(retained_count),
            "failure_code": failure_code,
        })
        if self.provider_reached > self.provider_limit or self.preconnect_failures > self.preconnect_limit:
            raise RuntimeError("operation budget exceeded")

    @property
    def provider_reached(self) -> int:
        return sum(row.get("provider_reached") is True for row in self.rows)

    @property
    def preconnect_failures(self) -> int:
        return sum(row.get("provider_reached") is False for row in self.rows)

    def summary(self) -> dict[str, int]:
        return {
            "provider_reached": self.provider_reached,
            "provider_limit": self.provider_limit,
            "preconnect_failures": self.preconnect_failures,
            "preconnect_limit": self.preconnect_limit,
            "quota_delta": 0,
        }


def browser_candidates(environ: dict[str, str] | None = None) -> list[Path]:
    env = os.environ if environ is None else environ
    values: list[Path] = []
    configured = str(env.get("KU2D_BROWSER_BINARY") or "").strip()
    if configured:
        values.append(Path(configured))
    for key, relative in (
        ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
        ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"),
        ("LOCALAPPDATA", "Microsoft/Edge/Application/msedge.exe"),
        ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
        ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
    ):
        root = str(env.get(key) or "").strip()
        if root:
            values.append(Path(root) / relative)
    return values


def find_browser(environ: dict[str, str] | None = None) -> Path:
    for candidate in browser_candidates(environ):
        if candidate.is_file():
            return candidate
    raise RuntimeError("Chrome or Edge executable was not found")


def browser_command(binary: Path, profile: Path) -> list[str]:
    return [
        str(binary), "--headless=new", "--disable-extensions", "--disable-sync",
        "--disable-background-networking", "--disable-component-update",
        "--disable-default-apps", "--no-first-run", "--block-third-party-cookies",
        "--remote-debugging-port=0", "--remote-allow-origins=http://localhost",
        f"--user-data-dir={profile}", "about:blank",
    ]


class EphemeralBrowser:
    """One disposable browser process and one CDP page."""

    def __init__(self, binary: Path | None = None) -> None:
        self.binary = binary or find_browser()
        self.temporary_root: Path | None = None
        self.profile: Path | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self.connection: Any = None
        self.sequence = 0
        self.pending: list[dict[str, Any]] = []
        self.third_party_requests_blocked = 0
        self.allowed_subresource_responses = 0
        self.first_party_cookie_count = 0

    def _command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sequence += 1
        command_id = self.sequence
        self.connection.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.connection.recv(timeout=10))
            if message.get("id") == command_id:
                if message.get("error"):
                    raise RuntimeError(f"CDP {method} failed: {message['error'].get('message', 'unknown error')}")
                return message
            self.pending.append(message)

    def start(self) -> None:
        if self.process is not None:
            raise RuntimeError("browser is already started")
        self.temporary_root = Path(tempfile.mkdtemp(prefix="ku2d-tiktok-ephemeral-"))
        self.profile = self.temporary_root / "profile"
        self.process = subprocess.Popen(
            browser_command(self.binary, self.profile),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        port_file = self.profile / "DevToolsActivePort"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not port_file.is_file():
            if self.process.poll() is not None:
                raise RuntimeError(f"browser exited before CDP became available ({self.process.returncode})")
            time.sleep(0.1)
        if not port_file.is_file():
            raise RuntimeError("browser CDP port was not available within 15 seconds")
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        request = Request(f"http://127.0.0.1:{port}/json/new?{quote('about:blank', safe='')}", method="PUT")
        with urlopen(request, timeout=5) as response:
            target = json.loads(response.read().decode("utf-8"))
        websocket_url = target.get("webSocketDebuggerUrl")
        if not websocket_url:
            raise RuntimeError("browser CDP target did not expose a WebSocket URL")
        self.connection = connect(websocket_url, origin="http://localhost", open_timeout=5, close_timeout=2)
        self._command("Page.enable")
        self._command("Runtime.enable")
        self._command("Network.enable")
        self._command("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})

    def _handle_event(self, message: dict[str, Any]) -> tuple[bool, int | None, str | None]:
        method = message.get("method")
        params = message.get("params") or {}
        if method == "Fetch.requestPaused":
            request = params.get("request") or {}
            host = urlparse(str(request.get("url") or "")).hostname
            request_id = params.get("requestId")
            if is_tiktok_host(host):
                self._command("Fetch.continueRequest", {"requestId": request_id})
            else:
                self.third_party_requests_blocked += 1
                self._command("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
            return False, None, None
        if method == "Network.responseReceived":
            response = params.get("response") or {}
            host = urlparse(str(response.get("url") or "")).hostname
            if is_tiktok_host(host):
                self.allowed_subresource_responses += 1
                if str(params.get("type") or "").casefold() == "document":
                    return True, int(response.get("status") or 0) or None, None
        if method == "Page.frameNavigated":
            frame = params.get("frame") or {}
            if not frame.get("parentId"):
                final = str(frame.get("url") or "")
                host = urlparse(final).hostname
                if final.startswith("http") and not is_tiktok_host(host):
                    return False, None, "top_level_left_tiktok"
                lowered = final.casefold()
                if any(marker in lowered for marker in ("/login", "captcha", "/verify/")):
                    return False, None, "challenge_or_login_wall"
        return False, None, None

    def navigate(self, url: str, *, timeout_seconds: int = 30) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not is_tiktok_host(parsed.hostname) or parsed.username or parsed.password:
            raise ValueError("only public HTTPS TikTok navigation is allowed")
        self._command("Page.navigate", {"url": url})
        provider_reached = False
        response_status: int | None = None
        failure_code: str | None = None
        loaded_at: float | None = None
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if loaded_at is not None and time.monotonic() - loaded_at >= 6:
                break
            if self.pending:
                message = self.pending.pop(0)
            else:
                try:
                    message = json.loads(self.connection.recv(timeout=1))
                except TimeoutError:
                    continue
            reached, status, failure = self._handle_event(message)
            provider_reached = provider_reached or reached
            response_status = status or response_status
            failure_code = failure or failure_code
            if message.get("method") == "Page.loadEventFired":
                loaded_at = time.monotonic()
            if failure_code:
                try:
                    self._command("Page.stopLoading")
                except Exception:
                    pass
                break
        evaluation = self._command("Runtime.evaluate", {
            "expression": """(() => { const text=(document.body&&document.body.innerText||'').toLowerCase(); return {title:(document.title||'').slice(0,300),url:location.href,challenge:/captcha|verify you are human|security check/.test(text),login:/log in to tiktok|sign in to tiktok/.test(text),anchors:Array.from(document.querySelectorAll('a[href*=\"/video/\"]')).slice(0,80).map(a=>({href:a.href,text:(a.innerText||a.getAttribute('aria-label')||'').slice(0,300)}))}; })()""",
            "returnByValue": True,
        })
        value = (((evaluation.get("result") or {}).get("result") or {}).get("value") or {})
        final_url = str(value.get("url") or "")
        if not is_tiktok_host(urlparse(final_url).hostname):
            failure_code = failure_code or "top_level_left_tiktok"
        if value.get("challenge") or value.get("login"):
            failure_code = failure_code or "challenge_or_login_wall"
        cookie_evaluation = self._command("Runtime.evaluate", {
            "expression": "document.cookie ? document.cookie.split(';').filter(Boolean).length : 0",
            "returnByValue": True,
        })
        cookie_value = (((cookie_evaluation.get("result") or {}).get("result") or {}).get("value") or 0)
        self.first_party_cookie_count = max(self.first_party_cookie_count, int(cookie_value))
        return {
            "provider_reached": provider_reached,
            "response_status": response_status,
            "page_load_event_observed": loaded_at is not None,
            "failure_code": failure_code,
            "title": " ".join(str(value.get("title") or "").split())[:300],
            "candidates": sanitize_discovery_candidates(value.get("anchors")),
            "telemetry": {
                "tiktok_response_count": self.allowed_subresource_responses,
                "third_party_requests_blocked": self.third_party_requests_blocked,
                "first_party_cookie_count": self.first_party_cookie_count,
            },
        }

    def close(self) -> dict[str, Any]:
        profile = self.profile
        if self.connection is not None:
            for method, params in (
                ("Network.clearBrowserCookies", None),
                ("Network.clearBrowserCache", None),
            ):
                try:
                    self._command(method, params)
                except Exception:
                    pass
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
        process_stopped = True
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            process_stopped = self.process.poll() is not None
            self.process = None
        profile_existed = bool(profile and profile.exists())
        if self.temporary_root is not None:
            shutil.rmtree(self.temporary_root, ignore_errors=False)
        profile_absent = profile is None or not profile.exists()
        return {
            "process_stopped": process_stopped,
            "profile_existed_before_teardown": profile_existed,
            "profile_absent_after_teardown": profile_absent,
            "first_party_cookie_count": self.first_party_cookie_count,
            "third_party_requests_blocked": self.third_party_requests_blocked,
            "cookie_values_read": False,
            "cookie_values_persisted": False,
            "storage_state_persisted": False,
            "browser_profile_persisted": not profile_absent,
            "raw_network_log_persisted": False,
        }


def verify_oembed(canonical_url: str, *, timeout_seconds: int = 15) -> dict[str, Any]:
    video_id, creator = video_identity(canonical_url)
    endpoint = f"https://www.tiktok.com/oembed?url={quote(canonical_url, safe='')}"
    request = Request(endpoint, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.status)
            body = response.read(MAX_OEMBED_BYTES + 1)
    except HTTPError as exc:
        return {
            "provider_reached": True, "response_status": int(exc.code), "verified": False,
            "failure_code": "official_verification_http_error", "video_id": video_id,
        }
    except Exception as exc:
        return {
            "provider_reached": False, "response_status": None, "verified": False,
            "failure_code": f"preconnect_{type(exc).__name__}", "video_id": video_id,
        }
    if len(body) > MAX_OEMBED_BYTES:
        return {
            "provider_reached": True, "response_status": status, "verified": False,
            "failure_code": "official_response_too_large", "video_id": video_id,
        }
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "provider_reached": True, "response_status": status, "verified": False,
            "failure_code": "official_response_invalid_json", "video_id": video_id,
        }
    if not isinstance(payload, dict):
        payload = {}
    title = " ".join(str(payload.get("title") or "").split())[:500]
    author_name = " ".join(str(payload.get("author_name") or "").split())[:200]
    author_url = str(payload.get("author_url") or "")
    author_host = urlparse(author_url).hostname
    verified = status == 200 and bool(title) and bool(author_name) and is_tiktok_host(author_host)
    return {
        "provider_reached": True,
        "response_status": status,
        "verified": verified,
        "failure_code": None if verified else "official_identity_incomplete",
        "video_id": video_id,
        "creator_handle": creator,
        "author_name": author_name,
        "title": title,
        "canonical_url": canonical_url,
    }
