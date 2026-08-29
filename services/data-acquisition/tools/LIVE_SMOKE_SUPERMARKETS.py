from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/'acquisition',ROOT/'repository'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from monitoring_registry import normalized_sources
from source_preflight import preflight_url

p=argparse.ArgumentParser();p.add_argument('--no-approve',action='store_true');p.add_argument('--no-store',action='store_true');p.add_argument('--max-sources',type=int,default=5)
a=p.parse_args()
rows=[]
for s in [x for x in normalized_sources() if str(x.get('domain')).lower()=='supermarket'][:a.max_sources]:
    try:r=preflight_url(s['url']); rows.append({'source_id':s['source_id'],'name':s['name'],'url':s['url'],'status':r.get('status'),'http_status':r.get('http_status'),'access_assessment':r.get('access_assessment')})
    except Exception as e:rows.append({'source_id':s['source_id'],'name':s['name'],'url':s['url'],'status':'failed','error':f'{type(e).__name__}: {e}'})
print(json.dumps({'ok':True,'live_smoke':rows,'note':'Public-access smoke only; no approve/store mutation.'},ensure_ascii=False,indent=2))
