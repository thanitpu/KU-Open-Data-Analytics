from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import sqlite3,json,hashlib,re,csv

ROOT=Path(__file__).resolve().parents[1]
APP_CONFIG=ROOT/"config/repository_config.json"
DEFAULT_DB=None
SCHEMA=Path(__file__).resolve().parent/"schema.sql"
SCHEMA_VERSION="ku2d-commerce-promotion-evidence-v1"

def now(): return datetime.now(timezone.utc).isoformat()
def norm(x): return re.sub(r"\s+"," ",str(x or "").strip().lower())
def hid(prefix,*parts):
    raw="|".join(norm(x) for x in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode()).hexdigest()[:18]}"
def fp(obj):
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def load_repository_config():
    if not APP_CONFIG.exists(): return {}
    try:return json.loads(APP_CONFIG.read_text(encoding="utf-8"))
    except:return {}
def configured_repository_path():
    p=load_repository_config().get("active_repository_path")
    return Path(p).expanduser() if p else None
def connect(path=None,create=False):
    explicit=path is not None
    p=Path(path).expanduser() if explicit else configured_repository_path()
    if p is None: raise FileNotFoundError("No repository is configured. Select or create a repository first.")
    # Read/open operations must never silently create an empty repository.
    # Creation is permitted only when the caller explicitly passes create=True.
    if not p.exists() and not create:
        raise FileNotFoundError(f"Repository not found: {p}")
    if create: p.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(p);con.row_factory=sqlite3.Row;con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("INSERT OR IGNORE INTO schema_meta VALUES(?,?)",(SCHEMA_VERSION,now()));con.commit()
    return con

def upsert_business(con,name,sector=None,website=None):
    bid=hid("biz",name);ts=now()
    con.execute("""INSERT INTO business VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(business_id) DO UPDATE SET name=excluded.name,sector=COALESCE(excluded.sector,business.sector),
      website=COALESCE(excluded.website,business.website),updated_at=excluded.updated_at""",
      (bid,name,norm(name),sector,website,ts,ts));con.commit();return bid

def add_evidence(con,business_id=None,source_url="",source_image="",source_document="",source_type="official",
                 extraction_method="",source_tag="",published_at="",collected_at=None,raw_text="",raw_json=None,confidence=None):
    collected_at=collected_at or now()
    rawj=json.dumps(raw_json,ensure_ascii=False,sort_keys=True) if raw_json is not None else ""
    ch=hashlib.sha256((raw_text+"\n"+rawj).encode()).hexdigest()
    eid=hid("ev",ch,source_url,extraction_method)
    con.execute("""INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (eid,business_id,source_url,source_image,source_document,source_type,extraction_method,source_tag,published_at,
       collected_at,ch,raw_text,rawj,confidence,SCHEMA_VERSION));con.commit();return eid

def upsert_product(con,name,brand="",category="",product_type="",variant_key="",gtin="",manufacturer_sku="",attributes=None):
    pid=hid("cp",brand,name,variant_key,gtin,manufacturer_sku);ts=now()
    con.execute("""INSERT INTO canonical_product VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(canonical_product_id) DO UPDATE SET canonical_name=excluded.canonical_name,category=excluded.category,
      product_type=excluded.product_type,attributes_json=excluded.attributes_json,updated_at=excluded.updated_at""",
      (pid,name,brand,name,category,product_type,variant_key,gtin,manufacturer_sku,
       json.dumps(attributes or {},ensure_ascii=False,sort_keys=True),ts,ts));con.commit();return pid

def add_resolution(con,canonical_product_id,raw_name,business_id=None,platform="",raw_sku="",source_url="",
                   match_method="manual",match_score=1.0,match_status="confirmed",attributes=None):
    rid=hid("res",canonical_product_id,business_id,platform,raw_name,raw_sku)
    con.execute("""INSERT OR REPLACE INTO entity_resolution_map VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (rid,canonical_product_id,business_id,platform,raw_name,norm(raw_name),raw_sku,source_url,match_method,match_score,
       match_status,json.dumps(attributes or {},ensure_ascii=False),now()));con.commit();return rid

