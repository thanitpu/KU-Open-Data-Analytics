from __future__ import annotations
import re,json
from urllib.parse import urlparse

def clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()

def money(x):
    m=re.search(r"(?:฿\s*)?(\d[\d,]*(?:\.\d+)?)",str(x or ""))
    return float(m.group(1).replace(",","")) if m else None

def _thai_date_range(text):
    # Preserves source wording and extracts a best-effort date range string.
    m=re.search(r"(?:เฉพาะวันสั่งซื้อ\s*:?\s*)?(\d{1,2}\s*[^\s]+\s*(?:25|20)\d{2})\s*[-–]\s*(\d{1,2}\s*[^\s]+\s*(?:25|20)\d{2})",text)
    return (m.group(1),m.group(2)) if m else ("","")

def tops_records(text,source_url):
    lines=[clean(x) for x in str(text or "").splitlines() if clean(x)]
    rec=[];i=0
    while i<len(lines):
        line=lines[i]
        # Product cards usually: product name -> mechanic -> current price -> optional regular price/saving.
        if re.search(r"\d+\s*(?:มล|ml|กรัม|g|กก|kg|แพค|แพ็ค|ชิ้น|ซอง|ลิตร)",line,re.I):
            name=line
            mechanic="";current=None;regular=None
            j=i+1
            while j<min(len(lines),i+5):
                x=lines[j]
                if re.search(r"ซื้อ\s*\d+|จ่าย\s*\d+|แถม|เซฟ|ลด",x,re.I) and "฿" not in x:
                    mechanic=x
                if "฿" in x:
                    vals=[float(v.replace(",","")) for v in re.findall(r"฿\s*(\d[\d,]*(?:\.\d+)?)",x)]
                    if vals:
                        current=vals[0]
                        if len(vals)>1:regular=vals[1]
                    break
                j+=1
            if current is not None:
                rec.append({"record_type":"ProductCandidate","product_name":name,"price":current,
                  "regular_price":regular,"promo_price":current if (mechanic or regular) else None,
                  "promotion_mechanic":mechanic,"currency":"THB","source_url":source_url,
                  "source_tag":"Marketing","provenance":"tops-card-text"})
                i=max(i,j)
        i+=1
    # Campaign/offer lines on home/detail pages.
    for line in lines:
        if ("เฉพาะวันสั่งซื้อ" in line or "โปรโมชั่น" in line or "ลดทันที" in line) and len(line)<500:
            start,end=_thai_date_range(line)
            if start or end or re.search(r"ลด|โปร",line):
                rec.append({"record_type":"PromotionCandidate","promotion_title":line[:180],
                  "offer":line,"start_date":start,"end_date":end,"terms":"",
                  "source_url":source_url,"source_tag":"Marketing","provenance":"tops-campaign-text"})
    return _dedup(rec)

def makro_records(text,images,source_url):
    rec=[]
    x=clean(text)
    if re.search(r"(?:600|six hundred).{0,80}(?:promotion|สินค้า)",x,re.I):
        rec.append({"record_type":"PromotionCandidate","promotion_title":"Makro Promotions Catalogue",
          "offer":"Promotion catalogue containing hundreds of promotional products",
          "source_url":source_url,"source_tag":"Marketing","provenance":"makro-catalog-page"})
    for im in images or []:
        s=(im.get("src","")+" "+im.get("alt","")).lower()
        if any(k in s for k in ("catalog","makro mail","promotion","catalogue")):
            rec.append({"record_type":"CatalogCandidate","title":clean(im.get("alt")) or "Makro catalogue",
              "source_image":im.get("src"),"source_url":source_url,"source_tag":"Marketing",
              "provenance":"makro-catalog-image"})
    return _dedup(rec)

