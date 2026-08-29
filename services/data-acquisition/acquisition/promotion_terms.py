from __future__ import annotations
import re
from datetime import datetime

TH_MONTHS={"ม.ค.":1,"มกราคม":1,"ก.พ.":2,"กุมภาพันธ์":2,"มี.ค.":3,"มีนาคม":3,"เม.ย.":4,"เมษายน":4,
"พ.ค.":5,"พฤษภาคม":5,"มิ.ย.":6,"มิถุนายน":6,"ก.ค.":7,"กรกฎาคม":7,"ส.ค.":8,"สิงหาคม":8,
"ก.ย.":9,"กันยายน":9,"ต.ค.":10,"ตุลาคม":10,"พ.ย.":11,"พฤศจิกายน":11,"ธ.ค.":12,"ธันวาคม":12}
EN_MONTHS={m.lower():i for i,m in enumerate(["","jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])}

def clean(x):return re.sub(r"\s+"," ",str(x or "")).strip()

def _iso(d,m,y):
    try:
        y=int(y);y=y-543 if y>2400 else y
        return f"{y:04d}-{int(m):02d}-{int(d):02d}"
    except:return ""

def parse_date_token(x):
    x=clean(x)
    m=re.search(r"(\d{1,2})\s*([ก-๙.]+)\s*((?:25|20)\d{2})",x)
    if m:
        mm=TH_MONTHS.get(m.group(2))
        if mm:return _iso(m.group(1),mm,m.group(3))
    m=re.search(r"(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*((?:20)\d{2})",x,re.I)
    if m:return _iso(m.group(1),EN_MONTHS[m.group(2)[:3].lower()],m.group(3))
    return ""

def parse_terms(text):
    x=clean(text);out={"valid_from":"","valid_to":"","valid_time_from":"","valid_time_to":"",
      "locations":[],"channels":[],"membership_required":False,"payment_methods":[],
      "minimum_spend":None,"maximum_discount":None,"quota_text":"","exclusions":[],"terms_text":x}
    # explicit ranges
    m=re.search(r"(\d{1,2}\s*[ก-๙.]+\s*(?:25|20)\d{2})\s*[-–ถึง]+\s*(\d{1,2}\s*[ก-๙.]+\s*(?:25|20)\d{2})",x)
    if not m:m=re.search(r"(\d{1,2}\s+\w+\s+20\d{2})\s*[-–to]+\s*(\d{1,2}\s+\w+\s+20\d{2})",x,re.I)
    if m:out["valid_from"],out["valid_to"]=parse_date_token(m.group(1)),parse_date_token(m.group(2))
    tm=re.search(r"(\d{1,2}[:.]\d{2})\s*(?:-|–|ถึง|to)\s*(\d{1,2}[:.]\d{2})",x,re.I)
    if tm:out["valid_time_from"],out["valid_time_to"]=tm.group(1).replace(".",":"),tm.group(2).replace(".",":")
    # channels/locations
    for key,label in [("ออนไลน์","online"),("online","online"),("เว็บไซต์","website"),("website","website"),
                      ("แอป","app"),("application","app"),("mobile order","mobile-order"),
                      ("delivery","delivery"),("หน้าร้าน","store"),("สาขา","store")]:
        if key.lower() in x.lower() and label not in out["channels"]:out["channels"].append(label)
    if re.search(r"เฉพาะ(?:ที่|สาขา)|participating stores|selected stores",x,re.I):
        out["locations"].append("restricted/participating locations")
    out["membership_required"]=bool(re.search(r"สมาชิก|member|rewards",x,re.I))
    for key,label in [("บัตรเครดิต","credit-card"),("credit card","credit-card"),("visa","visa"),
                      ("mastercard","mastercard"),("ทรูมันนี่","truemoney"),("rabbit","rabbit-line-pay")]:
        if key.lower() in x.lower() and label not in out["payment_methods"]:out["payment_methods"].append(label)
    m=re.search(r"(?:ขั้นต่ำ|min(?:imum)?(?: spend| order)?)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*บาท",x,re.I)
    if m:out["minimum_spend"]=float(m.group(1).replace(",",""))
    m=re.search(r"(?:ลดสูงสุด|maximum discount|up to)[^\d]{0,20}(\d[\d,]*(?:\.\d+)?)\s*บาท",x,re.I)
    if m:out["maximum_discount"]=float(m.group(1).replace(",",""))
    q=re.search(r"((?:จำกัด|สิทธิ์|quota|limited)[^.]{0,120})",x,re.I)
    if q:out["quota_text"]=q.group(1)
    for pat in [r"(ไม่รวม[^.]{1,120})",r"(ยกเว้น[^.]{1,120})",r"(exclud(?:e|es|ing)[^.]{1,120})"]:
        out["exclusions"] += [clean(v) for v in re.findall(pat,x,re.I)]
    return out

def enrich_promotion_record(r):
    if r.get("record_type") not in ("PromotionCandidate","promotion","BusinessRule","ChannelPolicy"):return r
    text=" ".join(str(r.get(k) or "") for k in ("promotion_title","title","offer","description","text","terms","validity_text"))
    t=parse_terms(text);z=dict(r)
    for k,v in t.items():
        if k=="terms_text":z.setdefault("terms",v)
        elif v not in ("",None,[],False):z.setdefault(k,v)
    return z
