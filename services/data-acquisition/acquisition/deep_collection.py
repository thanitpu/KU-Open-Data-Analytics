from __future__ import annotations
import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/'acquisition',ROOT/'repository'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from repository_engine import connect_profile,ingest_official_result
from operations_store import quality_profile,set_quality_approval,start_deep_run,finish_deep_run,frontier_add,frontier_summary,pagination_coverage,product_observe,product_observation_summary,technique_assignments
from monitoring_registry import update_source
from access_policy import policy
from technique_strategy import assigned_acquisition, technique_profile_fingerprint, technique_tracks_from_assignments
from control_plane.observation_bridge import persist_acquire


def _source_snapshot(con,business_name):
    row=con.execute('SELECT business_id FROM business WHERE lower(name)=lower(?)',(business_name,)).fetchone()
    if not row:return {'listings':0,'price_versions':0,'promotions':0,'evidence':0}
    bid=row['business_id']
    return {
      'listings':con.execute('SELECT COUNT(*) c FROM listing WHERE business_id=?',(bid,)).fetchone()['c'],
      'price_versions':con.execute('SELECT COUNT(*) c FROM price_version p JOIN listing l ON p.listing_id=l.listing_id WHERE l.business_id=?',(bid,)).fetchone()['c'],
      'promotions':con.execute('SELECT COUNT(*) c FROM promotion WHERE business_id=?',(bid,)).fetchone()['c'],
      'evidence':con.execute('SELECT COUNT(*) c FROM evidence WHERE business_id=?',(bid,)).fetchone()['c']}


def _audit_payload(qp):
    try:return json.loads((qp or {}).get('last_audit_json') or '{}')
    except:return {}


