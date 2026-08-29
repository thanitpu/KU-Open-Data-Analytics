from __future__ import annotations
import re
from evidence_verification_engine import similarity,classify_stance,register_claim
from repository_engine import hid

def passages(text,min_chars=35,max_chars=700):
    raw=[re.sub(r"\s+"," ",x).strip() for x in re.split(r"(?<=[.!?])\s+|\n+",text or "")]
    out=[];buf=""
    for x in raw:
        if not x:continue
        if len(buf)+len(x)+1<=max_chars:buf=(buf+" "+x).strip()
        else:
            if len(buf)>=min_chars:out.append(buf)
            buf=x
    if len(buf)>=min_chars:out.append(buf)
    return out

def verify_document_passages(con,acquired_document_id,claim_text,claim_type="general",top_k=12):
    row=con.execute("SELECT * FROM acquired_document WHERE acquired_document_id=?",(acquired_document_id,)).fetchone()
    if not row:raise KeyError(acquired_document_id)
    row=dict(row);vcid=register_claim(con,claim_text,claim_type)
    ranked=[]
    for i,p in enumerate(passages(row.get("raw_text",""))):
        rel=similarity(claim_text,p)
        if rel<.04:continue
        stance,conf=classify_stance(claim_text,p)
        ranked.append({"passage_index":i,"passage_text":p,"relevance":round(rel,3),
                       "stance":stance,"stance_confidence":conf})
    ranked.sort(key=lambda x:(-x["relevance"],-x["stance_confidence"]))
    selected=ranked[:max(1,min(top_k,50))]
    for x in selected:
        pid=hid("evidence-passage",acquired_document_id,vcid,x["passage_index"])
        con.execute("""INSERT OR REPLACE INTO evidence_passage(passage_id,acquired_document_id,verification_claim_id,
          passage_index,passage_text,relevance,stance,stance_confidence,method,char_start,char_end)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (pid,acquired_document_id,vcid,x["passage_index"],x["passage_text"],x["relevance"],x["stance"],
           x["stance_confidence"],"lexical-passage-v1",None,None))
    con.commit()
    counts={s:sum(x["stance"]==s for x in selected) for s in ("support","against","neutral")}
    return {"verification_claim_id":vcid,"acquired_document_id":acquired_document_id,
            "selected_passages":selected,"stance_counts":counts,
            "note":"Passage stance is baseline lexical classification; source provenance is retained at document level."}
