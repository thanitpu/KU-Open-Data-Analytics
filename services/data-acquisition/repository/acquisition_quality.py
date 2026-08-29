from collections import Counter,defaultdict

FIELDS=["product_name","price","regular_price","promo_price","promotion_title","start_date","end_date",
        "valid_time","participating_branch","terms","posted_at","source_url","source_image"]

def _present(v): return v not in (None,"",[],{})
def record_quality(r):
    rt=r.get("record_type","unknown")
    if rt in ("ProductCandidate","product","PriceCandidate","price","menu_item","MenuCandidate"):
        wanted=["product_name","price","regular_price","promo_price","source_url","posted_at"]
        name=r.get("product_name") or r.get("item_name") or r.get("title") or r.get("name")
        vals={"product_name":name,**r}
    elif rt in ("PromotionCandidate","promotion"):
        wanted=["promotion_title","start_date","end_date","participating_branch","terms","posted_at","source_url"]
        vals={"promotion_title":r.get("promotion_title") or r.get("title"),**r}
    else:
        wanted=["source_url","posted_at"];vals=r
    got=sum(_present(vals.get(k)) for k in wanted)
    return round(got/len(wanted),3) if wanted else 0

def quality_report(business_name,result,source_type="official"):
    records=result.get("records",[])
    types=Counter(r.get("record_type","unknown") for r in records)
    field_counts={f:sum(_present(r.get(f)) for r in records) for f in FIELDS}
    q=[record_quality(r) for r in records]
    useful=[r for r in records if r.get("record_type") in
            ("ProductCandidate","product","PriceCandidate","price","menu_item","MenuCandidate","PromotionCandidate","promotion")]
    return {
      "business":business_name,"source_type":source_type,"records":len(records),"useful_records":len(useful),
      "useful_rate":round(len(useful)/len(records),3) if records else 0,
      "record_types":dict(types),"field_counts":field_counts,
      "mean_record_quality":round(sum(q)/len(q),3) if q else 0,
      "recommendations":recommend(records)
    }

def recommend(records):
    rec=[]
    if not records:return ["No records retrieved: inspect navigation, sitemap/feed, structured data, APIs, and image/catalog paths."]
    products=[r for r in records if r.get("record_type") in ("ProductCandidate","product","PriceCandidate","price","menu_item","MenuCandidate")]
    promos=[r for r in records if r.get("record_type") in ("PromotionCandidate","promotion")]
    if products and sum(_present(r.get("price")) for r in products)/len(products)<.7:
        rec.append("Price completeness is low: prioritize product detail/listing APIs or structured product markup.")
    if promos:
        if sum(_present(r.get("start_date")) for r in promos)/len(promos)<.5 or sum(_present(r.get("end_date")) for r in promos)/len(promos)<.5:
            rec.append("Promotion validity is incomplete: inspect campaign pages, catalog images/PDFs, banners and terms.")
        if sum(_present(r.get("terms")) for r in promos)/len(promos)<.5:
            rec.append("Promotion terms are incomplete: retrieve linked detail/terms pages and use Vision for image-only terms.")
    if any(r.get("source_image") for r in records):
        rec.append("Relevant images detected: route menu/catalog/promotion images to Vision, excluding logos/decorative assets.")
    if not rec:rec.append("Core fields are reasonably complete; expand coverage/pagination and preserve temporal observations.")
    return rec
