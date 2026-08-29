import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from control_plane.scheduler import run_scheduler_cycle
p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--source-id',action='append');p.add_argument('--max-pages',type=int,default=None)
a=p.parse_args();print(json.dumps(run_scheduler_cycle(a.source_id,a.max_pages,a.dry_run),ensure_ascii=False,indent=2))
