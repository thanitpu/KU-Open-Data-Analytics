from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
_ACQ=Path(__file__).resolve().parents[1]/"acquisition"
if str(_ACQ) not in sys.path: sys.path.insert(0,str(_ACQ))
from diving_knowledge_intelligence import extract_entities,extract_claims,emerging_terms,source_agreement
from repository_engine import now,hid,add_evidence

DIVING_TOPICS=[
 ("Beginner","Diving"),("Process","Diving"),("Training","Diving"),("Safety","Diving"),
 ("Equipment","Diving"),("Dive Site","Diving"),("Travel","Diving"),("Cost","Diving"),
 ("Marine Life","Diving"),("Certification","Diving"),("Problem","Diving"),("Recommendation","Diving"),
 ("Equalization","Diving"),("Mask Fogging","Diving"),("Seasickness","Diving"),("Buoyancy","Diving"),
 ("Air Consumption","Diving")
]
JOURNEY=[
 "Interest","Snorkeling Experience","Discover Scuba","Choose Certification","Choose Dive School",
 "Medical / Prerequisites","Theory","Equipment Orientation","Confined-water Training","Open-water Dive",
 "Dive Briefing","Buddy Check","Entry","Dive","Safety Stop","Exit","Debrief","Certification",
 "Buy / Rent Equipment","Choose Next Dive Destination"
]

def seed_diving_domain(con):
    for name,domain in DIVING_TOPICS:
        tid=hid("topic",domain,name)
        con.execute("INSERT OR IGNORE INTO topic(topic_id,name,domain,status) VALUES(?,?,?,'controlled')",(tid,name,domain))
    for i,name in enumerate(JOURNEY,1):
        sid=hid("step","Diving",i,name)
        con.execute("""INSERT OR IGNORE INTO learning_journey_step(step_id,domain,sequence_no,name,description)
                       VALUES(?,?,?,?,?)""",(sid,"Diving",i,name,""))
    con.commit()

def authority_class(source_type,author=""):
    s=(source_type or "").lower()
    if s in ("padi","ssi","training-organization"):return "official-training-reference"
    if s in ("pantip","community","forum","youtube-comment"):return "community-experience"
    if s in ("youtube","creator-video"):return "creator-content"
    if s in ("dive-shop","operator"):return "commercial-operator"
    if s in ("tourism-authority","official-tourism"):return "official-destination-reference"
    return "unclassified"

