from __future__ import annotations
import json,sqlite3,hashlib,os
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config"/"acquisition_operations.json"

def cfg():
    return json.loads(CFG.read_text(encoding="utf-8"))
def db_resolution():
    c=cfg(); env_name=c.get("env_override") or "KU2D_OPERATIONS_DB"
    env=os.getenv(env_name," ").strip()
    if env:
        p=Path(env).expanduser(); return {"path":p,"source":"environment","exists":p.is_file(),"configured_path":c.get("operations_db")}
    configured=Path(c.get("operations_db") or "").expanduser()
    if configured.is_file(): return {"path":configured,"source":"configured-external","exists":True,"configured_path":str(configured)}
    fallback=ROOT/(c.get("local_fallback") or "data/ku2d_acquisition_ops.sqlite3")
    return {"path":fallback,"source":"local-fallback","exists":fallback.is_file(),"configured_path":str(configured)}
def db_path():
    return db_resolution()["path"]
def connect():
    p=db_path();p.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(p);con.row_factory=sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS source_run_state(
      source_id TEXT PRIMARY KEY, last_run_at TEXT, last_success_at TEXT, last_status TEXT,
      last_records INTEGER DEFAULT 0, last_stored_records INTEGER DEFAULT 0, total_runs INTEGER DEFAULT 0, total_success INTEGER DEFAULT 0,
      last_error TEXT, consecutive_failures INTEGER DEFAULT 0, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS acquisition_run_log(
      run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, registry TEXT, started_at TEXT NOT NULL,
      finished_at TEXT, status TEXT NOT NULL, records INTEGER DEFAULT 0, stored_records INTEGER DEFAULT 0,
      purpose TEXT, url TEXT, diagnostics_json TEXT, error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_run_source_time ON acquisition_run_log(source_id,started_at);
    CREATE TABLE IF NOT EXISTS exploration_session(
      exploration_id TEXT PRIMARY KEY, mode TEXT NOT NULL, query_text TEXT, url TEXT,
      domain TEXT, purpose TEXT, status TEXT, result_json TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS acquisition_campaign(
      campaign_id TEXT PRIMARY KEY, mode TEXT NOT NULL, status TEXT NOT NULL, total_sources INTEGER DEFAULT 0,
      completed_sources INTEGER DEFAULT 0, success_sources INTEGER DEFAULT 0, failed_sources INTEGER DEFAULT 0,
      current_source_id TEXT, current_source_name TEXT, started_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      finished_at TEXT, message TEXT
    );
    CREATE TABLE IF NOT EXISTS acquisition_campaign_source(
      campaign_id TEXT NOT NULL, source_id TEXT NOT NULL, source_name TEXT, sequence_no INTEGER,
      status TEXT DEFAULT 'queued', progress_pct INTEGER DEFAULT 0, phase TEXT DEFAULT 'queued',
      records_before INTEGER DEFAULT 0, records_found INTEGER DEFAULT 0, records_stored INTEGER DEFAULT 0,
      records_after INTEGER DEFAULT 0, delta_records INTEGER DEFAULT 0, started_at TEXT, finished_at TEXT,
      elapsed_seconds REAL DEFAULT 0, error TEXT, PRIMARY KEY(campaign_id,source_id)
    );
    CREATE INDEX IF NOT EXISTS idx_campaign_status ON acquisition_campaign(status,started_at);
    CREATE TABLE IF NOT EXISTS source_technique_assignment(
      source_id TEXT NOT NULL, technique TEXT NOT NULL, label TEXT, score INTEGER DEFAULT 0, rank_no INTEGER DEFAULT 0,
      assigned INTEGER DEFAULT 1, record_count INTEGER DEFAULT 0, evidence_json TEXT, tested_at TEXT, updated_at TEXT NOT NULL,
      PRIMARY KEY(source_id,technique)
    );
    CREATE INDEX IF NOT EXISTS idx_technique_source ON source_technique_assignment(source_id,assigned,rank_no);
    CREATE TABLE IF NOT EXISTS monitoring_activity_log(
      activity_id TEXT PRIMARY KEY, activity_type TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL,
      started_at TEXT NOT NULL, finished_at TEXT, source_count INTEGER DEFAULT 0, success_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0,
      records_found INTEGER DEFAULT 0, records_added INTEGER DEFAULT 0, summary_json TEXT, result_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_monitor_activity_time ON monitoring_activity_log(started_at);
    """)
    cols={r[1] for r in con.execute("PRAGMA table_info(source_run_state)").fetchall()}
    if "last_completed_at" not in cols:
        con.execute("ALTER TABLE source_run_state ADD COLUMN last_completed_at TEXT")
    if "last_stored_records" not in cols:
        con.execute("ALTER TABLE source_run_state ADD COLUMN last_stored_records INTEGER DEFAULT 0")
    if "consecutive_failures" not in cols:
        con.execute("ALTER TABLE source_run_state ADD COLUMN consecutive_failures INTEGER DEFAULT 0")
    _ensure_quality_tables(con) if "_ensure_quality_tables" in globals() else None
    con.commit();return con

def now():return datetime.now(timezone.utc).isoformat()
def hid(*parts):return hashlib.sha256("|".join(map(str,parts)).encode()).hexdigest()[:24]

def start_run(source):
    con=connect();ts=now();rid=hid("run",source["source_id"],ts)
    con.execute("""INSERT INTO acquisition_run_log(run_id,source_id,registry,started_at,status,purpose,url)
      VALUES(?,?,?,?,?,?,?)""",(rid,source["source_id"],source.get("registry"),ts,"running",source.get("purpose"),source.get("url")))
    con.execute("""INSERT INTO source_run_state(source_id,last_run_at,last_status,total_runs,updated_at)
      VALUES(?,?,?,1,?) ON CONFLICT(source_id) DO UPDATE SET
      last_run_at=excluded.last_run_at,last_status='running',total_runs=source_run_state.total_runs+1,updated_at=excluded.updated_at""",
      (source["source_id"],ts,"running",ts));con.commit();con.close();return rid

def finish_run(run_id,source_id,status,records=0,stored_records=0,diagnostics=None,error=None):
    con=connect();ts=now()
    con.execute("""UPDATE acquisition_run_log SET finished_at=?,status=?,records=?,stored_records=?,
      diagnostics_json=?,error=? WHERE run_id=?""",
      (ts,status,int(records or 0),int(stored_records or 0),json.dumps(diagnostics or {},ensure_ascii=False),error,run_id))
    success=1 if status=="success" else 0
    con.execute("""UPDATE source_run_state SET last_status=?,last_records=?,last_stored_records=?,last_error=?,updated_at=?,last_completed_at=?,
      last_success_at=CASE WHEN ?=1 THEN ? ELSE last_success_at END,
      total_success=total_success+?,
      consecutive_failures=CASE WHEN ?=1 THEN 0 ELSE consecutive_failures+1 END
      WHERE source_id=?""",
      (status,int(records or 0),int(stored_records or 0),error,ts,ts,success,ts,success,success,source_id));con.commit();con.close()

def states():
    con=connect();rows={r["source_id"]:dict(r) for r in con.execute("SELECT * FROM source_run_state").fetchall()};con.close();return rows
def recent_runs(limit=100):
    con=connect();rows=[dict(r) for r in con.execute("SELECT * FROM acquisition_run_log ORDER BY started_at DESC LIMIT ?",(limit,)).fetchall()];con.close();return rows
def save_activity(activity_type,action,status,started_at=None,finished_at=None,source_count=0,success_count=0,failed_count=0,records_found=0,records_added=0,summary=None,result=None,activity_id=None):
    con=connect();started_at=started_at or now();finished_at=finished_at or (now() if status in ('completed','failed','cancelled') else None);activity_id=activity_id or hid('activity',activity_type,action,started_at)
    con.execute("""INSERT OR REPLACE INTO monitoring_activity_log(activity_id,activity_type,action,status,started_at,finished_at,source_count,success_count,failed_count,records_found,records_added,summary_json,result_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(activity_id,activity_type,action,status,started_at,finished_at,int(source_count or 0),int(success_count or 0),int(failed_count or 0),int(records_found or 0),int(records_added or 0),json.dumps(summary or {},ensure_ascii=False),json.dumps(result or {},ensure_ascii=False)))
    con.commit();con.close();return activity_id

def recent_activities(limit=30):
    con=connect();rows=[]
    for r in con.execute("SELECT * FROM monitoring_activity_log ORDER BY started_at DESC LIMIT ?",(int(limit),)).fetchall():
        d=dict(r)
        try:d['summary']=json.loads(d.pop('summary_json') or '{}')
        except:d['summary']={}
        try:d['result']=json.loads(d.pop('result_json') or '{}')
        except:d['result']={}
        rows.append(d)
    con.close();return rows

def save_exploration(mode,payload,result):
    con=connect();ts=now();eid=hid("explore",mode,ts,payload.get("url") or payload.get("query_text") or "")
    con.execute("""INSERT INTO exploration_session(exploration_id,mode,query_text,url,domain,purpose,status,result_json,created_at)
      VALUES(?,?,?,?,?,?,?,?,?)""",(eid,mode,payload.get("query_text"),payload.get("url"),payload.get("domain"),payload.get("purpose"),
      result.get("status","completed"),json.dumps(result,ensure_ascii=False),ts));con.commit();con.close();return eid


def create_campaign(mode,sources):
    con=connect();ts=now();cid=hid("campaign",mode,ts)
    con.execute("""INSERT INTO acquisition_campaign(campaign_id,mode,status,total_sources,started_at,updated_at,message)
      VALUES(?,?,?,?,?,?,?)""",(cid,mode,"queued",len(sources),ts,ts,"Queued"))
    for i,x in enumerate(sources,1):
        con.execute("""INSERT INTO acquisition_campaign_source(campaign_id,source_id,source_name,sequence_no,status,progress_pct,phase)
          VALUES(?,?,?,?,?,?,?)""",(cid,x["source_id"],x.get("name"),i,"queued",0,"queued"))
    con.commit();con.close();return cid

def campaign_update(cid,**changes):
    if not changes:return
    allowed={"status","completed_sources","success_sources","failed_sources","current_source_id","current_source_name",
             "finished_at","message"}
    vals={k:v for k,v in changes.items() if k in allowed};vals["updated_at"]=now()
    con=connect();sql="UPDATE acquisition_campaign SET "+",".join(f"{k}=?" for k in vals)+" WHERE campaign_id=?"
    con.execute(sql,(*vals.values(),cid));con.commit();con.close()

def campaign_source_update(cid,sid,**changes):
    allowed={"status","progress_pct","phase","records_before","records_found","records_stored","records_after","delta_records",
             "started_at","finished_at","elapsed_seconds","error"}
    vals={k:v for k,v in changes.items() if k in allowed}
    if not vals:return
    con=connect();sql="UPDATE acquisition_campaign_source SET "+",".join(f"{k}=?" for k in vals)+" WHERE campaign_id=? AND source_id=?"
    con.execute(sql,(*vals.values(),cid,sid));con.commit();con.close()

def campaign_get(cid):
    con=connect();c=con.execute("SELECT * FROM acquisition_campaign WHERE campaign_id=?",(cid,)).fetchone()
    if not c:con.close();return None
    rows=[dict(r) for r in con.execute("SELECT * FROM acquisition_campaign_source WHERE campaign_id=? ORDER BY sequence_no",(cid,)).fetchall()]
    out=dict(c);out["sources"]=rows;con.close();return out

def request_campaign_cancel(cid):
    x=campaign_get(cid)
    if not x:return None
    if x.get('status') in ('completed','failed','cancelled'):return x
    campaign_update(cid,status='cancel-requested',message='Cancellation requested; stopping after the current source.')
    return campaign_get(cid)

def active_campaign():
    con=connect();r=con.execute("""SELECT campaign_id FROM acquisition_campaign WHERE status IN ('queued','running','cancel-requested')
      ORDER BY started_at DESC LIMIT 1""").fetchone();con.close()
    return campaign_get(r["campaign_id"]) if r else None

def _ensure_quality_tables(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS source_quality_profile(
      source_id TEXT PRIMARY KEY, accessibility_level INTEGER, accessibility_status TEXT,
      verified_access_method TEXT, quality_score REAL, quality_label TEXT, audit_passed INTEGER DEFAULT 0,
      approved_for_store INTEGER DEFAULT 0, continuous_enabled INTEGER DEFAULT 0,
      recommended_cadence TEXT, last_audit_at TEXT, last_audit_json TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS deep_acquisition_run(
      deep_run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, mode TEXT NOT NULL, started_at TEXT NOT NULL,
      finished_at TEXT, status TEXT NOT NULL, pages INTEGER DEFAULT 0, records_found INTEGER DEFAULT 0,
      records_stored INTEGER DEFAULT 0, new_listings INTEGER DEFAULT 0, new_price_versions INTEGER DEFAULT 0,
      extended_prices INTEGER DEFAULT 0, new_promotions INTEGER DEFAULT 0, extended_promotions INTEGER DEFAULT 0,
      quality_score REAL, diagnostics_json TEXT, result_json TEXT, error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_deep_source_time ON deep_acquisition_run(source_id,started_at);
    CREATE TABLE IF NOT EXISTS deep_batch_run(
      batch_id TEXT PRIMARY KEY, mode TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
      total_sources INTEGER DEFAULT 0, completed_sources INTEGER DEFAULT 0, success_sources INTEGER DEFAULT 0,
      failed_sources INTEGER DEFAULT 0, result_json TEXT, error TEXT
    );
    """)
    cols={r['name'] for r in con.execute("PRAGMA table_info(deep_acquisition_run)").fetchall()}
    if 'result_json' not in cols:con.execute("ALTER TABLE deep_acquisition_run ADD COLUMN result_json TEXT")
    con.commit()

def save_quality_audit(source_id,audit):
    con=connect();_ensure_quality_tables(con);ts=now();ac=audit.get('accessibility') or {}
    passed=int(bool(audit.get('audit_passed')))
    con.execute("""INSERT INTO source_quality_profile(source_id,accessibility_level,accessibility_status,verified_access_method,
      quality_score,quality_label,audit_passed,recommended_cadence,last_audit_at,last_audit_json,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
      accessibility_level=excluded.accessibility_level,accessibility_status=excluded.accessibility_status,
      verified_access_method=excluded.verified_access_method,quality_score=excluded.quality_score,
      quality_label=excluded.quality_label,audit_passed=excluded.audit_passed,recommended_cadence=excluded.recommended_cadence,
      last_audit_at=excluded.last_audit_at,last_audit_json=excluded.last_audit_json,updated_at=excluded.updated_at""",
      (source_id,ac.get('proposed_level'), 'verified' if passed else 'audit-needed',ac.get('verified_method'),
       audit.get('quality_score'),audit.get('quality_label'),passed,audit.get('safe_cadence_recommendation'),ts,
       json.dumps(audit,ensure_ascii=False),ts));con.commit();con.close()

def quality_profile(source_id=None):
    con=connect();_ensure_quality_tables(con)
    if source_id:
        r=con.execute('SELECT * FROM source_quality_profile WHERE source_id=?',(source_id,)).fetchone();out=dict(r) if r else None
    else:out=[dict(r) for r in con.execute('SELECT * FROM source_quality_profile ORDER BY updated_at DESC').fetchall()]
    con.close();return out

def set_quality_approval(source_id,approved=None,continuous=None):
    con=connect();_ensure_quality_tables(con);ts=now()
    con.execute('INSERT OR IGNORE INTO source_quality_profile(source_id,updated_at) VALUES(?,?)',(source_id,ts))
    if approved is not None:con.execute('UPDATE source_quality_profile SET approved_for_store=?,updated_at=? WHERE source_id=?',(int(bool(approved)),ts,source_id))
    if continuous is not None:con.execute('UPDATE source_quality_profile SET continuous_enabled=?,updated_at=? WHERE source_id=?',(int(bool(continuous)),ts,source_id))
    con.commit();r=dict(con.execute('SELECT * FROM source_quality_profile WHERE source_id=?',(source_id,)).fetchone());con.close();return r

def start_deep_run(source_id,mode):
    con=connect();_ensure_quality_tables(con);ts=now();rid=hid('deep',source_id,mode,ts)
    con.execute('INSERT INTO deep_acquisition_run(deep_run_id,source_id,mode,started_at,status) VALUES(?,?,?,?,?)',(rid,source_id,mode,ts,'running'));con.commit();con.close();return rid

def finish_deep_run(rid,status,metrics=None,error=None,result=None):
    metrics=metrics or {};con=connect();_ensure_quality_tables(con);ts=now()
    con.execute("""UPDATE deep_acquisition_run SET finished_at=?,status=?,pages=?,records_found=?,records_stored=?,
      new_listings=?,new_price_versions=?,extended_prices=?,new_promotions=?,extended_promotions=?,quality_score=?,diagnostics_json=?,result_json=?,error=?
      WHERE deep_run_id=?""",(ts,status,int(metrics.get('pages') or 0),int(metrics.get('records_found') or 0),int(metrics.get('records_stored') or 0),
      int(metrics.get('new_listings') or 0),int(metrics.get('new_price_versions') or 0),int(metrics.get('extended_prices') or 0),
      int(metrics.get('new_promotions') or 0),int(metrics.get('extended_promotions') or 0),metrics.get('quality_score'),
      json.dumps(metrics.get('diagnostics') or {},ensure_ascii=False),
      json.dumps(result if result is not None else metrics,ensure_ascii=False),error,rid));con.commit();con.close()

def recent_deep_runs(source_id=None,limit=50):
    con=connect();_ensure_quality_tables(con)
    if source_id:rows=con.execute('SELECT * FROM deep_acquisition_run WHERE source_id=? ORDER BY started_at DESC LIMIT ?',(source_id,limit)).fetchall()
    else:rows=con.execute('SELECT * FROM deep_acquisition_run ORDER BY started_at DESC LIMIT ?',(limit,)).fetchall()
    out=[dict(r) for r in rows];con.close();return out

def latest_deep_run(source_id,mode=None):
    con=connect();_ensure_quality_tables(con)
    if mode:r=con.execute("SELECT * FROM deep_acquisition_run WHERE source_id=? AND mode=? ORDER BY started_at DESC LIMIT 1",(source_id,mode)).fetchone()
    else:r=con.execute("SELECT * FROM deep_acquisition_run WHERE source_id=? ORDER BY started_at DESC LIMIT 1",(source_id,)).fetchone()
    out=dict(r) if r else None;con.close()
    if out:
        try:out['result']=json.loads(out.get('result_json') or '{}')
        except:out['result']={}
    return out

def source_stage(source_id):
    q=quality_profile(source_id) or {}
    audit=None
    try:audit=json.loads(q.get('last_audit_json') or '{}') if q else None
    except:audit=None
    store=latest_deep_run(source_id,'store')
    stage='not-audited'
    if audit:stage='audit-passed' if audit.get('audit_passed') else 'audit-failed'
    if q.get('approved_for_store'):stage='approved'
    if store and store.get('status')=='success':stage='acquired'
    elif store and store.get('status')=='failed':stage='acquire-failed'
    return {'source_id':source_id,'stage':stage,'audit':audit,'quality_profile':q,'last_store':store}

def source_stages(source_ids):
    """Bulk-read quality + latest store stages with one Operations DB connection."""
    ids=list(dict.fromkeys([str(x) for x in source_ids if x]))
    if not ids:return {}
    con=connect();_ensure_quality_tables(con)
    marks=",".join("?" for _ in ids)
    qrows={r['source_id']:dict(r) for r in con.execute(
        f"SELECT * FROM source_quality_profile WHERE source_id IN ({marks})",ids).fetchall()}
    # Latest store run per source, avoiding one DB open/query per Monitoring Queue row.
    rrows={}
    for r in con.execute(f"""SELECT d.* FROM deep_acquisition_run d
      JOIN (SELECT source_id,MAX(started_at) mx FROM deep_acquisition_run
            WHERE mode='store' AND source_id IN ({marks}) GROUP BY source_id) x
      ON d.source_id=x.source_id AND d.started_at=x.mx
      WHERE d.mode='store'""",ids).fetchall():
        z=dict(r)
        try:z['result']=json.loads(z.get('result_json') or '{}')
        except:z['result']={}
        rrows[z['source_id']]=z
    con.close()
    out={}
    for sid in ids:
        q=qrows.get(sid,{})
        audit=None
        try:audit=json.loads(q.get('last_audit_json') or '{}') if q else None
        except:audit=None
        store=rrows.get(sid)
        stage='not-audited'
        if audit:stage='audit-passed' if audit.get('audit_passed') else 'audit-failed'
        if q.get('approved_for_store'):stage='approved'
        if store and store.get('status')=='success':stage='acquired'
        elif store and store.get('status')=='failed':stage='acquire-failed'
        out[sid]={'source_id':sid,'stage':stage,'audit':audit,'quality_profile':q or None,'last_store':store}
    return out

def create_deep_batch(mode,source_ids):
    con=connect();_ensure_quality_tables(con);ts=now();bid=hid('batch',mode,ts,*source_ids)
    con.execute("""INSERT INTO deep_batch_run(batch_id,mode,status,started_at,total_sources,result_json)
      VALUES(?,?,?,?,?,?)""",(bid,mode,'running',ts,len(source_ids),json.dumps({'sources':[],'planned_source_ids':list(source_ids)},ensure_ascii=False)))
    con.commit();con.close();return bid

def update_deep_batch(batch_id,status=None,result=None,error=None):
    con=connect();_ensure_quality_tables(con);row=con.execute("SELECT * FROM deep_batch_run WHERE batch_id=?",(batch_id,)).fetchone()
    if not row:con.close();return None
    data=json.loads(row['result_json'] or '{"sources":[]}')
    if result is not None:data=result
    sources=data.get('sources') or [];completed=sum(x.get('status') in ('success','failed','skipped','cancelled') for x in sources)
    success=sum(x.get('status')=='success' for x in sources);failed=sum(x.get('status')=='failed' for x in sources)
    fin=now() if status in ('complete','failed','cancelled') else None
    con.execute("""UPDATE deep_batch_run SET status=COALESCE(?,status),finished_at=COALESCE(?,finished_at),
      completed_sources=?,success_sources=?,failed_sources=?,result_json=?,error=COALESCE(?,error) WHERE batch_id=?""",
      (status,fin,completed,success,failed,json.dumps(data,ensure_ascii=False),error,batch_id));con.commit()
    out=dict(con.execute("SELECT * FROM deep_batch_run WHERE batch_id=?",(batch_id,)).fetchone());con.close();return out

def request_deep_batch_cancel(batch_id):
    x=deep_batch(batch_id)
    if not x:return None
    if x.get('status') in ('complete','failed','cancelled'):return x
    return update_deep_batch(batch_id,status='cancel-requested',result=x.get('result') or {'sources':[]})

def deep_batch(batch_id):
    con=connect();_ensure_quality_tables(con);r=con.execute("SELECT * FROM deep_batch_run WHERE batch_id=?",(batch_id,)).fetchone()
    out=dict(r) if r else None;con.close()
    if out:
        try:out['result']=json.loads(out.get('result_json') or '{}')
        except:out['result']={}
    return out

def _ensure_frontier(con):
    # Legacy-safe migration: create base table, add missing columns, then indexes.
    con.execute("""CREATE TABLE IF NOT EXISTS source_url_frontier(
      source_id TEXT NOT NULL, canonical_url TEXT NOT NULL, discovered_from TEXT, url_type TEXT,
      status TEXT DEFAULT 'pending', first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
      last_acquired_at TEXT, acquire_count INTEGER DEFAULT 0, last_record_count INTEGER DEFAULT 0,
      pagination_group TEXT, page_number INTEGER, detected_total_pages INTEGER,
      last_content_hash TEXT, last_checked_at TEXT, last_changed_at TEXT,
      change_count INTEGER DEFAULT 0, unchanged_count INTEGER DEFAULT 0,
      last_http_status INTEGER, failure_count INTEGER DEFAULT 0,
      PRIMARY KEY(source_id,canonical_url)
    )""")
    cols={r['name'] for r in con.execute("PRAGMA table_info(source_url_frontier)").fetchall()}
    adds={
      'pagination_group':'TEXT','page_number':'INTEGER','detected_total_pages':'INTEGER',
      'last_content_hash':'TEXT','last_checked_at':'TEXT','last_changed_at':'TEXT',
      'change_count':'INTEGER DEFAULT 0','unchanged_count':'INTEGER DEFAULT 0',
      'last_http_status':'INTEGER','failure_count':'INTEGER DEFAULT 0'}
    for name,typ in adds.items():
        if name not in cols:con.execute(f"ALTER TABLE source_url_frontier ADD COLUMN {name} {typ}")
    con.executescript("""
    CREATE INDEX IF NOT EXISTS idx_frontier_source_status ON source_url_frontier(source_id,status,last_acquired_at);
    CREATE INDEX IF NOT EXISTS idx_frontier_pagination ON source_url_frontier(source_id,pagination_group,page_number);
    CREATE TABLE IF NOT EXISTS product_observation_index(
      source_id TEXT NOT NULL, product_key TEXT NOT NULL, product_name TEXT,
      first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
      last_price REAL, previous_price REAL, price_change_count INTEGER DEFAULT 0,
      surface_count INTEGER DEFAULT 0, surfaces_json TEXT DEFAULT '[]',
      last_source_url TEXT, last_observed_at TEXT,
      PRIMARY KEY(source_id,product_key)
    );
    CREATE INDEX IF NOT EXISTS idx_product_obs_source ON product_observation_index(source_id,last_seen_at);
    """)
    con.commit()

def canonical_url(url):
    from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
    try:
        x=urlsplit(url);drop={'utm_source','utm_medium','utm_campaign','utm_term','utm_content','fbclid','gclid','srsltid'}
        q=[(k,v) for k,v in parse_qsl(x.query,keep_blank_values=True) if k.lower() not in drop]
        return urlunsplit((x.scheme.lower(),x.netloc.lower(),x.path.rstrip('/') or '/',urlencode(q),''))
    except:return str(url).split('#')[0]

def frontier_add(source_id,urls,discovered_from=None):
    con=connect();_ensure_frontier(con);ts=now();n=0
    for item in urls:
        meta=item if isinstance(item,dict) else {"url":item}
        u=canonical_url(meta.get('url'))
        if not u:continue
        typ=meta.get('url_type') or ('promotion' if any(k in u.lower() for k in ('promo','promotion','campaign')) else 'product' if 'product' in u.lower() else 'category' if any(k in u.lower() for k in ('category','grocery','fresh','beverage','household')) else 'other')
        con.execute("""INSERT INTO source_url_frontier(source_id,canonical_url,discovered_from,url_type,status,first_seen_at,last_seen_at,
          pagination_group,page_number,detected_total_pages)
          VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id,canonical_url) DO UPDATE SET
          last_seen_at=excluded.last_seen_at,
          pagination_group=COALESCE(excluded.pagination_group,source_url_frontier.pagination_group),
          page_number=COALESCE(excluded.page_number,source_url_frontier.page_number),
          detected_total_pages=MAX(COALESCE(source_url_frontier.detected_total_pages,0),COALESCE(excluded.detected_total_pages,0))""",
          (source_id,u,discovered_from,typ,'pending',ts,ts,meta.get('pagination_group'),meta.get('page_number'),meta.get('detected_total_pages')));n+=1
    con.commit();con.close();return n

def frontier_next(source_id,limit=1):
    con=connect();_ensure_frontier(con)
    rows=[dict(r) for r in con.execute("""SELECT * FROM source_url_frontier WHERE source_id=? AND status IN ('pending','active')
      ORDER BY CASE WHEN last_acquired_at IS NULL THEN 0 ELSE 1 END,last_acquired_at,first_seen_at LIMIT ?""",(source_id,limit)).fetchall()]
    con.close();return rows

def frontier_mark_acquired(source_id,url,records=0):
    con=connect();_ensure_frontier(con);ts=now();u=canonical_url(url)
    con.execute("""UPDATE source_url_frontier SET status='active',last_acquired_at=?,acquire_count=acquire_count+1,last_record_count=?
      WHERE source_id=? AND canonical_url=?""",(ts,int(records or 0),source_id,u));con.commit();con.close()

def frontier_summary(source_id):
    con=connect();_ensure_frontier(con)
    rows=con.execute('SELECT status,COUNT(*) c FROM source_url_frontier WHERE source_id=? GROUP BY status',(source_id,)).fetchall()
    out={r['status']:r['c'] for r in rows};out['total']=sum(out.values());con.close();return out

def frontier_mark_observation(source_id,url,content_hash=None,http_status=200,records=0,pagination_group=None,page_number=None,detected_total_pages=None,acquired=True):
    con=connect();_ensure_frontier(con);ts=now();u=canonical_url(url)
    row=con.execute('SELECT last_content_hash FROM source_url_frontier WHERE source_id=? AND canonical_url=?',(source_id,u)).fetchone()
    if not row:
        frontier_row=(source_id,u,None,'other','active',ts,ts,pagination_group,page_number,detected_total_pages)
        con.execute("""INSERT OR IGNORE INTO source_url_frontier(source_id,canonical_url,discovered_from,url_type,status,first_seen_at,last_seen_at,
          pagination_group,page_number,detected_total_pages) VALUES(?,?,?,?,?,?,?,?,?,?)""",frontier_row)
        old_hash=None
    else:old_hash=row['last_content_hash']
    changed=bool(old_hash and content_hash and old_hash!=content_hash)
    unchanged=bool(old_hash and content_hash and old_hash==content_hash)
    con.execute("""UPDATE source_url_frontier SET status='active',last_seen_at=?,last_checked_at=?,
      last_acquired_at=CASE WHEN ? THEN ? ELSE last_acquired_at END,
      acquire_count=acquire_count+?,last_record_count=CASE WHEN ? THEN ? ELSE last_record_count END,last_http_status=?,failure_count=0,
      last_content_hash=COALESCE(?,last_content_hash),
      last_changed_at=CASE WHEN ? THEN ? ELSE last_changed_at END,
      change_count=change_count+?,unchanged_count=unchanged_count+?,
      pagination_group=COALESCE(?,pagination_group),page_number=COALESCE(?,page_number),
      detected_total_pages=MAX(COALESCE(detected_total_pages,0),COALESCE(?,0))
      WHERE source_id=? AND canonical_url=?""",
      (ts,ts,int(bool(acquired)),ts,int(bool(acquired)),int(bool(acquired)),int(records or 0),int(http_status or 0),content_hash,
       int(changed),ts,int(changed),int(unchanged),pagination_group,page_number,detected_total_pages,source_id,u))
    con.commit();con.close()
    return {'baseline':not bool(old_hash),'changed':changed,'unchanged':unchanged,'old_hash':old_hash,'new_hash':content_hash}

def frontier_mark_check_failure(source_id,url,http_status=0):
    con=connect();_ensure_frontier(con);ts=now();u=canonical_url(url)
    con.execute("""UPDATE source_url_frontier SET last_checked_at=?,last_http_status=?,failure_count=failure_count+1
      WHERE source_id=? AND canonical_url=?""",(ts,int(http_status or 0),source_id,u));con.commit();con.close()

def pagination_coverage(source_id):
    con=connect();_ensure_frontier(con)
    rows=[dict(r) for r in con.execute("""SELECT pagination_group,page_number,detected_total_pages,status,last_acquired_at
      FROM source_url_frontier WHERE source_id=? AND pagination_group IS NOT NULL
      ORDER BY pagination_group,page_number""",(source_id,)).fetchall()]
    groups={}
    for r in rows:
        g=groups.setdefault(r['pagination_group'],{'pagination_group':r['pagination_group'],'known_pages':set(),'fetched_pages':set(),'detected_total_pages':0})
        if r.get('page_number'):g['known_pages'].add(int(r['page_number']))
        if r.get('page_number') and r.get('last_acquired_at'):g['fetched_pages'].add(int(r['page_number']))
        g['detected_total_pages']=max(g['detected_total_pages'],int(r.get('detected_total_pages') or 0))
    out=[]
    for g in groups.values():
        total=g['detected_total_pages'] or None
        known=sorted(g['known_pages']);fetched=sorted(g['fetched_pages'])
        missing=sorted(set(range(1,total+1))-set(fetched)) if total else []
        out.append({'pagination_group':g['pagination_group'],'detected_total_pages':total,
                    'known_pages':len(known),'fetched_pages':len(fetched),'missing_pages':missing,
                    'coverage_pct':round(100*len(fetched)/total,1) if total else None,
                    'completeness':'verified' if total and len(fetched)>=total and not missing else 'partial' if total else 'unverified'})
    con.close()
    totals={'groups':len(out),'groups_verified':sum(x['completeness']=='verified' for x in out),
            'known_pages':sum(x['known_pages'] for x in out),'fetched_pages':sum(x['fetched_pages'] for x in out),
            'detected_total_pages':sum(x['detected_total_pages'] or 0 for x in out)}
    return {'summary':totals,'groups':out}

def product_observe(source_id,records):
    import hashlib
    con=connect();_ensure_frontier(con);ts=now();stats={'products_seen':0,'new_products':0,'price_changes':0,'unchanged_prices':0}
    for r in records or []:
        if r.get('record_type')!='ProductCandidate':continue
        name=str(r.get('product_name') or '').strip()
        if not name:continue
        key=str(r.get('product_id') or r.get('sku') or r.get('gtin') or hashlib.sha1(' '.join(name.lower().split()).encode()).hexdigest()[:20])
        price=r.get('price');url=canonical_url(r.get('source_url') or '')
        row=con.execute('SELECT * FROM product_observation_index WHERE source_id=? AND product_key=?',(source_id,key)).fetchone()
        stats['products_seen']+=1
        if not row:
            surfaces=[url] if url else []
            con.execute("""INSERT INTO product_observation_index(source_id,product_key,product_name,first_seen_at,last_seen_at,last_price,
              surface_count,surfaces_json,last_source_url,last_observed_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (source_id,key,name,ts,ts,price,len(surfaces),json.dumps(surfaces),url,ts));stats['new_products']+=1
        else:
            old=row['last_price'];changed=old is not None and price is not None and float(old)!=float(price)
            surfaces=set(json.loads(row['surfaces_json'] or '[]'))
            if url:surfaces.add(url)
            if changed:stats['price_changes']+=1
            elif old is not None and price is not None:stats['unchanged_prices']+=1
            con.execute("""UPDATE product_observation_index SET product_name=?,last_seen_at=?,previous_price=CASE WHEN ? THEN last_price ELSE previous_price END,
              last_price=COALESCE(?,last_price),price_change_count=price_change_count+?,surface_count=?,surfaces_json=?,
              last_source_url=?,last_observed_at=? WHERE source_id=? AND product_key=?""",
              (name,ts,int(changed),price,int(changed),len(surfaces),json.dumps(sorted(surfaces)),url,ts,source_id,key))
    con.commit();con.close();return stats

def product_observation_summary(source_id,limit=20):
    con=connect();_ensure_frontier(con)
    total=con.execute('SELECT COUNT(*) c FROM product_observation_index WHERE source_id=?',(source_id,)).fetchone()['c']
    changes=con.execute('SELECT COALESCE(SUM(price_change_count),0) c FROM product_observation_index WHERE source_id=?',(source_id,)).fetchone()['c']
    multi=con.execute('SELECT COUNT(*) c FROM product_observation_index WHERE source_id=? AND surface_count>1',(source_id,)).fetchone()['c']
    rows=[dict(r) for r in con.execute("""SELECT product_key,product_name,last_price,previous_price,price_change_count,surface_count,last_source_url,last_observed_at
      FROM product_observation_index WHERE source_id=? ORDER BY price_change_count DESC,last_observed_at DESC LIMIT ?""",(source_id,int(limit))).fetchall()]
    con.close();return {'total_products':total,'total_price_changes':changes,'multi_surface_products':multi,'recent':rows}

def replace_technique_assignments(source_id,recommendations):
    con=connect();ts=now();_ensure_quality_tables(con)
    old_rows=con.execute("SELECT technique,evidence_json FROM source_technique_assignment WHERE source_id=? AND assigned=1 ORDER BY rank_no,score DESC",(source_id,)).fetchall()
    old=[r['technique'] for r in old_rows]
    def _profile_sig(technique,evidence):
        try:ev=json.loads(evidence or '{}') if isinstance(evidence,str) else (evidence or {})
        except:ev={}
        op=((ev.get('potential') or {}).get('operational_config') or ev.get('operational_config') or {})
        stable_op=tuple((k,str(op.get(k))) for k in ('batch_endpoint','search_endpoint','seller_id','max_batch_size','catalog_url','category_urls','page_size','pagination_param','commerce_surface','official_related_domain','official_domain','graphql_endpoint','graphql_operation','graphql_query_hash','identity_source') if op.get(k) is not None)
        return (technique,tuple(ev.get('tracks') or []),str(ev.get('engine_version') or ''),stable_op)
    old_sig=[_profile_sig(r['technique'],r['evidence_json']) for r in old_rows]
    new_keys=[x.get('technique') for x in (recommendations or []) if x.get('technique')]
    new_sig=[_profile_sig(x.get('technique'),x) for x in (recommendations or []) if x.get('technique')]
    changed=(old!=new_keys or old_sig!=new_sig)
    con.execute("DELETE FROM source_technique_assignment WHERE source_id=?",(source_id,))
    for i,x in enumerate(recommendations or [],1):
        if not x.get('technique'):continue
        con.execute("""INSERT INTO source_technique_assignment(source_id,technique,label,score,rank_no,assigned,record_count,evidence_json,tested_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",(source_id,x.get('technique'),x.get('label'),int(x.get('score') or 0),i,1,int(x.get('record_count') or 0),json.dumps(x,ensure_ascii=False),ts,ts))
    # Best-Technique profile is part of the audit contract.  If its ordered profile changes,
    # prior audit/store approval is stale and must not authorize a different extraction method.
    if changed:
        con.execute("""UPDATE source_quality_profile SET audit_passed=0,approved_for_store=0,continuous_enabled=0,
          accessibility_status='audit-needed',quality_score=NULL,quality_label='stale-technique-profile',updated_at=? WHERE source_id=?""",(ts,source_id))
    con.commit();con.close();return technique_assignments(source_id)

def technique_assignments(source_id=None):
    con=connect();args=();q="SELECT * FROM source_technique_assignment WHERE assigned=1"
    if source_id:q+=" AND source_id=?";args=(source_id,)
    q+=" ORDER BY source_id,rank_no,score DESC"
    rows=[]
    for r in con.execute(q,args).fetchall():
        d=dict(r)
        try:d['evidence']=json.loads(d.pop('evidence_json') or '{}')
        except:d['evidence']={}
        rows.append(d)
    con.close();return rows

def technique_assignment_map():
    out={}
    for x in technique_assignments():out.setdefault(x['source_id'],[]).append(x)
    return out
