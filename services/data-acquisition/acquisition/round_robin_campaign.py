"""Bounded, checkpoint-first execution for KU2D's one-time P59 campaign.

The module is deliberately provider-agnostic.  A source adapter receives a
``VisitContext`` and must route every network operation through
``provider_call``.  The context checkpoints intent before the call and a
sanitized outcome afterwards, so a crash never makes the request ledger look
smaller than the work that may have reached a provider.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable
from urllib.parse import urlsplit


SCHEMA = "ku2d.multi-source-round-robin-manifest.v1"
LEDGER_SCHEMA = "ku2d.multi-source-round-robin-ledger.v1"
ALLOWED_STATES = {
    "preflight_pending", "active", "retry_next_round", "completed_slice",
    "exhausted", "to_be_skipped",
}
TERMINAL_STATES = {"exhausted", "to_be_skipped"}
GLOBAL_MAX_UNIQUE = 50_000
GLOBAL_MAX_PROVIDER_OPERATIONS = 5_000
GLOBAL_MAX_SECONDS = 12 * 60 * 60
VISIT_MAX_PROVIDER_OPERATIONS = 25
VISIT_MAX_SECONDS = 10 * 60
VISIT_RECORD_SLICE = 100
MIN_HOST_INTERVAL_SECONDS = 2.0


class CampaignValidationError(ValueError):
    """Raised before provider access when a campaign contract is invalid."""


class ProviderBoundary(RuntimeError):
    """Raised without provider access after a hard budget or access boundary."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic_write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _positive_int(value: Any, field: str, *, ceiling: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CampaignValidationError(f"{field} must be a positive integer")
    if ceiling is not None and value > ceiling:
        raise CampaignValidationError(f"{field} exceeds {ceiling}")
    return value


