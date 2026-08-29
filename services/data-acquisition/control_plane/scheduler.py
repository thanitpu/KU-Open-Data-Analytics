from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/'acquisition',ROOT/'repository'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from monitoring_registry import normalized_sources,cadence_due
from operations_store import states,quality_profile,technique_assignments,start_run,finish_run
from technique_strategy import technique_profile_fingerprint
from deep_collection import acquire_and_store
from .lifecycle_policy import evaluate_source
from .execution_environment import qualification


def _audited_fingerprint(qp):
    import json
    try:return ((json.loads(qp.get('last_audit_json') or '{}').get('technique_profile') or {}).get('fingerprint'))
    except Exception:return None


def scheduler_plan(source_ids=None):
    ids=set(source_ids or []); states_map=states(); out=[]
    for s in normalized_sources():
        if ids and s['source_id'] not in ids:continue
        qp=quality_profile(s['source_id']) or {}; rows=technique_assignments(s['source_id'])
        assigned=[x.get('technique') for x in rows if x.get('technique')]
        fp=technique_profile_fingerprint(assigned,rows) if assigned else None
        decision=evaluate_source(source=s,quality=qp,run_state=states_map.get(s['source_id'],{}),assigned_fingerprint=fp,audited_fingerprint=_audited_fingerprint(qp))
        due=cadence_due(states_map.get(s['source_id'],{}).get('last_success_at'),s.get('cadence')) if s.get('enabled') else False
        envq=qualification(s)
        out.append({'source_id':s['source_id'],'name':s.get('name'),'due':due,'decision':decision,'assigned_fingerprint':fp,'approved':bool(qp.get('approved_for_store')),'execution_environment':envq})
    return out


def run_scheduler_cycle(source_ids=None,max_pages=None,dry_run=False):
    srcmap={x['source_id']:x for x in normalized_sources()}; plan=scheduler_plan(source_ids); results=[]
    for item in plan:
        if item['decision']['action']!='scheduled-acquire' or not item['due']:
            results.append({**item,'status':'skipped'});continue
        if not (item.get('execution_environment') or {}).get('allowed',True):
            # Environment constraints are not acquisition failures and must not increment
            # source failure counters or trigger unnecessary technique churn.
            results.append({**item,'status':'environment-blocked','error':(item.get('execution_environment') or {}).get('reason')});continue
        if dry_run:
            results.append({**item,'status':'would-acquire'});continue
        s=srcmap[item['source_id']]; rid=start_run(s)
        try:
            r=acquire_and_store({**s,**(s.get('raw') or {})},max_pages=max_pages or s.get('max_pages') or 20,require_approval=True)
            metrics=r.get('metrics') or {}; found=int(metrics.get('records_found') or 0); stored=int(metrics.get('records_stored') or 0)
            finish_run(rid,s['source_id'],'success',found,stored,{'scheduler':True,'deep_run_id':r.get('deep_run_id')})
            results.append({**item,'status':'success','result':r})
        except Exception as e:
            finish_run(rid,s['source_id'],'failed',0,0,{'scheduler':True},f'{type(e).__name__}: {e}')
            results.append({**item,'status':'failed','error':f'{type(e).__name__}: {e}'})
    return {'source_count':len(plan),'results':results}