def acquire_and_store(source,max_pages=20,require_approval=True,progress=None,cancel_check=None):
    source_id=source['source_id']
    def cancelled():return bool(cancel_check and cancel_check())
    def guard():
        if cancelled():raise InterruptedError('Deep Acquire cancelled by user.')
    def emit(pct,phase,message,**extra):
        if progress:
            try: progress({"progress_pct":pct,"phase":phase,"message":message,**extra})
            except Exception: pass
        guard()

    emit(3,"gate","Checking audit/store approval")
    qp=quality_profile(source_id) or {}
    if not qp.get('audit_passed'):raise PermissionError('Source has not passed Deep Acquisition & Data Quality Audit.')
    if require_approval and not qp.get('approved_for_store'):raise PermissionError('Source has not been approved for repository storage.')

    assigned_rows=technique_assignments(source_id);assigned=[x.get('technique') for x in assigned_rows if x.get('technique')]
    if not assigned:raise PermissionError('No Best Acquisition Technique is assigned. Run Find Best Data Acquisition Techniques and Deep Audit again.')
    fp=technique_profile_fingerprint(assigned,assigned_rows);aud=_audit_payload(qp);audited_fp=((aud.get('technique_profile') or {}).get('fingerprint'))
    if not audited_fp:
        raise PermissionError('The saved Deep Audit predates Best-Technique auditing. Re-run Deep Audit before repository storage.')
    if audited_fp!=fp:
        raise PermissionError('Best Acquisition Technique profile changed after the last Deep Audit. Re-run Deep Audit before repository storage.')

    rid=start_deep_run(source_id,'deep-acquire-store');t0=time.time()
    try:
        if source.get('registry') and source.get('registry')!='commerce':
            emit(10,"best-technique","Starting Deep Acquire with audited Best Acquisition Technique profile",assigned_techniques=assigned)
            from acquisition_orchestrator import run_source as routed_run_source
            routed=routed_run_source(source,force_store=True)
            if not routed.get('ok'):
                raise RuntimeError(routed.get('error') or 'Non-commerce acquisition failed.')
            metrics={'records_found':int(routed.get('records') or 0),'records_stored':int(routed.get('records_added') or 0),
              'registry':source.get('registry'),'profile_id':source.get('profile_id'),
              'technique_profile':{'source_of_truth':'Best Acquisition Technique(s)','assigned_techniques':assigned,
                'fingerprint':fp,'audited_fingerprint':audited_fp,'assignments':assigned_rows,'tracks':technique_tracks_from_assignments(assigned_rows),
                'legacy_fallback_used':bool(routed.get('legacy_fallback_used'))},
              'elapsed_seconds':round(time.time()-t0,2)}
            finish_deep_run(rid,'success',metrics,result={'metrics':metrics,'acquisition':routed})
            emit(100,"complete","Deep Acquire completed in the source repository profile",records_found=metrics['records_found'],records_stored=metrics['records_stored'])
            return {'ok':True,'deep_run_id':rid,'source_id':source_id,'metrics':metrics,'routed':routed}
        ap=policy(qp.get('accessibility_level') or source.get('accessibility_level') or (source.get('raw') or {}).get('accessibility_level') or 0)
        cap=max(1,min(int(max_pages),int(ap.get('max_pages_per_run',40) or 40),40))
        emit(10,"best-technique","Starting Deep Acquire with audited Best Acquisition Technique profile",pages_target=cap,assigned_techniques=assigned)
        result=assigned_acquisition(source,max_pages=cap,progress=lambda q: emit(35,"best-technique",q.get('message','Applying Best Acquisition Technique profile'),**{k:v for k,v in q.items() if k not in ('message','phase')}),require_profile=True)
        records=result.get('records') or []
        product_records=[r for r in records if r.get('record_type')=='ProductCandidate']
        promotion_records=[r for r in records if r.get('record_type')=='PromotionCandidate']
        if not records:
            raise RuntimeError('The audited Best Acquisition Technique profile produced zero repository-ready records. No legacy fallback was used; re-run Find Best Tech / Deep Audit.')
        observation_write=persist_acquire(source_id,source.get('url') or '',records,fp)
        emit(68,"frontier","Updating discovery coverage from Best-Technique evidence",records_found=len(records),observations_stored=observation_write.get('stored'))
        urls=[]
        for u in result.get('urls_checked') or []:
            if u and u not in urls:urls.append(u)
        for r in records:
            u=r.get('source_url')
            if u and u not in urls:urls.append(u)
        frontier_add(source_id,urls,source.get('url'))
        product_changes=product_observe(source_id,records)

        emit(76,"repository","Opening Commerce repository")
        con=connect_profile('commerce',create=False)
        try:
            before=_source_snapshot(con,source['name'])
            emit(82,"repository","Repository snapshot captured",before=before)
            emit(86,"repository","Storing records from audited Best Acquisition Technique profile",records_found=len(records),assigned_techniques=assigned)
            stored=ingest_official_result(con,source['name'],{'records':records},sector=result.get('sector') or source.get('domain'),website=source['url'])
            emit(94,"repository","Repository storage completed")
            after=_source_snapshot(con,source['name'])
        finally:con.close()
        c=stored.get('counts') or {}
        rows_added=int(c.get('listing_created') or 0)+int(c.get('price_created') or 0)+int(c.get('promotion_created') or 0)
        metrics={'pages':int(result.get('pages_checked') or 0),'records_found':len(records),'records_stored':rows_added,
          'new_listings':c.get('listing_created',0),'seen_listings':c.get('listing_seen',0),
          'new_price_versions':c.get('price_created',0),'extended_prices':c.get('price_extended',0),
          'new_promotions':c.get('promotion_created',0),'extended_promotions':c.get('promotion_extended',0),
          'entity_matched':c.get('entity_matched',0),'entity_review':c.get('entity_review',0),'entity_created':c.get('entity_created',0),
          'before':before,'after':after,'delta':{k:after[k]-before[k] for k in before},
          'quality_score':qp.get('quality_score'),'records_by_track':{'product_price':len(product_records),'promotion':len(promotion_records)},'frontier':frontier_summary(source_id),
          'pagination_coverage':pagination_coverage(source_id),'product_change_observation':product_changes,
          'product_observation_summary':product_observation_summary(source_id),'observation_store':observation_write,
          'technique_profile':{'source_of_truth':'Best Acquisition Technique(s)','assigned_techniques':assigned,
            'fingerprint':fp,'audited_fingerprint':audited_fp,'assignments':assigned_rows,'tracks':result.get('technique_tracks') or {},'adapter':result.get('adapter'),
            'legacy_fallback_used':False},
          'elapsed_seconds':round(time.time()-t0,2),'diagnostics':result.get('diagnostics',[])}
        emit(98,"accounting","Finalizing change accounting",delta=metrics.get("delta"),records_added=rows_added)
        finish_deep_run(rid,'success',metrics,result={'metrics':metrics,'acquisition':{'adapter':result.get('adapter'),'records':records[:50],'benchmark':result.get('benchmark'),'assigned_techniques':assigned}})
        emit(100,"complete","Deep Acquire & Store completed using audited Best Acquisition Technique profile",records_found=metrics.get("records_found"),records_stored=rows_added,delta=metrics.get("delta"),assigned_techniques=assigned)
        return {'ok':True,'deep_run_id':rid,'source_id':source_id,'metrics':metrics,'stored':stored}
    except InterruptedError as e:
        finish_deep_run(rid,'cancelled',{},str(e));raise
    except Exception as e:
        finish_deep_run(rid,'failed',{},f'{type(e).__name__}: {e}');raise


def approve_for_store(source_id,approved=True):
    return set_quality_approval(source_id,approved=approved)


def set_continuous(source_id,enabled=True,cadence=None):
    qp=quality_profile(source_id) or {}
    if enabled and not (qp.get('audit_passed') and qp.get('approved_for_store')):
        raise PermissionError('Continuous collection requires passed audit and repository-store approval.')
    ap=policy(qp.get('accessibility_level') or 0)
    if enabled and not ap.get('continuous_allowed'):
        raise PermissionError('Continuous collection is not allowed by this Accessibility Level policy.')
    changes={'store_to_repository':bool(enabled)}
    if enabled:changes['max_pages']=min(20,int(ap.get('max_pages_per_run',20) or 20))
    if cadence:changes['cadence']=cadence
    elif enabled:changes['cadence']=ap.get('default_cadence','weekly')
    updated=update_source(source_id,changes)
    profile=set_quality_approval(source_id,continuous=enabled)
    return {'source':updated,'quality_profile':profile}
