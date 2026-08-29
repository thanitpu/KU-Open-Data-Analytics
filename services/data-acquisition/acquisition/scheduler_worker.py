from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/"acquisition",ROOT/"repository"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from acquisition_orchestrator import run_many,select_sources
from operations_store import recent_runs

def run_due():
    return run_many(due_only=True,force_store=False)

if __name__=="__main__":
    result=run_due()
    print(json.dumps(result,ensure_ascii=False,indent=2))
