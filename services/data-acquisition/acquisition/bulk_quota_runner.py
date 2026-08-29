from __future__ import annotations
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"repository") not in sys.path:sys.path.insert(0,str(ROOT/"repository"))
from acquisition_health import bulk_fill_plan

def build_run_manifest(connections):
    plan=bulk_fill_plan(connections)
    manifest=[]
    for t in plan["tasks"]:
        manifest.append({
          **t,
          "run_mode":"real-source-only",
          "stop_condition":f"stop when usable records reach {t['maximum']} or source exhaustion/constraint is documented",
          "quality_rules":["must retain source URL/provenance","must be parseable into a purpose-appropriate usable record",
                           "do not count duplicate/copy records toward quota","do not fabricate or synthesize quota records"],
          "status":"planned"
        })
    return {"policy":plan["target_policy"],"estimated_records_needed":plan["estimated_records_needed"],
            "task_count":len(manifest),"tasks":manifest,
            "note":"This manifest is intentionally separated from execution so the user can inspect source quotas and constraints before a long acquisition run."}

def write_manifest(path,connections):
    data=build_run_manifest(connections);Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return data
