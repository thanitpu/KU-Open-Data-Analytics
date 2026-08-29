from __future__ import annotations
import json
from repository_engine import hid,now

def save_discovery(con,claim_text,claim_type,result,verification_claim_id=None):
    rid=hid("evidence-search-run",claim_text,claim_type,now())
    con.execute("""INSERT INTO evidence_search_run(search_run_id,verification_claim_id,claim_text,claim_type,
      query_plan_json,candidate_count,bias_guard_pass,diagnostics_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
      (rid,verification_claim_id,claim_text,claim_type,json.dumps(result.get("plan",[]),ensure_ascii=False),
       len(result.get("candidates",[])),1 if result.get("bias_check",{}).get("bias_guard_pass") else 0,
       json.dumps(result.get("diagnostics",[]),ensure_ascii=False),now()))
    for x in result.get("candidates",[]):
        cid=hid("evidence-candidate",rid,x.get("link"))
        con.execute("""INSERT OR IGNORE INTO evidence_candidate_url(candidate_id,search_run_id,url,title,snippet,source_family,
          found_by_stances_json,found_by_queries_json,acquisition_status) VALUES(?,?,?,?,?,?,?,?,?)""",
          (cid,rid,x.get("link"),x.get("title"),x.get("snippet"),x.get("source_family"),
           json.dumps(x.get("found_by_stances",[]),ensure_ascii=False),
           json.dumps(x.get("found_by_queries",[]),ensure_ascii=False),"discovered"))
    con.commit();return rid

def recent_runs(con,limit=20):
    return [dict(x) for x in con.execute("""SELECT search_run_id,claim_text,claim_type,candidate_count,bias_guard_pass,created_at
      FROM evidence_search_run ORDER BY created_at DESC LIMIT ?""",(limit,)).fetchall()]

def run_candidates(con,search_run_id):
    return [dict(x) for x in con.execute("""SELECT url,title,snippet,source_family,found_by_stances_json,
      acquisition_status FROM evidence_candidate_url WHERE search_run_id=? ORDER BY source_family,title""",(search_run_id,)).fetchall()]
