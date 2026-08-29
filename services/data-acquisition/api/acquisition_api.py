from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sys, threading, uuid, hashlib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT=Path(__file__).resolve().parents[1]
for p in [ROOT, ROOT/'acquisition', ROOT/'repository', ROOT/'acquisition'/'providers']:
    if str(p) not in sys.path: sys.path.insert(0,str(p))

from monitoring_registry import normalized_sources as monitoring_sources, approve_source as monitoring_approve_source, update_source as monitoring_update_source, cadence_due
from operations_store import states as monitoring_states, recent_runs as monitoring_recent_runs, save_exploration, active_campaign as monitoring_active_campaign, technique_assignment_map, replace_technique_assignments, technique_assignments, save_activity, recent_activities
from acquisition_orchestrator import run_many as monitoring_run_many, start_campaign as monitoring_start_campaign, campaign_status as monitoring_campaign_status, cancel_campaign as monitoring_cancel_campaign
from source_explorer import explore_url as source_explore_url, discover_sources as source_discover_candidates
from technique_strategy import applicable_techniques, recommend, recommend_supermarket_tracks
from source_preflight import preflight_candidates
from deep_audit import audit_source
from change_monitor import check_source_changes
from deep_collection import acquire_and_store as deep_acquire_store, approve_for_store as deep_approve_store, set_continuous as deep_set_continuous
from operations_store import quality_profile as deep_quality_profile, recent_deep_runs, pagination_coverage, product_observation_summary, source_stage, source_stages, create_deep_batch, update_deep_batch, deep_batch, request_deep_batch_cancel
from acquisition_health import health_for_sources, bulk_fill_plan
from acquisition_progress_dashboard import monitor_registry_summary, profile_progress, combined_progress
from repository_browser import repository_overview, browse_table, data_coverage, coverage_sample, business_coverage, business_sample
from repository_engine import connect_profile as repo_connect_profile
from repository_profiles import load_profiles as repository_profiles_list, profile_statuses
from control_plane.observation_bridge import persist_explore, persist_audit
from control_plane.observation_store import ObservationStore
from control_plane.scheduler import scheduler_plan

app=FastAPI(title='KU2D Data Acquisition Service API',version='0.28')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])

@app.get('/health')
def health(): return {'ok':True,'product':'KU2D Data Acquisition Service','version':'0.28','upstream_checkpoint':'Text Analytics Lab v2.56 acquisition split'}

@app.get('/system/status')
def system_status():
    from operations_store import db_resolution
    from serper_provider import key_status
    ops=db_resolution(); profiles=profile_statuses()
    return {'ok':True,'operations_db':{**ops,'path':str(ops.get('path'))},'repositories':profiles,'discovery':key_status()}

class MonitoringRunRequest(BaseModel): source_ids:list[str]|None=None; due_only:bool=False; store:bool=True
class ExploreUrlRequest(BaseModel): url:str; domain:str='General'; purpose:str='research_evidence'; max_pages:int=3; techniques:list[str]|None=None
class DiscoverSourcesRequest(BaseModel):
    query_text:str; query_type:str='topic'; domain:str='General'; num_per_query:int=5; max_candidates:int=20; auto_preflight:bool=True; preflight_limit:int=20
class ApproveMonitoringRequest(BaseModel): source:dict
class MonitoringUpdateRequest(BaseModel): source_id:str; changes:dict
class ChangeCheckRequest(BaseModel): source_id:str; max_pages:int=25
class DeepBatchRequest(BaseModel): source_ids:list[str]; max_pages:int=20; repeat_check:bool=True
class DeepAuditRequest(BaseModel): source_id:str; max_pages:int=20; repeat_check:bool=True
class DeepStoreRequest(BaseModel): source_id:str; max_pages:int=20
class DeepApprovalRequest(BaseModel): source_id:str; approved:bool=True
class ContinuousCollectionRequest(BaseModel): source_id:str; enabled:bool=True; cadence:str|None=None
class TechniqueScanRequest(BaseModel): source_ids:list[str]|None=None; enabled_only:bool=True; max_pages:int=4


def _observation_source_id(url:str) -> str:
    wanted=(url or '').rstrip('/').lower()
    found=next((x.get('source_id') for x in monitoring_sources() if (x.get('url') or '').rstrip('/').lower()==wanted),None)
    return found or ('EXP-'+hashlib.sha256(wanted.encode('utf-8')).hexdigest()[:12].upper())

def _persist_explore_safely(url:str,result:dict):
    try:return persist_explore(_observation_source_id(url),url,result)
    except Exception as e:return {'stored':0,'warning':f'{type(e).__name__}: {e}'}

def _persist_audit_safely(source:dict,audit:dict):
    try:return persist_audit(source.get('source_id') or _observation_source_id(source.get('url') or ''),source.get('url') or '',audit)
    except Exception as e:return {'stored':0,'warning':f'{type(e).__name__}: {e}'}

