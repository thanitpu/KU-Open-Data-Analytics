from __future__ import annotations
import argparse,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/'acquisition',ROOT):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from coffee_techniques import punthai_menu_catalog,audit_punthai_runs

def compact(run):
    return {'ok':run.get('ok'),'metrics':run.get('metrics'),'diagnostics':(run.get('diagnostics') or [])[:20],
            'sample_records':(run.get('records') or [])[:12],'operational_config':run.get('operational_config'),'guardrail':run.get('guardrail')}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repeat-delay',type=float,default=10);ap.add_argument('--max-items',type=int,default=10);ap.add_argument('--output',default='validation/coffee-punthai-live.json');args=ap.parse_args()
    first=punthai_menu_catalog(max_items=max(5,args.max_items));delay=max(8,min(30,args.repeat_delay));time.sleep(delay);second=punthai_menu_catalog(max_items=max(5,args.max_items));audit=audit_punthai_runs(first,second)
    payload={'schema':'ku2d.coffee-punthai-live-evidence.v1','generated_at':datetime.now(timezone.utc).isoformat(),'execution_environment':'cloud-hosted-public-read-only','source':'PunThai Coffee','technique':'punthai_official_menu_detail','repeat_delay_seconds':delay,'first_run':compact(first),'second_run':compact(second),'audit':audit,'approval_status':'eligible-for-human-review' if audit.get('audit_passed') else 'not-approved','guardrail':'Public official menu detail pages only; workflow never production-approves or stores data.'}
    out=ROOT/args.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'first':first.get('metrics'),'second':second.get('metrics'),'audit':audit},ensure_ascii=False,indent=2));print(f'Wrote {out}')
if __name__=='__main__':main()
