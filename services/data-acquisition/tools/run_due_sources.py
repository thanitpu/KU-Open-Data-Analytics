from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"acquisition"));sys.path.insert(0,str(ROOT/"repository"))
from scheduler_worker import run_due
if __name__=="__main__":
    import json
    print(json.dumps(run_due(),ensure_ascii=False,indent=2))