@app.get('/monitoring/sources')
def monitoring_sources_endpoint():
    st=monitoring_states(); srcs=monitoring_sources(); stages=source_stages([x['source_id'] for x in srcs]); rows=[]; tmap=technique_assignment_map()
    for x in srcs:
        state=st.get(x['source_id'],{}); sg=stages.get(x['source_id']) or {'stage':'not-audited','quality_profile':None}
        rows.append({**x,'run_state':state,'quality_profile':sg.get('quality_profile'),'stage':sg,'technique_assignments':tmap.get(x['source_id'],[]),'due':cadence_due(state.get('last_success_at'),x.get('cadence')) if x.get('enabled') else False})
    return {'ok':True,'sources':rows,'summary':{'total':len(rows),'enabled':sum(bool(x.get('enabled')) for x in rows),'due':sum(bool(x.get('enabled')) and x['due'] for x in rows)}}

@app.post('/monitoring/run')
def monitoring_run_endpoint(req:MonitoringRunRequest): return {'ok':True,**monitoring_run_many(req.source_ids,req.due_only,req.store)}
@app.get('/monitoring/runs')
def monitoring_runs_endpoint(limit:int=100): return {'ok':True,'runs':monitoring_recent_runs(max(1,min(limit,500)))}
@app.post('/monitoring/update')
def monitoring_update_endpoint(req:MonitoringUpdateRequest):
    try:return {'ok':True,'source':monitoring_update_source(req.source_id,req.changes)}
    except Exception as e:raise HTTPException(status_code=400,detail=str(e))
@app.post('/explore/url')
def explore_url_endpoint(req:ExploreUrlRequest):
    result=source_explore_url(req.url,req.domain,req.purpose,req.max_pages,req.techniques)
    result['observation_store']=_persist_explore_safely(req.url,result)
    try:result['exploration_id']=save_exploration('url',req.model_dump(),result)
    except Exception as e:result['audit_warning']=str(e)
    return {'ok':result.get('status')=='completed',**result}

_EXPLORE_JOBS={}; _EXPLORE_LOCK=threading.Lock()
def _explore_bench_worker(job_id,req):
    def progress(done,total,last):
        with _EXPLORE_LOCK:
            _EXPLORE_JOBS[job_id].update({'status':'running','completed_techniques':done,'total_techniques':total,'progress_pct':round(100*done/max(1,total))})
    try:
        result=source_explore_url(req.url,req.domain,req.purpose,req.max_pages,None,progress_callback=progress)
        result['observation_store']=_persist_explore_safely(req.url,result)
        try:result['exploration_id']=save_exploration('url',req.model_dump(),result)
        except Exception as e:result['audit_warning']=str(e)
        with _EXPLORE_LOCK:
            j=_EXPLORE_JOBS[job_id];j.update({'status':'completed','completed_techniques':j.get('total_techniques',0),'progress_pct':100,'finished_at':datetime.now(timezone.utc).isoformat(),'result':result})
    except Exception as e:
        with _EXPLORE_LOCK:_EXPLORE_JOBS[job_id].update({'status':'failed','error':f'{type(e).__name__}: {e}','finished_at':datetime.now(timezone.utc).isoformat()})

@app.post('/explore/url/start')
def explore_url_start(req:ExploreUrlRequest):
    total=len(applicable_techniques(req.url));jid='EXP-'+uuid.uuid4().hex[:12]
    job={'job_id':jid,'status':'queued','url':req.url,'total_techniques':total,'completed_techniques':0,'progress_pct':0,'started_at':datetime.now(timezone.utc).isoformat()}
    _EXPLORE_JOBS[jid]=job;threading.Thread(target=_explore_bench_worker,args=(jid,req),daemon=True).start();return {'ok':True,'job':job}

@app.get('/explore/url/status/{job_id}')
def explore_url_status(job_id:str):
    x=_EXPLORE_JOBS.get(job_id)
    if not x:raise HTTPException(status_code=404,detail='Explore technique-bench job not found')
    return {'ok':True,'job':x}
@app.post('/discover/sources')
def discover_sources_endpoint(req:DiscoverSourcesRequest):
    result=source_discover_candidates(req.query_text,req.query_type,req.domain,req.num_per_query,req.max_candidates)
    if req.auto_preflight:
        checked=preflight_candidates(result.get('candidates',[]),max(1,min(req.preflight_limit,req.max_candidates)),4); byurl={x.get('url'):x for x in checked}
        result['candidates']=[byurl.get(x.get('url'),x) for x in result.get('candidates',[])]
    try:result['exploration_id']=save_exploration('discovery',req.model_dump(),result)
    except Exception as e:result['audit_warning']=str(e)
    return {'ok':True,**result}