def upsert_listing(con,business_id,raw_name,source_url,canonical_product_id=None,platform="official",
                   seller_name="",raw_sku="",variant_text="",channel_scope="",location_scope="",observed_at=None):
    observed_at=observed_at or now();lid=hid("lst",business_id,platform,source_url)
    con.execute("""INSERT INTO listing VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1)
      ON CONFLICT(business_id,platform,source_url) DO UPDATE SET
      canonical_product_id=COALESCE(excluded.canonical_product_id,listing.canonical_product_id),
      raw_name=excluded.raw_name,raw_sku=excluded.raw_sku,variant_text=excluded.variant_text,
      channel_scope=excluded.channel_scope,location_scope=excluded.location_scope,last_seen_at=excluded.last_seen_at,active=1""",
      (lid,business_id,canonical_product_id,platform,seller_name,raw_name,raw_sku,variant_text,source_url,
       channel_scope,location_scope,observed_at,observed_at));con.commit();return lid

def observe_price(con,listing_id,price,currency="THB",price_type="selling",regular_price=None,promo_price=None,
                  member_price=None,promotion_mechanic="",valid_from="",valid_to="",observed_at=None,evidence_id=None):
    observed_at=observed_at or now()
    obj=dict(price_type=price_type,price=float(price),currency=currency,regular_price=regular_price,promo_price=promo_price,
             member_price=member_price,promotion_mechanic=promotion_mechanic,valid_from=valid_from,valid_to=valid_to)
    f=fp(obj)
    current=con.execute("SELECT * FROM price_version WHERE listing_id=? AND current=1",(listing_id,)).fetchone()
    if current and current["fingerprint"]==f:
        con.execute("UPDATE price_version SET last_seen_at=? WHERE price_version_id=?",(observed_at,current["price_version_id"]))
        con.commit();return {"action":"extended","price_version_id":current["price_version_id"]}
    if current:
        con.execute("UPDATE price_version SET current=0,last_seen_at=? WHERE price_version_id=?",(observed_at,current["price_version_id"]))
    pvid=hid("price",listing_id,f,observed_at)
    con.execute("""INSERT INTO price_version VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (pvid,listing_id,price_type,float(price),currency,regular_price,promo_price,member_price,promotion_mechanic,
       valid_from,valid_to,observed_at,observed_at,1,f,evidence_id))
    con.commit();return {"action":"created","price_version_id":pvid}

def observe_promotion(con,business_id,campaign_name="",promotion_type="",description="",valid_from="",valid_to="",
                      valid_time_from="",valid_time_to="",days_of_week="",published_at="",observed_at=None,offers=None):
    observed_at=observed_at or now();offers=offers or []
    core=dict(campaign_name=campaign_name,promotion_type=promotion_type,description=description,valid_from=valid_from,
              valid_to=valid_to,valid_time_from=valid_time_from,valid_time_to=valid_time_to,days_of_week=days_of_week,offers=offers)
    f=fp(core)
    row=con.execute("SELECT * FROM promotion WHERE business_id=? AND fingerprint=?",(business_id,f)).fetchone()
    if row:
        con.execute("UPDATE promotion SET last_seen_at=?,current=1 WHERE promotion_id=?",(observed_at,row["promotion_id"]))
        con.commit();return {"action":"extended","promotion_id":row["promotion_id"]}
    pid=hid("promo",business_id,f)
    con.execute("""INSERT INTO promotion VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (pid,business_id,campaign_name,promotion_type,description,valid_from,valid_to,valid_time_from,valid_time_to,
       days_of_week,published_at,observed_at,observed_at,1,f))
    for i,o in enumerate(offers):
        oid=hid("offer",pid,i,json.dumps(o,ensure_ascii=False,sort_keys=True))
        con.execute("""INSERT INTO promotion_offer VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (oid,pid,o.get("offer_type"),o.get("product_scope"),o.get("category_scope"),o.get("regular_price"),o.get("promo_price"),
           o.get("discount_amount"),o.get("discount_percent"),o.get("minimum_spend"),o.get("minimum_quantity"),o.get("free_item"),
           o.get("promo_code"),o.get("usage_limit"),o.get("quota"),o.get("stackable"),o.get("terms"),o.get("exclusions"),
           json.dumps(o.get("availability_scope") or {},ensure_ascii=False),
           json.dumps(o.get("eligibility") or {},ensure_ascii=False),
           json.dumps(o.get("payment_condition") or {},ensure_ascii=False)))
    con.commit();return {"action":"created","promotion_id":pid}

def summary(con):
    tables=["business","canonical_product","entity_resolution_map","listing","price_version","promotion","promotion_offer","evidence","marketplace_signal"]
    return {t:con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] for t in tables}


def ingest_official_result(con,business_name,result,sector=None,website=None,resolve_entities=True):
    bid=upsert_business(con,business_name,sector,website)
    counts={"evidence":0,"products":0,"listings":0,"prices":0,"promotions":0,
            "entity_matched":0,"entity_review":0,"entity_created":0,"ignored":0,
            "listing_created":0,"listing_seen":0,"price_created":0,"price_extended":0,
            "promotion_created":0,"promotion_extended":0}
    decisions=[]
    for r in result.get("records",[]):
        eid=add_evidence(con,bid,r.get("source_url",""),r.get("source_image",""),source_type="official",
                         extraction_method=r.get("provenance","official"),source_tag=r.get("source_tag",""),
                         published_at=r.get("posted_at",""),collected_at=r.get("collected_at"),raw_text=r.get("text",""),
                         raw_json=r,confidence=r.get("confidence"));counts["evidence"]+=1
        rt=r.get("record_type","")
        if rt in ("menu_item","MenuCandidate","product","ProductCandidate","price","PriceCandidate"):
            name=r.get("item_name") or r.get("product_name") or r.get("title") or r.get("name") or "Product"
            brand=r.get("brand") or (business_name if rt in ("menu_item","MenuCandidate") else "")
            category=r.get("category") or ("Menu" if rt in ("menu_item","MenuCandidate") else "")
            if resolve_entities:
                er=resolve_product_with_review(con,bid,name,"official",r.get("sku",""),
                                               r.get("source_url") or r.get("url") or "",brand,category,r)
                decisions.append({"raw_name":name,"action":er.get("action"),"decision":er.get("decision"),
                                  "score":er.get("match_score"),"canonical_name":er.get("canonical_name") or (er.get("candidate") or {}).get("canonical_name"),
                                  "review_id":er.get("review_id")})
                if er.get("action")=="matched":
                    pid=er["canonical_product_id"];counts["entity_matched"]+=1
                elif er.get("action")=="review":
                    # Do not prematurely link an ambiguous listing. Evidence + review queue are retained.
                    counts["entity_review"]+=1;continue
                else:
                    pid=er["canonical_product_id"];counts["entity_created"]+=1
            else:
                pid=upsert_product(con,name,brand,category,"MenuItem" if rt in ("menu_item","MenuCandidate") else "Product",
                                   r.get("variant",""),attributes=r)
            counts["products"]+=1
            listing_url=r.get("source_url") or r.get("url") or f"evidence:{eid}"
            existed=con.execute("SELECT 1 FROM listing WHERE business_id=? AND platform='official' AND source_url=?",(bid,listing_url)).fetchone() is not None
            lid=upsert_listing(con,bid,name,listing_url,pid,
                               raw_sku=r.get("sku",""),platform="official",variant_text=r.get("variant",""))
            counts["listings"]+=1;counts["listing_seen" if existed else "listing_created"]+=1
            price=r.get("price")
            if price is None: price=r.get("current_price")
            if price is not None:
                pa=observe_price(con,lid,price,r.get("currency") or "THB",
                              regular_price=r.get("regular_price"),promo_price=r.get("promo_price"),
                              member_price=r.get("member_price"),promotion_mechanic=r.get("promotion_mechanic",""),
                              valid_from=r.get("price_from",""),valid_to=r.get("price_to",""),
                              observed_at=r.get("collected_at"),evidence_id=eid);counts["prices"]+=1
                counts["price_created" if pa.get("action")=="created" else "price_extended"]+=1
        elif rt in ("promotion","PromotionCandidate"):
            offer={"offer_type":"official","product_scope":r.get("title") or r.get("name"),"terms":r.get("terms"),
                   "availability_scope":{"branch":r.get("participating_branch") or r.get("location"),
                                         "time":r.get("valid_time")}}
            pra=observe_promotion(con,bid,r.get("promotion_title") or r.get("title") or "",
                              promotion_type=r.get("promotion_type",""),
                              description=r.get("offer") or r.get("text") or "",
                              valid_from=r.get("start_date") or r.get("posted_at") or "",
                              valid_to=r.get("end_date") or "",
                              valid_time_from=r.get("valid_time_from",""),valid_time_to=r.get("valid_time_to",""),
                              days_of_week=r.get("days_of_week",""),
                              published_at=r.get("posted_at") or "",
                              observed_at=r.get("collected_at"),offers=[offer]);counts["promotions"]+=1
            counts["promotion_created" if pra.get("action")=="created" else "promotion_extended"]+=1
        else:
            counts["ignored"]+=1
    return {"business_id":bid,"counts":counts,"entity_resolution":decisions}

def export_repository(con,out_dir):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    tables=["business","location","channel","canonical_product","entity_resolution_map","listing","price_version","promotion","promotion_offer","evidence","marketplace_signal"]
    files=[]
    for t in tables:
        rows=con.execute(f"SELECT * FROM {t}").fetchall()
        if not rows: continue
        f=out/f"{t}.csv"
        with f.open("w",newline="",encoding="utf-8-sig") as fh:
            w=csv.writer(fh);w.writerow(rows[0].keys());w.writerows([tuple(r) for r in rows])
        files.append(str(f))
    manifest={"schema_version":SCHEMA_VERSION,"exported_at":now(),"summary":summary(con),"files":files}
    (out/"repository_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest


def canonical_candidates(con,brand="",category="",limit=200):
    q="SELECT * FROM canonical_product WHERE 1=1"
    args=[]
    if brand:
        q+=" AND lower(brand)=lower(?)";args.append(brand)
    if category:
        q+=" AND lower(category)=lower(?)";args.append(category)
    q+=" ORDER BY updated_at DESC LIMIT ?";args.append(limit)
    out=[]
    for r in con.execute(q,args).fetchall():
        try:attrs=json.loads(r["attributes_json"] or "{}")
        except:attrs={}
        out.append({"canonical_product_id":r["canonical_product_id"],"canonical_name":r["canonical_name"],
                    "brand":r["brand"],"category":r["category"],"attributes":attrs})
    return out

def auto_resolve_product(con,business_id,raw_name,platform="official",raw_sku="",source_url="",brand="",category="",
                         attributes=None,auto_threshold=.90,review_threshold=.72):
    from entity_resolution import extract_attributes,resolve_against_candidates
    attrs=attributes or extract_attributes(raw_name)
    candidates=canonical_candidates(con,brand=brand,category=category)
    ranked=resolve_against_candidates(raw_name,candidates,attrs,5)
    top=ranked[0] if ranked else None
    if top and top["decision"]=="auto-match" and top["score"]>=auto_threshold:
        pid=top["canonical_product_id"]
        add_resolution(con,pid,raw_name,business_id,platform,raw_sku,source_url,
                       "hybrid-nlp",top["score"],"auto-matched",attrs)
        return {"action":"matched","canonical_product_id":pid,"canonical_name":top["canonical_name"],
                "match_score":top["score"],"decision":"auto-match","candidates":ranked,"attributes":attrs}
    if top and top["score"]>=review_threshold and top["decision"]!="do-not-match":
        return {"action":"review","decision":"review","match_score":top["score"],
                "candidate":top,"candidates":ranked,"attributes":attrs}
    pid=upsert_product(con,raw_name,brand=brand,category=category,attributes=attrs)
    add_resolution(con,pid,raw_name,business_id,platform,raw_sku,source_url,
                   "hybrid-nlp",1.0,"new-canonical",attrs)
    return {"action":"created","canonical_product_id":pid,"canonical_name":raw_name,
            "match_score":1.0,"decision":"new-candidate","candidates":ranked,"attributes":attrs}


def queue_resolution_review(con,business_id,raw_name,platform="",source_url="",brand="",category="",
                            attributes=None,candidate=None):
    candidate=candidate or {}
    rid=hid("review",business_id,platform,source_url,raw_name,candidate.get("canonical_product_id",""))
    con.execute("""INSERT OR IGNORE INTO entity_resolution_review
      (review_id,business_id,raw_name,platform,source_url,brand,category,extracted_attributes_json,
       candidate_product_id,candidate_name,match_score,conflicts_json,status,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (rid,business_id,raw_name,platform,source_url,brand,category,
       json.dumps(attributes or {},ensure_ascii=False,sort_keys=True),
       candidate.get("canonical_product_id"),candidate.get("canonical_name"),candidate.get("score"),
       json.dumps(candidate.get("conflicts") or [],ensure_ascii=False),"pending",now()))
    con.commit();return rid

def resolve_product_with_review(con,business_id,raw_name,platform="official",raw_sku="",source_url="",
                                brand="",category="",attributes=None):
    result=auto_resolve_product(con,business_id,raw_name,platform,raw_sku,source_url,brand,category,attributes)
    if result.get("action")=="review":
        result["review_id"]=queue_resolution_review(
            con,business_id,raw_name,platform,source_url,brand,category,result.get("attributes"),
            result.get("candidate") or (result.get("candidates") or [{}])[0])
    return result

def pending_resolution_reviews(con,limit=100):
    rows=con.execute("""SELECT r.*,b.name business_name FROM entity_resolution_review r
                       LEFT JOIN business b ON b.business_id=r.business_id
                       WHERE r.status='pending' ORDER BY r.created_at LIMIT ?""",(limit,)).fetchall()
    return [dict(x) for x in rows]

def decide_resolution_review(con,review_id,decision,note=""):
    r=con.execute("SELECT * FROM entity_resolution_review WHERE review_id=?",(review_id,)).fetchone()
    if not r: raise KeyError(review_id)
    if r["status"]!="pending": raise ValueError("Review has already been decided.")
    if decision=="approve-match":
        if not r["candidate_product_id"]: raise ValueError("No candidate product to approve.")
        add_resolution(con,r["candidate_product_id"],r["raw_name"],r["business_id"],r["platform"] or "",
                       source_url=r["source_url"] or "",match_method="human-reviewed",
                       match_score=r["match_score"] or 0,match_status="confirmed")
    elif decision=="create-new":
        attrs=json.loads(r["extracted_attributes_json"] or "{}")
        pid=upsert_product(con,r["raw_name"],brand=r["brand"] or "",category=r["category"] or "",attributes=attrs)
        add_resolution(con,pid,r["raw_name"],r["business_id"],r["platform"] or "",
                       source_url=r["source_url"] or "",match_method="human-reviewed",
                       match_score=1.0,match_status="new-canonical")
    else: raise ValueError("decision must be approve-match or create-new")
    con.execute("UPDATE entity_resolution_review SET status=?,reviewer_note=?,reviewed_at=? WHERE review_id=?",
                (decision,note,now(),review_id));con.commit()
    return {"review_id":review_id,"decision":decision}

def batch_resolve_products(con,business_id,records,platform="official"):
    out={"matched":0,"review":0,"created":0,"results":[]}
    for r in records:
        x=resolve_product_with_review(con,business_id,r.get("raw_name") or r.get("name") or "",
                                      r.get("platform") or platform,r.get("raw_sku",""),r.get("source_url",""),
                                      r.get("brand",""),r.get("category",""),r.get("attributes"))
        out[x["action"]]=out.get(x["action"],0)+1;out["results"].append(x)
    return out


def record_acquisition_run(con,business_id,adapter_key,source_url,page_type,quality,status="completed",diagnostics=None):
    rid=hid("acq",business_id,adapter_key,source_url,now())
    con.execute("""INSERT INTO acquisition_run
      (run_id,business_id,adapter_key,source_url,page_type,started_at,completed_at,raw_record_count,
       useful_record_count,quality_score,status,diagnostics_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
      (rid,business_id,adapter_key,source_url,page_type,now(),now(),quality.get("records",0),
       quality.get("useful_records",0),quality.get("mean_record_quality",0),status,
       json.dumps(diagnostics or {},ensure_ascii=False)))
    con.commit();return rid

def acquisition_history(con,business_id=None,limit=100):
    q="""SELECT a.*,b.name business_name FROM acquisition_run a
         LEFT JOIN business b ON b.business_id=a.business_id"""
    args=[]
    if business_id:q+=" WHERE a.business_id=?";args.append(business_id)
    q+=" ORDER BY a.completed_at DESC LIMIT ?";args.append(limit)
    return [dict(x) for x in con.execute(q,args).fetchall()]


def connect_profile(profile_id,create=False):
    from repository_profiles import profile_by_id
    p=profile_by_id(profile_id)
    if not p: raise KeyError(profile_id)
    return connect(p["path"],create=create)