def dean_deluca_records(text,images,source_url,title=""):
    rec=[];x=clean(text);low=(title+" "+source_url).lower()
    section="Menu" if any(k in low for k in ("espresso","menu","bakery","pastry")) else "Promotion" if "promotion" in low else "General"
    dates=re.findall(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b",x,re.I)
    for im in images or []:
        s=(im.get("src","")+" "+im.get("alt","")).lower()
        if im.get("score",0)>0 or any(k in s for k in ("menu","espresso","promotion","promo","bakery","cafe")):
            rec.append({"record_type":"MenuCandidate" if section=="Menu" else "PromotionCandidate",
              "title":title or section,"source_image":im.get("src"),"source_url":source_url,
              "posted_at":dates[-1] if dates else "","source_tag":"Product" if section=="Menu" else "Marketing",
              "visual_readiness":"vision-ready","provenance":"dean-deluca-official-image"})
    # Promotion date range in HTML.
    m=re.search(r"(\d{1,2}\s+\w+\s*-\s*\d{1,2}\s+\w+\s+20\d{2})",x,re.I)
    if section=="Promotion" and m:
        rec.append({"record_type":"PromotionCandidate","promotion_title":title or "DEAN & DELUCA Promotion",
          "offer":"","start_date":"","end_date":"","validity_text":m.group(1),
          "posted_at":dates[-1] if dates else "","source_url":source_url,
          "source_tag":"Marketing","provenance":"dean-deluca-promotion-html"})
    return _dedup(rec)

def starbucks_records(text,source_url,title=""):
    rec=[];x=clean(text)
    # Business rules from Mobile Order / Delivery.
    for pat,label in [
      (r"ยอดสั่งซื้อขั้นต่ำ\s*(\d+)\s*บาท","Minimum order"),
      (r"มูลค่า\s*(\d+)\s*-\s*(\d+)\s*บาท.{0,50}?ค่าบริการจัดส่ง\s*(\d+)\s*บาท","Delivery fee band"),
      (r"มูลค่า\s*(\d+)\s*บาท\s*ขึ้นไป.{0,50}?ไม่มีค่าบริการจัดส่ง","Free delivery threshold"),
      (r"(\d+)\s*ดวง.{0,60}?ส่วนลด\s*(\d+)%","Reward discount")
    ]:
        for m in re.finditer(pat,x,re.I):
            rec.append({"record_type":"BusinessRule","title":label,"text":m.group(0),
              "source_url":source_url,"source_tag":"Marketing","provenance":"starbucks-official-rule"})
    # Rewards / availability conditions.
    if any(k in x.lower() for k in ("starbucks delivery","mobile order","rewards","reward")):
        rec.append({"record_type":"ChannelPolicy","title":title or "Starbucks Channel / Rewards Policy",
          "text":x[:3000],"source_url":source_url,"source_tag":"Marketing",
          "provenance":"starbucks-official-policy"})
    return _dedup(rec)

def generic_retail_records(text,source_url,sector="Retail"):
    lines=[clean(x) for x in str(text or "").splitlines() if clean(x)]
    rec=[]
    for i,line in enumerate(lines):
        prices=[float(v.replace(",","")) for v in re.findall(r"(?:฿|THB|บาท)\s*(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s*(?:บาท)",line,re.I) for v in v if v]
        if prices and 3<len(line)<260:
            rec.append({"record_type":"ProductCandidate","product_name":re.sub(r"(?:฿|THB).*","",line,flags=re.I).strip(" -:"),
              "price":prices[0],"regular_price":prices[1] if len(prices)>1 else None,"currency":"THB",
              "source_url":source_url,"source_tag":"Marketing","provenance":"optimized-retail-text"})
    for line in lines:
        if re.search(r"โปรโมชั่น|promotion|ลด\s*\d+%|ซื้อ\s*\d+.*แถม|flash sale|coupon|คูปอง",line,re.I) and len(line)<400:
            rec.append({"record_type":"PromotionCandidate","promotion_title":line[:180],"offer":line,
              "source_url":source_url,"source_tag":"Marketing","provenance":"optimized-retail-promotion"})
    return _dedup(rec)

def beauty_records(text,source_url):
    rows=generic_retail_records(text,source_url,"Beauty")
    x=clean(text)
    for m in re.finditer(r"([A-Za-z0-9ก-๙][^|]{3,100}?)\s+(?:สมาชิก|member)[^\d]{0,15}(?:฿|บาท)?\s*(\d[\d,]*(?:\.\d+)?)",x,re.I):
        rows.append({"record_type":"ProductCandidate","product_name":clean(m.group(1)),"member_price":float(m.group(2).replace(",","")),
          "currency":"THB","source_url":source_url,"source_tag":"Marketing","provenance":"beauty-member-price"})
    return _dedup(rows)

def it_records(text,source_url):
    rows=generic_retail_records(text,source_url,"IT Retail")
    x=clean(text)
    # Useful structured attributes for future canonical-product matching.
    for m in re.finditer(r"(?:SKU|รหัสสินค้า|Part No\.?|Model)\s*[:#]?\s*([A-Za-z0-9._/-]{3,40})",x,re.I):
        rows.append({"record_type":"ProductIdentifier","identifier":m.group(1),"identifier_type":"model-or-sku",
          "source_url":source_url,"source_tag":"Product","provenance":"it-model-sku"})
    if re.search(r"มีสินค้า|in stock|พร้อมส่ง|สินค้าพร้อม",x,re.I):
        rows.append({"record_type":"AvailabilitySignal","availability":"in-stock","source_url":source_url,
          "source_tag":"Product","provenance":"it-stock-text"})
    return _dedup(rows)

def optimized_records(adapter_key,text,images,source_url,title=""):
    if adapter_key=="tops":return tops_records(text,source_url)
    if adapter_key=="makro":return makro_records(text,images,source_url)
    if adapter_key=="dean-deluca":return dean_deluca_records(text,images,source_url,title)
    if adapter_key=="starbucks-th":return starbucks_records(text,source_url,title)
    if adapter_key in ("lotuss","bigc","gourmetmarket"):return generic_retail_records(text,source_url,"Supermarket")
    if adapter_key in ("watsons","konvy","eveandboy","beautrium","boots"):return beauty_records(text,source_url)
    if adapter_key in ("jib","advice","it-city","ihavecpu","banana"):return it_records(text,source_url)
    return []

def _dedup(rows):
    out=[];seen=set()
    for r in rows:
        k=(r.get("record_type"),r.get("product_name") or r.get("title") or r.get("promotion_title"),
           r.get("price"),r.get("source_url"),r.get("source_image"))
        if k not in seen:seen.add(k);out.append(r)
    return out