@app.post('/monitoring/approve')
def monitoring_approve_endpoint(req:ApproveMonitoringRequest):
    try:
        wanted=(req.source.get('url') or '').rstrip('/').lower(); explicit_id=req.source.get('source_id')
        existing=next((x for x in monitoring_sources() if explicit_id and x.get('source_id')==explicit_id),None)
        if not existing:existing=next((x for x in monitoring_sources() if (x.get('url') or '').rstrip('/').lower()==wanted),None)
        recs=req.source.get('recommended_techniques') or req.source.get('technique_assignment') or []
        if existing:
            if recs: replace_technique_assignments(existing['source_id'],recs)
            return {'ok':True,'action':'techniques-updated','source':existing,'technique_assignments':technique_assignments(existing['source_id'])}
        out=monitoring_approve_source(req.source); sid=out.get('source_id')
        if sid and recs: replace_technique_assignments(sid,recs)
        return {'ok':True,'action':'source-added','source':out,'technique_assignments':technique_assignments(sid) if sid else []}
    except Exception as e:raise HTTPException(status_code=400,detail=str(e))
_TECHNIQUE_JOBS={}; _TECHNIQUE_LOCK=threading.Lock()
def _technique_scan_worker(job_id,sources,max_pages):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    total=max(1,len(sources))
    def cancel_requested():
        with _TECHNIQUE_LOCK:return bool((_TECHNIQUE_JOBS.get(job_id) or {}).get('cancel_requested'))
    def one(src):
        if cancel_requested():return {'source_id':src['source_id'],'name':src.get('name'),'url':src.get('url'),'status':'cancelled','recommended_techniques':[],'technique_results':[]}
        try:
            url=src.get('url') or ''; lowurl=url.lower(); is_lotus='lotuss.com' in lowurl; is_bigc='bigc.co.th' in lowurl; is_makro=('makro.co.th' in lowurl or 'makro.pro' in lowurl); is_tops='tops.co.th' in lowurl
            if is_lotus: fast=None
            elif is_bigc: fast=['basic_crawler','structured_data','generic_sitemap','generic_app_bundle','bigc_product_catalog','bigc_promotion_surface','bigc_catalog_network']
            elif is_makro: fast=['basic_crawler','structured_data','generic_sitemap','generic_app_bundle','makro_pro_catalog','makro_promotion_catalogue','makro_pro_network']
            elif is_tops: fast=['basic_crawler','structured_data','generic_sitemap','generic_app_bundle','tops_product_catalog','tops_campaign_catalog','tops_promotion_surface','tops_catalog_network']
            else: fast=['basic_crawler','structured_data','generic_document','generic_sitemap','generic_app_bundle','generic_api_probe']
            r=source_explore_url(url,src.get('domain') or 'General',src.get('purpose') or 'research_evidence',max_pages,fast)
            if cancel_requested():return {'source_id':src['source_id'],'name':src.get('name'),'url':src.get('url'),'status':'cancelled','recommended_techniques':[],'technique_results':r.get('technique_results') or []}
            recs=r.get('recommended_techniques') or []
            purpose=src.get('purpose') or 'research_evidence'
            needs_business_facts=purpose in {'retail_market_intelligence','competitive_intelligence'}
            has_acquisition=any(z.get('role')=='acquisition' for z in recs)
            # For commerce/market-intelligence, a readable document or endpoint list is evidence,
            # but it is not enough to become the Best Acquisition Technique. Escalate to browser/network.
            if not is_lotus and ((needs_business_facts and not has_acquisition) or not recs):
                r2=source_explore_url(url,src.get('domain') or 'General',purpose,max_pages,
                    ['generic_browser_rendered','generic_browser_network','generic_api_probe'])
                combined=(r.get('technique_results') or [])+(r2.get('technique_results') or [])
                # Deduplicate by technique, keeping the later extended result.
                by={z.get('technique'):z for z in combined if z.get('technique')}
                r['technique_results']=list(by.values())
                if is_bigc: recs,_tracks=recommend_supermarket_tracks(r['technique_results'],'bigc')
                elif is_makro: recs,_tracks=recommend_supermarket_tracks(r['technique_results'],'makro')
                elif is_tops: recs,_tracks=recommend_supermarket_tracks(r['technique_results'],'tops')
                else: recs=recommend(r['technique_results'],allow_documents=not needs_business_facts)
            if recs and not cancel_requested(): replace_technique_assignments(src['source_id'],recs)
            return {'source_id':src['source_id'],'name':src.get('name'),'url':src.get('url'),'status':'assigned' if recs else 'unresolved','recommended_techniques':recs,'technique_results':r.get('technique_results') or []}
        except Exception as e:
            return {'source_id':src['source_id'],'name':src.get('name'),'url':src.get('url'),'status':'failed','error':f'{type(e).__name__}: {e}','recommended_techniques':[],'technique_results':[]}
    done=0;assigned=0;failed=0;results=[];cancelled=False
    with ThreadPoolExecutor(max_workers=min(3,max(1,len(sources)))) as ex:
        fut={ex.submit(one,x):x for x in sources}
        for f in as_completed(fut):
            if cancel_requested():
                cancelled=True
                for pending in fut:pending.cancel()
            if f.cancelled():continue
            r=f.result();results.append(r)
            if r.get('status')!='cancelled':done+=1
            if r.get('status')=='assigned':assigned+=1
            elif r.get('status')=='failed':failed+=1
            with _TECHNIQUE_LOCK:
                _TECHNIQUE_JOBS[job_id].update({'status':'cancel-requested' if cancel_requested() else 'running','completed_sources':done,'assigned_sources':assigned,'failed_sources':failed,'progress_pct':round(100*done/total),'current_source_name':r.get('name'),'results':results})
            if cancel_requested():cancelled=True
    finished=datetime.now(timezone.utc).isoformat();status='cancelled' if cancelled else 'completed'
    with _TECHNIQUE_LOCK:
        _TECHNIQUE_JOBS[job_id].update({'status':status,'progress_pct':round(100*done/total) if cancelled else 100,'completed_sources':done,'assigned_sources':assigned,'failed_sources':failed,'results':results,'finished_at':finished,'current_source_name':None})
    save_activity('technique-benchmark','Find Best Data Acquisition Techniques',status,started_at=_TECHNIQUE_JOBS[job_id].get('started_at'),finished_at=finished,source_count=done,success_count=assigned,failed_count=failed,summary={'assigned_sources':assigned,'unresolved_sources':max(0,done-assigned-failed),'cancelled':cancelled,'planned_sources':len(sources)},result={'job':_TECHNIQUE_JOBS[job_id]})

