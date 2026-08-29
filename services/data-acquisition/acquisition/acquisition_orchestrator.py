from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT/"repository",ROOT/"acquisition"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
from monitoring_registry import normalized_sources,cadence_due
from operations_store import start_run,finish_run,states,create_campaign,campaign_update,campaign_source_update,campaign_get,request_campaign_cancel,now,quality_profile,frontier_add,frontier_next,frontier_mark_acquired,frontier_summary,technique_assignments,save_activity
from actual_acquisition import discover as commerce_discover
from acquisition_quality import quality_report
from repository_engine import connect_profile
from repository_engine import ingest_official_result as ingest_official
from access_policy import policy
from knowledge_repository import add_content,store_analytics,store_intelligence,authority_class
from q_diving_acquisition import acquire_url as q_acquire, source_type_for as q_source_type_for, content_type_for as q_content_type_for
from diving_text_analytics import analyze as q_analyze
from unified_acquisition import acquire as generic_acquire,store_document
from technique_strategy import materialize_for_run,document_from_assigned

def _stored_count(x):
    """New repository analytical rows created by this run, not rows merely observed/extended."""
    if not isinstance(x,dict):return 0
    c=x.get('counts') if isinstance(x.get('counts'),dict) else x
    # Official commerce ingest explicitly differentiates new rows from repeated observations.
    created=sum(int(c.get(k) or 0) for k in ('listing_created','price_created','promotion_created'))
    if created:return created
    for k in ("records_stored","content_items"):
        if isinstance(c.get(k),int):return c[k]
    return 0

