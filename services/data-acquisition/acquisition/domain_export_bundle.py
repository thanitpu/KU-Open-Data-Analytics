"""Deterministic, formula-safe P59 domain exports using only the stdlib."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import zipfile
from xml.sax.saxutils import escape


BASE_COLUMNS = [
    "domain", "source_id", "source_name", "stable_record_id", "record_type",
    "observed_at", "canonical_public_source", "technique_id",
    "provenance_reference", "run_id", "normalized_json",
]
NULL_TOKEN = "\\N"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_text(value):
    if value is None:
        return None
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def csv_value(value):
    if value is None:
        return NULL_TOKEN
    text = safe_text(value)
    return "\\\\N" if text == NULL_TOKEN else text


def flat_record(row):
    return {
        **{key: safe_text(row.get(key)) for key in BASE_COLUMNS[:-1]},
        "normalized_json": json.dumps(row.get("normalized"), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    }


def csv_bytes(rows, columns=BASE_COLUMNS):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: csv_value(row.get(key)) for key in columns})
    return stream.getvalue().encode("utf-8")


def jsonl_bytes(rows):
    return ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)).encode("utf-8")


def _cell(ref, value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = escape(safe_text(value) or "")
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _col(index):
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def _sheet(rows, headers):
    xml_rows = []
    for row_index, values in enumerate([headers, *rows], 1):
        cells = "".join(_cell(f"{_col(index)}{row_index}", value) for index, value in enumerate(values, 1))
        xml_rows.append(f'<row r="{row_index}">{cells}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>').encode("utf-8")


def xlsx_bytes(record_rows, source_rows, failure_rows):
    from io import BytesIO
    target = BytesIO()
    sheets = [
        ("Records", BASE_COLUMNS, [[row.get(key) for key in BASE_COLUMNS] for row in record_rows]),
        ("Source Summary", ["source_id", "source_name", "domain", "state", "accepted_unique", "observations", "provider_operations", "quota", "reason"], source_rows),
        ("Failures", ["source_id", "source_name", "domain", "state", "reason", "attempted_techniques", "provider_operations", "quota", "evidence_references"], failure_rows),
    ]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        workbook_sheets = "".join(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>' for index, (name, _, _) in enumerate(sheets, 1))
        archive.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets></workbook>')
        relationships = "".join(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>' for index in range(1, 4))
        archive.writestr("xl/_rels/workbook.xml.rels", f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{relationships}</Relationships>')
        for index, (_, headers, rows) in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet(rows, headers))
    return target.getvalue()


def domain_slug(domain):
    value = re.sub(r"[^a-z0-9]+", "-", str(domain).lower()).strip("-")
    return value or "unknown-domain"


def build_export_bundle(ledger, manifest, fixture_report, output_dir: Path):
    if ledger.get("sealed_live") is not True:
        raise ValueError("live ledger must be sealed before export")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = ledger["run_id"]
    stage = output_dir / f"{run_id}-members"
    stage.mkdir(parents=True, exist_ok=True)
    sources = {row["source_id"]: row for row in manifest["sources"]}
    records = sorted(ledger.get("records") or [], key=lambda row: (row["domain"], row["source_id"], row["stable_record_id"], row["observed_at"]))
    domains = sorted({row["domain"] for row in manifest["sources"]})
    member_meta = []
    failure_rows = []
    summary_by_domain = {domain: [] for domain in domains}
    failures_by_domain = {domain: [] for domain in domains}
    for source_id in manifest["source_order"]:
        source, state = sources[source_id], ledger["source_states"][source_id]
        summary = [source_id, source["source_name"], source["domain"], state["state"], state["accepted_unique"], state["observations"], state["provider_operations"], state["quota"], state["reason"]]
        summary_by_domain[source["domain"]].append(summary)
        if state["state"] != "exhausted":
            failure = [source_id, source["source_name"], source["domain"], state["state"], state["reason"], ",".join(state["attempted_techniques"]), state["provider_operations"], state["quota"], ";".join(state["evidence_references"])]
            failures_by_domain[source["domain"]].append(failure)
            failure_rows.append({
                "source_id": source_id, "source_name": source["source_name"], "domain": source["domain"],
                "state": state["state"], "reason": state["reason"],
                "attempted_techniques": state["attempted_techniques"],
                "provider_operations": state["provider_operations"], "quota": state["quota"],
                "evidence_references": state["evidence_references"],
            })
    for domain in domains:
        slug = domain_slug(domain)
        domain_dir = stage / slug
        domain_dir.mkdir(parents=True, exist_ok=True)
        domain_records = [flat_record(row) for row in records if row["domain"] == domain]
        payloads = {
            f"{slug}/records.csv": csv_bytes(domain_records),
            f"{slug}/records.jsonl": jsonl_bytes([row for row in records if row["domain"] == domain]),
            f"{slug}/records.xlsx": xlsx_bytes(domain_records, summary_by_domain[domain], failures_by_domain[domain]),
        }
        for name, payload in payloads.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            member_meta.append({"name": name, "rows": len(domain_records), "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    root_payloads = {
        "failure_report.csv": csv_bytes(failure_rows, ["source_id", "source_name", "domain", "state", "reason", "attempted_techniques", "provider_operations", "quota", "evidence_references"]),
        "failure_report.json": (json.dumps(failure_rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "fixture_report.json": (json.dumps(fixture_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    for name, payload in root_payloads.items():
        (stage / name).write_bytes(payload)
        member_meta.append({"name": name, "rows": len(failure_rows) if name.startswith("failure") else len(fixture_report.get("sources") or []), "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    campaign_manifest = {
        "schema": "ku2d.multi-source-domain-export-manifest.v1", "run_id": run_id,
        "code_sha": ledger.get("code_sha"), "code_tree": ledger.get("code_tree"),
        "source_order": manifest["source_order"], "record_slice_per_visit": 100,
        "started_at": ledger["started_at"], "ended_at": ledger["ended_at"],
        "stop_reason": ledger["stop_reason"], "accepted_unique": ledger["accepted_unique"],
        "observations": ledger["observations"], "provider_operations": ledger["provider_operations"],
        "quota": ledger["quota"], "source_states": ledger["source_states"],
        "schemas": {"csv_null_token": NULL_TOKEN, "jsonl": "one-object-per-line", "xlsx_sheets": ["Records", "Source Summary", "Failures"]},
        "members": sorted(member_meta, key=lambda row: row["name"]),
        "zip_sha256": None,
        "zip_hash_note": "The exact archive hash is recorded in the detached delivery manifest because an archive cannot contain its own cryptographic hash without changing that hash.",
    }
    manifest_payload = (json.dumps(campaign_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (stage / "campaign_manifest.json").write_bytes(manifest_payload)
    member_meta.append({"name": "campaign_manifest.json", "rows": 1, "size": len(manifest_payload), "sha256": hashlib.sha256(manifest_payload).hexdigest()})
    zip_path = output_dir / f"KU2D_P59_MultiSource_RoundRobin_{run_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(stage).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, path.read_bytes())
    zip_hash = sha256_file(zip_path)
    delivery = {
        "schema": "ku2d.multi-source-domain-export-delivery.v1", "run_id": run_id,
        "zip_name": zip_path.name, "zip_size": zip_path.stat().st_size, "zip_sha256": zip_hash,
        "member_manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "member_count": len(member_meta),
        "members": sorted(member_meta, key=lambda row: row["name"]),
        "delivered_outside_git": True,
    }
    delivery_path = output_dir / f"{zip_path.stem}.delivery.json"
    delivery_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"zip_path": str(zip_path), "delivery_manifest_path": str(delivery_path), "zip_sha256": zip_hash, "members": sorted(member_meta, key=lambda row: row["name"])}


def verify_export_bundle(zip_path: Path, delivery_path: Path):
    zip_path, delivery_path = Path(zip_path), Path(delivery_path)
    delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
    if delivery.get("zip_sha256") != sha256_file(zip_path):
        raise ValueError("ZIP hash mismatch")
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or "campaign_manifest.json" not in names:
            raise ValueError("ZIP membership is incomplete or duplicated")
        manifest_bytes = archive.read("campaign_manifest.json")
        if hashlib.sha256(manifest_bytes).hexdigest() != delivery.get("member_manifest_sha256"):
            raise ValueError("manifest hash mismatch")
        manifest = json.loads(manifest_bytes)
        for member in manifest["members"]:
            payload = archive.read(member["name"])
            if len(payload) != member["size"] or hashlib.sha256(payload).hexdigest() != member["sha256"]:
                raise ValueError(f"member mismatch: {member['name']}")
        if {row["name"] for row in delivery.get("members") or []} != set(names):
            raise ValueError("detached delivery membership mismatch")
        for member in delivery["members"]:
            payload = archive.read(member["name"])
            if len(payload) != member["size"] or hashlib.sha256(payload).hexdigest() != member["sha256"]:
                raise ValueError(f"detached member mismatch: {member['name']}")
        for name in names:
            if name.endswith(".xlsx"):
                with zipfile.ZipFile(BytesIO(archive.read(name))) as workbook:
                    required = {"xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"}
                    if not required <= set(workbook.namelist()):
                        raise ValueError(f"XLSX worksheets missing: {name}")
    return delivery