@app.post('/monitoring/techniques/start')
def monitoring_techniques_start(req:TechniqueScanRequest):
    active=next((x for x in _TECHNIQUE_JOBS.values() if x.get('status') in ('queued','running','cancel-requested')),None)
    if active:return {'ok':False,'detail':'A technique-discovery job is already running.','job':active}
    ids=set(req.source_ids or []);srcs=[x for x in monitoring_sources() if (not req.enabled_only or x.get('enabled')) and (not ids or x.get('source_id') in ids)]
    jid='TECH-'+uuid.uuid4().hex[:12];job={'job_id':jid,'status':'queued','total_sources':len(srcs),'completed_sources':0,'assigned_sources':0,'failed_sources':0,'progress_pct':0,'results':[],'started_at':datetime.now(timezone.utc).isoformat()}
    _TECHNIQUE_JOBS[jid]=job;threading.Thread(target=_technique_scan_worker,args=(jid,srcs,max(1,min(req.max_pages,6))),daemon=True).start()
    return {'ok':True,'job':job}

@app.post('/monitoring/techniques/cancel/{job_id}')
def monitoring_techniques_cancel(job_id:str):
    with _TECHNIQUE_LOCK:
        x=_TECHNIQUE_JOBS.get(job_id)
        if not x:raise HTTPException(status_code=404,detail='Technique-discovery job not found')
        if x.get('status') in ('completed','failed','cancelled'):return {'ok':True,'job':x}
        x['cancel_requested']=True;x['status']='cancel-requested';x['message']='Cancellation requested; stopping after active technique tests finish.'
        return {'ok':True,'job':x}

@app.get('/monitoring/techniques/status/{job_id}')
def monitoring_techniques_status(job_id:str):
    x=_TECHNIQUE_JOBS.get(job_id)
    if not x:raise HTTPException(status_code=404,detail='Technique-discovery job not found')
    return {'ok':True,'job':x}

@app.get('/monitoring/techniques/{source_id}')
def monitoring_techniques_source(source_id:str):return {'ok':True,'source_id':source_id,'assignments':technique_assignments(source_id)}

@app.get('/monitoring/activity-log')
def monitoring_activity_log(limit:int=30):return {'ok':True,'activities':recent_activities(max(1,min(limit,100)))}

@app.get('/monitoring/export')
def monitoring_export():
    st=monitoring_states();srcs=monitoring_sources();stages=source_stages([x['source_id'] for x in srcs]);tmap=technique_assignment_map();rows=[]
    for x in srcs:
        rs=st.get(x['source_id'],{});sg=stages.get(x['source_id']) or {}
        rows.append({**x,'technique_assignments':tmap.get(x['source_id'],[]),'access_quality':sg.get('quality_profile'),'stage':sg.get('stage'),'run_state':rs,'due':cadence_due(rs.get('last_success_at'),x.get('cadence')) if x.get('enabled') else False})
    return {'ok':True,'generated_at':datetime.now(timezone.utc).isoformat(),'source_count':len(rows),'sources':rows}

@app.post('/monitoring/campaign/start')
def monitoring_campaign_start_endpoint(req:MonitoringRunRequest):
    active=monitoring_active_campaign()
    if active:return {'ok':False,'active_campaign':active,'detail':'An acquisition campaign is already running or queued.'}
    return {'ok':True,**monitoring_start_campaign(req.source_ids,req.due_only,req.store)}
@app.post('/monitoring/campaign/{campaign_id}/cancel')
def monitoring_campaign_cancel_endpoint(campaign_id:str):
    x=monitoring_cancel_campaign(campaign_id)
    if not x:raise HTTPException(status_code=404,detail='Campaign not found')
    return {'ok':True,'campaign':x}

@app.get('/monitoring/campaign/{campaign_id}')
def monitoring_campaign_status_endpoint(campaign_id:str):
    x=monitoring_campaign_status(campaign_id)
    if not x:raise HTTPException(status_code=404,detail='Campaign not found')
    return {'ok':True,'campaign':x}
