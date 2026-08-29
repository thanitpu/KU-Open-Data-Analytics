from __future__ import annotations
import json,re
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlparse
from acquisition_progress_dashboard import monitor_registry_summary

ROOT=Path(__file__).resolve().parents[1]

def _targets():
    return json.loads((ROOT/"config"/"acquisition_targets.json").read_text(encoding="utf-8"))

def _host(url):
    try:return urlparse(url or "").netloc.lower().removeprefix("www.")
    except:return ""

def _target_for(source):
    c=_targets();d=c["default"];x={"minimum":d["minimum_usable_records_per_source"],
      "target":d["target_usable_records_per_source"],"maximum":d["maximum_usable_records_per_source"]}
    for r in c.get("rules",[]):
        if all(source.get(k)==v for k,v in r.get("match",{}).items()):
            x={"minimum":r["minimum"],"target":r["target"],"maximum":r["maximum"]};break
    return x

def _exists(con,t):
    return bool(con.execute("select 1 from sqlite_master where type='table' and name=?",(t,)).fetchone())

def _count_url_host(con,table,url_col,host):
    if not host or not _exists(con,table):return 0
    return int(con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE lower("{url_col}") LIKE ?',
                           (f"%{host}%",)).fetchone()[0])

def _latest_url_host(con,table,url_col,time_col,host):
    if not host or not _exists(con,table):return None
    r=con.execute(f'SELECT MAX("{time_col}") FROM "{table}" WHERE lower("{url_col}") LIKE ?',
                  (f"%{host}%",)).fetchone()
    return r[0] if r else None

def _parse_dt(x):
    if not x:return None
    try:
        d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except:return None

def freshness(latest,cadence):
    dt=_parse_dt(latest)
    if not dt:return {"state":"never-seen","age_days":None,"overdue":True}
    age=(datetime.now(timezone.utc)-dt).total_seconds()/86400
    limits={"daily":1.5,"weekly":8,"monthly":35,"quarterly":100}
    lim=limits.get((cadence or "").lower(),14)
    return {"state":"fresh" if age<=lim else "overdue","age_days":round(age,1),"overdue":age>lim}

def source_observed_records(con,source):
    host=_host(source.get("url"))
    # Count traceable structured observations. These are intentionally not summed across derived tables
    # that represent the same observation many times.
    evidence=_count_url_host(con,"evidence","source_url",host)
    content=_count_url_host(con,"content_item","source_url",host)
    listings=_count_url_host(con,"listing","source_url",host)
    docs=_count_url_host(con,"acquired_document","source_url",host)
    candidates=[evidence,content,listings,docs]
    # Use the strongest source-level unit count, rather than double-counting the same material downstream.
    observed=max(candidates) if candidates else 0
    latest=max([x for x in [
      _latest_url_host(con,"evidence","source_url","collected_at",host),
      _latest_url_host(con,"content_item","source_url","collected_at",host),
      _latest_url_host(con,"listing","source_url","last_seen_at",host),
      _latest_url_host(con,"acquired_document","source_url","fetched_at",host)] if x] or [None])
    return {"observed_usable_records":observed,"raw_counts":{"evidence":evidence,"content":content,"listings":listings,"acquired_documents":docs},
            "latest_seen_at":latest}

def health_for_sources(connections):
    monitors=monitor_registry_summary()["sources"];rows=[]
    for s in monitors:
        best={"observed_usable_records":0,"raw_counts":{},"latest_seen_at":None};best_profile=None
        for pid,con in connections:
            x=source_observed_records(con,s)
            if x["observed_usable_records"]>best["observed_usable_records"] or (not best["latest_seen_at"] and x["latest_seen_at"]):
                best=x;best_profile=pid
        tgt=_target_for(s);n=best["observed_usable_records"];gap=max(0,tgt["target"]-n)
        if n>=tgt["maximum"]:qstate="cap-reached"
        elif n>=tgt["target"]:qstate="target-met"
        elif n>=tgt["minimum"]:qstate="minimum-met"
        elif n>0:qstate="below-minimum"
        else:qstate="empty"
        fr=freshness(best["latest_seen_at"],s.get("cadence"))
        priority=(3 if qstate in {"empty","below-minimum"} else 0)+(2 if fr["overdue"] else 0)+(1 if s.get("enabled") else 0)
        rows.append({**s,**best,"profile_id":best_profile,"quota":tgt,"gap_to_target":gap,"quota_state":qstate,
                     "freshness":fr,"priority_score":priority})
    rows.sort(key=lambda x:(-x["priority_score"],-x["gap_to_target"],x.get("domain",""),x.get("name","") or ""))
    summary={"sources":len(rows),"target_met":sum(x["quota_state"] in {"target-met","cap-reached"} for x in rows),
      "minimum_met":sum(x["quota_state"] in {"minimum-met","target-met","cap-reached"} for x in rows),
      "below_minimum":sum(x["quota_state"] in {"empty","below-minimum"} for x in rows),
      "overdue":sum(x["freshness"]["overdue"] for x in rows),
      "total_gap_to_target":sum(x["gap_to_target"] for x in rows)}
    return {"summary":summary,"sources":rows}

def bulk_fill_plan(connections,limit=None):
    h=health_for_sources(connections)
    tasks=[]
    for x in h["sources"]:
        if not x.get("enabled") or x["gap_to_target"]<=0:continue
        tasks.append({"source_id":x.get("source_id"),"name":x.get("name"),"domain":x.get("domain"),"channel":x.get("channel"),
          "url":x.get("url"),"current_records":x["observed_usable_records"],"minimum":x["quota"]["minimum"],
          "target":x["quota"]["target"],"maximum":x["quota"]["maximum"],"records_needed":x["gap_to_target"],
          "cadence":x.get("cadence"),"freshness_state":x["freshness"]["state"],"priority_score":x["priority_score"],
          "instruction":"Acquire real source-traceable records only; stop at maximum quota and record constraints rather than fabricating data."})
    tasks.sort(key=lambda x:(-x["priority_score"],-x["records_needed"]))
    if limit:tasks=tasks[:limit]
    return {"target_policy":_targets(),"task_count":len(tasks),"estimated_records_needed":sum(x["records_needed"] for x in tasks),
            "tasks":tasks}