def add_content(con,source_type,content_type,title,source_url,raw_text="",author="",channel="",
                published_at="",language="th",segments=None):
    seed_diving_domain(con)
    collected=now()
    ch=hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest()
    cid=hid("content",source_url,ch)
    eid=add_evidence(con,source_url=source_url,source_type=source_type,extraction_method="knowledge-ingest",
                     source_tag="Knowledge",published_at=published_at,collected_at=collected,
                     raw_text=raw_text,raw_json={"title":title,"author":author,"channel":channel})
    con.execute("""INSERT OR IGNORE INTO content_item(content_id,source_type,content_type,title,author,channel,
      source_url,published_at,collected_at,language,authority_class,raw_text,content_hash,evidence_id)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (cid,source_type,content_type,title,author,channel,source_url,published_at,collected,language,
       authority_class(source_type,author),raw_text,ch,eid))
    for i,s in enumerate(segments or []):
        text=s.get("text","")
        sh=hashlib.sha256(text.encode("utf-8")).hexdigest()
        sid=hid("seg",cid,i,sh)
        con.execute("""INSERT OR IGNORE INTO content_segment(segment_id,content_id,segment_index,start_seconds,end_seconds,text,segment_hash)
                       VALUES(?,?,?,?,?,?,?)""",
                    (sid,cid,i,s.get("start_seconds"),s.get("end_seconds"),text,sh))
    con.commit()
    return {"content_id":cid,"evidence_id":eid,"authority_class":authority_class(source_type)}

def knowledge_summary(con):
    tables=["content_item","content_segment","topic","opinion","claim","learning_journey_step",
            "content_journey_link","place","equipment_knowledge"]
    return {t:con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] for t in tables}


def _topic_id(con,name):
    r=con.execute("SELECT topic_id FROM topic WHERE name=? AND domain='Diving'",(name,)).fetchone()
    return r["topic_id"] if r else None

def _step_id(con,name):
    r=con.execute("SELECT step_id FROM learning_journey_step WHERE name=? AND domain='Diving'",(name,)).fetchone()
    return r["step_id"] if r else None

def store_analytics(con,content_id,analytics):
    # Deterministic baseline analytics are stored with explicit method so later LLM/semantic output can coexist.
    for op in analytics.get("opinions",[]):
        stmt=op.get("statement","")
        oid=hid("opinion",content_id,stmt,op.get("opinion_type"))
        topic=op.get("topics",[{}])[0].get("label") if op.get("topics") else None
        tid=_topic_id(con,topic) if topic else None
        con.execute("""INSERT OR IGNORE INTO opinion(opinion_id,content_id,topic_id,statement,sentiment,opinion_type,confidence,evidence_text)
          VALUES(?,?,?,?,?,?,?,?)""",(oid,content_id,tid,stmt,op.get("sentiment"),op.get("opinion_type"),
          op.get("confidence"),stmt))
        for t in op.get("topics",[]):
            tid2=_topic_id(con,t.get("label"))
            if tid2:
                con.execute("""INSERT INTO content_topic(content_id,topic_id,confidence,method) VALUES(?,?,?,?)
                  ON CONFLICT(content_id,topic_id) DO UPDATE SET confidence=MAX(confidence,excluded.confidence)""",
                  (content_id,tid2,t.get("confidence"),"rule-baseline-v1"))
        for j in op.get("journey_steps",[]):
            sid=_step_id(con,j.get("label"))
            if sid:
                con.execute("""INSERT INTO content_journey_link(content_id,step_id,relevance,method) VALUES(?,?,?,?)
                  ON CONFLICT(content_id,step_id) DO UPDATE SET relevance=MAX(relevance,excluded.relevance)""",
                  (content_id,sid,j.get("confidence"),"rule-baseline-v1"))
    con.commit()
    return {"opinions_stored":len(analytics.get("opinions",[])),
            "questions":len(analytics.get("questions",[])),
            "pain_points":len(analytics.get("pain_points",[])),
            "recommendations":len(analytics.get("recommendations",[]))}

def knowledge_dashboard(con):
    summary=knowledge_summary(con)
    topics=[dict(r) for r in con.execute("""SELECT t.name topic,COUNT(*) mentions
      FROM content_topic ct JOIN topic t ON t.topic_id=ct.topic_id GROUP BY t.name ORDER BY mentions DESC,t.name LIMIT 30""").fetchall()]
    journey=[dict(r) for r in con.execute("""SELECT j.sequence_no,j.name step,COUNT(c.content_id) contents
      FROM learning_journey_step j LEFT JOIN content_journey_link c ON c.step_id=j.step_id
      WHERE j.domain='Diving' GROUP BY j.step_id ORDER BY j.sequence_no""").fetchall()]
    opinion_types=[dict(r) for r in con.execute("""SELECT opinion_type,COUNT(*) count FROM opinion
      GROUP BY opinion_type ORDER BY count DESC""").fetchall()]
    sentiment=[dict(r) for r in con.execute("""SELECT sentiment,COUNT(*) count FROM opinion
      GROUP BY sentiment ORDER BY count DESC""").fetchall()]
    sources=[dict(r) for r in con.execute("""SELECT source_type,authority_class,COUNT(*) contents
      FROM content_item GROUP BY source_type,authority_class ORDER BY contents DESC""").fetchall()]
    return {"summary":summary,"topics":topics,"journey":journey,"opinion_types":opinion_types,
            "sentiment":sentiment,"sources":sources}


def store_intelligence(con,content_id,text,source_type,authority):
    entity_map={}
    for e in extract_entities(text):
        norm=re.sub(r"\s+"," ",e["canonical_name"].lower()).strip()
        eid=hid("knowledge-entity",e["entity_type"],norm)
        con.execute("""INSERT OR IGNORE INTO knowledge_entity(entity_id,entity_type,canonical_name,normalized_name,attributes_json,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)""",(eid,e["entity_type"],e["canonical_name"],norm,json.dumps({},ensure_ascii=False),now(),now()))
        mid=hid("mention",content_id,eid,"rule-entity-v1")
        con.execute("""INSERT OR IGNORE INTO entity_mention(mention_id,content_id,entity_id,mention_text,mention_count,confidence,method)
          VALUES(?,?,?,?,?,?,?)""",(mid,content_id,eid,", ".join(e["mentions"][:5]),e["count"],e["confidence"],"rule-entity-v1"))
        entity_map[(e["entity_type"],e["canonical_name"])]=eid
    claims=extract_claims(text,authority)
    for c in claims:
        cid=hid("claim",content_id,c["statement"],",".join(c["claim_types"]))
        con.execute("""INSERT OR IGNORE INTO claim(claim_id,content_id,statement,claim_type,authority_class,confidence,evidence_text)
          VALUES(?,?,?,?,?,?,?)""",(cid,content_id,c["statement"],",".join(c["claim_types"]),authority,c["confidence"],c["statement"]))
        for e in c["entities"]:
            eid=entity_map.get((e["entity_type"],e["canonical_name"]))
            if eid:con.execute("INSERT OR IGNORE INTO claim_entity(claim_id,entity_id) VALUES(?,?)",(cid,eid))
    con.commit()
    return {"entities_stored":len(entity_map),"claims_stored":len(claims)}

def refresh_emerging_topics(con,min_docs=2):
    texts=[r["raw_text"] for r in con.execute("SELECT raw_text FROM content_item WHERE raw_text IS NOT NULL").fetchall()]
    terms=emerging_terms(texts,min_docs=min_docs)
    ts=now()
    for x in terms:
        eid=hid("emerging","Diving",x["term"])
        con.execute("""INSERT INTO emerging_topic(emerging_id,domain,term,document_frequency,status,examples_json,first_seen_at,last_seen_at)
          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(domain,term) DO UPDATE SET
          document_frequency=excluded.document_frequency,examples_json=excluded.examples_json,last_seen_at=excluded.last_seen_at""",
          (eid,"Diving",x["term"],x["document_frequency"],"candidate",json.dumps(x["examples"],ensure_ascii=False),ts,ts))
    con.commit();return terms

def evidence_backed_insights(con,entity_type=None,entity_name=None,limit=50):
    wh=[];args=[]
    if entity_type:wh.append("ke.entity_type=?");args.append(entity_type)
    if entity_name:wh.append("ke.normalized_name=?");args.append(entity_name.lower().strip())
    where=(" WHERE "+" AND ".join(wh)) if wh else ""
    rows=[dict(x) for x in con.execute("""SELECT c.statement,c.claim_type,c.authority_class,c.confidence,
      ci.source_type,ci.source_url,ci.title,ci.published_at,ke.entity_type,ke.canonical_name
      FROM claim c JOIN content_item ci ON ci.content_id=c.content_id
      LEFT JOIN claim_entity ce ON ce.claim_id=c.claim_id LEFT JOIN knowledge_entity ke ON ke.entity_id=ce.entity_id"""
      +where+" ORDER BY c.confidence DESC LIMIT ?",(*args,limit)).fetchall()]
    return {"claims":rows,"agreement":source_agreement(rows)}

def entity_dashboard(con):
    entities=[dict(x) for x in con.execute("""SELECT ke.entity_type,ke.canonical_name,
      SUM(em.mention_count) mentions,COUNT(DISTINCT em.content_id) contents
      FROM knowledge_entity ke JOIN entity_mention em ON em.entity_id=ke.entity_id
      GROUP BY ke.entity_id ORDER BY contents DESC,mentions DESC LIMIT 50""").fetchall()]
    emerging=[dict(x) for x in con.execute("""SELECT term,document_frequency,status,examples_json
      FROM emerging_topic WHERE domain='Diving' ORDER BY document_frequency DESC,term LIMIT 40""").fetchall()]
    return {"entities":entities,"emerging_topics":emerging}