@app.get('/monitoring/campaign-active')
def monitoring_campaign_active_endpoint(): return {'ok':True,'campaign':monitoring_active_campaign()}
@app.get('/monitoring/coverage/{source_id}')
def monitoring_coverage(source_id:str): return {'ok':True,'source_id':source_id,'pagination':pagination_coverage(source_id),'products':product_observation_summary(source_id,50)}
@app.get('/monitoring/source-stage/{source_id}')
def monitoring_source_stage(source_id:str): return {'ok':True,**source_stage(source_id)}

_CHANGE_JOBS={}; _CHANGE_LOCK=threading.Lock()
def _change_worker(job_id,source,max_pages):
    def progress(ev):
        with _CHANGE_LOCK:
            if job_id in _CHANGE_JOBS:_CHANGE_JOBS[job_id].update(ev)
    try:
        progress({'status':'running','progress_pct':2,'phase':'checking','message':'Change check starting'})
        qp=deep_quality_profile(source['source_id']) or {}; level=qp.get('accessibility_level') or (source.get('raw') or {}).get('accessibility_level') or 0; delays={1:1.5,2:3.0,3:8.0,4:1.0}
        result=check_source_changes(source,max_pages=max_pages,delay_seconds=delays.get(int(level or 0),2.0),progress=lambda ev:progress({**ev,'progress_pct':min(95,5+int(90*(ev.get('pages_done',0)/max(1,ev.get('pages_target',1)))))}))
        with _CHANGE_LOCK:_CHANGE_JOBS[job_id].update({'status':'complete','progress_pct':100,'phase':'complete','message':'Change check completed','result':result,'finished_at':datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        with _CHANGE_LOCK:_CHANGE_JOBS[job_id].update({'status':'failed','phase':'failed','error':f'{type(e).__name__}: {e}'})
@app.post('/monitoring/change-check/start')
def monitoring_change_check_start(req:ChangeCheckRequest):
    source=next((x for x in monitoring_sources() if x.get('source_id')==req.source_id),None)
    if not source:raise HTTPException(status_code=404,detail='Monitoring source not found')
    jid='CHG-'+uuid.uuid4().hex[:12]; _CHANGE_JOBS[jid]={'job_id':jid,'source_id':req.source_id,'status':'queued','progress_pct':0}
    threading.Thread(target=_change_worker,args=(jid,source,max(1,min(req.max_pages,100))),daemon=True).start(); return {'ok':True,'job':_CHANGE_JOBS[jid]}
@app.get('/monitoring/change-check/status/{job_id}')
def monitoring_change_check_status(job_id:str):
    x=_CHANGE_JOBS.get(job_id)
    if not x:raise HTTPException(status_code=404,detail='Change-check job not found')
    return {'ok':True,'job':x}

_BATCH_JOBS={}
def _batch_cancel_requested(batch_id):
    x=deep_batch(batch_id) or {};return x.get('status')=='cancel-requested'

def _batch_audit_worker(batch_id,source_ids,max_pages,repeat_check):
    result={'sources':[],'current':None};cancelled=False
    try:
        allsrc={x['source_id']:x for x in monitoring_sources()}; total=max(1,len(source_ids))
        for pos,sid in enumerate(source_ids,1):
            if _batch_cancel_requested(batch_id):cancelled=True;break
            src=allsrc.get(sid)
            if not src: result['sources'].append({'source_id':sid,'status':'failed','error':'Monitoring source not found'}); update_deep_batch(batch_id,result=result); continue
            def progress(ev):
                result['current']={'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'position':pos,'total':total,**ev}; update_deep_batch(batch_id,result=result)
            try:
                audit=audit_source({**src,**(src.get('raw') or {})},max_pages=max_pages,repeat_check=repeat_check,progress=progress,cancel_check=lambda:_batch_cancel_requested(batch_id))
                audit['observation_store']=_persist_audit_safely(src,audit)
                result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'success','audit':audit})
            except InterruptedError as e:
                result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'cancelled','error':str(e)});cancelled=True
            except Exception as e: result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'failed','error':f'{type(e).__name__}: {e}'})
            result['current']=None; update_deep_batch(batch_id,result=result)
            if cancelled or _batch_cancel_requested(batch_id):cancelled=True;break
        update_deep_batch(batch_id,status='cancelled' if cancelled else 'complete',result=result)
    except Exception as e:update_deep_batch(batch_id,status='failed',result=result,error=f'{type(e).__name__}: {e}')

