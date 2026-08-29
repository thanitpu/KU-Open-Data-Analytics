from __future__ import annotations
import time
import re
from source_preflight import preflight_url
from operations_store import save_quality_audit
from monitoring_registry import update_source
from access_policy import policy
from technique_strategy import assigned_acquisition, assigned_profile, technique_profile_fingerprint


def _pct(a,b): return round(100*a/b,1) if b else 0.0

def _field_stats(records):
    fields=["product_name","price","regular_price","promo_price","promotion_mechanic","promotion_title",
            "start_date","end_date","source_url","provenance"]
    return {f:{"present":sum(r.get(f) not in (None,"","[]") for r in records),
               "pct":_pct(sum(r.get(f) not in (None,"","[]") for r in records),len(records))}
            for f in fields}


def _record_key(r):
    return (r.get("record_type"),r.get("product_name") or r.get("promotion_title") or r.get("title"),
            r.get("price"),r.get("source_url"))

def _repeatability_breakdown(records1,records2):
    """Compute overall and per-track repeatability.

    Retail audits must not be able to report 100% repeatability merely because
    promotions repeat while the Product & Price track yields zero products.
    """
    r1=list(records1 or []);r2=list(records2 or [])
    def calc(a,b):
        k1={_record_key(r) for r in a};k2={_record_key(r) for r in b}
        overlap=len(k1&k2);smaller=min(len(k1),len(k2))
        # Deep Audit intentionally rechecks a smaller bounded sample. Reproducibility
        # therefore measures how much of the smaller sample is reproduced, while
        # Jaccard is retained as a diagnostic rather than used as the hard gate.
        return {"first_records":len(a),"second_records":len(b),"key_overlap":overlap,
                "repeatability_pct":_pct(overlap,smaller) if smaller else 0.0,
                "set_similarity_pct":_pct(overlap,len(k1|k2))}
    overall=calc(r1,r2)
    prod=calc([r for r in r1 if r.get('record_type')=='ProductCandidate'],
              [r for r in r2 if r.get('record_type')=='ProductCandidate'])
    promo=calc([r for r in r1 if r.get('record_type')=='PromotionCandidate'],
               [r for r in r2 if r.get('record_type')=='PromotionCandidate'])
    overall.update({"product":prod,"promotion":promo,
                    "product_repeatability_pct":prod['repeatability_pct'],
                    "promotion_repeatability_pct":promo['repeatability_pct']})
    return overall


def _semantically_plausible_product(r):
    name=str(r.get('product_name') or '').strip();prov=str(r.get('provenance') or '')
    if not name:return False
    if prov in {'text-pattern','optimized-retail-text'}:return False
    if re.match(r'^(?:ลด|ซื้อครบ|โค้ด|คูปอง|coupon|discount)\b',name,re.I):return False
    if name.lower() in {'shop','ช็อป','ซื้อครบ','คูปอง'}:return False
    identity=bool(r.get('sku')) or bool(re.search(r'/(?:product|p)/',r.get('source_url') or '',re.I)) or prov in {
      'lotus-public-catalog-api','bigc-sitemap-product-detail','bigc-category-card',
      'makro-pro-listing-card','makro-pro-product-detail','makro-pro-embedded-state','makro-pro-accessible-text',
      'tops-sitemap-product-detail','tops-campaign-product-card',
      'gourmet-graphql-product','gourmet-rendered-product-card'}
    return bool(identity and r.get('price') is not None)



def _records_for_assigned_track(run,track_name,record_type):
    tracks=run.get('technique_tracks') or {}
    tr=tracks.get(track_name) or {}
    key=tr.get('technique')
    if not key:return []
    for x in run.get('technique_results') or []:
        if x.get('technique')==key:
            return [r for r in (x.get('sample_records') or []) if r.get('record_type')==record_type]
    return []

def _audit_business_records(run):
    """Use each assigned acquisition track as its own quality source of truth.

    A generic technique assigned only to Promotions must not contaminate Product &
    Price quality with heuristic ProductCandidate rows, and vice versa.
    """
    raw=list(run.get('records') or [])
    tracks=run.get('technique_tracks') or {}
    if not tracks:return raw
    out=[]
    product=_records_for_assigned_track(run,'product_price','ProductCandidate')
    promo=_records_for_assigned_track(run,'promotion','PromotionCandidate')
    out.extend(product);out.extend(promo)
    # Preserve non-commerce facts only when no business track exists for them.
    if not product and 'product_price' not in tracks:
        out.extend(r for r in raw if r.get('record_type')=='ProductCandidate')
    if not promo and 'promotion' not in tracks:
        out.extend(r for r in raw if r.get('record_type')=='PromotionCandidate')
    seen=set();clean=[]
    for r in out:
        k=_record_key(r)
        if k in seen:continue
        seen.add(k);clean.append(r)
    return clean

