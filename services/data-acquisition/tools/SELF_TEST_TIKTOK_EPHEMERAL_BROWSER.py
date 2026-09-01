"""Deterministic security and lifecycle tests for P58 ephemeral discovery."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
TIKTOK = ROOT / "knowledge" / "v1" / "tiktok"
sys.path[:0] = [str(ROOT / "tools"), str(ACQUISITION), str(TIKTOK)]

import tiktok_ephemeral_browser as browser
import LIVE_TIKTOK_EPHEMERAL_BROWSER as live
from scope_declaration import validate_scope_declaration


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


root = load(TIKTOK / "KU2D-SCOPE-000005.json")
p01 = load(TIKTOK / "KU2D-SCOPE-000005-P01.json")
assert validate_scope_declaration(root, allowed_root_files=root["authorized_files_or_modules"]) == root
assert validate_scope_declaration(p01, parent=root) == p01
weakened = copy.deepcopy(p01)
weakened["acquisition_technique"]["browser_policy"]["third_party_cookie_storage_blocked"] = False
try:
    validate_scope_declaration(weakened, parent=root)
except ValueError:
    pass
else:
    raise AssertionError("weakened third-party cookie policy was accepted")
expanded = copy.deepcopy(p01)
expanded["acquisition_technique"]["operation_counting"]["maximum_provider_reached"] = 41
try:
    validate_scope_declaration(expanded, parent=root)
except ValueError:
    pass
else:
    raise AssertionError("expanded provider limit was accepted")

valid = "https://www.tiktok.com/@dive.school/video/7461234567890123456?lang=en"
assert browser.canonical_video_url(valid) == "https://www.tiktok.com/@dive.school/video/7461234567890123456"
for invalid in (
    "http://www.tiktok.com/@dive/video/1",
    "https://example.com/@dive/video/1",
    "https://user:pass@www.tiktok.com/@dive/video/1",
    "https://www.tiktok.com/@dive/photo/1",
):
    assert browser.canonical_video_url(invalid) is None
rows = browser.sanitize_discovery_candidates([
    {"href": valid, "text": "  เรียนดำน้ำ   Open Water  "},
    {"href": valid, "text": "duplicate"},
    {"href": "https://tracker.example/video/99", "text": "reject"},
])
assert rows == [{
    "video_id": "7461234567890123456",
    "creator_handle": "dive.school",
    "canonical_url": "https://www.tiktok.com/@dive.school/video/7461234567890123456",
    "visible_context": "เรียนดำน้ำ Open Water",
}]
assert browser.topic_qualified("Diving lesson", "เรียนดำน้ำ Open Water course")
assert browser.topic_qualified("Diving equipment", "รีวิวอุปกรณ์ดำน้ำ regulator BCD")
assert not browser.topic_qualified("Diving lesson", "snorkeling beach holiday")
assert not browser.topic_qualified("Diving equipment", "เรียนดำน้ำ Open Water")
assert browser.is_allowed_tiktok_resource_host("www.tiktok.com")
assert browser.is_allowed_tiktok_resource_host("sf16-webcast.tiktokcdn.com")
assert browser.is_allowed_tiktok_resource_host("lf16-tiktok-web.ttwstatic.com")
assert not browser.is_allowed_tiktok_resource_host("tracker.example")

ledger = browser.OperationLedger(provider_limit=2, preconnect_limit=1)
first = ledger.begin(phase="preflight", round_id="preflight", operation="navigate")
ledger.finish(first, provider_reached=True, response_status=200)
second = ledger.begin(phase="round_one", round_id="round-1", operation="discover", topic="Diving lesson")
ledger.finish(second, provider_reached=False, failure_code="preconnect_timeout")
assert ledger.summary() == {
    "provider_reached": 1, "provider_limit": 2,
    "preconnect_failures": 1, "preconnect_limit": 1, "quota_delta": 0,
}
try:
    ledger.begin(phase="round_one", round_id="round-1", operation="discover")
except RuntimeError:
    pass
else:
    raise AssertionError("exhausted preconnect budget permitted another operation")

command = browser.browser_command(Path("browser.exe"), Path("temporary-profile"))
assert "--block-third-party-cookies" in command
assert "--disable-background-networking" in command
assert "--remote-debugging-port=0" in command
assert any(value == "--user-data-dir=temporary-profile" for value in command)
assert not any("proxy" in value.casefold() or "login" in value.casefold() for value in command)


class FakeCDPConnection:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = [json.dumps(row) for row in messages]
        self.sent: list[dict] = []

    def send(self, value: str) -> None:
        self.sent.append(json.loads(value))

    def recv(self, timeout: int) -> str:
        assert timeout == 10
        return self.messages.pop(0)


cdp_session = browser.EphemeralBrowser(binary=Path("browser.exe"))
cdp_session.connection = FakeCDPConnection([
    {
        "method": "Fetch.requestPaused",
        "params": {"requestId": "paused-1", "request": {"url": "https://www.tiktok.com/"}},
    },
    {"id": 1, "result": {}},
])
assert cdp_session._command("Page.navigate", {"url": "https://www.tiktok.com/"}) == {"id": 1, "result": {}}
assert cdp_session.connection.sent[1]["method"] == "Fetch.continueRequest"
assert cdp_session.third_party_requests_blocked == 0

cdp_session = browser.EphemeralBrowser(binary=Path("browser.exe"))
cdp_session.connection = FakeCDPConnection([
    {
        "method": "Fetch.requestPaused",
        "params": {"requestId": "paused-2", "request": {"url": "https://tracker.example/pixel"}},
    },
    {"id": 1, "result": {}},
])
cdp_session._command("Page.navigate", {"url": "https://www.tiktok.com/"})
assert cdp_session.connection.sent[1]["method"] == "Fetch.failRequest"
assert cdp_session.third_party_requests_blocked == 1


class FakeProcess:
    def __init__(self) -> None:
        self.stopped = False

    def terminate(self) -> None:
        self.stopped = True

    def wait(self, timeout: int) -> int:
        assert timeout == 5
        return 0

    def poll(self) -> int | None:
        return 0 if self.stopped else None


class FakeConnection:
    def close(self) -> None:
        return None


with tempfile.TemporaryDirectory(prefix="ku2d-p58-test-") as temporary:
    outer = Path(temporary)
    session = browser.EphemeralBrowser(binary=Path("browser.exe"))
    session.temporary_root = outer / "session"
    session.profile = session.temporary_root / "profile"
    session.profile.mkdir(parents=True)
    (session.profile / "ephemeral-state").write_text("temporary", encoding="utf-8")
    session.process = FakeProcess()  # type: ignore[assignment]
    session.connection = FakeConnection()
    session._command = lambda method, params=None: {}  # type: ignore[method-assign]
    session.first_party_cookie_count = 3
    session.third_party_requests_blocked = 7
    proof = session.close()
    assert proof == {
        "process_stopped": True,
        "profile_existed_before_teardown": True,
        "profile_absent_after_teardown": True,
        "first_party_cookie_count": 3,
        "third_party_requests_blocked": 7,
        "cookie_values_read": False,
        "cookie_values_persisted": False,
        "storage_state_persisted": False,
        "browser_profile_persisted": False,
        "raw_network_log_persisted": False,
    }
    assert not session.temporary_root.exists()


def candidates(base: int, topic: str) -> list[dict[str, str]]:
    creator = "dive.school" if topic == "Diving lesson" else "dive.gear"
    context = "เรียนดำน้ำ Open Water course" if topic == "Diving lesson" else "อุปกรณ์ดำน้ำ regulator BCD gear"
    return [
        {
            "video_id": str(base + index),
            "creator_handle": creator,
            "canonical_url": f"https://www.tiktok.com/@{creator}/video/{base + index}",
            "visible_context": context,
        }
        for index in range(5)
    ]


class FakeLiveBrowser:
    def __init__(self, round_number: int, *, mismatch: bool = False, preflight_failure: bool = False) -> None:
        self.round_number = round_number
        self.mismatch = mismatch
        self.preflight_failure = preflight_failure
        self.started = False

    def start(self) -> None:
        self.started = True

    def navigate(self, url: str) -> dict:
        assert self.started
        if url == "https://www.tiktok.com/":
            return {
                "provider_reached": not self.preflight_failure,
                "response_status": 200 if not self.preflight_failure else None,
                "failure_code": None if not self.preflight_failure else "preconnect_timeout",
                "candidates": [],
            }
        lesson = "course" in url
        base = 100 if lesson else 200
        if self.mismatch and self.round_number == 2:
            base += 1000
        topic = "Diving lesson" if lesson else "Diving equipment"
        return {
            "provider_reached": True,
            "response_status": 200,
            "failure_code": None,
            "candidates": candidates(base, topic),
        }

    def close(self) -> dict:
        return {
            "process_stopped": True,
            "profile_existed_before_teardown": True,
            "profile_absent_after_teardown": True,
            "first_party_cookie_count": 2,
            "third_party_requests_blocked": 4,
            "cookie_values_read": False,
            "cookie_values_persisted": False,
            "storage_state_persisted": False,
            "browser_profile_persisted": False,
            "raw_network_log_persisted": False,
        }


def fake_verifier(url: str) -> dict:
    video_id, creator = browser.video_identity(url)
    lesson = int(video_id) < 200
    return {
        "provider_reached": True,
        "response_status": 200,
        "verified": True,
        "failure_code": None,
        "video_id": video_id,
        "creator_handle": creator,
        "author_name": "KU2D test creator",
        "title": "เรียนดำน้ำ Open Water course" if lesson else "อุปกรณ์ดำน้ำ regulator BCD gear",
        "canonical_url": url,
    }


with tempfile.TemporaryDirectory(prefix="ku2d-p58-campaign-") as temporary:
    output = Path(temporary) / "evidence.json"
    counter = iter((0, 1, 2))
    code, result = live.run_campaign(
        output,
        browser_factory=lambda: FakeLiveBrowser(next(counter)),  # type: ignore[arg-type]
        verifier=fake_verifier,
    )
    assert code == live.EXIT_SUCCESS
    assert result["status"] == "live_rounds_complete"
    assert result["technical_completion"] is True and result["success"] is True
    assert result["operation_accounting"] == {
        "provider_reached": 25, "provider_limit": 40,
        "preconnect_failures": 0, "preconnect_limit": 10, "quota_delta": 0,
    }
    assert len(result["context_destruction_proofs"]) == 3
    assert all(len(result["final_records"][topic]) == 5 for topic in live.TOPICS)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == result
    assert all(row["status"] != "started" for row in persisted["operation_ledger"])
    assert persisted["boundaries"]["production_store"] is False
    assert persisted["boundaries"]["scheduler_action"] is None

with tempfile.TemporaryDirectory(prefix="ku2d-p58-preflight-") as temporary:
    output = Path(temporary) / "evidence.json"
    code, result = live.run_campaign(
        output,
        browser_factory=lambda: FakeLiveBrowser(0, preflight_failure=True),  # type: ignore[arg-type]
        verifier=fake_verifier,
    )
    assert code == live.EXIT_EVIDENCE_WITHHELD
    assert result["stop_condition"] == "network_preflight_failed"
    assert result["operation_accounting"]["preconnect_failures"] == 1
    assert output.is_file()
    counter = iter((0, 1, 2))
    code, result = live.run_campaign(
        output,
        browser_factory=lambda: FakeLiveBrowser(next(counter)),  # type: ignore[arg-type]
        verifier=fake_verifier,
        resume_mode="preconnect",
    )
    assert code == live.EXIT_SUCCESS
    assert result["operation_accounting"]["provider_reached"] == 25
    assert result["operation_accounting"]["preconnect_failures"] == 1
    assert [row["provider_reached"] for row in result["network_preflight_history"]] == [False, True]
    assert result["operation_ledger"][1]["operation"] == "network_preflight_diagnostic"

with tempfile.TemporaryDirectory(prefix="ku2d-p58-reproduction-") as temporary:
    output = Path(temporary) / "evidence.json"
    counter = iter((0, 1, 2))
    code, result = live.run_campaign(
        output,
        browser_factory=lambda: FakeLiveBrowser(next(counter), mismatch=True),  # type: ignore[arg-type]
        verifier=fake_verifier,
    )
    assert code == live.EXIT_EVIDENCE_WITHHELD
    assert result["stop_condition"] == "round_two_identity_reproduction_failed"
    assert result["success"] is False
    assert output.is_file()

with tempfile.TemporaryDirectory(prefix="ku2d-p58-render-correction-") as temporary:
    output = Path(temporary) / "evidence.json"
    counter = iter((0, 1))
    code, result = live.run_campaign(
        output,
        browser_factory=lambda: FakeLiveBrowser(next(counter)),  # type: ignore[arg-type]
        verifier=lambda url: {
            "provider_reached": True, "response_status": 200, "verified": False,
            "failure_code": "official_identity_incomplete", "video_id": browser.video_identity(url)[0],
        },
    )
    assert code == live.EXIT_EVIDENCE_WITHHELD
    assert result["stop_condition"] == "insufficient_topic_records:Diving lesson"
    counter = iter((1, 2))
    code, result = live.run_campaign(
        output,
        browser_factory=lambda: FakeLiveBrowser(next(counter)),  # type: ignore[arg-type]
        verifier=fake_verifier,
        resume_mode="render",
    )
    assert code == live.EXIT_SUCCESS
    assert result["operation_accounting"]["provider_reached"] > 25
    assert [row["round_id"] for row in result["rounds"][-2:]] == ["round-1-recovery", "round-2-recovery"]

print("TikTok P58 ephemeral-browser checks passed: scope=2 identity=8 ledger=3 cdp=2 teardown=9 campaigns=5")