def _batch_store_worker(batch_id,source_ids,max_pages):
    result={'sources':[],'current':None};cancelled=False
    try:
        allsrc={x['source_id']:x for x in monitoring_sources()}; total=max(1,len(source_ids))
        for pos,sid in enumerate(source_ids,1):
            if _batch_cancel_requested(batch_id):cancelled=True;break
            src=allsrc.get(sid); qp=deep_quality_profile(sid) or {}
            if not src: result['sources'].append({'source_id':sid,'status':'failed','error':'Monitoring source not found'}); update_deep_batch(batch_id,result=result); continue
            if not qp.get('approved_for_store'): result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'skipped','error':'Not approved for repository store'}); update_deep_batch(batch_id,result=result); continue
            def progress(ev): result['current']={'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'position':pos,'total':total,**ev}; update_deep_batch(batch_id,result=result)
            try:
                stored=deep_acquire_store({**src,**(src.get('raw') or {})},max_pages=max_pages,require_approval=True,progress=progress,cancel_check=lambda:_batch_cancel_requested(batch_id)); result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'success','result':stored})
            except InterruptedError as e:
                result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'cancelled','error':str(e)});cancelled=True
            except Exception as e: result['sources'].append({'source_id':sid,'source_name':src.get('name'),'url':src.get('url'),'status':'failed','error':f'{type(e).__name__}: {e}'})
            result['current']=None;update_deep_batch(batch_id,result=result)
            if cancelled or _batch_cancel_requested(batch_id):cancelled=True;break
        update_deep_batch(batch_id,status='cancelled' if cancelled else 'complete',result=result)
    except Exception as e:update_deep_batch(batch_id,status='failed',result=result,error=f'{type(e).__name__}: {e}')

@app.post('/monitoring/deep-audit/batch/start')
def deep_audit_batch(req:DeepBatchRequest):
    ids=list(dict.fromkeys(req.source_ids));
    if not ids:raise HTTPException(status_code=400,detail='Select at least one source')
    bid=create_deep_batch('audit',ids);threading.Thread(target=_batch_audit_worker,args=(bid,ids,max(1,min(req.max_pages,40)),req.repeat_check),daemon=True).start();return {'ok':True,'batch_id':bid}
@app.post('/monitoring/deep-store/batch/start')
def deep_store_batch(req:DeepBatchRequest):
    ids=list(dict.fromkeys(req.source_ids));
    if not ids:raise HTTPException(status_code=400,detail='Select at least one source')
    bid=create_deep_batch('store',ids);threading.Thread(target=_batch_store_worker,args=(bid,ids,max(1,min(req.max_pages,40))),daemon=True).start();return {'ok':True,'batch_id':bid}
@app.get('/monitoring/deep-batch/{batch_id}')
def deep_batch_status(batch_id:str):
    x=deep_batch(batch_id)
    if not x:raise HTTPException(status_code=404,detail='Deep batch not found')
    return {'ok':True,'batch':x}

@app.get('/monitoring/deep-batch/{batch_id}/export')
def deep_batch_export(batch_id:str):
    b=deep_batch(batch_id)
    if not b: raise HTTPException(status_code=404,detail='Deep batch not found')
    ids=list(dict.fromkeys((b.get('result') or {}).get('planned_source_ids') or [x.get('source_id') for x in ((b.get('result') or {}).get('sources') or []) if x.get('source_id')]))
    srcmap={x['source_id']:x for x in monitoring_sources()}
    st=monitoring_states(); stages=source_stages(ids); tmap=technique_assignment_map()
    rows=[]
    for sid in ids:
        src=srcmap.get(sid) or {'source_id':sid}
        sg=stages.get(sid) or {}
        rows.append({**src,
          'technique_assignments':tmap.get(sid,[]),
          'access_quality':sg.get('quality_profile'),
          'stage':sg.get('stage'),
          'run_state':st.get(sid,{})})
    export_type='deep-acquire-full-results' if b.get('mode')=='store' else 'deep-audit-full-results' if b.get('mode')=='audit' else 'deep-batch-full-results'
    return {'ok':True,'generated_at':datetime.now(timezone.utc).isoformat(),
      'export_type':export_type,'batch':b,'source_count':len(rows),'sources':rows}

@app.post('/monitoring/deep-batch/{batch_id}/cancel')
def deep_batch_cancel(batch_id:str):
    x=request_deep_batch_cancel(batch_id)
    if not x:raise HTTPException(status_code=404,detail='Deep batch not found')
    return {'ok':True,'batch':deep_batch(batch_id)}

_DEEP_AUDIT_JOBS={};_DEEP_AUDIT_LOCK=threading.Lock();_DEEP_STORE_JOBS={};_DEEP_STORE_LOCK=threading.Lock()
def _deep_audit_worker(job_id,source,max_pages,repeat_check):
    def progress(ev):
        with _DEEP_AUDIT_LOCK:
            if job_id in _DEEP_AUDIT_JOBS:_DEEP_AUDIT_JOBS[job_id].update(ev)
    try:
        r=audit_source(source,max_pages=max_pages,repeat_check=repeat_check,progress=progress,cancel_check=lambda:bool((_DEEP_AUDIT_JOBS.get(job_id) or {}).get('cancel_requested')))
        r['observation_store']=_persist_audit_safely(source,r)
        with _DEEP_AUDIT_LOCK:_DEEP_AUDIT_JOBS[job_id].update({'status':'complete','progress_pct':100,'audit':r})
    except InterruptedError as e:
        with _DEEP_AUDIT_LOCK:_DEEP_AUDIT_JOBS[job_id].update({'status':'cancelled','error':str(e)})
    except Exception as e:
        with _DEEP_AUDIT_LOCK:_DEEP_AUDIT_JOBS[job_id].update({'status':'failed','error':f'{type(e).__name__}: {e}'})
