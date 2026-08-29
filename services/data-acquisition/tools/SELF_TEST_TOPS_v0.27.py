from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'acquisition'),str(ROOT/'repository'),str(ROOT)]
import supermarket_techniques as st
import technique_strategy as ts

# 1) Product detail parser — current Tops public pattern: H1 + SKU + sale unit + optional mechanic.
DETAIL='''<html><head><meta property="og:title" content="ท็อปส์น้ำดื่ม 600มล. แพค 12 | ของแท้ 100% ส่งไวทั่วไทย | TOPS ONLINE"></head><body>
<h1>ท็อปส์น้ำดื่ม 600มล. แพค 12</h1><div>SKU 8853474057863</div><div>ซื้อ 3 ชิ้นราคา 129 (เซฟ 15)</div>
<div>วันนี้ - 1 ก.ย. 2569</div><div>ราคาอาจแตกต่างกันตามสาขาที่เลือก</div><div>48 / แพค</div><div>รายละเอียดสินค้า</div></body></html>'''
r=st.tops_detail_record(DETAIL,'https://www.tops.co.th/th/tops-drinking-water-600ml-pack-12-8853474057863')
assert r and r['sku']=='8853474057863' and r['price']==48.0 and r['provenance']=='tops-sitemap-product-detail',r

# 2) Campaign listing card — product link carries identity; card carries current/regular price.
HOME='''<html><body><a href="/th/campaign/promotions/fresh-food-bakery">โปรอาหารสด</a></body></html>'''
CAMPAIGN='''<html><body><div class="product-card"><a href="/th/tops-salmon-100g-8850000000001"><span>ท็อปส์เนื้อแซลมอนหั่นชิ้นแช่แข็ง 100กรัม</span></a>
<div>ซื้อ 2 ชิ้นราคา 199 (เซฟ 39)</div><div class="sale-price">฿119 /ชิ้น</div><div class="regular-price">฿169 ประหยัด ฿50</div></div></body></html>'''
orig_get=st.get
try:
    def fake_get(url,timeout=12,**kwargs):
        if url==st.TOPS_HOME:return {'ok':True,'text':HOME,'final_url':url,'bytes':len(HOME)}
        if 'campaign/promotions/fresh-food-bakery' in url:return {'ok':True,'text':CAMPAIGN,'final_url':url,'bytes':len(CAMPAIGN)}
        return {'ok':False,'error':'fixture-miss'}
    st.get=fake_get
    x=st.tops_campaign_catalog(max_pages=1)
    assert x['rows'],x
    c=x['rows'][0]
    assert c['sku']=='8850000000001' and c['price']==119.0 and c['regular_price']==169.0,c
finally:
    st.get=orig_get

# 3) Promotion surface — official homepage block with source-stated date range.
PROMO='''<html><body>โปรของสด ลดท้ายเดือน\nลด ฿120 เมื่อช็อปอาหารสด ครบ ฿600/ใบเสร็จ\nเฉพาะวันสั่งซื้อ : 25 ส.ค. 2569 - 31 ส.ค. 2569</body></html>'''
try:
    st.get=lambda url,timeout=12,**kwargs:{'ok':True,'text':PROMO,'final_url':url,'bytes':len(PROMO)}
    p=st.tops_promotion_surface(max_pages=2)
    assert p['rows'] and p['rows'][0]['end_date']=='2026-08-31',p
finally:
    st.get=orig_get

# 4) Recommender transfer test: source-specific Tops beats noisy generic crawler.
results=[
 {'technique':'basic_crawler','label':'Basic HTML Crawler','status':'completed','record_count':158,'record_types':[{'type':'ProductCandidate','count':158}],
  'sample_records':[{'record_type':'ProductCandidate','product_name':'สมัคร Tops Prime วันนี้เพียง','price':1,'sku':'','source_url':'https://www.tops.co.th/th','provenance':'text-pattern'}]},
 {'technique':'tops_campaign_catalog','label':'Tops Campaign Product & Price Surface','status':'completed','record_count':12,'record_types':[{'type':'ProductCandidate','count':12}],
  'sample_records':[{'record_type':'ProductCandidate','product_name':'สินค้า A','price':119,'sku':'8850000000001','source_url':'https://www.tops.co.th/th/item-a-8850000000001','provenance':'tops-campaign-product-card'}],
  'potential':{'confidence':'high'}},
 {'technique':'tops_promotion_surface','label':'Tops Official Campaign Surface','status':'completed','record_count':5,'record_types':[{'type':'PromotionCandidate','count':5}],
  'sample_records':[{'record_type':'PromotionCandidate','promotion_title':'โปรของสด','source_url':'https://www.tops.co.th/th','provenance':'tops-official-campaign'}],
  'potential':{'confidence':'high'}},
 {'technique':'generic_sitemap','label':'Robots / Sitemap Discovery','status':'completed','record_count':12,'record_types':[{'type':'URLCandidate','count':12}],
  'sample_records':[],'potential':{'discovered_urls':154011,'confidence':'high'}},
]
recs,tracks=ts.recommend_supermarket_tracks(results,'tops')
assert tracks['product_price']['technique']=='tops_campaign_catalog',tracks
assert tracks['promotion']['technique']=='tops_promotion_surface',tracks
assert tracks['discovery']['technique']=='generic_sitemap',tracks

# 5) Existing approved profile is not auto-invalidated by a global engine bump: engine remains 0.24.
assert ts.TECHNIQUE_ENGINE_VERSION=='0.24'
print('[PASS] v0.27 Tops generalized supermarket patterns')