def run_source(source,force_store=True):
    rid=start_run(source)
    try:
        if source["registry"]=="commerce":
            qp=quality_profile(source["source_id"]) or {};ap=policy(qp.get("accessibility_level") or (source.get("raw") or {}).get("accessibility_level") or 0)
            page_cap=max(1,min(int(source.get("max_pages",8)),int(ap.get("max_pages_per_run",20) or 20),40))
            frontier=frontier_next(source["source_id"],1) if qp.get("continuous_enabled") else []
            start_url=(frontier[0]["canonical_url"] if frontier else source["url"])
            assigned_rows=technique_assignments(source["source_id"]); assigned=[z.get("technique") for z in assigned_rows if z.get("technique")]
            technique_run=None
            if assigned:
                technique_run=materialize_for_run({**source,"url":start_url},assigned,page_cap,assignment_rows=assigned_rows)
                technique_records=technique_run.get("records") or []
            else: technique_records=[]
            # Technique profile is the preferred acquisition path. Preserve the legacy adapter as a conservative fallback
            # when assigned discovery techniques do not yet materialize repository-ready business facts.
            if technique_records:
                x={"records":technique_records,"pages":[],"adapter":"assigned-technique:"+",".join(assigned)}
            else:
                x=commerce_discover(start_url,page_cap,delay_seconds=ap.get("min_delay_seconds",0))
            links=[]
            for pg in x.get("pages",[]):links.extend(pg.get("links") or [])
            frontier_add(source["source_id"],links,start_url)
            for pg in x.get("pages",[]):frontier_mark_acquired(source["source_id"],pg.get("url"),len(pg.get("records") or []))
            q=quality_report(source["name"],{"records":x["records"]},x["adapter"])
            stored={};storage_gate={"requested":bool(force_store or source.get("store_to_repository")),"approved":False,"stored":False}
            if storage_gate["requested"]:
                qp=quality_profile(source["source_id"]) or {};storage_gate["approved"]=bool(qp.get("audit_passed") and qp.get("approved_for_store"))
                if storage_gate["approved"]:
                    con=connect_profile("commerce",create=False)
                    try:stored=ingest_official(con,source["name"],{"records":x["records"]},sector=x.get("sector") or source.get("domain") or (source.get("raw") or {}).get("sector") or "General",website=source["url"]);storage_gate["stored"]=True
                    finally:con.close()
                else:storage_gate["reason"]="Repository store locked until Deep Audit passes and source is approved for storage."
            n=len(x["records"]);diag={"adapter":x["adapter"],"pages_checked":len(x.get("pages") or []),"quality":q,"frontier":frontier_summary(source["source_id"]),"start_url":start_url,"assigned_techniques":assigned,"technique_profile_applied":bool(assigned),"technique_materialized_records":len(technique_records),"legacy_fallback_used":bool(assigned and not technique_records)}
            added=_stored_count(stored);diag["repository_rows_added"]=added;diag["repository_store_counts"]=(stored.get("counts") if isinstance(stored,dict) else {})
            finish_run(rid,source["source_id"],"success",n,added,diag)
            return {"ok":True,"run_id":rid,"source_id":source["source_id"],"records":n,"stored":stored,"quality":q,"storage_gate":storage_gate,"frontier":frontier_summary(source["source_id"]),"start_url":start_url,"records_added":added,**diag}
        if source["registry"]=="q-diving":
            assigned_rows=technique_assignments(source["source_id"]);assigned=[z.get("technique") for z in assigned_rows if z.get("technique")]
            assigned_doc=None;technique_bench=None
            if assigned:
                assigned_doc,technique_bench=document_from_assigned(source,assigned,min(4,int(source.get("max_pages",3) or 3)))
            if assigned_doc:
                st=q_source_type_for(source["url"]);text=assigned_doc.get("raw_text") or ''
                x={"ok":True,"source_type":st,"content_type":q_content_type_for(st,source["url"]),"title":assigned_doc.get("title"),"source_url":assigned_doc.get("source_url"),"published_at":"","description":"","raw_text":text,"analytics":q_analyze(text),"diagnostics":{"assigned_techniques":assigned,"parser_method":assigned_doc.get("parser_method")}}
            else:x=q_acquire(source["url"])
            con=connect_profile("q-diving",create=False)
            try:
                added=add_content(con,x["source_type"],x["content_type"],x["title"],x["source_url"],x["raw_text"],
                                  published_at=x.get("published_at",""))
                a=store_analytics(con,added["content_id"],x["analytics"])
                intel=store_intelligence(con,added["content_id"],x["raw_text"],x["source_type"],added["authority_class"])
            finally:con.close()
            # One fetched source can create several structured records; the run count is the content item itself.
            finish_run(rid,source["source_id"],"success",1,1,{"analytics":a,"intelligence":intel,"diagnostics":x.get("diagnostics"),"assigned_techniques":assigned,"technique_profile_applied":bool(assigned),"legacy_fallback_used":bool(assigned and not assigned_doc)})
            return {"ok":True,"run_id":rid,"source_id":source["source_id"],"records":1,"records_added":1,"analytics":a,"intelligence":intel,"assigned_techniques":assigned,"technique_profile_applied":bool(assigned),"legacy_fallback_used":bool(assigned and not assigned_doc)}
        assigned_rows=technique_assignments(source["source_id"]);assigned=[z.get("technique") for z in assigned_rows if z.get("technique")]
        assigned_doc=None;technique_bench=None
        if assigned:assigned_doc,technique_bench=document_from_assigned(source,assigned,min(4,int(source.get("max_pages",3) or 3)))
        x=assigned_doc or generic_acquire(source["url"],source.get("domain","general"),source.get("purpose","research_evidence"),source.get("source_type","web"))
        if not x.get("ok"):raise RuntimeError(x.get("error") or "Generic acquisition failed.")
        profile=source.get("profile_id") or "q-diving";con=connect_profile(profile,create=False)
        try:stored=store_document(con,x,profile,discovered_from="monitoring")
        finally:con.close()
        finish_run(rid,source["source_id"],"success",1,1,{"document":stored,"assigned_techniques":assigned,"technique_profile_applied":bool(assigned),"legacy_fallback_used":bool(assigned and not assigned_doc)})
        return {"ok":True,"run_id":rid,"source_id":source["source_id"],"records":1,"records_added":1,"stored":stored,"assigned_techniques":assigned,"technique_profile_applied":bool(assigned),"legacy_fallback_used":bool(assigned and not assigned_doc)}
    except Exception as e:
        finish_run(rid,source["source_id"],"failed",0,0,error=f"{type(e).__name__}: {e}")
        return {"ok":False,"run_id":rid,"source_id":source["source_id"],"error":f"{type(e).__name__}: {e}"}