def _deep_store_worker(job_id,source,max_pages):
    def progress(ev):
        with _DEEP_STORE_LOCK:
            if job_id in _DEEP_STORE_JOBS:_DEEP_STORE_JOBS[job_id].update(ev)
    try:
        r=deep_acquire_store(source,max_pages=max_pages,require_approval=True,progress=progress,cancel_check=lambda:bool((_DEEP_STORE_JOBS.get(job_id) or {}).get('cancel_requested')))
        with _DEEP_STORE_LOCK:_DEEP_STORE_JOBS[job_id].update({'status':'complete','progress_pct':100,'result':r})
    except InterruptedError as e:
        with _DEEP_STORE_LOCK:_DEEP_STORE_JOBS[job_id].update({'status':'cancelled','error':str(e)})
    except Exception as e:
        with _DEEP_STORE_LOCK:_DEEP_STORE_JOBS[job_id].update({'status':'failed','error':f'{type(e).__name__}: {e}'})
@app.post('/monitoring/deep-audit/start')
def deep_audit_start(req:DeepAuditRequest):
    source=next((x for x in monitoring_sources() if x.get('source_id')==req.source_id),None)
    if not source:raise HTTPException(status_code=404,detail='Monitoring source not found')
    source={**source,**(source.get('raw') or {})}; jid='AUD-'+uuid.uuid4().hex[:12];_DEEP_AUDIT_JOBS[jid]={'job_id':jid,'source_id':req.source_id,'status':'queued','progress_pct':0};threading.Thread(target=_deep_audit_worker,args=(jid,source,max(1,min(req.max_pages,40)),req.repeat_check),daemon=True).start();return {'ok':True,'job':_DEEP_AUDIT_JOBS[jid]}
@app.post('/monitoring/deep-audit/cancel/{job_id}')
def deep_audit_cancel(job_id:str):
    with _DEEP_AUDIT_LOCK:
        x=_DEEP_AUDIT_JOBS.get(job_id)
        if not x:raise HTTPException(status_code=404,detail='Deep Audit job not found')
        if x.get('status') not in ('complete','failed','cancelled'):
            x['cancel_requested']=True;x['status']='cancel-requested';x['message']='Cancellation requested'
        return {'ok':True,'job':x}

@app.get('/monitoring/deep-audit/status/{job_id}')
def deep_audit_status(job_id:str):
    x=_DEEP_AUDIT_JOBS.get(job_id)
    if not x:raise HTTPException(status_code=404,detail='Deep Audit job not found')
    return {'ok':True,'job':x}
@app.get('/monitoring/deep-quality/{source_id}')
def deep_quality(source_id:str): return {'ok':True,'profile':deep_quality_profile(source_id),'runs':recent_deep_runs(source_id,20)}
@app.post('/monitoring/deep-approve-store')
def deep_approve(req:DeepApprovalRequest):
    qp=deep_quality_profile(req.source_id) or {}
    if req.approved and not qp.get('audit_passed'):raise HTTPException(status_code=400,detail='Source must pass Deep Audit before store approval.')
    return {'ok':True,'profile':deep_approve_store(req.source_id,req.approved)}
@app.post('/monitoring/deep-acquire-store/start')
def deep_store_start(req:DeepStoreRequest):
    source=next((x for x in monitoring_sources() if x.get('source_id')==req.source_id),None)
    if not source:raise HTTPException(status_code=404,detail='Monitoring source not found')
    qp=deep_quality_profile(req.source_id) or {}
    if not qp.get('audit_passed') or not qp.get('approved_for_store'):raise HTTPException(status_code=400,detail='Source is not approved for repository storage.')
    jid='STORE-'+uuid.uuid4().hex[:12];_DEEP_STORE_JOBS[jid]={'job_id':jid,'source_id':req.source_id,'status':'queued','progress_pct':0};threading.Thread(target=_deep_store_worker,args=(jid,source,max(1,min(req.max_pages,40))),daemon=True).start();return {'ok':True,'job':_DEEP_STORE_JOBS[jid]}
@app.post('/monitoring/deep-acquire-store/cancel/{job_id}')
def deep_store_cancel(job_id:str):
    with _DEEP_STORE_LOCK:
        x=_DEEP_STORE_JOBS.get(job_id)
        if not x:raise HTTPException(status_code=404,detail='Deep Store job not found')
        if x.get('status') not in ('complete','failed','cancelled'):
            x['cancel_requested']=True;x['status']='cancel-requested';x['message']='Cancellation requested'
        return {'ok':True,'job':x}

@app.get('/monitoring/deep-acquire-store/status/{job_id}')
def deep_store_status(job_id:str):
    x=_DEEP_STORE_JOBS.get(job_id)
    if not x:raise HTTPException(status_code=404,detail='Deep Store job not found')
    return {'ok':True,'job':x}
