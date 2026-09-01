"""Deterministic P59 CSV/JSONL/XLSX/ZIP integrity tests."""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "acquisition"))

from domain_export_bundle import (  # noqa: E402
    BASE_COLUMNS, NULL_TOKEN, build_export_bundle, csv_bytes, safe_text,
    verify_export_bundle, xlsx_bytes,
)
from round_robin_campaign import load_campaign_manifest  # noqa: E402


manifest = load_campaign_manifest(ROOT / "config" / "multi_source_round_robin_manifest_v1.json")
states = {}
for source in manifest["sources"]:
    states[source["source_id"]] = {
        "state": "exhausted" if source["source_id"] == "SRC-001" else "to_be_skipped",
        "reason": "fixture_complete" if source["source_id"] == "SRC-001" else source["skip_reason"] or "deterministic_skip",
        "visits": 1 if source["source_id"] == "SRC-001" else 0,
        "provider_operations": 0, "quota": 0,
        "accepted_unique": 2 if source["source_id"] == "SRC-001" else 0,
        "observations": 2 if source["source_id"] == "SRC-001" else 0,
        "no_new_visits": 0, "transient_failure_rounds": 0,
        "attempted_techniques": source["technique_ids"] if source["source_id"] == "SRC-001" else [],
        "evidence_references": source["evidence_references"],
    }
records = []
for index, name in enumerate(("กาแฟ", "=HYPERLINK(\"bad\")"), 1):
    records.append({
        "domain": "Supermarket", "source_id": "SRC-001", "source_name": "Tops",
        "stable_record_id": f"SRC-001:{index:024d}", "record_type": "ProductCandidate",
        "observed_at": "2026-09-02T00:00:00+00:00",
        "canonical_public_source": f"https://www.tops.co.th/th/product/{index}",
        "technique_id": "tops_product_catalog", "provenance_reference": None if index == 1 else "fixture",
        "run_id": "P59-TEST", "normalized": {"product_name": name, "empty": "", "missing": None},
    })
ledger = {
    "sealed_live": True, "run_id": "P59-TEST", "code_sha": "1" * 40, "code_tree": "2" * 40,
    "started_at": "2026-09-02T00:00:00+00:00", "ended_at": "2026-09-02T00:01:00+00:00",
    "stop_reason": "empty_active_source_set", "accepted_unique": 2, "observations": 2,
    "provider_operations": 0, "quota": 0, "source_states": states, "records": records,
}
fixture_report = {"schema": "ku2d.multi-source-fixture-report.v1", "provider_operations": 0, "sources": [{"source_id": row["source_id"], "status": "passed" if row["fixture_paths"] else "not_available", "fixtures": row["fixture_paths"]} for row in manifest["sources"]]}


# EX1-EX5: formula strings are neutralized and null remains distinct from empty text.
assert safe_text("=1+1") == "'=1+1"
payload = csv_bytes([{"domain": "=1+1", "source_id": None, "source_name": ""}])
text = payload.decode("utf-8")
assert "'=1+1" in text and NULL_TOKEN in text
parsed = next(csv.DictReader(StringIO(text)))
assert parsed["source_id"] == NULL_TOKEN and parsed["source_name"] == ""
escaped = next(csv.DictReader(StringIO(csv_bytes([{"domain": NULL_TOKEN}]).decode("utf-8"))))
assert escaped["domain"] == "\\\\N" and escaped["domain"] != NULL_TOKEN


# EX6-EX10: the stdlib workbook is valid ZIP/XML and has exactly three named sheets.
book = xlsx_bytes([], [], [])
with zipfile.ZipFile(BytesIO(book)) as archive:
    workbook = archive.read("xl/workbook.xml").decode("utf-8")
    assert all(name in workbook for name in ("Records", "Source Summary", "Failures"))
    assert all(f"xl/worksheets/sheet{index}.xml" in archive.namelist() for index in range(1, 4))


# EX11-EX20: complete bundle membership, Unicode, row counts, member and archive hashes reconcile.
with TemporaryDirectory() as tmp:
    result = build_export_bundle(ledger, manifest, fixture_report, Path(tmp))
    delivery = verify_export_bundle(Path(result["zip_path"]), Path(result["delivery_manifest_path"]))
    assert delivery["zip_sha256"] == result["zip_sha256"]
    with zipfile.ZipFile(result["zip_path"]) as archive:
        names = set(archive.namelist())
        assert {"campaign_manifest.json", "failure_report.csv", "failure_report.json", "fixture_report.json"} <= names
        domains = {row["domain"] for row in manifest["sources"]}
        assert len([name for name in names if name.endswith("/records.csv")]) == len(domains)
        assert len([name for name in names if name.endswith("/records.jsonl")]) == len(domains)
        assert len([name for name in names if name.endswith("/records.xlsx")]) == len(domains)
        lines = archive.read("supermarket/records.jsonl").decode("utf-8").splitlines()
        assert len(lines) == 2 and json.loads(lines[0])["normalized"]["product_name"] == "กาแฟ"
        export_manifest = json.loads(archive.read("campaign_manifest.json"))
        assert export_manifest["zip_sha256"] is None
        assert "detached delivery manifest" in export_manifest["zip_hash_note"]
        assert {row["name"] for row in delivery["members"]} == names
    assert Path(result["zip_path"]).parent == Path(tmp).resolve()


print("P59 domain export deterministic tests passed (EX1-EX20).")
