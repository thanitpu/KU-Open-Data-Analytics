"""Execute the human-authorized, bounded P58 TikTok browser campaign."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "acquisition"
if str(ACQUISITION) not in sys.path:
    sys.path.insert(0, str(ACQUISITION))

from tiktok_ephemeral_browser import (
    MAX_RECORDS_PER_TOPIC,
    EphemeralBrowser,
    OperationLedger,
    observed_at,
    topic_qualified,
    verify_oembed,
)


EXIT_SUCCESS = 0
EXIT_TECHNICAL_FAILURE = 1
EXIT_EVIDENCE_WITHHELD = 2
EVIDENCE_ID = "KU2D-TIKTOK-LIVE-EVIDENCE-000003"
TOPICS = {
    "Diving lesson": "เรียนดำน้ำ scuba course",
    "Diving equipment": "อุปกรณ์ดำน้ำ scuba gear",
}
ALLOWED_OUTPUT_ROOT = (ROOT / "knowledge" / "v1" / "tiktok").resolve()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Bounded P58 TikTok ephemeral-browser discovery")
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--execute-authorized-live", action="store_true")
    value.add_argument("--no-production-store", action="store_true")
    return value


def validate_args(args: argparse.Namespace) -> Path:
    if not args.execute_authorized_live:
        raise ValueError("--execute-authorized-live is required")
    if not args.no_production_store:
        raise ValueError("--no-production-store is required")
    output = args.output.resolve()
    if not output.is_relative_to(ALLOWED_OUTPUT_ROOT):
        raise ValueError("evidence output must remain under knowledge/v1/tiktok")
    if output.exists():
        raise ValueError("live evidence already exists; automatic replay is prohibited")
    return output


def initial_evidence() -> dict[str, Any]:
    now = observed_at()
    return {
        "schema": "ku2d.tiktok-ephemeral-browser-evidence.v1",
        "evidence_id": EVIDENCE_ID,
        "prompt_id": "KU2D-P-000058",
        "human_authority_id": "KU2D-H-000027",
        "started_at": now,
        "updated_at": now,
        "status": "in_progress",
        "technical_completion": False,
        "success": False,
        "selected_technique": "fresh Chrome/Edge CDP context -> public rendered TikTok discovery -> canonical URL extraction -> official TikTok oEmbed/public-page verification -> destroy context -> repeat in a new context",
        "topics": list(TOPICS),
        "target_records_per_topic": MAX_RECORDS_PER_TOPIC,
        "entered_phases": ["P58-01"],
        "operation_ledger": [],
        "operation_accounting": {},
        "network_preflight": None,
        "rounds": [],
        "final_records": {"Diving lesson": [], "Diving equipment": []},
        "context_destruction_proofs": [],
        "stop_condition": None,
        "technical_failure": None,
        "minimum_trusted_connection": None,
        "analysis_handoff": None,
        "boundaries": {
            "official_public_surfaces_only": True,
            "first_party_session_cookies_allowed_only_in_temporary_context": True,
            "third_party_cookie_storage_blocked": True,
            "cookie_values_read": False,
            "cookie_values_persisted": False,
            "storage_state_persisted": False,
            "browser_profile_persisted": False,
            "raw_network_log_persisted": False,
            "login_used": False,
            "credentials_used": False,
            "captcha_or_bypass_attempted": False,
            "provider_quota_delta": 0,
            "production_store": False,
            "production_approved": False,
            "scheduler_action": None,
        },
    }


def write_evidence(path: Path, evidence: dict[str, Any], ledger: OperationLedger) -> None:
    evidence["updated_at"] = observed_at()
    evidence["operation_ledger"] = copy.deepcopy(ledger.rows)
    evidence["operation_accounting"] = ledger.summary()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _teardown(session: EphemeralBrowser | None, evidence: dict[str, Any], *, context_id: str) -> None:
    if session is None:
        proof = {
            "process_stopped": True,
            "profile_existed_before_teardown": False,
            "profile_absent_after_teardown": True,
            "first_party_cookie_count": 0,
            "third_party_requests_blocked": 0,
            "cookie_values_read": False,
            "cookie_values_persisted": False,
            "storage_state_persisted": False,
            "browser_profile_persisted": False,
            "raw_network_log_persisted": False,
        }
    else:
        proof = session.close()
    proof["context_id"] = context_id
    proof["destroyed_at"] = observed_at()
    evidence["context_destruction_proofs"].append(proof)
    if not all((
        proof["process_stopped"], proof["profile_absent_after_teardown"],
        not proof["cookie_values_read"], not proof["cookie_values_persisted"],
        not proof["storage_state_persisted"], not proof["browser_profile_persisted"],
        not proof["raw_network_log_persisted"],
    )):
        raise RuntimeError("ephemeral browser teardown proof failed")


def _navigation_operation(
    *, ledger: OperationLedger, evidence: dict[str, Any], output: Path,
    session: EphemeralBrowser, phase: str, round_id: str, operation: str,
    url: str, topic: str | None = None,
) -> dict[str, Any]:
    row = ledger.begin(phase=phase, round_id=round_id, operation=operation, topic=topic)
    write_evidence(output, evidence, ledger)
    try:
        result = session.navigate(url)
    except Exception as exc:
        ledger.finish(row, provider_reached=False, failure_code=f"preconnect_{type(exc).__name__}")
        write_evidence(output, evidence, ledger)
        raise
    ledger.finish(
        row, provider_reached=bool(result["provider_reached"]),
        response_status=result.get("response_status"),
        candidate_count=len(result.get("candidates") or []),
        failure_code=result.get("failure_code"),
    )
    write_evidence(output, evidence, ledger)
    return result


def _verification_operation(
    *, ledger: OperationLedger, evidence: dict[str, Any], output: Path,
    round_id: str, topic: str, candidate: dict[str, str],
    verifier: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    row = ledger.begin(
        phase="official_verification", round_id=round_id, operation="official_oembed_verify",
        topic=topic, public_identity=candidate["video_id"],
    )
    write_evidence(output, evidence, ledger)
    result = verifier(candidate["canonical_url"])
    ledger.finish(
        row, provider_reached=bool(result.get("provider_reached")),
        response_status=result.get("response_status"),
        retained_count=int(bool(result.get("verified"))),
        failure_code=result.get("failure_code"),
    )
    write_evidence(output, evidence, ledger)
    return result


def _discovery_url(query: str) -> str:
    return f"https://www.tiktok.com/search?q={quote_plus(query)}"


def run_campaign(
    output: Path, *, browser_factory: Callable[[], EphemeralBrowser] = EphemeralBrowser,
    verifier: Callable[[str], dict[str, Any]] = verify_oembed,
) -> tuple[int, dict[str, Any]]:
    ledger = OperationLedger()
    evidence = initial_evidence()
    write_evidence(output, evidence, ledger)
    session: EphemeralBrowser | None = None
    try:
        session = browser_factory()
        preflight_row = ledger.begin(
            phase="P58-01", round_id="preflight", operation="network_preflight",
        )
        write_evidence(output, evidence, ledger)
        try:
            session.start()
            preflight = session.navigate("https://www.tiktok.com/")
            ledger.finish(
                preflight_row, provider_reached=bool(preflight["provider_reached"]),
                response_status=preflight.get("response_status"),
                failure_code=preflight.get("failure_code"),
            )
        except Exception as exc:
            ledger.finish(preflight_row, provider_reached=False, failure_code=f"preconnect_{type(exc).__name__}")
            preflight = {"provider_reached": False, "response_status": None, "failure_code": f"preconnect_{type(exc).__name__}"}
        evidence["network_preflight"] = {
            "provider_reached": bool(preflight["provider_reached"]),
            "response_status": preflight.get("response_status"),
            "failure_code": preflight.get("failure_code"),
        }
        write_evidence(output, evidence, ledger)
        _teardown(session, evidence, context_id="preflight")
        session = None
        write_evidence(output, evidence, ledger)
        if not preflight["provider_reached"] or preflight.get("failure_code"):
            evidence.update({"status": "evidence_withheld", "technical_completion": True,
                             "stop_condition": "network_preflight_failed"})
            write_evidence(output, evidence, ledger)
            return EXIT_EVIDENCE_WITHHELD, evidence

        round_one_records: dict[str, list[dict[str, Any]]] = {topic: [] for topic in TOPICS}
        for round_number in (1, 2):
            round_id = f"round-{round_number}"
            phase = f"P58-0{round_number + 1}"
            evidence["entered_phases"].append(phase)
            session = browser_factory()
            discovered: dict[str, list[dict[str, str]]] = {}
            round_summary: dict[str, Any] = {
                "round_id": round_id,
                "phase": phase,
                "started_at": observed_at(),
                "discovery_counts": {},
                "records": {topic: [] for topic in TOPICS},
                "completed_at": None,
            }
            evidence["rounds"].append(round_summary)
            try:
                for index, (topic, query) in enumerate(TOPICS.items()):
                    if index == 0:
                        row = ledger.begin(
                            phase=phase, round_id=round_id, operation="public_topic_discovery", topic=topic,
                        )
                        write_evidence(output, evidence, ledger)
                        try:
                            session.start()
                            result = session.navigate(_discovery_url(query))
                        except Exception as exc:
                            ledger.finish(row, provider_reached=False, failure_code=f"preconnect_{type(exc).__name__}")
                            write_evidence(output, evidence, ledger)
                            raise
                        ledger.finish(
                            row, provider_reached=bool(result["provider_reached"]),
                            response_status=result.get("response_status"),
                            candidate_count=len(result.get("candidates") or []),
                            failure_code=result.get("failure_code"),
                        )
                        write_evidence(output, evidence, ledger)
                    else:
                        result = _navigation_operation(
                            ledger=ledger, evidence=evidence, output=output, session=session,
                            phase=phase, round_id=round_id, operation="public_topic_discovery",
                            url=_discovery_url(query), topic=topic,
                        )
                    if result.get("failure_code"):
                        evidence["stop_condition"] = result["failure_code"]
                        raise StopIteration
                    discovered[topic] = list(result.get("candidates") or [])
                    round_summary["discovery_counts"][topic] = len(discovered[topic])

                for topic in TOPICS:
                    if round_number == 1:
                        candidates = discovered[topic]
                    else:
                        expected = {row["video_id"]: row for row in round_one_records[topic]}
                        found = {row["video_id"]: row for row in discovered[topic]}
                        if not set(expected).issubset(found):
                            evidence["stop_condition"] = "round_two_identity_reproduction_failed"
                            raise StopIteration
                        candidates = [found[row["video_id"]] for row in round_one_records[topic]]
                    for candidate in candidates:
                        verified = _verification_operation(
                            ledger=ledger, evidence=evidence, output=output, round_id=round_id,
                            topic=topic, candidate=candidate, verifier=verifier,
                        )
                        if not verified.get("provider_reached"):
                            if ledger.preconnect_failures >= ledger.preconnect_limit:
                                evidence["stop_condition"] = "preconnect_failure_limit_reached"
                                raise StopIteration
                            continue
                        if not verified.get("verified"):
                            continue
                        if not topic_qualified(topic, candidate.get("visible_context"), verified.get("title")):
                            continue
                        record = {
                            "topic": topic,
                            "video_id": verified["video_id"],
                            "canonical_url": verified["canonical_url"],
                            "creator_handle": verified["creator_handle"],
                            "author_name": verified["author_name"],
                            "title": verified["title"],
                            "observed_at": observed_at(),
                            "official_verification": "tiktok_oembed",
                        }
                        round_summary["records"][topic].append(record)
                        if len(round_summary["records"][topic]) >= MAX_RECORDS_PER_TOPIC:
                            break
                    if len(round_summary["records"][topic]) != MAX_RECORDS_PER_TOPIC:
                        evidence["stop_condition"] = f"insufficient_topic_records:{topic}"
                        raise StopIteration
                round_summary["completed_at"] = observed_at()
                if round_number == 1:
                    round_one_records = copy.deepcopy(round_summary["records"])
                else:
                    for topic in TOPICS:
                        if [row["video_id"] for row in round_summary["records"][topic]] != [row["video_id"] for row in round_one_records[topic]]:
                            evidence["stop_condition"] = "round_two_identity_reproduction_failed"
                            raise StopIteration
            finally:
                _teardown(session, evidence, context_id=round_id)
                session = None
                write_evidence(output, evidence, ledger)
            if evidence.get("stop_condition"):
                break

        if evidence.get("stop_condition"):
            evidence.update({"status": "evidence_withheld", "technical_completion": True})
            write_evidence(output, evidence, ledger)
            return EXIT_EVIDENCE_WITHHELD, evidence
        evidence["final_records"] = round_one_records
        evidence.update({"status": "live_rounds_complete", "technical_completion": True, "success": True})
        write_evidence(output, evidence, ledger)
        return EXIT_SUCCESS, evidence
    except StopIteration:
        if session is not None:
            _teardown(session, evidence, context_id="interrupted")
        evidence.update({"status": "evidence_withheld", "technical_completion": True,
                         "stop_condition": evidence.get("stop_condition") or "contract_not_met"})
        write_evidence(output, evidence, ledger)
        return EXIT_EVIDENCE_WITHHELD, evidence
    except Exception as exc:
        if session is not None:
            try:
                _teardown(session, evidence, context_id="technical-failure")
            except Exception:
                pass
        evidence.update({
            "status": "technical_failure", "technical_completion": False, "success": False,
            "technical_failure": {"type": type(exc).__name__, "message": str(exc)[:500]},
            "stop_condition": "technical_failure",
        })
        write_evidence(output, evidence, ledger)
        return EXIT_TECHNICAL_FAILURE, evidence


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        output = validate_args(args)
    except Exception as exc:
        print(f"TikTok P58 argument validation failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    try:
        exit_code, evidence = run_campaign(output)
    except Exception as exc:
        print(f"TikTok P58 evidence writing failed: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_FAILURE
    print(json.dumps({
        "evidence_id": evidence["evidence_id"],
        "status": evidence["status"],
        "technical_completion": evidence["technical_completion"],
        "success": evidence["success"],
        "provider_reached": evidence["operation_accounting"]["provider_reached"],
        "preconnect_failures": evidence["operation_accounting"]["preconnect_failures"],
        "output": str(output),
        "exit_classification": exit_code,
    }, ensure_ascii=False, sort_keys=True))
    if exit_code != EXIT_SUCCESS:
        print(f"TikTok P58 evidence withheld: {evidence.get('stop_condition')}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