def select_sources(source_ids=None,due_only=False):
    ids=set(source_ids or []);st=states();out=[]
    for s in normalized_sources():
        if not s.get("enabled"):continue
        if ids and s["source_id"] not in ids:continue
        if due_only and not cadence_due(st.get(s["source_id"],{}).get("last_success_at"),s.get("cadence")):continue
        out.append(s)
    return out

def run_many(source_ids=None,due_only=False,force_store=True):
    xs=select_sources(source_ids,due_only)
    return {"source_count":len(xs),"results":[run_source(s,force_store) for s in xs]}


def start_campaign(source_ids=None,due_only=False,force_store=True):
    import threading,time
    xs=select_sources(source_ids,due_only)
    cid=create_campaign("due" if due_only else ("selected" if source_ids else "all"),xs)
    def worker():
        campaign_update(cid,status="running",message="Acquisition running")
        ok=fail=done=0;cancelled=False
        for s in xs:
            current=campaign_get(cid) or {}
            if current.get('status')=='cancel-requested':
                cancelled=True;break
            sid=s["source_id"];t0=time.time()
            campaign_update(cid,current_source_id=sid,current_source_name=s.get("name"),message=f"Acquiring {s.get('name') or sid}")
            campaign_source_update(cid,sid,status="running",progress_pct=10,phase="starting",started_at=now())
            campaign_source_update(cid,sid,progress_pct=25,phase="fetching")
            result=run_source(s,force_store)
            campaign_source_update(cid,sid,progress_pct=80,phase="validating/storing")
            found=int(result.get("records") or 0);stored=int(result.get("records_added") or 0)
            st=result.get("stored")
            if not stored and isinstance(st,dict):stored=_stored_count(st)
            if result.get("ok"):
                ok+=1;status="success";err=None
            else:
                fail+=1;status="failed";err=result.get("error")
            done+=1
            campaign_source_update(cid,sid,status=status,progress_pct=100,phase="complete" if status=="success" else "failed",
              records_found=found,records_stored=stored,delta_records=stored,finished_at=now(),elapsed_seconds=round(time.time()-t0,2),error=err)
            campaign_update(cid,completed_sources=done,success_sources=ok,failed_sources=fail,message=f"Completed {done}/{len(xs)} sources")
            current=campaign_get(cid) or {}
            if current.get('status')=='cancel-requested':
                cancelled=True;break
        if cancelled:
            campaign_update(cid,status="cancelled",current_source_id=None,current_source_name=None,finished_at=now(),message=f"Cancelled after {done}/{len(xs)} sources")
        else:
            campaign_update(cid,status="completed",current_source_id=None,current_source_name=None,finished_at=now(),message=f"Completed {done}/{len(xs)} sources")
        final=campaign_get(cid) or {};srcrows=final.get('sources') or []
        save_activity('acquisition','Run '+('Due Sources' if due_only else ('Selected Sources' if source_ids else 'All Enabled')),'cancelled' if cancelled else 'completed',
          started_at=final.get('started_at'),finished_at=final.get('finished_at'),source_count=done,success_count=ok,failed_count=fail,
          records_found=sum(int(z.get('records_found') or 0) for z in srcrows),records_added=sum(int(z.get('delta_records') or 0) for z in srcrows),
          summary={'campaign_id':cid,'mode':final.get('mode'),'cancelled':cancelled,'planned_sources':len(xs)},result={'campaign':final})
    threading.Thread(target=worker,name=f"ku2d-acq-{cid[:8]}",daemon=True).start()
    return {"campaign_id":cid,"source_count":len(xs),"status":"queued"}

def cancel_campaign(cid):
    return request_campaign_cancel(cid)

def campaign_status(cid):
    return campaign_get(cid)