@app.post('/monitoring/continuous-collection')
def continuous(req:ContinuousCollectionRequest):
    try:return {'ok':True,**deep_set_continuous(req.source_id,req.enabled,req.cadence)}
    except Exception as e:raise HTTPException(status_code=400,detail=str(e))

@app.get('/observations/summary')
def observations_summary(source_id:str|None=None):
    try:return {'ok':True,**ObservationStore().summary(source_id)}
    except Exception as e:raise HTTPException(status_code=500,detail=str(e))

@app.get('/observations/recent')
def observations_recent(source_id:str|None=None,limit:int=100):
    try:return {'ok':True,'observations':ObservationStore().observations(source_id,limit)}
    except Exception as e:raise HTTPException(status_code=500,detail=str(e))

@app.get('/scheduler/plan')
def scheduler_plan_endpoint():
    return {'ok':True,'plan':scheduler_plan()}

@app.get('/acquisition/dashboard/monitors')
def dash_monitors(): return {'ok':True,**monitor_registry_summary()}
def _pairs():
    cfg=repository_profiles_list();pairs=[];bad=[]
    for p in cfg.get('profiles',[]):
        try:pairs.append((p.get('profile_id'),repo_connect_profile(p.get('profile_id'),create=False)))
        except Exception as e:bad.append({'profile_id':p.get('profile_id'),'error':str(e)})
    return pairs,bad
@app.get('/acquisition/dashboard/progress')
def dash_progress():
    pairs,bad=_pairs()
    try:r=combined_progress(pairs);r['unavailable_profiles']=bad;return {'ok':True,**r}
    finally:
        for _,c in pairs:c.close()
@app.get('/acquisition/dashboard/health')
def dash_health():
    pairs,bad=_pairs()
    try:r=health_for_sources(pairs);r['unavailable_profiles']=bad;return {'ok':True,**r}
    finally:
        for _,c in pairs:c.close()
@app.get('/acquisition/dashboard/bulk-fill-plan')
def dash_plan(limit:int|None=None):
    pairs,bad=_pairs()
    try:r=bulk_fill_plan(pairs,limit);r['unavailable_profiles']=bad;return {'ok':True,**r}
    finally:
        for _,c in pairs:c.close()
@app.get('/repository/browser/overview/{profile_id}')
def repo_overview(profile_id:str):
    try:c=repo_connect_profile(profile_id,create=False)
    except FileNotFoundError as e:raise HTTPException(status_code=409,detail=str(e))
    try:return {'ok':True,**repository_overview(c,profile_id)}
    finally:c.close()
@app.get('/repository/browser/coverage/{profile_id}')
def repo_coverage(profile_id:str):
    try:c=repo_connect_profile(profile_id,create=False)
    except FileNotFoundError as e:raise HTTPException(status_code=409,detail=str(e))
    try:return {'ok':True,'profile_id':profile_id,**data_coverage(c)}
    finally:c.close()

@app.get('/repository/browser/coverage-sample/{profile_id}')
def repo_coverage_sample(profile_id:str,analytical_use:str,industry_raw:str='Unspecified',limit:int=25,offset:int=0):
    try:c=repo_connect_profile(profile_id,create=False)
    except FileNotFoundError as e:raise HTTPException(status_code=409,detail=str(e))
    try:
        try:return {'ok':True,'profile_id':profile_id,**coverage_sample(c,analytical_use,industry_raw,limit,offset)}
        except ValueError as e:raise HTTPException(status_code=400,detail=str(e))
    finally:c.close()

@app.get('/repository/browser/business-coverage/{profile_id}')
def repo_business_coverage(profile_id:str,industry_raw:str|None=None):
    try:c=repo_connect_profile(profile_id,create=False)
    except FileNotFoundError as e:raise HTTPException(status_code=409,detail=str(e))
    try:return {'ok':True,'profile_id':profile_id,**business_coverage(c,industry_raw)}
    finally:c.close()

@app.get('/repository/browser/business-sample/{profile_id}')
def repo_business_sample(profile_id:str,business_id:str,data_type:str,limit:int=25,offset:int=0):
    try:c=repo_connect_profile(profile_id,create=False)
    except FileNotFoundError as e:raise HTTPException(status_code=409,detail=str(e))
    try:
        try:return {'ok':True,'profile_id':profile_id,**business_sample(c,business_id,data_type,limit,offset)}
        except ValueError as e:raise HTTPException(status_code=400,detail=str(e))
    finally:c.close()

@app.get('/repository/browser/table/{profile_id}/{table}')
def repo_table(profile_id:str,table:str,limit:int=100,offset:int=0,search:str|None=None):
    try:c=repo_connect_profile(profile_id,create=False)
    except FileNotFoundError as e:raise HTTPException(status_code=409,detail=str(e))
    try:
        try:return {'ok':True,**browse_table(c,table,limit,offset,search)}
        except ValueError as e:raise HTTPException(status_code=400,detail=str(e))
    finally:c.close()