def _block_events(diag):
    text=str(diag or [])
    return text.count("HTTP 403")+text.count("HTTP 429")


def _profile_execution(acq,assigned):
    by={x.get('technique'):x for x in (acq.get('technique_results') or [])}
    executed=0;with_output=0;details=[]
    for key in assigned:
        x=by.get(key) or {};status=x.get('status') or 'not-run';rc=int(x.get('record_count') or 0)
        if status=='completed':executed+=1
        if rc>0:with_output+=1
        details.append({'technique':key,'label':x.get('label') or key,'status':status,'record_count':rc,
          'pages_checked':int(x.get('pages_checked') or 0),'potential':x.get('potential') or {}})
    return {'assigned_count':len(assigned),'executed_count':executed,'techniques_with_output':with_output,
      'execution_pct':_pct(executed,len(assigned)) if assigned else 0.0,'details':details}


def audit_source(source,max_pages=20,repeat_check=True,progress=None,cancel_check=None):
    url=source["url"];started=time.time();source_id=source.get('source_id')
    assignment_rows,assigned=assigned_profile(source_id)
    if not assigned:
        raise RuntimeError('No Best Acquisition Technique is assigned. Run Find Best Data Acquisition Techniques before Deep Audit.')

    def cancelled():
        return bool(cancel_check and cancel_check())
    def guard():
        if cancelled(): raise InterruptedError('Deep Audit cancelled by user.')
    def emit(pct,phase,message,**extra):
        if progress:
            try: progress({"progress_pct":pct,"phase":phase,"message":message,**extra})
            except Exception: pass
        guard()

    emit(4,"preflight","Checking public access",assigned_techniques=assigned)
    pre=preflight_url(url,timeout=12)
    emit(10,"preflight","Preflight completed",preflight_status=pre.get("status"),assigned_techniques=assigned)
    ap=policy(source.get("accessibility_level",0));page_cap=max(1,min(int(max_pages),int(ap.get("max_pages_per_run",40) or 40),40))

    emit(15,"best-technique","Applying Best Acquisition Technique profile",pages_target=page_cap,assigned_techniques=assigned)
    run1=assigned_acquisition(source,max_pages=page_cap,stable_sample=True,progress=lambda q: emit(30,"best-technique",q.get('message','Applying assigned techniques'),**{k:v for k,v in q.items() if k not in ('message','phase')}),require_profile=True)
    emit(68,"quality","Calculating extraction and field quality",records_found=len(run1.get('records') or []))

    records=_audit_business_records(run1);keys=[_record_key(r) for r in records];unique=len(set(keys));dups=max(0,len(keys)-unique)
    products=[r for r in records if r.get("record_type")=="ProductCandidate"]
    promos=[r for r in records if r.get("record_type")=="PromotionCandidate"]
    technique_tracks=run1.get('technique_tracks') or {}
    product_track=technique_tracks.get('product_price')
    promotion_track=technique_tracks.get('promotion')
    discovery_track=technique_tracks.get('discovery')
    profile_exec=_profile_execution(run1,assigned)

    repeat=None
    if repeat_check:
        repeat_cap=min(page_cap,5)
        emit(76,"repeatability","Repeating the same Best Acquisition Technique profile",pages_target=repeat_cap,assigned_techniques=assigned)
        run2=assigned_acquisition(source,max_pages=repeat_cap,stable_sample=True,progress=lambda q: emit(84,"repeatability",q.get('message','Repeatability sample'),**{k:v for k,v in q.items() if k not in ('message','phase')}),require_profile=True)
        repeat=_repeatability_breakdown(records,_audit_business_records(run2))
        repeat["technique_profile_fingerprint"]=run2.get('technique_profile_fingerprint')
    emit(92,"quality","Evaluating audit gates")

    diag=run1.get("diagnostics",[]);block_events=_block_events(diag)
    # When a source-specific public technique produces records, that is stronger access evidence than the homepage preflight alone.
    accessible=bool(records)
    execution_pct=profile_exec.get('execution_pct',0)
    price_pct=_pct(sum(r.get("price") is not None for r in products),len(products))
    semantic_product_pct=_pct(sum(_semantically_plausible_product(r) for r in products),len(products))
    expected_product_catalog=(str(source.get('source_type') or '').lower() in {'lotuss','bigc','makro','tops','gourmetmarket','gourmet'} or str(source.get('adapter') or '').lower() in {'lotuss','bigc','makro','tops','gourmetmarket','gourmet'} or str(source.get('name') or source.get('business') or '').lower() in {"lotus's",'lotuss','big c','bigc','makro','tops','gourmet market','gourmet'})
    required_product_records=min(5,page_cap) if expected_product_catalog else 0
    provenance_pct=_pct(sum(bool(r.get("source_url")) for r in records),len(records))
    repeat_pct=(repeat or {}).get("repeatability_pct",0)
    product_repeat_pct=(repeat or {}).get("product_repeatability_pct",0)
    promotion_repeat_pct=(repeat or {}).get("promotion_repeatability_pct",0)
    proposed=1 if accessible and block_events==0 else 2 if accessible else 3 if block_events else 0

    score=0
    score+=20 if accessible else 0
    score+=20 if execution_pct>=80 else 10 if execution_pct>0 else 0
    score+=20 if len(records)>=50 else round(min(20,len(records)/50*20))
    score+=15 if (not products or price_pct>=80) else 5
    score+=10 if unique==len(records) else 5
    score_repeat=product_repeat_pct if expected_product_catalog else repeat_pct
    score+=10 if (not repeat_check or score_repeat>=80) else 5 if score_repeat>=70 else 0
    score+=5 if provenance_pct>=95 else 0
    quality_label="strong" if score>=80 else "good" if score>=65 else "moderate" if score>=45 else "weak"

    gate_checks={
      "best_technique_profile":{"passed":bool(assigned),"value":assigned,"required":"at least one assigned Best Acquisition Technique"},
      "technique_execution":{"passed":execution_pct>=80,"value":execution_pct,"required":">=80% assigned techniques completed"},
      "usable_records":{"passed":len(records)>0,"value":len(records),"required":">0 repository-ready records from assigned techniques"},
      "product_price_track":{"passed":(not expected_product_catalog or bool(product_track)),"value":product_track,
        "required":"Retail catalog source must have an assigned Product & Price acquisition track" if expected_product_catalog else "not required for this source"},
      "product_catalog_coverage":{"passed":(not expected_product_catalog or len(products)>=required_product_records),"value":len(products),"required":f">={required_product_records} product records for this retail catalog audit sample" if expected_product_catalog else "not required for this source"},
      "product_price":{"passed":((not products and not expected_product_catalog) or (bool(products) and price_pct>=80)),"value":price_pct,"required":">=80% price completeness; retail catalog source also requires product records" if expected_product_catalog else ">=80% when products exist"},
      "product_semantic_quality":{"passed":(not expected_product_catalog or (bool(products) and semantic_product_pct>=80)),"value":semantic_product_pct,
        "required":">=80% product rows must have plausible product identity + price and must not be coupon/marketing text" if expected_product_catalog else "not required for this source"},
      "promotion_track_yield":{"passed":(not promotion_track or len(promos)>0),"value":{"track":promotion_track,"records":len(promos)},
        "required":"If a Promotion track is assigned, it must materialize at least one promotion record"},
      "repeatability":{"passed":(not repeat_check or repeat_pct>=70),"value":repeat_pct,"required":">=70% using the same technique profile"},
      "product_track_repeatability":{"passed":(not expected_product_catalog or not repeat_check or (bool(products) and product_repeat_pct>=70)),
        "value":product_repeat_pct,"required":">=70% Product & Price repeatability for retail catalog sources" if expected_product_catalog else "not required for this source"},
      "provenance":{"passed":provenance_pct>=95,"value":provenance_pct,"required":">=95% source URL"},
    }
    hard_failures=[k for k,v in gate_checks.items() if not v["passed"]]
    warnings=[]
    if pre.get('status')!='accessible' and accessible:
        warnings.append({"code":"homepage-preflight-differs","message":"The supplied URL preflight was not fully accessible, but the assigned official acquisition surface produced usable records."})
    if block_events:
        warnings.append({"code":"access-sensitive","message":f"{block_events} HTTP 403/429 event(s) observed; use controlled L2 cadence."})
    if expected_product_catalog and not promotion_track:
        warnings.append({"code":"promotion-track-not-assigned","message":"No Promotion acquisition track is currently assigned for this retail source; product/price acquisition may still pass, but promotion coverage is incomplete."})
    promo_validity_pct=_pct(sum(bool(r.get("start_date") or r.get("end_date")) for r in promos),len(promos))
    if promos and promo_validity_pct<80:
        warnings.append({"code":"promotion-temporal-incomplete","message":f"Promotion validity captured for {promo_validity_pct}% of promotion records. Preserve observed_at and treat source-stated validity as incomplete."})
    if repeat_check and promotion_track and promos and promotion_repeat_pct<70:
        warnings.append({"code":"promotion-repeatability-low","message":f"Promotion-track repeatability is {promotion_repeat_pct}%. Promotions may change rapidly; review before enabling continuous acquisition."})
    regular_price_pct=_pct(sum(r.get("regular_price") is not None for r in products),len(products))
    promotional_products=[r for r in products if r.get("promotion_mechanic") or r.get("promo_price") is not None]
    product_promotion_mechanic_pct=_pct(sum(bool(r.get("promotion_mechanic")) for r in promotional_products),len(promotional_products))
    product_promotion_validity_pct=_pct(sum(bool(r.get("start_date") or r.get("end_date")) for r in promotional_products),len(promotional_products))
    if products and regular_price_pct<50:
        warnings.append({"code":"regular-price-low","message":f"Regular/original price is present in {regular_price_pct}% of products. This is informational unless a discount is explicitly detected."})
    audit_passed=not hard_failures
    audit_status="pass-with-warnings" if audit_passed and warnings else "pass" if audit_passed else "fail"
    fp=technique_profile_fingerprint(assigned,assignment_rows)
    out={
      "source":{"source_id":source_id,"name":source.get("business") or source.get("name"),"url":url,"domain":source.get("sector") or source.get("domain")},
      "technique_profile":{"source_of_truth":"Best Acquisition Technique(s)","assigned_techniques":assigned,
        "fingerprint":fp,"assignments":assignment_rows,"tracks":technique_tracks,"execution":profile_exec,"adapter":run1.get('adapter'),
        "legacy_fallback_used":False},
      "accessibility":{"current_level":source.get("accessibility_level",0),"status":source.get("accessibility_status","unknown"),
                       "verified_method":"best-technique:"+','.join(assigned),"preflight":pre,
                       "proposed_level":proposed,"blocked_or_rate_limited_events":block_events},
      "coverage":{"basis":"assigned-technique execution","technique_execution_pct":execution_pct,
                  "pages_requested":page_cap,"pages_tested":run1.get('pages_checked',0),"urls_tested":run1.get('urls_checked') or [],
                  "techniques":profile_exec.get('details') or []},
      "yield":{"records":len(records),"products":len(products),"promotions":len(promos),"unique_records":unique,"duplicate_records":dups,
               "by_track":{"product_price":{"assigned":bool(product_track),"records":len(products),"technique":(product_track or {}).get("technique")},
                           "promotion":{"assigned":bool(promotion_track),"records":len(promos),"technique":(promotion_track or {}).get("technique")},
                           "discovery":{"assigned":bool(discovery_track),"technique":(discovery_track or {}).get("technique")}}},
      "field_quality":{"all_records":_field_stats(records),"product_price_pct":price_pct,
                       "product_semantic_quality_pct":semantic_product_pct,"product_regular_price_pct":regular_price_pct,
                       "product_promotion_mechanic_pct":product_promotion_mechanic_pct,"product_promotion_validity_pct":product_promotion_validity_pct,
                       "promotion_validity_pct":promo_validity_pct,"provenance_pct":provenance_pct},
      "repeatability":repeat,"diagnostics":diag,"quality_score":score,"quality_label":quality_label,"audit_passed":audit_passed,
      "audit_status":audit_status,"gate_checks":gate_checks,"hard_failures":hard_failures,"warnings":warnings,
      "safe_cadence_recommendation":"daily" if proposed==1 else "controlled-daily-or-weekly" if proposed==2 else "weekly-or-manual",
      "access_policy":{"min_delay_seconds":ap.get("min_delay_seconds",0),"max_pages_per_run":page_cap,"continuous_allowed":ap.get("continuous_allowed",False)},
      "elapsed_seconds":round(time.time()-started,2),"sample_records":records[:20],
      "guardrail":"Deep Audit evaluates the persisted Best Acquisition Technique profile on public official-site access only; no authentication/challenge bypass."}
    emit(96,"persistence","Saving Best-Technique audit profile",audit_passed=audit_passed,quality_score=score)
    try:
        save_quality_audit(source_id,out)
        if audit_passed:
            update_source(source_id,{"accessibility_level":proposed,"accessibility_status":"verified",
              "verified_access_method":"best-technique:"+','.join(assigned),"safe_cadence":out["safe_cadence_recommendation"],"last_deep_audit_score":score})
    except Exception as e:out["audit_persistence_warning"]=f"{type(e).__name__}: {e}"
    emit(100,"complete","Deep Audit completed using Best Acquisition Technique profile",audit_passed=audit_passed,quality_score=score,assigned_techniques=assigned)
    return out
