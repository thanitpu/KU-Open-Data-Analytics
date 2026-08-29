from collections import defaultdict
import json

def _rows(con,limit=5000):
    return [dict(r) for r in con.execute("""
      SELECT a.*,b.name business_name,b.sector
      FROM acquisition_run a
      LEFT JOIN business b ON b.business_id=a.business_id
      ORDER BY a.completed_at DESC LIMIT ?""",(limit,)).fetchall()]

def benchmark(con,sector=None,limit=5000):
    rows=_rows(con,limit)
    if sector: rows=[r for r in rows if (r.get("sector") or "")==sector]
    g=defaultdict(list)
    for r in rows:g[(r.get("sector") or "Unknown",r.get("business_name") or "Unknown")].append(r)
    businesses=[]
    for (sec,biz),xs in sorted(g.items()):
        qs=[float(x.get("quality_score") or 0) for x in xs]
        raw=sum(int(x.get("raw_record_count") or 0) for x in xs)
        useful=sum(int(x.get("useful_record_count") or 0) for x in xs)
        businesses.append({
          "sector":sec,"business":biz,"runs":len(xs),
          "records":raw,"useful_records":useful,
          "useful_rate":round(useful/raw,3) if raw else 0,
          "mean_quality":round(sum(qs)/len(qs),3) if qs else 0,
          "latest_run":xs[0].get("completed_at"),
          "latest_status":xs[0].get("status"),
          "adapter":xs[0].get("adapter_key"),
          "latest_source_url":xs[0].get("source_url")
        })
    sectors=[]
    sg=defaultdict(list)
    for x in businesses:sg[x["sector"]].append(x)
    for sec,xs in sorted(sg.items()):
        records=sum(x["records"] for x in xs);useful=sum(x["useful_records"] for x in xs)
        sectors.append({"sector":sec,"businesses":len(xs),"runs":sum(x["runs"] for x in xs),
          "records":records,"useful_records":useful,"useful_rate":round(useful/records,3) if records else 0,
          "mean_quality":round(sum(x["mean_quality"] for x in xs)/len(xs),3) if xs else 0})
    return {"sector_filter":sector,"businesses":businesses,"sectors":sectors,"runs_analyzed":len(rows)}

def recommendations(report):
    out=[]
    for x in report.get("businesses",[]):
        if not x["records"]:out.append({"business":x["business"],"priority":"high","action":"No useful acquisition history: inspect source URL, navigation and adapter."})
        elif x["useful_rate"]<.35:out.append({"business":x["business"],"priority":"high","action":"Low useful-record rate: tighten source-specific page discovery/extraction."})
        elif x["mean_quality"]<.55:out.append({"business":x["business"],"priority":"medium","action":"Field completeness is weak: prioritize structured data/detail pages/Vision."})
    if not out:out.append({"priority":"normal","action":"Coverage is acceptable; expand pagination and temporal observations."})
    return out