def validate_campaign_manifest(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise CampaignValidationError(f"schema must be {SCHEMA}")
    required = {
        "schema", "campaign_id", "prompt_id", "scope_declaration_id", "created_at",
        "source_order", "sources", "limits", "phase_declarations", "boundaries",
    }
    if set(document) != required:
        raise CampaignValidationError(f"manifest fields must be exactly {sorted(required)}")
    if document.get("prompt_id") != "KU2D-P-000059" or document.get("scope_declaration_id") != "KU2D-SCOPE-000006":
        raise CampaignValidationError("P59 scope linkage drifted")
    try:
        stamp = datetime.fromisoformat(str(document.get("created_at") or ""))
    except ValueError as exc:
        raise CampaignValidationError("created_at must be ISO date-time") from exc
    if stamp.tzinfo is None:
        raise CampaignValidationError("created_at must include timezone")
    limits = document.get("limits")
    if not isinstance(limits, dict) or set(limits) != {
        "record_slice_per_visit", "per_visit_provider_operations", "per_visit_seconds",
        "global_unique_records", "global_provider_operations", "global_seconds",
        "same_host_minimum_interval_seconds", "concurrency",
    }:
        raise CampaignValidationError("limits are incomplete or contain unknown fields")
    expected = {
        "record_slice_per_visit": VISIT_RECORD_SLICE,
        "per_visit_provider_operations": VISIT_MAX_PROVIDER_OPERATIONS,
        "per_visit_seconds": VISIT_MAX_SECONDS,
        "global_unique_records": GLOBAL_MAX_UNIQUE,
        "global_provider_operations": GLOBAL_MAX_PROVIDER_OPERATIONS,
        "global_seconds": GLOBAL_MAX_SECONDS,
        "same_host_minimum_interval_seconds": MIN_HOST_INTERVAL_SECONDS,
        "concurrency": 1,
    }
    if limits != expected:
        raise CampaignValidationError("P59 global or visit limits drifted")
    sources = document.get("sources")
    order = document.get("source_order")
    if not isinstance(sources, list) or not sources or not isinstance(order, list):
        raise CampaignValidationError("sources and source_order must be non-empty arrays")
    by_id: dict[str, dict[str, Any]] = {}
    source_fields = {
        "source_id", "source_name", "domain", "readiness_tier", "preflight_status",
        "skip_reason", "technique_ids", "method_lock_fingerprint", "environment",
        "budgets", "evidence_references", "fixture_paths",
    }
    for source in sources:
        if not isinstance(source, dict) or set(source) != source_fields:
            raise CampaignValidationError("source fields are incomplete or contain unknown fields")
        source_id = str(source.get("source_id") or "")
        if not source_id or source_id in by_id:
            raise CampaignValidationError("source IDs must be non-empty and unique")
        text = canonical_json(source).lower()
        if "tiktok" in text:
            raise CampaignValidationError("TikTok is excluded from P59")
        status = source.get("preflight_status")
        if status not in {"live_eligible", "preflight_skipped"}:
            raise CampaignValidationError(f"{source_id} has invalid preflight_status")
        budgets = source.get("budgets")
        if not isinstance(budgets, dict) or set(budgets) != {
            "max_provider_operations", "max_records", "max_visits", "timeout_seconds", "quota_ceiling",
        }:
            raise CampaignValidationError(f"{source_id} budgets are incomplete")
        if status == "live_eligible":
            if source.get("readiness_tier") not in {"A", "B"}:
                raise CampaignValidationError(f"{source_id} is not live-eligible by tier")
            if source.get("skip_reason") is not None:
                raise CampaignValidationError(f"{source_id} live source has skip_reason")
            if not source.get("technique_ids") or not source.get("method_lock_fingerprint"):
                raise CampaignValidationError(f"{source_id} lacks reviewed method lock")
            _positive_int(budgets.get("max_provider_operations"), f"{source_id}.max_provider_operations")
            _positive_int(budgets.get("max_records"), f"{source_id}.max_records")
            _positive_int(budgets.get("max_visits"), f"{source_id}.max_visits")
            _positive_int(budgets.get("timeout_seconds"), f"{source_id}.timeout_seconds")
            if not isinstance(budgets.get("quota_ceiling"), int) or budgets["quota_ceiling"] < 0:
                raise CampaignValidationError(f"{source_id}.quota_ceiling must be non-negative")
        else:
            if not str(source.get("skip_reason") or "").strip():
                raise CampaignValidationError(f"{source_id} skipped source lacks exact reason")
            if any(budgets.get(key) is not None for key in budgets):
                raise CampaignValidationError(f"{source_id} skipped source cannot receive live budgets")
        refs = source.get("evidence_references")
        fixtures = source.get("fixture_paths")
        if not isinstance(refs, list) or not refs or not isinstance(fixtures, list):
            raise CampaignValidationError(f"{source_id} evidence/fixture lists are invalid")
        by_id[source_id] = source
    expected_order = [row["source_id"] for row in sorted(sources, key=lambda row: (row["domain"], row["source_id"]))]
    if order != expected_order or set(order) != set(by_id):
        raise CampaignValidationError("source_order must be exact domain/source_id order")
    phases = document.get("phase_declarations")
    expected_phases = [f"P59-0{index}" for index in range(1, 8)]
    if not isinstance(phases, list) or [row.get("phase_id") for row in phases if isinstance(row, dict)] != expected_phases:
        raise CampaignValidationError("all seven P59 phase declarations are required in order")
    seven = {
        "domain", "source", "capability", "acquisition_technique",
        "authorized_files_or_modules", "explicit_out_of_scope", "validation_profile",
    }
    for phase in phases:
        if set(phase) != {"phase_id", "entered", *seven} or not all(phase.get(field) for field in seven):
            raise CampaignValidationError(f"{phase.get('phase_id')} lacks the seven-field declaration")
        if not isinstance(phase.get("entered"), bool):
            raise CampaignValidationError("phase entered must be boolean")
    boundaries = document.get("boundaries")
    if boundaries != {
        "production_approved": False, "production_store": False,
        "recurring_schedule": False, "scheduler_action": None,
        "live_exports_committed_to_git": False,
    }:
        raise CampaignValidationError("campaign safety boundaries drifted")
    return deepcopy(document)


def load_campaign_manifest(path: Path) -> dict[str, Any]:
    return validate_campaign_manifest(json.loads(Path(path).read_text(encoding="utf-8")))


def sanitized_url(url: str) -> str:
    split = urlsplit(str(url or ""))
    return f"{split.scheme}://{split.netloc}{split.path}" if split.scheme and split.netloc else "invalid-url"


def stable_record_identity(source: dict[str, Any], row: dict[str, Any]) -> tuple[str, str]:
    canonical = str(row.get("source_url") or row.get("canonical_public_source") or "").strip()
    local = str(row.get("sku") or row.get("product_id") or row.get("video_id") or row.get("id") or canonical).strip()
    if not canonical or not local:
        raise CampaignValidationError("accepted record lacks canonical public source or stable local identity")
    raw = canonical_json({"domain": source["domain"], "source_id": source["source_id"], "local": local, "canonical": canonical})
    return f"{source['source_id']}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}", canonical


def normalized_record(source: dict[str, Any], row: dict[str, Any], *, run_id: str, observed_at: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise CampaignValidationError("provider record must be a JSON object")
    stable_id, canonical = stable_record_identity(source, row)
    payload = deepcopy(row)
    payload.pop("raw", None)
    payload.pop("headers", None)
    return {
        "domain": source["domain"],
        "source_id": source["source_id"],
        "source_name": source["source_name"],
        "stable_record_id": stable_id,
        "record_type": str(row.get("record_type") or "PublicDomainRecord"),
        "observed_at": observed_at,
        "canonical_public_source": canonical,
        "technique_id": source["technique_ids"][0],
        "provenance_reference": str(row.get("provenance") or canonical),
        "run_id": run_id,
        "normalized": payload,
    }


@dataclass
class VisitResult:
    outcome: str
    records: list[dict[str, Any]]
    quota_delta: int = 0
    frontier_exhausted: bool = False
    warning: str | None = None


class VisitContext:
    def __init__(self, runner: "RoundRobinCampaign", source: dict[str, Any], source_state: dict[str, Any]):
        self.runner = runner
        self.source = source
        self.source_state = source_state
        self.started_monotonic = runner.monotonic()
        self.visit_provider_operations = 0
        self.access_boundary: str | None = None

    def _assert_budget(self) -> None:
        now = self.runner.monotonic()
        if now - self.started_monotonic >= VISIT_MAX_SECONDS:
            raise ProviderBoundary("per_visit_wall_clock_ceiling")
        if now - self.runner.started_monotonic >= GLOBAL_MAX_SECONDS:
            raise ProviderBoundary("global_wall_clock_ceiling")
        if self.visit_provider_operations >= VISIT_MAX_PROVIDER_OPERATIONS:
            raise ProviderBoundary("per_visit_provider_operation_ceiling")
        if self.runner.ledger["provider_operations"] >= GLOBAL_MAX_PROVIDER_OPERATIONS:
            raise ProviderBoundary("global_provider_operation_ceiling")
        if self.source_state["provider_operations"] >= self.source["budgets"]["max_provider_operations"]:
            raise ProviderBoundary("source_provider_operation_ceiling")
        if self.access_boundary:
            raise ProviderBoundary(self.access_boundary)

    def provider_call(self, url: str, operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        self._assert_budget()
        host = urlsplit(url).netloc.lower()
        previous = self.runner.last_host_operation.get(host)
        if previous is not None:
            remaining = MIN_HOST_INTERVAL_SECONDS - (self.runner.monotonic() - previous)
            if remaining > 0:
                self.runner.sleeper(remaining)
        operation_id = f"OP-{self.runner.ledger['provider_operations'] + 1:06d}"
        pending = {
            "operation_id": operation_id, "source_id": self.source["source_id"],
            "sanitized_url": sanitized_url(url), "checkpointed_at": self.runner.now(),
            "state": "intent_checkpointed",
        }
        self.runner.ledger["pending_operation"] = pending
        self.runner._checkpoint()
        reached = False
        try:
            reached = True
            response = operation()
            if not isinstance(response, dict):
                raise RuntimeError("provider operation returned a non-object")
        except Exception as exc:
            response = {"ok": False, "status": 0, "error": f"{type(exc).__name__}: {exc}"}
        self.visit_provider_operations += 1
        self.runner.ledger["provider_operations"] += 1
        self.source_state["provider_operations"] += 1
        self.runner.last_host_operation[host] = self.runner.monotonic()
        status = int(response.get("status") or 0)
        if status in {401, 403, 429}:
            self.access_boundary = f"http_{status}_access_boundary"
        outcome = {
            **pending, "state": "finalized", "finalized_at": self.runner.now(),
            "provider_reached": reached, "http_status": status,
            "ok": bool(response.get("ok")), "bytes": int(response.get("bytes") or 0),
            "error_type": str(response.get("error") or "").split(":", 1)[0] or None,
        }
        self.runner.ledger["operation_log"].append(outcome)
        self.runner.ledger["pending_operation"] = None
        self.runner._checkpoint()
        return response


class RoundRobinCampaign:
    def __init__(
        self, manifest: dict[str, Any], checkpoint_path: Path,
        adapters: dict[str, Callable[[dict[str, Any], VisitContext], VisitResult]],
        *, run_id: str, now: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.manifest = validate_campaign_manifest(manifest)
        self.checkpoint_path = Path(checkpoint_path)
        self.adapters = adapters
        self.run_id = run_id
        self.now, self.monotonic, self.sleeper = now, monotonic, sleeper
        self.started_monotonic = monotonic()
        self.last_host_operation: dict[str, float] = {}
        self.sources = {source["source_id"]: source for source in self.manifest["sources"]}
        self.ledger = self._new_ledger()

    def _new_ledger(self) -> dict[str, Any]:
        states = {}
        for source in self.manifest["sources"]:
            skipped = source["preflight_status"] == "preflight_skipped"
            states[source["source_id"]] = {
                "state": "to_be_skipped" if skipped else "active",
                "reason": source["skip_reason"] if skipped else None,
                "visits": 0, "provider_operations": 0, "quota": 0,
                "accepted_unique": 0, "observations": 0, "no_new_visits": 0,
                "transient_failure_rounds": 0, "attempted_techniques": [],
                "evidence_references": list(source["evidence_references"]),
            }
        return {
            "schema": LEDGER_SCHEMA, "run_id": self.run_id,
            "code_sha": None, "code_tree": None, "started_at": self.now(), "ended_at": None,
            "sealed_live": False, "stop_reason": None, "rounds_completed": 0,
            "provider_operations": 0, "quota": 0, "accepted_unique": 0,
            "observations": 0, "elapsed_seconds": 0.0,
            "pending_operation": None, "operation_log": [],
            "source_states": states, "records": [],
        }

    def _checkpoint(self) -> None:
        self.ledger["elapsed_seconds"] = round(
            max(float(self.ledger.get("elapsed_seconds") or 0), self.monotonic() - self.started_monotonic), 3,
        )
        atomic_write_json(self.checkpoint_path, self.ledger)

    @classmethod
    def resume(
        cls, manifest: dict[str, Any], checkpoint_path: Path,
        adapters: dict[str, Callable[[dict[str, Any], VisitContext], VisitResult]],
        *, run_id: str, now: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> "RoundRobinCampaign":
        checkpoint = json.loads(Path(checkpoint_path).read_text(encoding="utf-8"))
        if checkpoint.get("schema") != LEDGER_SCHEMA or checkpoint.get("run_id") != run_id:
            raise CampaignValidationError("resume checkpoint identity mismatch")
        if checkpoint.get("sealed_live") is True:
            raise CampaignValidationError("sealed live ledger cannot resume provider access")
        runner = cls(
            manifest, checkpoint_path, adapters, run_id=run_id,
            now=now, monotonic=monotonic, sleeper=sleeper,
        )
        runner.ledger = checkpoint
        elapsed = max(0.0, float(checkpoint.get("elapsed_seconds") or 0))
        runner.started_monotonic = monotonic() - elapsed
        pending = checkpoint.get("pending_operation")
        if pending:
            source_id = pending.get("source_id")
            if source_id not in runner.ledger["source_states"]:
                raise CampaignValidationError("pending operation references unknown source")
            outcome = {
                **pending, "state": "finalized_after_crash", "finalized_at": now(),
                "provider_reached": True, "http_status": 0, "ok": False,
                "bytes": 0, "error_type": "outcome_unknown_after_crash",
            }
            runner.ledger["operation_log"].append(outcome)
            runner.ledger["provider_operations"] += 1
            runner.ledger["source_states"][source_id]["provider_operations"] += 1
            runner.ledger["pending_operation"] = None
            runner._checkpoint()
        return runner

    def set_code_identity(self, sha: str, tree: str) -> None:
        if len(sha) != 40 or len(tree) != 40:
            raise CampaignValidationError("code SHA/tree must be exact 40-character Git identities")
        self.ledger["code_sha"], self.ledger["code_tree"] = sha, tree
        self._checkpoint()

    def run(self) -> dict[str, Any]:
        self._checkpoint()
        round_number = 0
        while self.ledger["accepted_unique"] < GLOBAL_MAX_UNIQUE:
            active = [
                source_id for source_id in self.manifest["source_order"]
                if self.ledger["source_states"][source_id]["state"] not in TERMINAL_STATES
            ]
            if not active:
                self.ledger["stop_reason"] = "empty_active_source_set"
                break
            if self.ledger["provider_operations"] >= GLOBAL_MAX_PROVIDER_OPERATIONS:
                self.ledger["stop_reason"] = "global_provider_operation_ceiling"
                break
            if self.monotonic() - self.started_monotonic >= GLOBAL_MAX_SECONDS:
                self.ledger["stop_reason"] = "global_wall_clock_ceiling"
                break
            round_number += 1
            for source_id in active:
                if self.ledger["accepted_unique"] >= GLOBAL_MAX_UNIQUE:
                    self.ledger["stop_reason"] = "global_unique_record_ceiling"
                    break
                source, state = self.sources[source_id], self.ledger["source_states"][source_id]
                if state["provider_operations"] >= source["budgets"]["max_provider_operations"]:
                    state.update(state="to_be_skipped", reason="source_provider_operation_ceiling")
                    self._checkpoint()
                    continue
                if state["visits"] >= source["budgets"]["max_visits"]:
                    state.update(state="exhausted", reason="immutable_source_visit_frontier_exhausted")
                    self._checkpoint()
                    continue
                adapter = self.adapters.get(source_id)
                if adapter is None:
                    state.update(state="to_be_skipped", reason="reviewed_executable_adapter_unavailable")
                    self._checkpoint()
                    continue
                state["state"] = "active"
                state["visits"] += 1
                state["attempted_techniques"] = list(source["technique_ids"])
                self._checkpoint()
                context = VisitContext(self, source, state)
                try:
                    result = adapter(source, context)
                    if not isinstance(result, VisitResult):
                        raise RuntimeError("source adapter returned an invalid visit result")
                except ProviderBoundary as exc:
                    result = VisitResult("boundary", [], warning=str(exc))
                except Exception as exc:
                    result = VisitResult("transient_failure", [], warning=f"{type(exc).__name__}: {exc}")
                observed_at = self.now()
                accepted_this_visit = 0
                seen = {row["stable_record_id"] for row in self.ledger["records"]}
                source_remaining = max(0, source["budgets"]["max_records"] - state["accepted_unique"])
                global_remaining = max(0, GLOBAL_MAX_UNIQUE - self.ledger["accepted_unique"])
                visit_limit = min(VISIT_RECORD_SLICE, source_remaining, global_remaining)
                for row in result.records[:visit_limit]:
                    try:
                        normalized = normalized_record(source, row, run_id=self.run_id, observed_at=observed_at)
                    except CampaignValidationError:
                        continue
                    state["observations"] += 1
                    self.ledger["observations"] += 1
                    if normalized["stable_record_id"] in seen:
                        continue
                    seen.add(normalized["stable_record_id"])
                    self.ledger["records"].append(normalized)
                    state["accepted_unique"] += 1
                    self.ledger["accepted_unique"] += 1
                    accepted_this_visit += 1
                    if accepted_this_visit >= VISIT_RECORD_SLICE or self.ledger["accepted_unique"] >= GLOBAL_MAX_UNIQUE:
                        break
                quota = max(0, int(result.quota_delta or 0))
                state["quota"] += quota
                self.ledger["quota"] += quota
                if state["quota"] > source["budgets"]["quota_ceiling"]:
                    state.update(state="to_be_skipped", reason="source_quota_ceiling_exceeded")
                elif context.access_boundary or result.outcome in {"boundary", "permanent_failure"}:
                    state.update(state="to_be_skipped", reason=context.access_boundary or result.warning or result.outcome)
                elif result.outcome == "transient_failure":
                    state["transient_failure_rounds"] += 1
                    if state["transient_failure_rounds"] >= 2:
                        state.update(state="to_be_skipped", reason="two_rounds_transient_technical_failure")
                    else:
                        state["state"] = "retry_next_round"
                        state["reason"] = result.warning
                elif result.frontier_exhausted or state["accepted_unique"] >= source["budgets"]["max_records"]:
                    state.update(state="exhausted", reason="reviewed_source_frontier_exhausted")
                elif accepted_this_visit == 0:
                    state["no_new_visits"] += 1
                    if state["no_new_visits"] >= 2:
                        state.update(state="to_be_skipped", reason="two_visits_without_new_stable_identity")
                    else:
                        state["state"] = "completed_slice"
                        state["reason"] = "one_visit_without_new_stable_identity"
                else:
                    state["no_new_visits"] = 0
                    state["state"] = "completed_slice"
                    state["reason"] = result.warning
                self._checkpoint()
            self.ledger["rounds_completed"] = round_number
            self._checkpoint()
            if self.ledger.get("stop_reason"):
                break
        if self.ledger["accepted_unique"] >= GLOBAL_MAX_UNIQUE and not self.ledger.get("stop_reason"):
            self.ledger["stop_reason"] = "global_unique_record_ceiling"
        self.ledger["ended_at"] = self.now()
        self.ledger["sealed_live"] = True
        self.ledger["pending_operation"] = None
        self._checkpoint()
        return deepcopy(self.ledger)


def verify_sealed_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ledger, dict) or ledger.get("schema") != LEDGER_SCHEMA:
        raise CampaignValidationError("invalid live ledger schema")
    if ledger.get("sealed_live") is not True or ledger.get("pending_operation") is not None:
        raise CampaignValidationError("live ledger is not safely sealed")
    if ledger.get("provider_operations") != len(ledger.get("operation_log") or []):
        raise CampaignValidationError("provider-operation totals do not reconcile")
    unique = {row.get("stable_record_id") for row in ledger.get("records") or []}
    if len(unique) != ledger.get("accepted_unique"):
        raise CampaignValidationError("accepted unique count does not reconcile")
    return deepcopy(ledger)
